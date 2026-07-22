import sys, asyncio
sys.path.insert(0, r'E:\wu\xidian\job\java\agent\CampusCare')

# Step 1: 生成 FlagEmbedding 向量
from config.model_provider import create_embedding_model
m = create_embedding_model()
v = m.embed_query('嗓子疼怎么办')
print(f'FlagEmbedding 向量维度: {len(v)}')
print(f'前5维: {v[:5]}')

# Step 2: PCA 降维验证
from services.milvus_service import MilvusService
svc = MilvusService()
asyncio.run(svc.initialize(dim=768))
if svc._pca is not None:
    import numpy as np
    arr = np.array(v, dtype=np.float32).reshape(1, -1)
    reduced = svc._pca.transform(arr)[0]
    print(f'PCA 降维后维度: {len(reduced)}')
    print(f'前5维: {reduced[:5]}')
else:
    print('PCA 模型未加载!')
