
"""
从原始CSV数据重建metadata
"""
import numpy as np
import csv
from pathlib import Path
from tqdm import tqdm

# 数据集目录 - 根据项目结构
DATASET_BASE = Path("models/Chinese-medical-dialogue-data-master/Data_数据")

print("=== 从CSV重建metadata ===")

# 加载所有CSV数据
def load_all_metadata():
    all_metadata = []
    total_records = 0

    for folder in DATASET_BASE.iterdir():
        if folder.is_dir():
            print(f"\nProcessing department: {folder.name}")
            for csv_file in folder.glob("*.csv"):
                print(f"  Loading {csv_file.name}...", end=" ")
                data = []
                encodings = ['gbk', 'gb2312', 'utf-8', 'gb18030']

                loaded = False
                for encoding in encodings:
                    try:
                        with open(csv_file, 'r', encoding=encoding) as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if 'ask' in row and 'answer' in row:
                                    title = row.get('title', '')
                                    ask = row.get('ask', '')
                                    answer = row.get('answer', '')
                                    department = row.get('department', '') or folder.name

                                    data.append({
                                        'department': department,
                                        'title': title,
                                        'ask': ask,
                                        'answer': answer,
                                        'source': csv_file.name
                                    })
                        print(f"OK ({len(data)} records)")
                        loaded = True
                        break
                    except UnicodeDecodeError:
                        continue
                    except Exception as e:
                        print(f"FAIL: {e}")
                        continue

                if not loaded:
                    print(f"FAIL: No encoding worked")
                    continue

                all_metadata.extend(data)
                total_records += len(data)

    return all_metadata

print("Loading CSV data...")
metadata_list = load_all_metadata()
print(f"\nTotal records loaded from CSV: {len(metadata_list)}")

# 检查数量是否匹配
OUTPUT_DIR = Path("embedding/my_folder/embedding_merged")
ids = np.load(OUTPUT_DIR / "ids.npy")
expected_count = len(ids)

print(f"Expected count from merged ids: {expected_count}")
print(f"Actual count from CSV: {len(metadata_list)}")

if len(metadata_list) < expected_count:
    print(f"WARNING: CSV data has fewer records than embeddings ({expected_count - len(metadata_list)} missing)")
elif len(metadata_list) > expected_count:
    print(f"WARNING: CSV data has more records than embeddings ({len(metadata_list) - expected_count} excess)")

# 截取到对应数量
metadata_to_save = metadata_list[:expected_count]

print(f"\nUsing {len(metadata_to_save)} metadata records")

# 转换为numpy数组并保存
print("Converting to numpy array...")
metadata_array = np.array(metadata_to_save, dtype=object)

print(f"Metadata array shape: {metadata_array.shape}")
print(f"First metadata sample: {metadata_array[0]}")
print(f"Last metadata sample: {metadata_array[-1]}")

print("\nSaving metadata...")
np.save(OUTPUT_DIR / "metadata.npy", metadata_array)
print(f"Saved: {OUTPUT_DIR / 'metadata.npy'}")

# 更新checkpoint
print("\nUpdating checkpoint...")
ckpt_path = OUTPUT_DIR / "checkpoints" / "checkpoint_final.npz"
ckpt_data = np.load(ckpt_path)

new_checkpoint = {
    'embeddings': ckpt_data['embeddings'],
    'ids': ids,
    'metadata': metadata_array,
    'start_batch': ckpt_data['start_batch']
}

np.savez(ckpt_path, **new_checkpoint)
print(f"Updated: {ckpt_path}")

print("\n=== Metadata重建完成 ===")
