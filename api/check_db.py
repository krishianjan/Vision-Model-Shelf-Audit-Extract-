import asyncio
import os
import asyncpg
import json
from dotenv import load_dotenv

load_dotenv()

async def check_db():
    db_url = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)
    
    # Get most recent audit
    audit = await conn.fetchrow("SELECT id, status, capture_quality, created_at FROM shelf_audits ORDER BY created_at DESC LIMIT 1")
    if not audit:
        print("No audits found.")
        return
        
    print(f"Latest Audit: {audit['id']} | Status: {audit['status']} | Created: {audit['created_at']}")
    print(f"Capture Quality: {audit['capture_quality']}")
    
    events = await conn.fetch("SELECT event_type, payload, created_at FROM audit_events WHERE audit_id = $1 ORDER BY created_at ASC", audit['id'])
    for ev in events:
        print(f"  [{ev['created_at']}] {ev['event_type']}: {json.dumps(ev['payload'])[:200]}")
        
    await conn.close()

asyncio.run(check_db())
