#!/usr/bin/env python3
"""
Seed Qdrant with documents.

Behavior:
- If sentence-transformers is installed and importable, use it for embeddings (preferred).
- Otherwise fall back to TF-IDF (scikit-learn) to produce dense vectors (approximate semantic).
This avoids hard dependency failures when sentence-transformers / huggingface_hub have version issues.
"""
import os
from pathlib import Path
import json
import sys
import time

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "agent_docs")
DOC_DIR = Path(__file__).resolve().parent.parent / "seed_data" / "docs"

# Attempt semantic path
USE_ST = False
try:
    from sentence_transformers import SentenceTransformer
    USE_ST = True
except Exception as e:
    USE_ST = False

# TF-IDF fallback
from sklearn.feature_extraction.text import TfidfVectorizer

# Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import VectorParams, Distance
except Exception as e:
    print("ERROR: qdrant-client is not installed or cannot be imported:", e)
    print("Install: pip install qdrant-client")
    sys.exit(1)

def load_docs():
    docs = []
    titles = []
    if not DOC_DIR.exists():
        print("No docs directory found at:", DOC_DIR)
        return docs, titles
    for p in sorted(DOC_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        docs.append(text)
        titles.append(p.name)
    return docs, titles

def create_or_replace_collection(client, dim):
    cols = [c.name for c in client.get_collections().collections]
    if COLLECTION in cols:
        print(f"Recreating collection '{COLLECTION}' with dim={dim}")
        client.recreate_collection(collection_name=COLLECTION, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))
    else:
        print(f"Creating collection '{COLLECTION}' with dim={dim}")
        client.recreate_collection(collection_name=COLLECTION, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

def seed_with_st(client, docs, titles):
    print("Seeding using sentence-transformers (semantic embeddings).")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    vectors = model.encode(docs, show_progress_bar=True)
    dim = len(vectors[0])
    create_or_replace_collection(client, dim)
    points = []
    for i, (v, t, txt) in enumerate(zip(vectors, titles, docs)):
        points.append({"id": i, "vector": v.tolist() if hasattr(v, "tolist") else list(v), "payload": {"title": t, "text": txt}})
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"Seeded {len(points)} points using sentence-transformers.")

def seed_with_tfidf(client, docs, titles):
    print("sentence-transformers not available — falling back to TF-IDF dense vectors.")
    tf = TfidfVectorizer()
    X = tf.fit_transform(docs)  # sparse
    arr = X.toarray()
    dim = arr.shape[1]
    create_or_replace_collection(client, dim)
    points = []
    for i, (v, t, txt) in enumerate(zip(arr, titles, docs)):
        points.append({"id": i, "vector": v.tolist(), "payload": {"title": t, "text": txt}})
    client.upsert(collection_name=COLLECTION, points=points)
    print(f"Seeded {len(points)} points using TF-IDF (dim={dim}).")

def main():
    docs, titles = load_docs()
    if not docs:
        print("No documents to seed. Please add .md files to seed_data/docs/")
        return
    client = QdrantClient(url=QDRANT_URL)
    # quick connectivity check
    try:
        client.get_collections()
    except Exception as e:
        print("Could not connect to Qdrant at", QDRANT_URL, ":", e)
        print("Start Qdrant with Docker (example): docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant")
        return
    if USE_ST:
        try:
            seed_with_st(client, docs, titles)
            return
        except Exception as e:
            print("sentence-transformers seeding failed; falling back to TF-IDF. Error:", e)
    # fallback
    seed_with_tfidf(client, docs, titles)

if __name__ == "__main__":
    main()
