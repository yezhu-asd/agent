import sys, numpy as np
sys.path.insert(0, r'E:\wu\xidian\job\java\agent\CampusCare')

# 加载原始的 npz embedding 数据（PCA 前的 1024 维向量）
orig = np.load(r'E:\wu\xidian\job\java\agent\CampusCare\embedding\embedding_merged\embeddings.npy')
print(f"原始保存的向量: shape={orig.shape}")

# 取第一条数据对应的文本（从 metadata 拿）
meta = np.load(r'E:\wu\xidian\job\java\agent\CampusCare\embedding\embedding_merged\metadata.npy', allow_pickle=True)
print(f"原来的第一条元数据: {meta[0].item() if hasattr(meta[0], 'item') else meta[0]}")
print(f"原来第一条向量的前10维: {orig[0][:10].round(4).tolist()}")

# 现在用 SentenceTransformer 重新生成
from sentence_transformers import SentenceTransformer
st = SentenceTransformer(r'E:\wu\xidian\job\java\agent\models\bge-m3', device='cpu')
meta0 = meta[0].item() if hasattr(meta[0], 'item') else meta[0]
text = f"{meta0.get('ask', '')} {meta0.get('answer', '')} {meta0.get('title', '')}"
v1 = st.encode(text, normalize_embeddings=False)
print(f"\nSentenceTransformer 生成向量前10维: {v1[:10].round(4).tolist()}")

# 余弦相似度比较
cos_sim = np.dot(orig[0], v1) / (np.linalg.norm(orig[0]) * np.linalg.norm(v1))
print(f"余弦相似度: {cos_sim:.4f}")
if cos_sim > 0.99:
    print("结论：✅ 几乎完全一致，可以继续使用")
elif cos_sim > 0.80:
    print("结论：⚠️ 有一定差异，需要调整参数")
else:
    print("结论：❌ 完全不同，无法复用原有向量")
