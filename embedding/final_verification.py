"""
完整验证：检查所有合并后的文件是否可用于RAG项目
"""
import numpy as np
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = Path("embedding/my_folder/embedding_merged")

print("="*70)
print("完整验证检查")
print("="*70)

# 检查所有必需文件
print("\n=== 1. 文件完整性检查 ===")
required_files = {
    "ids.npy": "Vector IDs",
    "embeddings.npy": "Embedding vectors",
    "metadata.npy": "Document metadata"
}

all_files_exist = True
for filename, description in required_files.items():
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        size_mb = file_path.stat().st_size / (1024 * 1024)
        print(f"OK {filename}: {size_mb:.2f} MB - {description}")
    else:
        print(f"FAIL {filename}: 不存在 - {description}")
        all_files_exist = False

# 加载所有数据
print("\n=== 2. 加载数据 ===")
ids = np.load(OUTPUT_DIR / "ids.npy")
embeddings = np.load(OUTPUT_DIR / "embeddings.npy")
metadata = np.load(OUTPUT_DIR / "metadata.npy", allow_pickle=True)

print(f"IDs: {ids.shape}, dtype={ids.dtype}")
print(f"Embeddings: {embeddings.shape}, dtype={embeddings.dtype}")
print(f"Metadata: {metadata.shape}, dtype={metadata.dtype}")

# 检查数据一致性
print("\n=== 3. 数据一致性检查 ===")
n_ids = len(ids)
n_embeddings = embeddings.shape[0]
n_metadata = len(metadata)

print(f"IDs count: {n_ids}")
print(f"Embeddings count: {n_embeddings}")
print(f"Metadata count: {n_metadata}")

if n_ids == n_embeddings == n_metadata:
    print("OK: 所有数据数量一致!")
    data_consistent = True
else:
    print(f"FAIL: 数据数量不一致!")
    data_consistent = False

# 检查ID连续性
print("\n=== 4. ID连续性检查 ===")
first_id = int(ids[0].split('_')[1])
last_id = int(ids[-1].split('_')[1])
expected_count = last_id + 1

print(f"First ID: {ids[0]} (num: {first_id})")
print(f"Last ID: {ids[-1]} (num: {last_id})")
print(f"Expected count: {expected_count}")
print(f"Actual count: {len(ids)}")

if expected_count == len(ids):
    print("OK: ID序列完整，无缺口!")
    ids_complete = True
else:
    print(f"FAIL: ID序列不完整，缺口: {expected_count - len(ids)}")
    ids_complete = False

# 检查embedding质量
print("\n=== 5. Embedding质量检查 ===")
embedding_dim = embeddings.shape[1]
has_nan = np.isnan(embeddings).any()
has_inf = np.isinf(embeddings).any()

print(f"Embedding dimension: {embedding_dim}")
print(f"Has NaN: {has_nan}")
print(f"Has Inf: {has_inf}")

if not has_nan and not has_inf:
    mean_norm = np.linalg.norm(embeddings, axis=1).mean()
    std_norm = np.linalg.norm(embeddings, axis=1).std()
    print(f"Mean L2 norm: {mean_norm:.3f}")
    print(f"L2 norm std: {std_norm:.3f}")
    print("OK: 所有向量都是有效的归一化向量!")
    embeddings_valid = True
else:
    print("FAIL: 发现无效数值!")
    embeddings_valid = False

# 检查metadata结构
print("\n=== 6. Metadata结构检查 ===")
sample_metadata = metadata[0]
required_keys = {'department', 'title', 'ask', 'answer', 'source'}

if isinstance(sample_metadata, dict):
    available_keys = set(sample_metadata.keys())
    missing_keys = required_keys - available_keys
    extra_keys = available_keys - required_keys

    print(f"Metadata type: dict")
    print(f"Required keys: {required_keys}")
    print(f"Available keys: {available_keys}")

    if missing_keys:
        print(f"WARNING: Missing keys: {missing_keys}")
    if extra_keys:
        print(f"NOTE: Extra keys: {extra_keys}")

    if not missing_keys:
        print("OK: Metadata结构完整!")
        metadata_valid = True
    else:
        print("FAIL: Metadata缺少必需字段!")
        metadata_valid = False
else:
    print(f"FAIL: Metadata不是dict类型，而是 {type(sample_metadata)}")
    metadata_valid = False

# 检查checkpoint文件
print("\n=== 7. Checkpoint文件检查 ===")
ckpt_path = OUTPUT_DIR / "checkpoints" / "checkpoint_final.npz"
if ckpt_path.exists():
    ckpt_data = np.load(ckpt_path, allow_pickle=True)
    ckpt_keys = set(ckpt_data.keys())
    required_ckpt_keys = {'embeddings', 'ids', 'metadata', 'start_batch'}

    print(f"Checkpoint file exists: {ckpt_path}")
    print(f"Checkpoint keys: {ckpt_keys}")
    print(f"Required keys: {required_ckpt_keys}")

    if required_ckpt_keys.issubset(ckpt_keys):
        print("OK: Checkpoint包含所有必需字段!")
        checkpoint_valid = True
    else:
        missing = required_ckpt_keys - ckpt_keys
        print(f"FAIL: Checkpoint缺少字段: {missing}")
        checkpoint_valid = False
else:
    print("WARNING: Checkpoint文件不存在（可选）")
    checkpoint_valid = True  # 不是必需的

# 最终评估
print("\n" + "="*70)
print("验证总结")
print("="*70)

checks = [
    ("文件完整性", all_files_exist),
    ("数据一致性", data_consistent),
    ("ID连续性", ids_complete),
    ("Embedding质量", embeddings_valid),
    ("Metadata结构", metadata_valid),
    ("Checkpoint文件", checkpoint_valid)
]

all_passed = all(result for _, result in checks)

for check_name, result in checks:
    status = "PASS" if result else "FAIL"
    symbol = "✓" if result else "✗"
    print(f"{symbol} {check_name}: {status}")

print("="*70)

if all_passed:
    print("\nSUCCESS: 所有检查通过！该embedding文件组可以用于RAG项目。")
    print(f"\n使用方式:")
    print(f"  加载ID: np.load('{OUTPUT_DIR}/ids.npy')")
    print(f"  加载Embedding: np.load('{OUTPUT_DIR}/embeddings.npy')")
    print(f"  加载Metadata: np.load('{OUTPUT_DIR}/metadata.npy', allow_pickle=True)")
else:
    print("\nFAILURE: 部分检查未通过，请检查上述失败项。")
