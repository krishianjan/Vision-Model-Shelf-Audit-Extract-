import os
import asyncio
from src.perception.vlm import QwenVLOpenRouterClient

async def test():
    client = QwenVLOpenRouterClient()
    try:
        # Just passing a simple text prompt, no image bytes
        res = await client._call("You are a helpful assistant.", "Respond with exactly the word SUCCESS", None, None)
        print(f"OpenRouter Response: {res}")
    except Exception as e:
        print(f"OpenRouter Error: {e}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test())
