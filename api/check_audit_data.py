import asyncio
import json
import os
from dotenv import load_dotenv
load_dotenv('../.env')

async def check():
    from src.persistence.db import create_pool
    db = await create_pool(os.environ["DATABASE_URL"])
    
    async with db.acquire() as conn:
        # Get latest final audit
        audit = await conn.fetchrow("""
            SELECT id, status FROM shelf_audits 
            WHERE status = 'final' 
            ORDER BY created_at DESC LIMIT 1
        """)
        
        if not audit:
            print("❌ No final audits found")
            return
        
        audit_id = audit['id']
        print(f"📊 AUDIT ID: {audit_id}")
        print(f"Status: {audit['status']}\n")
        
        # Get observations
        obs = await conn.fetch("""
            SELECT 
              brand_read, size_read, price_value, facings, shelf_position,
              field_confidence, sku_guess_text, matched_sku_id
            FROM audit_observations 
            WHERE audit_id = $1
        """, audit_id)
        
        for i, o in enumerate(obs, 1):
            print(f"=== OBSERVATION {i} ===")
            print(f"Brand Read: {o['brand_read']}")
            print(f"Size Read: {o['size_read']}")
            print(f"Price Value: {o['price_value']}")
            print(f"Facings: {o['facings']}")
            print(f"Position: {o['shelf_position']}")
            print(f"SKU Guess: {o['sku_guess_text']}")
            print(f"Matched SKU ID: {o['matched_sku_id']}")
            
            conf = o['field_confidence']
            if isinstance(conf, str):
                conf = json.loads(conf)
            print(f"\nField Confidence:")
            print(f"  Brand: {conf.get('brand', 'N/A')}")
            print(f"  Size: {conf.get('size', 'N/A')}")
            print(f"  Price: {conf.get('price', 'N/A')}")
            print(f"  Facings: {conf.get('facings', 'N/A')}")
            print()
        
        # Get events (processing log)
        events = await conn.fetch("""
            SELECT event_type, payload FROM audit_events 
            WHERE audit_id = $1 
            ORDER BY created_at
        """, audit_id)
        
        print(f"\n=== AUDIT EVENTS LOG ===")
        for evt in events:
            print(f"{evt['event_type']}")
            if evt['payload']:
                print(f"  {json.dumps(evt['payload'], indent=2)}")
    
    await db.close()

asyncio.run(check())
