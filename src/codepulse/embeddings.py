"""Embedding generation for code symbols."""

import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Callable

from codepulse.db import GraphDB


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
    return _get_local_embedder(model or "all-MiniLM-L6-v2")


def serialize_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def index_embeddings(
    db: GraphDB,
    backend: str = "local",
    model: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> int:
    # Resolve actual model name
    actual_model = model or "all-MiniLM-L6-v2"

    count = 0
    batch_size = 32
    embed_fn: Callable[[list[str]], list[list[float]]] | None = None

    placeholders = ",".join("?" for _ in ("file", "external_module", "unresolved_symbol"))
    all_nodes = db.conn.execute(
        f"""SELECT id, name, kind, signature, file_path, line_start, line_end
            FROM nodes
            WHERE kind NOT IN ({placeholders})
            ORDER BY id""",
        ("file", "external_module", "unresolved_symbol"),
    ).fetchall()

    for i in range(0, len(all_nodes), batch_size):
        batch = all_nodes[i:i + batch_size]
        texts: list[str] = []
        ids: list[str] = []
        hashes: list[str] = []

        for row in batch:
            sig = row["signature"] or row["name"]
            node_id = row["id"]
            text = f"{row['name']}: {sig}"
            content_hash = hashlib.md5(
                f"{node_id}:{row['name']}:{row['kind']}:{sig}:{row['file_path']}:{row['line_start']}:{row['line_end']}".encode()
            ).hexdigest()

            # Skip if we already have a matching embedding
            existing = db.conn.execute(
                "SELECT 1 FROM embeddings WHERE node_id = ? AND model = ? AND content_hash = ?",
                (node_id, actual_model, content_hash),
            ).fetchone()
            if existing:
                continue

            ids.append(node_id)
            texts.append(text)
            hashes.append(content_hash)

        if not ids:
            continue

        if on_progress:
            on_progress(f"Embedding {i + len(batch)}/{len(all_nodes)}")

        if embed_fn is None:
            embed_fn = get_embedder(backend, model)
        vectors = embed_fn(texts)
        for node_id, vec, h in zip(ids, vectors, hashes):
            db.upsert_embedding(
                node_id, serialize_vector(vec),
                model=actual_model, dimensions=len(vec), content_hash=h,
            )
            count += 1

    return count
