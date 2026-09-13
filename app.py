from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import sqlite3

from chatbot.rag_engine import generate_response
from chatbot.fraud_detector import detect_fraud
from chatbot.recommendation_engine import get_recommendation

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-before-running-in-production")

DB = "database.db"

# ─────────────────────────────────────────────
#  DB Helper
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
#  Ensure DB tables exist on startup
# ─────────────────────────────────────────────
def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            intent TEXT,
            sentiment TEXT,
            language TEXT,
            is_fraud INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        )
    """)
    # Add extra columns if upgrading from older schema
    try:
        cur.execute("ALTER TABLE messages ADD COLUMN intent TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE messages ADD COLUMN sentiment TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE messages ADD COLUMN language TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE messages ADD COLUMN is_fraud INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()

init_db()


# ─────────────────────────────────────────────
#  HOME — redirect to history / latest chat
# ─────────────────────────────────────────────
@app.route("/")
def home():
    return redirect(url_for("history"))


# ─────────────────────────────────────────────
#  HISTORY — list all conversations
# ─────────────────────────────────────────────
@app.route("/history")
def history():
    conn = get_db()
    chats = conn.execute(
        "SELECT * FROM conversations ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return render_template("history.html", chats=chats)


# ─────────────────────────────────────────────
#  NEW CHAT
# ─────────────────────────────────────────────
@app.route("/new_chat")
def new_chat():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO conversations (title) VALUES (?)", ("New Chat",))
    chat_id = cur.lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for("chat_view", chat_id=chat_id))


# ─────────────────────────────────────────────
#  CHAT VIEW — open a specific conversation
# ─────────────────────────────────────────────
@app.route("/chat/<int:chat_id>")
def chat_view(chat_id):
    conn = get_db()

    convo = conn.execute(
        "SELECT * FROM conversations WHERE id=?", (chat_id,)
    ).fetchone()

    if not convo:
        conn.close()
        return redirect(url_for("history"))

    messages = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC",
        (chat_id,)
    ).fetchall()

    conn.close()

    # Store active chat id in session
    session["chat_id"] = chat_id

    return render_template("chat.html", convo=convo, messages=messages, chat_id=chat_id)


# ─────────────────────────────────────────────
#  DELETE CHAT
# ─────────────────────────────────────────────
@app.route("/delete_chat/<int:chat_id>", methods=["POST"])
def delete_chat(chat_id):
    conn = get_db()
    conn.execute("DELETE FROM messages WHERE conversation_id=?", (chat_id,))
    conn.execute("DELETE FROM conversations WHERE id=?", (chat_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("history"))


# ─────────────────────────────────────────────
#  RENAME CHAT
# ─────────────────────────────────────────────
@app.route("/rename_chat/<int:chat_id>", methods=["POST"])
def rename_chat(chat_id):
    data = request.get_json()
    new_title = data.get("title", "New Chat").strip() or "New Chat"
    conn = get_db()
    conn.execute("UPDATE conversations SET title=? WHERE id=?", (new_title, chat_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "title": new_title})


# ─────────────────────────────────────────────
#  SEND MESSAGE — main AI endpoint
# ─────────────────────────────────────────────
@app.route("/chat/<int:chat_id>/send", methods=["POST"])
def send_message(chat_id):
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "No message provided"}), 400

    user_message = data["message"].strip()
    selected_language = data.get("language", "Auto")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    conn = get_db()

    # ── Verify the conversation exists ──
    convo = conn.execute(
        "SELECT * FROM conversations WHERE id=?", (chat_id,)
    ).fetchone()
    if not convo:
        conn.close()
        return jsonify({"error": "Conversation not found"}), 404

    # ── Build conversation history for context ──
    prior_messages = conn.execute(
        """SELECT sender, message FROM messages
           WHERE conversation_id=?
           ORDER BY timestamp ASC""",
        (chat_id,)
    ).fetchall()

    # Format history as list of dicts for the RAG engine
    history = [
        {"role": "user" if m["sender"] == "user" else "assistant", "content": m["message"]}
        for m in prior_messages
    ]

    # ── Save user message ──
    conn.execute(
        "INSERT INTO messages (conversation_id, sender, message) VALUES (?, ?, ?)",
        (chat_id, "user", user_message)
    )

    # ── Generate AI response with conversation history ──
    try:
        result = generate_response(user_message, selected_language, history=history)
        intent = result.get("intent", "General Banking Query")
        answer = result.get("answer", "I'm sorry, I couldn't process your request.")
        sentiment = result.get("sentiment", "Neutral")
        lang = result.get("language", "English")
    except Exception as e:
        intent = "General Banking Query"
        answer = f"⚠️ AI service error: {str(e)}"
        sentiment = "Neutral"
        lang = "English"

    # ── Fraud Detection ──
    try:
        fraud_result = detect_fraud(user_message)
        is_fraud = 1 if fraud_result.get("is_fraud") else 0
        fraud_warning = fraud_result.get("warning")
    except Exception:
        is_fraud = 0
        fraud_warning = None

    # ── Product Recommendation ──
    try:
        recommendation = get_recommendation(intent, user_message)
    except Exception:
        recommendation = None

    # ── Save AI response ──
    conn.execute(
        """INSERT INTO messages
               (conversation_id, sender, message, intent, sentiment, language, is_fraud)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, "ai", answer, intent, sentiment, lang, is_fraud)
    )

    # ── Auto-title the conversation from the first user message ──
    if convo["title"] == "New Chat" and len(prior_messages) == 0:
        short_title = user_message[:50] + ("..." if len(user_message) > 50 else "")
        conn.execute(
            "UPDATE conversations SET title=? WHERE id=?",
            (short_title, chat_id)
        )

    conn.commit()
    conn.close()

    return jsonify({
        "intent": intent,
        "response": answer,
        "sentiment": sentiment,
        "language": lang,
        "is_fraud": is_fraud == 1,
        "fraud_warning": fraud_warning,
        "recommendation": recommendation
    })


# ─────────────────────────────────────────────
#  GET MESSAGES (for continuing a chat via AJAX)
# ─────────────────────────────────────────────
@app.route("/chat/<int:chat_id>/messages")
def get_messages(chat_id):
    conn = get_db()
    messages = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(m) for m in messages])


# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
