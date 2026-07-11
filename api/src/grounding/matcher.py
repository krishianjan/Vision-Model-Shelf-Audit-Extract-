"""
Phase 6 — RAG SKU grounding: three-tier cascade.

Tier 1: Exact text match (normalized brand + product_name + size_ml).
Tier 2: pg_trgm fuzzy + rapidfuzz re-ranking on candidates.
Tier 3: BGE-small embedding cosine search via pgvector.

Never force-matches: if best similarity < 0.75 on embedding tier → unresolved.
Unknown brands are preserved (matched_sku_id=None) for competitive intel.
"""
from __future__ import annotations

import asyncio
import os
import re
import unicodedata
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from rapidfuzz import fuzz


@dataclass
class MatchResult:
    matched_sku_id: UUID | None
    match_method: str          # "exact" | "fuzzy" | "embedding" | "unresolved"
    match_similarity: float    # 0.0–1.0
    top_candidates: list[dict] = field(default_factory=list)
    sku_guess_text: str | None = None


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[‘’’`]", "", text)
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(text.split())


def _parse_size_to_ml(size_text: str | None) -> int | None:
    """Parse volume string to milliliters.
    Examples: 750ml->750, 1.75L->1750, 200oz->5914, 50cl->500
    """
    if not size_text:
        return None

    text = size_text.lower().strip()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None

    value = float(match.group(1))

    # Check more specific units first
    if "ml" in text or "milliliter" in text:
        return int(value)
    elif "oz" in text or "fl oz" in text:
        return int(value * 29.5735)
    elif "cl" in text or "centiliter" in text:
        return int(value * 10)
    elif "cc" in text:
        return int(value)
    elif "l" in text or "litre" in text or "liter" in text:
        return int(value * 1000)
    else:
        # No unit found, assume ml
        return int(value)


def _make_query_text(brand_read: str | None, size_read: str | None, sku_guess_text: str | None) -> str:
    parts = [brand_read, sku_guess_text, size_read]
    return " ".join(filter(None, parts)).strip()


class SKUMatcher:
    """
    Stateful SKU resolver. Holds a reference to the BGE embedder and db pool.
    Instantiate once at app startup; pass a connection per match call.
    """

    # Thresholds - configurable via environment variables
    FUZZY_TRGM_THRESHOLD = float(os.getenv("FUZZY_TRGM_THRESHOLD", "0.3"))
    FUZZY_RF_THRESHOLD = float(os.getenv("FUZZY_RF_THRESHOLD", "0.65"))
    EMBEDDING_THRESHOLD = float(os.getenv("EMBEDDING_THRESHOLD", "0.75"))

    def __init__(self, embedder=None):
        self._embedder = embedder   # SentenceTransformer instance or None

    def set_embedder(self, embedder) -> None:
        self._embedder = embedder

    async def match(
        self,
        conn: asyncpg.Connection,
        brand_read: str | None,
        size_read: str | None,
        sku_guess_text: str | None = None,
    ) -> MatchResult:
        query_raw = _make_query_text(brand_read, size_read, sku_guess_text)
        if not query_raw.strip():
            return MatchResult(None, "unresolved", 0.0, sku_guess_text=query_raw or None)

        # ── Tier 1: Exact normalized match ────────────────────────────────────
        result = await self._exact_match(conn, brand_read, size_read)
        if result:
            return result

        # ── Tier 2: Fuzzy (pg_trgm + rapidfuzz) ───────────────────────────────
        result = await self._fuzzy_match(conn, query_raw)
        if result:
            return result

        # ── Tier 3: Embedding cosine ───────────────────────────────────────────
        result = await self._embedding_match(conn, query_raw)
        if result:
            return result

        return MatchResult(
            matched_sku_id=None,
            match_method="unresolved",
            match_similarity=0.0,
            sku_guess_text=query_raw or None,
        )

    # ── Tier 1 ─────────────────────────────────────────────────────────────────

    async def _exact_match(
        self,
        conn: asyncpg.Connection,
        brand_read: str | None,
        size_read: str | None,
    ) -> MatchResult | None:
        if not brand_read:
            return None

        brand_norm = _normalize(brand_read)

        # Use SQL ILIKE instead of loading ALL products into memory
        # This scales to 50k+ products without issue
        rows = await conn.fetch(
            "SELECT id, brand, product_name, size_ml FROM products WHERE lower(brand) = lower($1)",
            brand_read.strip(),
        )
        for row in rows:
            db_brand = _normalize(row["brand"])
            db_product = _normalize(row["product_name"])
            if db_brand != brand_norm:
                continue

            # If size provided, parse it to ml and compare with db
            if size_read:
                size_ml_parsed = _parse_size_to_ml(size_read)
                db_size_ml = row["size_ml"]
                # Both must have size for comparison, and must match
                if size_ml_parsed is not None and db_size_ml is not None:
                    if size_ml_parsed != db_size_ml:
                        continue
                elif size_ml_parsed is not None or db_size_ml is not None:
                    # One has size, other doesn't → no match
                    continue

            return MatchResult(
                matched_sku_id=row["id"],
                match_method="exact",
                match_similarity=1.0,
                sku_guess_text=f"{row['brand']} {row['product_name']}",
                top_candidates=[{"id": str(row["id"]), "brand": row["brand"], "sim": 1.0}],
            )
        return None

    # ── Tier 2 ─────────────────────────────────────────────────────────────────

    async def _fuzzy_match(
        self, conn: asyncpg.Connection, query_raw: str
    ) -> MatchResult | None:
        query_norm = _normalize(query_raw)

        try:
            rows = await conn.fetch(
                """
                SELECT id, brand, product_name, size_ml,
                       similarity(lower(brand) || ' ' || lower(product_name), $1) AS trgm_sim
                FROM products
                WHERE similarity(lower(brand) || ' ' || lower(product_name), $1) > $2
                ORDER BY trgm_sim DESC
                LIMIT 10
                """,
                query_norm,
                self.FUZZY_TRGM_THRESHOLD,
            )
        except Exception as e:
            print(f"[WARN] pg_trgm fuzzy match failed (extension missing?): {e}")
            return None
        if not rows:
            return None

        candidates = []
        for row in rows:
            full = _normalize(f"{row['brand']} {row['product_name']}")
            rf_score = fuzz.token_set_ratio(query_norm, full) / 100.0
            combined = 0.5 * float(row["trgm_sim"]) + 0.5 * rf_score
            candidates.append((row, combined))

        candidates.sort(key=lambda x: x[1], reverse=True)
        best_row, best_score = candidates[0]

        top_candidates = [
            {"id": str(r["id"]), "brand": r["brand"], "product_name": r["product_name"], "sim": round(s, 3)}
            for r, s in candidates[:3]
        ]

        if best_score >= self.FUZZY_RF_THRESHOLD:
            return MatchResult(
                matched_sku_id=best_row["id"],
                match_method="fuzzy",
                match_similarity=round(best_score, 3),
                sku_guess_text=f"{best_row['brand']} {best_row['product_name']}",
                top_candidates=top_candidates,
            )
        return None

    # ── Tier 3 ─────────────────────────────────────────────────────────────────

    async def _embedding_match(
        self, conn: asyncpg.Connection, query_raw: str
    ) -> MatchResult | None:
        if self._embedder is None:
            return None

        loop = asyncio.get_running_loop()
        emb = await loop.run_in_executor(
            None,
            lambda: self._embedder.encode(query_raw, normalize_embeddings=True),
        )
        emb_str = "[" + ",".join(f"{x:.6f}" for x in emb.tolist()) + "]"

        try:
            rows = await conn.fetch(
                """
                SELECT id, brand, product_name,
                       round((1 - (embedding <=> $1::vector))::numeric, 4) AS cosine_sim
                FROM products
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 5
                """,
                emb_str,
            )
        except Exception as e:
            print(f"[WARN] pgvector embedding match failed (extension missing?): {e}")
            return None
        if not rows:
            return None

        top = rows[0]
        cosine = float(top["cosine_sim"])
        top_candidates = [
            {"id": str(r["id"]), "brand": r["brand"], "product_name": r["product_name"], "sim": float(r["cosine_sim"])}
            for r in rows
        ]

        if cosine >= self.EMBEDDING_THRESHOLD:
            return MatchResult(
                matched_sku_id=top["id"],
                match_method="embedding",
                match_similarity=cosine,
                sku_guess_text=f"{top['brand']} {top['product_name']}",
                top_candidates=top_candidates,
            )
        return None
