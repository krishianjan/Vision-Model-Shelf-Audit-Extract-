#!/usr/bin/env python
"""Quick test to verify Gemini Flash is configured and working."""
import asyncio
import os
import sys
from dotenv import load_dotenv
from pathlib import Path
from PIL import Image
from io import BytesIO

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_FLASH_ENABLED = bool(GEMINI_API_KEY)

print("=" * 70)
print("GEMINI FLASH CONFIGURATION TEST")
print("=" * 70)
print(f"✓ API Key loaded: {bool(GEMINI_API_KEY)}")
print(f"✓ Gemini Flash enabled: {GEMINI_FLASH_ENABLED}")
if GEMINI_API_KEY:
    print(f"✓ Key prefix: {GEMINI_API_KEY[:20]}...")
print()

if not GEMINI_FLASH_ENABLED:
    print("❌ GEMINI_API_KEY not set in .env file!")
    print("   Add this line to .env:")
    print("   GEMINI_API_KEY=your-key-here")
    sys.exit(1)

# Test the guardrail
async def test_gemini():
    from src.perception.guardrail import Guardrail

    print("Testing Gemini Flash detection...")
    guardrail = Guardrail()

    # Create a simple test image (blank white image)
    test_img = Image.new("RGB", (640, 480), color="white")
    img_bytes = BytesIO()
    test_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    try:
        result = await guardrail.classify(img_bytes.getvalue())
        print(f"✓ Gemini Flash responded!")
        print(f"  Verdict: {result.verdict}")
        print(f"  Confidence: {result.confidence}")
        print(f"  Reason: {result.reason}")
        return True
    except Exception as e:
        print(f"❌ Error calling Gemini Flash: {e}")
        return False

if __name__ == "__main__":
    print("Initializing Guardrail...")
    success = asyncio.run(test_gemini())
    if success:
        print("\n" + "=" * 70)
        print("✅ GEMINI FLASH WORKING - Ready to test with real images!")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("❌ GEMINI FLASH NOT WORKING - Check API key and network")
        print("=" * 70)
        sys.exit(1)
