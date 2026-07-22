"""
将 1024 维 embedding 通过 PCA 降至 768 维，使 100 万条数据能放入 Zilliz Cloud Free 档（5 GB）。
同时随机抽取 100 万条，保存到 embedding_sampled/ 目录。

存储估算（768 维，100 万条）：
  原始向量：~3 GB
  IVF_FLAT 索引：~3 GB（Milvus 对向量数据建立索引会占等量空间）
  合计：~6 GB → 略超 Free 档 5 GB，实际以服务端为准

如果仍超限，把 TARGET 改为 800_000 即可（~4.8 GB，肯定放得下）
"""
import numpy as np
from pathlib import Path
from sklearn.decomposition import IncrementalPCA

SOURCE_DIR = Path(__file__).parent / "embedding_merged"
OUTPUT_DIR = Path(__file__).parent / "embedding_sampled"

TARGET = 1_000_000
TARGET_DIM = 768
PCA_CHUNK = 10_000  # 分批处理，控制内存

# ── 1. 加载原始数据 ──────────────────────────────────────────────
print("📂 加载原始数据...")
embeddings = np.load(SOURCE_DIR / "embeddings.npy")
ids = np.load(SOURCE_DIR / "ids.npy", allow_pickle=True)
metadata = np.load(SOURCE_DIR / "metadata.npy", allow_pickle=True)
print(f"   原始形状: {embeddings.shape}，即 {len(embeddings):,} 条 × {embeddings.shape[1]} 维")

# ── 2. 随机抽取条数 ──────────────────────────────────────────────
total = len(embeddings)
if total > TARGET:
    print(f"\n🎲 随机抽取 {TARGET:,} 条（丢弃 {total - TARGET:,} 条）...")
    rng = np.random.default_rng(42)
    chosen = sorted(rng.choice(total, size=TARGET, replace=False))
    embeddings = embeddings[chosen]
    ids = ids[chosen]
    metadata = metadata[chosen]

# ── 3. PCA 降维（IncrementalPCA，内存友好）──────────────────────
print(f"\n🔽 PCA 降维 {embeddings.shape[1]} → {TARGET_DIM} 维...")
ipca = IncrementalPCA(n_components=TARGET_DIM)

# 分批 partial_fit 学习主成分
for start in range(0, len(embeddings), PCA_CHUNK):
    ipca.partial_fit(embeddings[start:start + PCA_CHUNK])
print(f"   解释方差比合计: {ipca.explained_variance_ratio_.sum():.4f}（越接近1越好，>0.9 为佳）")

# 分批 transform
reduced = np.empty((len(embeddings), TARGET_DIM), dtype=np.float32)
for start in range(0, len(embeddings), PCA_CHUNK):
    reduced[start:start + PCA_CHUNK] = ipca.transform(embeddings[start:start + PCA_CHUNK])

print(f"   降维后形状: {reduced.shape}")

# ── 4. 保存 ──────────────────────────────────────────────────────
import pickle
OUTPUT_DIR.mkdir(exist_ok=True)
np.save(OUTPUT_DIR / "embeddings.npy", reduced)
np.save(OUTPUT_DIR / "ids.npy", ids)
np.save(OUTPUT_DIR / "metadata.npy", metadata)
# 保存 PCA 模型，供查询时变换查询向量
with open(OUTPUT_DIR / "pca_model.pkl", "wb") as f:
    pickle.dump(ipca, f)

print(f"\n✅ 已保存到: {OUTPUT_DIR}")
print(f"   embeddings.npy : {reduced.shape}")
print(f"   ids.npy        : {ids.shape}")
print(f"   metadata.npy   : {metadata.shape}")
print(f"   pca_model.pkl  : PCA 模型（1024→768维）")
