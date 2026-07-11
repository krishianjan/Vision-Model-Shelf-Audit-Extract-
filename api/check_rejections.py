import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def check():
    db_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    
    rejs = await conn.fetch("SELECT id, category, clip_confidence, reason, created_at FROM guardrail_rejections ORDER BY created_at DESC LIMIT 5")
    if not rejs:
        print("No guardrail rejections found.")
    else:
        for r in rejs:
            print(dict(r))
        
    await conn.close()

asyncio.run(check())
