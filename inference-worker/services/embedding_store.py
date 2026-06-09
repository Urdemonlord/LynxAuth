from __future__ import annotations

import math
import os
from typing import Any

import psycopg


class EmbeddingStore:
    """PostgreSQL + pgvector-backed embedding store for backend phase 1.

    Notes:
    - keeps max 5 embeddings per user by deleting oldest sample first
    - uses pgvector cosine distance operator (`<=>`) for matching
    - stores vectors through text casting (`CAST(%s AS vector)`) so the worker
      can function without additional pgvector Python bindings
    """

    def __init__(self, database_url: str | None = None, threshold: float | None = None) -> None:
        self._database_url = database_url or os.environ.get(
            "DATABASE_URL",
            "postgresql://lynxauth:lynxauth@127.0.0.1:5432/lynxauth",
        )
        self._threshold = threshold if threshold is not None else float(os.environ.get("FACE_MATCH_THRESHOLD", "0.6"))

    async def initialize(self, reset: bool = False) -> None:
        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                if reset:
                    await cursor.execute("TRUNCATE TABLE face_embeddings RESTART IDENTITY")

                await cursor.execute(
                    """
                    CREATE EXTENSION IF NOT EXISTS vector;
                    CREATE TABLE IF NOT EXISTS face_embeddings (
                        id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        embedding vector(512) NOT NULL,
                        source TEXT NOT NULL DEFAULT 'enrollment',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_face_embeddings_user_id
                        ON face_embeddings (user_id);
                    """
                )
            await connection.commit()

    async def store(self, user_id: str, embedding: list[float]) -> None:
        self._validate_embedding(embedding)
        vector_literal = to_vector_literal(embedding)

        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT id
                    FROM face_embeddings
                    WHERE user_id = %s
                    ORDER BY created_at ASC, id ASC
                    """,
                    (user_id,),
                )
                rows = await cursor.fetchall()
                overflow = max(0, len(rows) - 4)
                for row in rows[:overflow]:
                    await cursor.execute("DELETE FROM face_embeddings WHERE id = %s", (row[0],))

                await cursor.execute(
                    """
                    INSERT INTO face_embeddings (user_id, embedding)
                    VALUES (%s, CAST(%s AS vector))
                    """,
                    (user_id, vector_literal),
                )
            await connection.commit()

    async def match(self, embedding: list[float]) -> tuple[str | None, float | None]:
        self._validate_embedding(embedding)
        vector_literal = to_vector_literal(embedding)

        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    """
                    SELECT
                        user_id,
                        1 - (embedding <=> CAST(%s AS vector)) AS cosine_similarity
                    FROM face_embeddings
                    ORDER BY embedding <=> CAST(%s AS vector) ASC
                    LIMIT 1
                    """,
                    (vector_literal, vector_literal),
                )
                row = await cursor.fetchone()

        if row is None:
            return None, None

        user_id, confidence = row
        confidence = float(confidence)
        if confidence >= self._threshold:
            return user_id, round(confidence, 4)
        return None, None

    async def count_by_user(self, user_id: str) -> int:
        async with await self._connect() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM face_embeddings WHERE user_id = %s", (user_id,))
                row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def _connect(self) -> psycopg.AsyncConnection[Any]:
        return await psycopg.AsyncConnection.connect(self._database_url)

    @staticmethod
    def _validate_embedding(embedding: list[float]) -> None:
        if len(embedding) != 512:
            raise ValueError(f"embedding must contain 512 floats, got {len(embedding)}")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    numerator = sum(x * y for x, y in zip(a, b))
    denom_a = math.sqrt(sum(x * x for x in a))
    denom_b = math.sqrt(sum(y * y for y in b))
    if denom_a == 0 or denom_b == 0:
        return 0.0
    return numerator / (denom_a * denom_b)


def to_vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"
