import os
import json
import re
import pandas as pd
import numpy as np
import faiss
import ollama

from sentence_transformers import SentenceTransformer
from config import MODEL_NAME, TOP_K, TEMPERATURE, MAX_TOKENS
from chatbot.intent_detector import detect_intent

# ─────────────────────────────────────────────────────────────────────────────
#  GPU-first Ollama options
#  num_gpu=99 → offload ALL model layers to GPU
# ─────────────────────────────────────────────────────────────────────────────
_OLLAMA_OPTIONS = {
    "num_gpu":    99,
    "num_thread": 4,
    "temperature": TEMPERATURE,
    "num_predict": MAX_TOKENS + 100,
}

# Language code map for deep-translator (Google Translate)
_LANG_CODES = {
    "Malayalam": "ml",
    "Hindi":     "hi",
    "Tamil":     "ta",
    "English":   "en",
}

# ─────────────────────────────────────────────────────────────────────────────
#  Lazy-loaded resources
# ─────────────────────────────────────────────────────────────────────────────
_data            = None
_index           = None
_embedding_model = None
_pdf_index       = None
_pdf_chunks      = []


def _load_resources():
    global _data, _index, _embedding_model, _pdf_index, _pdf_chunks

    if _embedding_model is not None:
        return  # already loaded

    print("Loading embedding model and vector stores...")
    _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

    csv_path = "datasets/cleaned_datasets/cleaned_traindata.csv"
    if os.path.exists(csv_path):
        _data = pd.read_csv(csv_path)
        print(f"Dataset: {len(_data)} rows")
    else:
        print(f"Warning: dataset not found at {csv_path}")
        _data = pd.DataFrame(columns=["text"])

    faiss_path = "vectorstore/banking_index.faiss"
    if os.path.exists(faiss_path):
        _index = faiss.read_index(faiss_path)
        print("Loaded banking FAISS index.")
    else:
        print(f"Warning: FAISS index not found at {faiss_path}")
        _index = None

    pdf_faiss = "vectorstore/pdf_index.faiss"
    pdf_json  = "vectorstore/pdf_chunks.json"
    if os.path.exists(pdf_faiss) and os.path.exists(pdf_json):
        try:
            _pdf_index = faiss.read_index(pdf_faiss)
            with open(pdf_json, "r", encoding="utf-8") as f:
                _pdf_chunks = json.load(f)
            print(f"PDF index loaded ({len(_pdf_chunks)} chunks).")
        except Exception as e:
            print(f"PDF index load error: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Language Detection (Unicode ranges)
# ─────────────────────────────────────────────────────────────────────────────
def detect_query_language(query: str) -> str:
    if re.search(r"[\u0d00-\u0d7f]", query):
        return "Malayalam"
    elif re.search(r"[\u0900-\u097f]", query):
        return "Hindi"
    elif re.search(r"[\u0b80-\u0bff]", query):
        return "Tamil"
    return "English"


# ─────────────────────────────────────────────────────────────────────────────
#  Google Translate helpers (via deep-translator — no API key required)
#  Falls back to the original text if offline / quota exceeded.
# ─────────────────────────────────────────────────────────────────────────────
def _google_translate(text: str, source_lang_code: str, target_lang_code: str) -> str:
    """Translate text using Google Translate via deep-translator."""
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(
            source=source_lang_code,
            target=target_lang_code
        ).translate(text)
        return result.strip() if result else text
    except Exception as e:
        print(f"[GoogleTranslate] {source_lang_code}→{target_lang_code} error: {e}")
        return text  # safe fallback: return original


def translate_to_english(text: str, from_lang: str) -> str:
    """Translate a regional language query into English for RAG retrieval."""
    src_code = _LANG_CODES.get(from_lang, "auto")
    result = _google_translate(text, src_code, "en")
    print(f"[translate_to_english] {from_lang} → EN: '{result}'")
    return result


def translate_to_language(english_text: str, target_lang: str) -> str:
    """Translate an English response into the target regional language."""
    tgt_code = _LANG_CODES.get(target_lang)
    if not tgt_code or tgt_code == "en":
        return english_text
    result = _google_translate(english_text, "en", tgt_code)
    print(f"[translate_to_language] EN → {target_lang}: done")
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Context Retrieval (FAISS RAG)
# ─────────────────────────────────────────────────────────────────────────────
def retrieve_context(english_query: str) -> str:
    _load_resources()

    if _embedding_model is None:
        return ""

    query_embedding = _embedding_model.encode([english_query])
    query_embedding = np.array(query_embedding).astype("float32")
    context_parts   = []

    # Dataset FAISS search
    if _index is not None and _data is not None and len(_data) > 0:
        try:
            k = min(TOP_K, len(_data))
            _, indices = _index.search(query_embedding, k)
            for idx in indices[0]:
                if 0 <= idx < len(_data):
                    context_parts.append(str(_data.iloc[idx]["text"]))
        except Exception as e:
            print(f"[retrieve_context] dataset error: {e}")

    # PDF FAISS search
    if _pdf_index is not None and len(_pdf_chunks) > 0:
        try:
            _, pdf_indices = _pdf_index.search(query_embedding, 2)
            for idx in pdf_indices[0]:
                if 0 <= idx < len(_pdf_chunks):
                    context_parts.append(_pdf_chunks[idx])
        except Exception as e:
            print(f"[retrieve_context] pdf error: {e}")

    return "\n".join(context_parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Main Response Generator
# ─────────────────────────────────────────────────────────────────────────────
def generate_response(
    user_query: str,
    selected_language: str = "Auto",
    history: list = None
) -> dict:
    """
    Pipeline:
      1. Detect language of user's query.
      2. Translate query → English via Google Translate (accurate for all languages).
      3. Use translated English query for RAG retrieval & intent detection.
      4. Generate the answer in English using Phi3 (most accurate for English).
      5. Translate English answer → target language via Google Translate.

    This separation ensures:
      - RAG retrieval always uses clean English.
      - The LLM only has to reason in English (its strongest language).
      - The final translation is done by Google Translate (professional quality).
    """
    _load_resources()
    if history is None:
        history = []

    # ── 1. Language detection ───────────────────────────────────────────────
    if selected_language == "Auto":
        lang = detect_query_language(user_query)
    else:
        lang = selected_language

    # ── 2. Translate query → English ────────────────────────────────────────
    if lang != "English":
        english_query = translate_to_english(user_query, lang)
        # Safety: if translation returned the same script characters, it failed
        if detect_query_language(english_query) != "English":
            print("[generate_response] Translation produced non-English text; using original for retrieval")
            english_query = user_query  # last resort
    else:
        english_query = user_query

    # ── 3. Intent + RAG context (English only) ──────────────────────────────
    intent  = detect_intent(english_query)
    context = retrieve_context(english_query)

    # ── 4. Build conversation history for Phi3 (English only) ───────────────
    history_lines = []
    for msg in history[-10:]:
        role = "Customer" if msg.get("role") == "user" else "Assistant"
        history_lines.append(f"{role}: {msg.get('content', '')}")
    history_text = "\n".join(history_lines) if history_lines else "None"

    # ── 5. Generate English answer with Phi3 ────────────────────────────────
    system_prompt = (
        "You are a professional Banking AI Assistant. "
        "You answer customer banking questions clearly and concisely. "
        "Always respond in English only."
    )

    user_prompt = f"""Previous conversation context:
{history_text}

Relevant banking knowledge:
{context if context else "No specific entry found — answer from general banking knowledge."}

Customer's question: {english_query}
Detected intent: {intent}

Instructions:
- Line 1 MUST be exactly: [SENTIMENT: <value>] where <value> is one of: Positive, Negative, Neutral, Frustrated, Urgent
- Then write a helpful, accurate banking response in English (max 80 words).
- Be specific and directly answer the question.
- Do NOT add any preamble, do NOT repeat the sentiment tag.
"""

    # Build Ollama message list (include recent history for multi-turn awareness)
    ollama_messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        ollama_messages.append({
            "role":    msg.get("role", "user"),
            "content": msg.get("content", ""),
        })
    ollama_messages.append({"role": "user", "content": user_prompt})

    try:
        response   = ollama.chat(model=MODEL_NAME, messages=ollama_messages, options=_OLLAMA_OPTIONS)
        en_content = response["message"]["content"].strip()
    except Exception as e:
        print(f"[Ollama Service Warning] {e}")
        if context and len(context.strip()) > 0:
            first_fact = context.strip().split("\n")[0]
            en_content = f"[SENTIMENT: Neutral]\nThank you for your banking query. Based on our bank records:\n\n{first_fact}"
        else:
            en_content = f"[SENTIMENT: Neutral]\nThank you for reaching out to Banking Support. Regarding '{english_query}', our services and branch support are available 24/7. Please contact customer service or visit your nearest branch."

    # ── 6. Parse sentiment tag ───────────────────────────────────────────────
    sentiment = "Neutral"
    match = re.search(
        r"\[SENTIMENT:\s*(Positive|Negative|Neutral|Frustrated|Urgent)\]",
        en_content, re.IGNORECASE
    )
    if match:
        sentiment  = match.group(1).capitalize()
        en_content = re.sub(
            r"\[SENTIMENT:\s*(Positive|Negative|Neutral|Frustrated|Urgent)\]\s*\n?",
            "", en_content, flags=re.IGNORECASE
        ).strip()

    # ── 7. Translate English answer → target language (Google Translate) ─────
    if lang != "English" and en_content and not en_content.startswith("⚠️"):
        final_answer = translate_to_language(en_content, lang)
    else:
        final_answer = en_content

    return {
        "intent":    intent,
        "answer":    final_answer,
        "sentiment": sentiment,
        "language":  lang,
    }