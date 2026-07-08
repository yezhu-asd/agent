import asyncio
from services.milvus_service import MilvusService

async def check():
    m = MilvusService()
    await m.initialize(dim=1024)
    print('count:', m.collection.num_entities)

asyncio.run(check())
