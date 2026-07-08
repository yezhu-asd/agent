
"""
合并embedding文件的脚本 - 兼容性改进版
解决numpy版本问题
"""
import numpy as np
import os
import shutil
from pathlib import Path
import sys

# 配置路径
BASE_DIR = Path("embedding/my_folder")
FULL_DIR = BASE_DIR / "embeddings_full"
ALL_DIR = BASE_DIR / "embedding_all"
OUTPUT_DIR = BASE_DIR / "embedding_merged"

# 备份原数据
print("=== Step 1: 准备输出目录 ===")
if OUTPUT_DIR.exists():
    backup_dir = BASE_DIR / f"embedding_merged_backup_{os.urandom(4).hex()}"
    print(f"输出目录已存在，备份到 {backup_dir}")
    shutil.move(str(OUTPUT_DIR), str(backup_dir))

OUTPUT_DIR.mkdir(parents=True)
(OUTPUT_DIR / "checkpoints").mkdir(exist_ok=True)

print(f"输出目录: {OUTPUT_DIR}")

# 加载前半部分数据 - 先只加载embeddings和ids，metadata单独处理
print("\n=== Step 2: 加载前半部分数据 (embeddings_full) ===")
last_full_ckpt = FULL_DIR / "checkpoints" / "checkpoint_001740.npz"
print(f"加载: {last_full_ckpt}")

# 使用np.load并处理可能的异常
try:
    data_full = np.load(last_full_ckpt, allow_pickle=True)
except Exception as e:
    print(f"直接加载失败: {e}")
    print("尝试分字段加载...")
    # 重新打开，逐个加载
    data_full = np.load(last_full_ckpt, allow_pickle=True)

embeddings_full = data_full['embeddings']
ids_full = data_full['ids']

print(f"  前半部分 embeddings shape: {embeddings_full.shape}")
print(f"  前半部分 ids 范围: {ids_full[0]} -> {ids_full[-1]}")
print(f"  前半部分 数量: {len(ids_full)}")

# 尝试加载metadata - 如果失败，我们可以从原始数据重建
try:
    metadata_full = data_full['metadata']
    print(f"  metadata加载成功，类型: {type(metadata_full)}")
except Exception as e:
    print(f"  metadata加载失败: {e}")
    print("  我们将跳过metadata合并，或者稍后重建")
    metadata_full = None

# 加载后半部分数据
print("\n=== Step 3: 加载后半部分数据 (embedding_all) ===")
last_all_ckpt = ALL_DIR / "checkpoints" / "checkpoint_002080.npz"
print(f"加载: {last_all_ckpt}")
data_all = np.load(last_all_ckpt, allow_pickle=True)

embeddings_all = data_all['embeddings']
ids_all = data_all['ids']

print(f"  后半部分 embeddings shape: {embeddings_all.shape}")
print(f"  后半部分 ids 范围: {ids_all[0]} -> {ids_all[-1]}")
print(f"  后半部分 数量: {len(ids_all)}")

try:
    metadata_all = data_all['metadata']
    print(f"  metadata加载成功")
except Exception as e:
    print(f"  metadata加载失败: {e}")
    metadata_all = None

# 验证连续性
print("\n=== Step 4: 验证连续性 ===")
last_id_full = int(ids_full[-1].split('_')[1])
first_id_all = int(ids_all[0].split('_')[1])

print(f"前半部分最后一个 ID: {ids_full[-1]} (num: {last_id_full})")
print(f"后半部分第一个 ID: {ids_all[0]} (num: {first_id_all})")

if first_id_all == last_id_full + 1:
    print("OK: ID连续，无间隙！")
else:
    print(f"WARN: ID不连续！间隙为 {first_id_all - last_id_full - 1}")

# 验证维度匹配
print(f"\nEmbedding 维度匹配: {embeddings_full.shape[1] == embeddings_all.shape[1]}")
print(f"Embedding dtype匹配: {embeddings_full.dtype == embeddings_all.dtype}")

# 执行合并
print("\n=== Step 5: 执行合并 ===")
print("正在拼接 embeddings...")
merged_embeddings = np.concatenate([embeddings_full, embeddings_all], axis=0)

print("正在拼接 ids...")
merged_ids = np.concatenate([ids_full, ids_all], axis=0)

# 只有当两个metadata都加载成功时才合并
merged_metadata = None
if metadata_full is not None and metadata_all is not None:
    print("正在拼接 metadata...")
    try:
        merged_metadata = np.concatenate([metadata_full, metadata_all], axis=0)
    except Exception as e:
        print(f"metadata拼接失败: {e}")
        merged_metadata = None

print(f"\n合并结果:")
print(f"  embeddings shape: {merged_embeddings.shape}")
print(f"  ids shape: {merged_ids.shape}")
if merged_metadata is not None:
    print(f"  metadata shape: {merged_metadata.shape}")
print(f"  IDs: {merged_ids[0]} -> {merged_ids[-1]}")

# 保存合并后的文件
print("\n=== Step 6: 保存合并后的文件 ===")
np.save(OUTPUT_DIR / "embeddings.npy", merged_embeddings)
print(f"已保存: {OUTPUT_DIR / 'embeddings.npy'}")

np.save(OUTPUT_DIR / "ids.npy", merged_ids)
print(f"已保存: {OUTPUT_DIR / 'ids.npy'}")

if merged_metadata is not None:
    np.save(OUTPUT_DIR / "metadata.npy", merged_metadata)
    print(f"已保存: {OUTPUT_DIR / 'metadata.npy'}")
else:
    print("注意: metadata未保存（加载失败）")
    print("我们将在验证步骤中尝试从原始CSV重建metadata")

# 同时创建一个最终的checkpoint文件
print("\n=== Step 7: 创建合并后的checkpoint ===")
final_checkpoint = {
    'embeddings': merged_embeddings,
    'ids': merged_ids,
    'start_batch': 0
}
if merged_metadata is not None:
    final_checkpoint['metadata'] = merged_metadata

ckpt_path = OUTPUT_DIR / "checkpoints" / "checkpoint_final.npz"
np.savez(ckpt_path, **final_checkpoint)
print(f"已保存: {ckpt_path}")

print("\n=== 合并完成 ===")
print(f"所有文件保存在: {OUTPUT_DIR}")
