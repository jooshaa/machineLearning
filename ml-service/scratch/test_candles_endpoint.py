import asyncio
from app.main import get_candles

async def run_test():
    print("Testing candles endpoint for 2023-01-03...")
    result = await get_candles("2023-01-03")
    print(f"Result type: {type(result)}")
    if isinstance(result, list):
        print(f"Loaded {len(result)} candles successfully!")
        if len(result) > 0:
            print(f"First candle: {result[0]}")
    else:
        print(f"Returned dict / error: {result}")

if __name__ == "__main__":
    asyncio.run(run_test())
