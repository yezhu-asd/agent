
"""
验证已合并的embedding文件
"""
import numpy as np
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = Path("embedding/my_folder/embedding_merged")

print("=== 验证合并后的文件 ===")

# 检查文件是否存在
files_to_check = ["ids.npy", "embeddings.npy"]
for filename in files_to_check:
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"OK {filename}: {size_mb:.2f} MB")
    else:
        print(f"FAIL {filename}: 不存在!")

print("\n=== 加载数据 ===")

ids = np.load(OUTPUT_DIR / "ids.npy")
embeddings = np.load(OUTPUT_DIR / "embeddings.npy")

print(f"ids shape: {ids.shape}")
print(f"ids dtype: {ids.dtype}")
print(f"ids first 5: {ids[:5]}")
print(f"ids last 5: {ids[-5:]}")

print(f"\nembeddings shape: {embeddings.shape}")
print(f"embeddings dtype: {embeddings.dtype}")

# 验证ID连续性
print("\n=== 验证ID连续性 ===")
last_id = int(ids[-1].split('_')[1])
expected_count = last_id + 1
actual_count = len(ids)

print(f"Last ID: {ids[-1]} (num: {last_id})")
print(f"Expected count: {expected_count}")
print(f"Actual count: {actual_count}")

if expected_count == actual_count:
    print("OK: ID序列完整，无缺口!")
else:
    print(f"FAIL: ID序列不完整，缺口: {expected_count - actual_count}")

# 抽样验证embedding
print("\n=== 抽样验证embedding ===")
sample_indices = [0, len(ids)//2, len(ids)-1]
for idx in sample_indices:
    vec_id = ids[idx]
    embedding = embeddings[idx]
    print(f"ID {vec_id} (index {idx}):")
    print(f"  Vector shape: {embedding.shape}")
    print(f"  Range: [{embedding.min():.3f}, {embedding.max():.3f}]")
    print(f"  L2 norm: {np.linalg.norm(embedding):.3f}")

# 统计embedding特征
print("\n=== Embedding统计信息 ===")
mean_norm = np.linalg.norm(embeddings, axis=1).mean()
std_norm = np.linalg.norm(embeddings, axis=1).std()
print(f"Mean L2 norm: {mean_norm:.3f}")
print(f"L2 norm std: {std_norm:.3f}")

# 检查是否有NaN或Inf
has_nan = np.isnan(embeddings).any()
has_inf = np.isinf(embeddings).any()
print(f"Has NaN: {has_nan}")
print(f"Has Inf: {has_inf}")

if not has_nan and not has_inf:
    print("OK: 所有向量都是有效的数值!")
else:
    print("FAIL: 发现无效数值!")

print("\n=== 验证总结 ===")
print(f"OK: 成功加载 {len(ids)} 个向量")
print(f"OK: 向量维度: {embeddings.shape[1]}")
print(f"OK: ID范围: vec_0 -> vec_{last_id}")
print(f"OK: 数据类型: {embeddings.dtype}")

# 检查checkpoint
ckpt_path = OUTPUT_DIR / "checkpoints" / "checkpoint_final.npz"
if ckpt_path.exists():
    print(f"\nOK: Checkpoint文件存在")
    ckpt_data = np.load(ckpt_path)
    print(f"  Checkpoint keys: {list(ckpt_data.keys())}")
