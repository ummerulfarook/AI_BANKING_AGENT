import pandas as pd
import numpy as np
import faiss


from sentence_transformers import SentenceTransformer

#Load dataset

data=pd.read_csv("datasets/cleaned_datasets/cleaned_traindata.csv")

#load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

#Convert questions into list
texts = data['text'].tolist()

#Create embeddings
embeddings = model.encode(texts)

#convert to numpy
embeddings = np.array(embeddings).astype('float32')

#create FAISS index
dimension = embeddings.shape[1]

index = faiss.IndexFlatL2(dimension)

#Add embeddings to index
index.add(embeddings)

print("FAISS index created successfully!")

#save index
faiss.write_index(index, "vectorstore/banking_index.faiss")

print("Vector database saved!")