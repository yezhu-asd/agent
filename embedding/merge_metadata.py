
"""
尝试从embedding_all的完整文件加载metadata并合并
"""
import numpy as np
from pathlib import Path
import sys

# 配置路径
BASE_DIR = Path("embedding/my_folder")
FULL_DIR = BASE_DIR / "embeddings_full"
ALL_DIR = BASE_DIR / "embedding_all"
OUTPUT_DIR = BASE_DIR / "embedding_merged"

print("=== 尝试加载后半部分的metadata ===")

# 先尝试从embedding_all的完整文件加载metadata
try:
    print("尝试从 embedding_all/metadata.npy 加载...")
    metadata_all = np.load(ALL_DIR / "metadata.npy", allow_pickle=True)
    ids_all_full = np.load(ALL_DIR / "ids.npy", allow_pickle=True)

    print(f"metadata_all shape: {metadata_all.shape}")
    print(f"ids_all_full shape: {ids_all_full.shape}")
    print(f"ids_all_full 范围: {ids_all_full[0]} -> {ids_all_full[-1]}")

    # 我们需要的是前 174080 条（从vec_890880到vec_1064959）
    # 因为embedding_all的完整文件有179876条，但我们只合并了174080条
    target_count = 174080
    metadata_subset = metadata_all[:target_count]
    ids_subset = ids_all_full[:target_count]

    print(f"截取的metadata shape: {metadata_subset.shape}")
    print(f"截取的ids 范围: {ids_subset[0]} -> {ids_subset[-1]}")

except Exception as e:
    print(f"从完整文件加载失败: {e}")
    print("尝试从checkpoint加载...")
    try:
        data_all = np.load(ALL_DIR / "checkpoints" / "checkpoint_002080.npz", allow_pickle=True)
        metadata_subset = data_all['metadata']
        ids_subset = data_all['ids']
        print(f"从checkpoint加载的metadata shape: {metadata_subset.shape}")
    except Exception as e2:
        print(f"从checkpoint加载也失败: {e2}")
        metadata_subset = None
        ids_subset = None

if metadata_subset is not None:
    print("\n=== 尝试加载前半部分的metadata ===")
    # 尝试从embeddings_full加载前半部分的metadata
    try:
        data_full = np.load(FULL_DIR / "checkpoints" / "checkpoint_001740.npz", allow_pickle=True)
        metadata_full = data_full['metadata']
        ids_full = data_full['ids']
        print(f"前半部分 metadata shape: {metadata_full.shape}")
        print(f"前半部分 ids 范围: {ids_full[0]} -> {ids_full[-1]}")

        print("\n=== 合并metadata ===")
        merged_metadata = np.concatenate([metadata_full, metadata_subset], axis=0)
        merged_ids = np.concatenate([ids_full, ids_subset], axis=0)

        print(f"合并后的metadata shape: {merged_metadata.shape}")
        print(f"合并后的ids 范围: {merged_ids[0]} -> {merged_ids[-1]}")

        # 保存
        print("\n=== 保存metadata ===")
        np.save(OUTPUT_DIR / "metadata.npy", merged_metadata)
        print(f"已保存: {OUTPUT_DIR / 'metadata.npy'}")

        # 同时更新checkpoint
        print("\n=== 更新checkpoint ===")
        data_merged = np.load(OUTPUT_DIR / "checkpoints" / "checkpoint_final.npz", allow_pickle=True)
        new_checkpoint = {
            'embeddings': data_merged['embeddings'],
            'ids': merged_ids,
            'metadata': merged_metadata,
            'start_batch': data_merged['start_batch']
        }
        np.savez(OUTPUT_DIR / "checkpoints" / "checkpoint_final.npz", **new_checkpoint)
        print(f"已更新: {OUTPUT_DIR / 'checkpoints' / 'checkpoint_final.npz'}")

    except Exception as e:
        print(f"加载前半部分metadata失败: {e}")
        print("\n=== 尝试从embeddings_full中查找metadata文件 ===")
        # 查找是否有metadata相关文件
        for file in FULL_DIR.rglob("*.npy"):
            if "metadata" in file.name.lower():
                print(f"找到: {file}")
else:
    print("metadata_subset is None，无法合并metadata")
