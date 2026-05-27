"""Embedding generation for code symbols.

Supports multiple backends for generating vector embeddings.
"""

import json
import struct
from pathlib import Path
from typing import Any, Callable

from codepulse.db import GraphDB


def _get_openai_embedder(model: str = "text-embedding-3-small") -> Callable:
    import os
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    def embed(texts: list[str]) -> list[list[float]]:
        resp = client.embeddings.create(input=texts, model=model)
        return [d.embedding for d in resp.data]

    return embed


def _get_local_embedder(model: str = "all-MiniLM-L6-v2") -> Callable:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers not installed. Run: pip install sentence-transformers"
        )
    st = SentenceTransformer(model)

    def embed(texts: list[str]) -> list[list[float]]:
        return st.encode(texts, show_progress_bar=False).tolist()

    return embed


def get_embedder(backend: str = "local", model: str | None = None) -> Callable:
    if backend == "openai":
        return _get_openai_embedder(model or "text-embedding-3-small")
    return _get_local_embedder(model or "all-MiniLM-L6-v2")


def serialize_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def index_embeddings(
    db: GraphDB,
    backend: str = "local",
    model: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    embed_fn = get_embedder(backend, model)
    count = 0
    batch_size = 32

    all_nodes = db.conn.execute(
        "SELECT id, name, signature FROM nodes ORDER BY id"
    ).fetchall()

    for i in range(0, len(all_nodes), batch_size):
        batch = all_nodes[i:i + batch_size]
        texts: list[str] = []
        ids: list[str] = []

        for row in batch:
            sig = row["signature"] or row["name"]
            ids.append(row["id"])
            texts.append(f"{row['name']}: {sig}")

        if on_progress:
            on_progress(f"Embedding {i + len(batch)}/{len(all_nodes)}")

        vectors = embed_fn(texts)
        for node_id, vec in zip(ids, vectors):
            db.upsert_embedding(node_id, serialize_vector(vec), model=backend, dimensions=len(vec))
            count += 1

    return count
