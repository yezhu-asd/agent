"""
用 FlagEmbedding 重新生成 1024 维 embedding → PCA 降维到 768 → 上传 Milvus
确保查询和存储使用完全一致的 encoder。
"""
import numpy as np
import pickle
from pathlib import Path
from sklearn.decomposition import IncrementalPCA
from FlagEmbedding import BGEM3FlagModel

SOURCE_DIR = Path(__file__).parent / "embedding_merged"
OUTPUT_DIR = Path(__file__).parent / "embedding_st"

TARGET = 1_000_000      # 全量生成
TARGET_DIM = 768
BATCH = 128  # 每批编码条数（4GB GPU 显存建议 128）

print("📂 加载原始数据...")
ids = np.load(SOURCE_DIR / "ids.npy", allow_pickle=True)
metadata = np.load(SOURCE_DIR / "metadata.npy", allow_pickle=True)
total = len(ids)
print(f"   共 {total:,} 条")

# ── 1. 随机抽样 ──────────────────────
if total > TARGET:
    print(f"\n🎲 随机抽样 {TARGET:,} 条...")
    rng = np.random.default_rng(42)
    chosen = sorted(rng.choice(total, size=TARGET, replace=False))
    ids = ids[chosen]
    metadata = metadata[chosen]

# ── 2. 用 SentenceTransformer 生成 embedding（GPU 利用率更高）───
print("\n正在加载 SentenceTransformer BGE-M3...")
from sentence_transformers import SentenceTransformer
model = SentenceTransformer(r'E:\wu\xidian\job\java\agent\models\bge-m3', device='cuda')
model.max_seq_length = 512

print("\n生成 embedding...")
all_vecs = np.empty((len(ids), 1024), dtype=np.float32)
for start in range(0, len(ids), BATCH):
    batch = metadata[start:start + BATCH]
    texts = []
    for m in batch:
        m = m.item() if hasattr(m, 'item') else m
        text = f"{m.get('ask', '')} {m.get('answer', '')} {m.get('title', '')}"
        texts.append(text)
    vecs = model.encode(texts, normalize_embeddings=False, show_progress_bar=False, batch_size=BATCH)
    all_vecs[start:start + BATCH] = vecs.astype(np.float32)
    if (start // BATCH) % 5 == 0:
        print(f"   {min(start + BATCH, len(ids))}/{len(ids)}")

print(f"\n生成完成: shape={all_vecs.shape}")

# ── 3. PCA 降维 ──────────────────────
print(f"\nPCA 降维 1024 -> {TARGET_DIM}...")
from sklearn.decomposition import IncrementalPCA
pca = IncrementalPCA(n_components=TARGET_DIM)
for start in range(0, len(all_vecs), 10000):
    pca.partial_fit(all_vecs[start:start + 10000])
print(f"   解释方差比: {pca.explained_variance_ratio_.sum():.4f}")

reduced = np.empty((len(all_vecs), TARGET_DIM), dtype=np.float32)
for start in range(0, len(all_vecs), 10000):
    reduced[start:start + 10000] = pca.transform(all_vecs[start:start + 10000])

# ── 4. 保存 ──────────────────────────
OUTPUT_DIR.mkdir(exist_ok=True)
np.save(OUTPUT_DIR / "embeddings.npy", reduced)
np.save(OUTPUT_DIR / "ids.npy", ids)
np.save(OUTPUT_DIR / "metadata.npy", metadata)
with open(OUTPUT_DIR / "pca_model.pkl", "wb") as f:
    pickle.dump(pca, f)
print(f"\n✅ 已保存到 {OUTPUT_DIR}")
print(f"   embeddings.npy : {reduced.shape}")
print(f"   ids.npy        : {ids.shape}")
print(f"   metadata.npy   : {metadata.shape}")
print(f"   pca_model.pkl  : PCA 模型")
