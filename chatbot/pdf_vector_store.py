import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from chatbot.pdf_loader import load_pdf

def build_pdf_index():
    print("Building PDF vector store...")

    # Check paths
    pdf_dir = "documents"
    pdf_files = ["CreditCard.pdf", "HomeLoan.pdf", "FAQ.pdf"]

    model = SentenceTransformer('all-MiniLM-L6-v2')
    chunks = []

    # Process CreditCard.pdf
    cc_path = os.path.join(pdf_dir, "CreditCard.pdf")
    if os.path.exists(cc_path):
        text = load_pdf(cc_path)
        text = text.replace("■", "Rs. ")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title = "Credit Card Guide"
        for line in lines:
            if ":" in line and not line.startswith("Credit Card Guide"):
                chunks.append(f"{title}: {line}")
            elif not line.startswith("Credit Card Guide") and len(line) > 10:
                chunks.append(f"{title}: {line}")

    # Process HomeLoan.pdf
    hl_path = os.path.join(pdf_dir, "HomeLoan.pdf")
    if os.path.exists(hl_path):
        text = load_pdf(hl_path)
        text = text.replace("■", "Rs. ")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title = "Home Loan Guide"
        current_section = ""
        for i, line in enumerate(lines):
            if line == "Home Loan Guide":
                continue
            if line in ["Eligibility", "Interest Rate", "Maximum Tenure", "Documents Required"]:
                current_section = line
            else:
                if current_section:
                    chunks.append(f"{title} - {current_section}: {line}")
                else:
                    chunks.append(f"{title}: {line}")

    # Process FAQ.pdf
    faq_path = os.path.join(pdf_dir, "FAQ.pdf")
    if os.path.exists(faq_path):
        text = load_pdf(faq_path)
        text = text.replace("■", "Rs. ")
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title = "Banking FAQ"
        # FAQ alternates between questions and answers
        i = 1
        while i < len(lines):
            question = lines[i]
            if i + 1 < len(lines):
                answer = lines[i+1]
                chunks.append(f"{title}: {question} Answer: {answer}")
                i += 2
            else:
                chunks.append(f"{title}: {question}")
                i += 1

    if not chunks:
        print("No chunks extracted from PDFs.")
        return

    print(f"Extracted {len(chunks)} chunks from PDFs:")
    for c in chunks:
        # Encode printable characters safely for windows console
        safe_c = c.encode('ascii', 'replace').decode('ascii')
        print(f"- {safe_c}")

    # Generate embeddings
    embeddings = model.encode(chunks)
    embeddings = np.array(embeddings).astype('float32')

    # Create FAISS Index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Save index and chunks
    os.makedirs("vectorstore", exist_ok=True)
    faiss.write_index(index, "vectorstore/pdf_index.faiss")

    with open("vectorstore/pdf_chunks.json", "w") as f:
        json.dump(chunks, f, indent=4)

    print("PDF Vector Store built and saved successfully!")

if __name__ == "__main__":
    build_pdf_index()
