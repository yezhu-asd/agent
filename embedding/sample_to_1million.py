"""
从 106 万条数据中随机抽取 100 万条，保存到新文件，供 Zilliz Cloud Sandbox 免费档使用。
原始文件不会被修改。
"""
import numpy as np
from pathlib import Path

SOURCE_DIR = Path(__file__).parent / "embedding" / "embedding_merged"
OUTPUT_DIR = Path(__file__).parent / "embedding" / "embedding_sampled"

TARGET = 1_000_000  # Zilliz free tier 上限

embeddings = np.load(SOURCE_DIR / "embeddings.npy")
ids = np.load(SOURCE_DIR / "ids.npy", allow_pickle=True)
metadata = np.load(SOURCE_DIR / "metadata.npy", allow_pickle=True)

total = len(embeddings)
print(f"原始数据量: {total:,} 条")
print(f"目标数据量: {TARGET:,} 条")
print(f"将随机丢弃: {total - TARGET:,} 条\n")

# 随机抽取索引（不重复，保持原始顺序）
rng = np.random.default_rng(42)
chosen = sorted(rng.choice(total, size=TARGET, replace=False))

# 按抽取索引截取
sampled_embeddings = embeddings[chosen]
sampled_ids = ids[chosen]
sampled_metadata = metadata[chosen]

# 保存到新目录
OUTPUT_DIR.mkdir(exist_ok=True)
np.save(OUTPUT_DIR / "embeddings.npy", sampled_embeddings)
np.save(OUTPUT_DIR / "ids.npy", sampled_ids)
np.save(OUTPUT_DIR / "metadata.npy", sampled_metadata)

print(f"✅ 已保存到: {OUTPUT_DIR}")
print(f"   embeddings.npy : {sampled_embeddings.shape}")
print(f"   ids.npy        : {sampled_ids.shape}")
print(f"   metadata.npy   : {sampled_metadata.shape}")
