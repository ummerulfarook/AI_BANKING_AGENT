import pandas as pd
import numpy as np
import faiss

from sentence_transformers import SentenceTransformer

# Load dataset
data = pd.read_csv("datasets/cleaned_datasets/cleaned_traindata.csv")

# Load model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Load FAISS index
index = faiss.read_index("vectorstore/banking_index.faiss")


def search_query(user_query, top_k=3):

    # Convert user query to embedding
    query_embedding = model.encode([user_query])

    query_embedding = np.array(query_embedding).astype('float32')

    # Search FAISS
    distances, indices = index.search(query_embedding, top_k)

    results = []

    for idx in indices[0]:

        results.append(data.iloc[idx]['text'])

    return results


# Test
query = "My ATM card is blocked"

results = search_query(query)

print("Top Matches:\n")

for r in results:

    print("-", r)