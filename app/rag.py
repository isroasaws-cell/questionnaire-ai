import os
import requests
import numpy as np
import faiss

from PyPDF2 import PdfReader


# ----------------------------
# Extract text from file
# ----------------------------
def extract_text_from_file(file_path: str) -> str:

    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)

        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""

        return text

    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    return ""


# ----------------------------
# Extract questions
# ----------------------------
def extract_questions(file_path: str):

    text = extract_text_from_file(file_path)

    questions = [
        q.strip()
        for q in text.split("\n")
        if q.strip()
    ]

    return questions


# ----------------------------
# Chunk reference documents
# ----------------------------
def chunk_text(text: str, chunk_size: int = 500):

    chunks = []

    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i + chunk_size])

    return chunks


# ----------------------------
# Create embedding
# ----------------------------
def create_embedding(text: str):

    api_key = os.getenv("OPENROUTER_API_KEY")

    response = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "text-embedding-3-small",
            "input": text
        }
    )

    data = response.json()

    return data["data"][0]["embedding"]


# ----------------------------
# Build FAISS index
# ----------------------------
def build_vector_index(reference_files):

    chunks_metadata = []
    vectors = []

    for file_path in reference_files:

        text = extract_text_from_file(file_path)

        chunks = chunk_text(text)

        for chunk in chunks:

            embedding = create_embedding(chunk)

            vectors.append(embedding)

            chunks_metadata.append({
                "text": chunk,
                "source": os.path.basename(file_path)
            })

    vectors_np = np.array(vectors).astype("float32")

    dimension = vectors_np.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(vectors_np)

    return index, chunks_metadata


# ----------------------------
# Retrieve relevant chunks
# ----------------------------
def retrieve_context(question, index, chunks_metadata, top_k=3):

    question_embedding = create_embedding(question)

    q_vector = np.array([question_embedding]).astype("float32")

    D, I = index.search(q_vector, top_k)

    retrieved_chunks = []
    citations = []

    for idx in I[0]:

        chunk = chunks_metadata[idx]

        retrieved_chunks.append(chunk["text"])

        citations.append(
            f'{chunk["source"]} – "{chunk["text"][:150]}..."'
        )

    context = "\n\n".join(retrieved_chunks)

    return context, citations, D 