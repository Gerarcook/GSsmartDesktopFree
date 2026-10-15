import httpx
import asyncio

async def test():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get('http://localhost:20128/v1/models')
            print('Status:', r.status_code)
            print('Response:', r.text[:200])
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    asyncio.run(test())