"""
Seed ~50 bev-alc SKUs with BGE-small-en embeddings into the products table.
Run from the db/ directory:  python seeds/products.py
Requires: DATABASE_URL env var, sentence-transformers installed.
"""
import asyncio
import os
import sys
from typing import Any

import asyncpg
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

SKUS: list[dict[str, Any]] = [
    # Vodka
    {"brand": "Tito's Handmade",    "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "081753807056"},
    {"brand": "Tito's Handmade",    "product_name": "Vodka",               "size_ml": 1750, "category": "vodka",   "upc": "081753807063"},
    {"brand": "Grey Goose",         "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "080480280025"},
    {"brand": "Absolut",            "product_name": "Original Vodka",      "size_ml": 750,  "category": "vodka",   "upc": "085592100108"},
    {"brand": "Absolut",            "product_name": "Lime Vodka",          "size_ml": 750,  "category": "vodka",   "upc": "085592302017"},
    {"brand": "Smirnoff",           "product_name": "No. 21 Vodka",        "size_ml": 750,  "category": "vodka",   "upc": "082000730017"},
    {"brand": "Smirnoff",           "product_name": "No. 21 Vodka",        "size_ml": 1750, "category": "vodka",   "upc": "082000730024"},
    {"brand": "Ketel One",          "product_name": "Vodka",               "size_ml": 750,  "category": "vodka",   "upc": "085276030040"},
    {"brand": "Belvedere",          "product_name": "Pure Vodka",          "size_ml": 750,  "category": "vodka",   "upc": "089540502076"},
    {"brand": "Ciroc",              "product_name": "Ultra Premium Vodka", "size_ml": 750,  "category": "vodka",   "upc": "088004001835"},
    # Whiskey
    {"brand": "Jack Daniel's",      "product_name": "Old No. 7 Tennessee Whiskey", "size_ml": 750,  "category": "whiskey", "upc": "082184090916"},
    {"brand": "Jack Daniel's",      "product_name": "Old No. 7 Tennessee Whiskey", "size_ml": 1750, "category": "whiskey", "upc": "082184091302"},
    {"brand": "Jameson",            "product_name": "Irish Whiskey",       "size_ml": 750,  "category": "whiskey", "upc": "080432402619"},
    {"brand": "Maker's Mark",       "product_name": "Bourbon Whisky",      "size_ml": 750,  "category": "whiskey", "upc": "039964000143"},
    {"brand": "Bulleit",            "product_name": "Bourbon Frontier Whiskey", "size_ml": 750, "category": "whiskey", "upc": "088004003006"},
    {"brand": "Woodford Reserve",   "product_name": "Distiller's Select Bourbon", "size_ml": 750, "category": "whiskey", "upc": "096749012344"},
    {"brand": "Crown Royal",        "product_name": "Canadian Whisky",     "size_ml": 750,  "category": "whiskey", "upc": "082000728489"},
    {"brand": "Johnnie Walker",     "product_name": "Black Label Scotch",  "size_ml": 750,  "category": "whiskey", "upc": "050000119028"},
    {"brand": "Johnnie Walker",     "product_name": "Red Label Scotch",    "size_ml": 750,  "category": "whiskey", "upc": "050000119059"},
    {"brand": "Glenfiddich",        "product_name": "12 Year Single Malt", "size_ml": 750,  "category": "whiskey", "upc": "083664100025"},
    # Tequila
    {"brand": "Patron",             "product_name": "Silver Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733100018"},
    {"brand": "Patron",             "product_name": "Anejo Tequila",       "size_ml": 750,  "category": "tequila", "upc": "721733100056"},
    {"brand": "Don Julio",          "product_name": "Blanco Tequila",      "size_ml": 750,  "category": "tequila", "upc": "721733015404"},
    {"brand": "Don Julio",          "product_name": "1942 Tequila",        "size_ml": 750,  "category": "tequila", "upc": "721733015817"},
    {"brand": "Casamigos",          "product_name": "Blanco Tequila",      "size_ml": 750,  "category": "tequila", "upc": "888283003020"},
    {"brand": "Jose Cuervo",        "product_name": "Gold Tequila",        "size_ml": 750,  "category": "tequila", "upc": "082000700003"},
    # Rum
    {"brand": "Captain Morgan",     "product_name": "Original Spiced Rum", "size_ml": 750,  "category": "rum",     "upc": "082000116916"},
    {"brand": "Bacardi",            "product_name": "Superior White Rum",  "size_ml": 750,  "category": "rum",     "upc": "080480010078"},
    {"brand": "Malibu",             "product_name": "Coconut Rum",         "size_ml": 750,  "category": "rum",     "upc": "082184090268"},
    {"brand": "Mount Gay",          "product_name": "Eclipse Rum",         "size_ml": 750,  "category": "rum",     "upc": "085276009175"},
    # Gin
    {"brand": "Tanqueray",          "product_name": "London Dry Gin",      "size_ml": 750,  "category": "gin",     "upc": "088004025992"},
    {"brand": "Hendrick's",         "product_name": "Gin",                 "size_ml": 750,  "category": "gin",     "upc": "088076181368"},
    {"brand": "Bombay Sapphire",    "product_name": "London Dry Gin",      "size_ml": 750,  "category": "gin",     "upc": "088004001767"},
    # Wine
    {"brand": "Barefoot",           "product_name": "Cabernet Sauvignon",  "size_ml": 750,  "category": "wine",    "upc": "085000014576"},
    {"brand": "Josh Cellars",       "product_name": "Cabernet Sauvignon",  "size_ml": 750,  "category": "wine",    "upc": "019375100147"},
    {"brand": "Kim Crawford",       "product_name": "Sauvignon Blanc",     "size_ml": 750,  "category": "wine",    "upc": "009473702004"},
    # Beer
    {"brand": "Modelo Especial",    "product_name": "Lager Beer",          "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "013346500005"},
    {"brand": "Corona Extra",       "product_name": "Lager Beer",          "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "018200009045"},
    {"brand": "Bud Light",          "product_name": "Light Lager",         "size_ml": 355,  "pack_count": 12, "category": "beer", "upc": "018200006099"},
    {"brand": "Heineken",           "product_name": "Lager Beer",          "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "072039001003"},
    {"brand": "Blue Moon",          "product_name": "Belgian White",       "size_ml": 355,  "pack_count": 6,  "category": "beer", "upc": "707015154102"},
    # RTD
    {"brand": "White Claw",         "product_name": "Hard Seltzer Mango",  "size_ml": 355,  "pack_count": 12, "category": "rtd",  "upc": "818502020049"},
    {"brand": "High Noon",          "product_name": "Watermelon Vodka Soda","size_ml": 355, "pack_count": 4,  "category": "rtd",  "upc": "850006188044"},
    {"brand": "Truly",              "product_name": "Wild Berry Hard Seltzer","size_ml": 355,"pack_count": 12,"category": "rtd",  "upc": "040978006042"},
    # Liqueur
    {"brand": "Baileys",            "product_name": "Original Irish Cream","size_ml": 750,  "category": "liqueur", "upc": "086003000016"},
    {"brand": "Kahlua",             "product_name": "Coffee Liqueur",      "size_ml": 750,  "category": "liqueur", "upc": "080432402428"},
    {"brand": "Fireball",           "product_name": "Cinnamon Whisky",     "size_ml": 750,  "category": "liqueur", "upc": "088004002191"},
    {"brand": "Aperol",             "product_name": "Aperitivo",           "size_ml": 750,  "category": "liqueur", "upc": "080480280179"},
    {"brand": "Campari",            "product_name": "Bitter Liqueur",      "size_ml": 750,  "category": "liqueur", "upc": "085276001001"},
    {"brand": "Grand Marnier",      "product_name": "Cordon Rouge",        "size_ml": 750,  "category": "liqueur", "upc": "082184090459"},
]


def make_embedding_text(sku: dict) -> str:
    size = f"{sku['size_ml']}ml" if sku.get("size_ml") else ""
    pack = f"{sku['pack_count']}pk" if sku.get("pack_count", 1) > 1 else ""
    return " ".join(filter(None, [sku["brand"], sku["product_name"], size, pack])).strip()


async def seed(dsn: str):
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    print("Loading BGE-small-en model...")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    texts = [make_embedding_text(s) for s in SKUS]
    print(f"Embedding {len(texts)} SKUs...")
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        inserted = 0
        for sku, emb in zip(SKUS, embeddings):
            emb_str = "[" + ",".join(f"{x:.6f}" for x in emb.tolist()) + "]"
            await conn.execute(
                """
                INSERT INTO products (brand, product_name, size_ml, pack_count, category, upc, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7::vector)
                ON CONFLICT (upc) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                sku["brand"],
                sku["product_name"],
                sku.get("size_ml"),
                sku.get("pack_count", 1),
                sku["category"],
                sku.get("upc"),
                emb_str,
            )
            inserted += 1
        print(f"Seeded {inserted} products.")
    finally:
        await conn.close()


if __name__ == "__main__":
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    asyncio.run(seed(dsn))
