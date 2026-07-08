"""
Python脚本版：全量医学问答向量生成
适配Linux服务器 + RTX 4090D
处理所有107万条医疗问答记录
修复：增加检查点文件完整性检查和错误处理，避免BadZipFile错误
新增：支持手动指定从某个checkpoint文件开始继续处理
新增：支持直接跳过前面N个批次（checkpoint太大传不了时用这个）
"""
import os
import csv
import time
import gc
import numpy as np
import zipfile
from pathlib import Path
from tqdm import tqdm  # 普通Python用进度条
from datetime import datetime, timedelta

from FlagEmbedding import BGEM3FlagModel


# ============================================================
# 🔧 请修改为你的服务器实际路径
# ============================================================
DATASET_DIR = Path("/workspace/models/models/Chinese-medical-dialogue-data-master/Data_╩²╛▌")  # 医疗数据集目录
MODEL_PATH = "/workspace/models/models/bge-m3"  # BGE-M3模型路径
OUTPUT_DIR = Path("/workspace/embedding")  # 结果保存目录
CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"  # 检查点目录
# 如果要从指定checkpoint文件加载，把这里改成你的checkpoint文件路径，例如：
# RESUME_FROM_CHECKPOINT = Path("/root/data/agent/EmbeddingToPinecone/data/embeddings_full/checkpoints/checkpoint_000100.npz")
RESUME_FROM_CHECKPOINT = None  # None = 自动加载最新，指定具体文件路径 = 从该checkpoint继续
# 如果只想跳过前面N个批次，不需要加载旧checkpoint（当checkpoint太大传不了时使用）
# 例如 START_FROM_BATCH = 100 就是直接跳过前100个批次，从第101批开始处理
START_FROM_BATCH = 1740  # None = 不跳过，按checkpoint逻辑走，数字 = 直接从该批次开始
BATCH_SIZE = 512  # RTX 4090D推荐512，显存不足的话调为256
CHECKPOINT_INTERVAL = 20  # 每20批次保存一次检查点
MAX_LENGTH = 512  # 文本最大长度


def load_csv_data(file_path):
    """加载单个CSV文件，自动适配中文编码"""
    data = []
    encodings = ['gbk', 'gb2312', 'utf-8', 'gb18030']

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'ask' in row and 'answer' in row:
                        title = row.get('title', '')
                        ask = row.get('ask', '')
                        answer = row.get('answer', '')
                        department = row.get('department', '')
                        if not department:
                            department = file_path.parent.name  # 用文件夹名作为科室名

                        # 拼接成完整文本
                        combined_text = f"科室: {department}\n标题: {title}\n问题: {ask}\n回答: {answer}"

                        data.append({
                            'department': department,
                            'title': title,
                            'ask': ask,
                            'answer': answer,
                            'text': combined_text,
                            'source': file_path.name
                        })
            print(f"  ✅ {file_path.name} ({encoding}) → {len(data)} 条")
            return data
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"  ❌ 加载 {file_path.name} 失败: {e}")
            continue

    print(f"  ⚠️  无法加载 {file_path.name}，所有编码都不匹配")
    return []


def load_all_datasets(base_dir):
    """加载所有CSV文件，不采样，返回全部数据"""
    all_data = []
    total_files = 0

    for folder in base_dir.iterdir():
        if folder.is_dir():
            print(f"\n📂 处理科室: {folder.name}")
            for csv_file in folder.glob("*.csv"):
                total_files += 1
                data = load_csv_data(csv_file)
                all_data.extend(data)

    print(f"\n{'='*60}")
    print(f"📊 数据加载完成:")
    print(f"   总文件数: {total_files}")
    print(f"   总记录数: {len(all_data)}")
    print(f"{'='*60}")

    return all_data


def validate_checkpoint(checkpoint_path):
    """验证检查点文件完整性"""
    try:
        # 检查文件大小（太小肯定损坏）
        file_size = checkpoint_path.stat().st_size
        if file_size < 100:  # 小于100字节肯定损坏
            print(f"   ⚠️  文件过小 ({file_size} bytes)，跳过")
            return False

        # 检查ZIP完整性
        with zipfile.ZipFile(checkpoint_path, 'r') as z:
            z.testzip()  # 测试所有文件完整性

        # 尝试加载验证必要字段
        data = np.load(checkpoint_path, allow_pickle=True)
        required_keys = ['embeddings', 'ids', 'metadata', 'start_batch']
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            print(f"   ⚠️  缺少字段: {missing_keys}，跳过")
            return False

        return True
    except zipfile.BadZipFile:
        print(f"   ❌ 文件损坏 (BadZipFile)，跳过")
        return False
    except Exception as e:
        print(f"   ❌ 验证失败: {e}，跳过")
        return False


def load_checkpoint():
    """加载检查点，支持自动加载最新或手动指定，实现断点续传（带完整性验证和损坏回退）"""

    # 如果手动指定了checkpoint文件，优先使用指定文件
    if RESUME_FROM_CHECKPOINT is not None:
        print(f"\n📌 手动指定从检查点加载: {RESUME_FROM_CHECKPOINT}")
        checkpoint_path = Path(RESUME_FROM_CHECKPOINT)
        if not checkpoint_path.exists():
            print(f"   ❌ 指定的检查点文件不存在: {checkpoint_path}")
            print(f"   🔄 回退到自动加载最新检查点...")
        else:
            if validate_checkpoint(checkpoint_path):
                try:
                    data = np.load(checkpoint_path, allow_pickle=True)
                    all_embeddings = list(data['embeddings'])
                    all_ids = list(data['ids'])
                    all_metadata = list(data['metadata'])
                    start_batch = int(data['start_batch'])
                    print(f"⏯️  从指定检查点批次 {start_batch} 继续，已处理 {len(all_embeddings)} 条向量")
                    return (all_embeddings, all_ids, all_metadata), start_batch
                except Exception as e:
                    print(f"   ❌ 加载指定检查点失败: {e}")
                    print(f"   🔄 回退到自动加载最新检查点...")
            else:
                print(f"   ❌ 指定的检查点文件验证失败")
                print(f"   🔄 回退到自动加载最新检查点...")

    # 自动加载最新检查点逻辑
    if not CHECKPOINT_DIR.exists():
        return None, 0

    # 按文件名排序（批次号越大越新）
    checkpoint_files = sorted(CHECKPOINT_DIR.glob("checkpoint_*.npz"))
    if not checkpoint_files:
        return None, 0

    print(f"\n🔍 找到 {len(checkpoint_files)} 个检查点文件")

    # 从最新的开始尝试加载，如果损坏就尝试前一个
    for checkpoint_file in reversed(checkpoint_files):
        print(f"   尝试加载: {checkpoint_file.name}")

        if not validate_checkpoint(checkpoint_file):
            # 文件损坏，删除并尝试前一个
            try:
                checkpoint_file.unlink()
                print(f"   🗑️  已删除损坏文件")
            except Exception as e:
                print(f"   ⚠️  删除损坏文件失败: {e}")
            continue

        # 文件有效，尝试加载
        try:
            data = np.load(checkpoint_file, allow_pickle=True)
            all_embeddings = list(data['embeddings'])
            all_ids = list(data['ids'])
            all_metadata = list(data['metadata'])
            start_batch = int(data['start_batch'])

            print(f"⏯️  从批次 {start_batch} 继续，已处理 {len(all_embeddings)} 条向量")
            return (all_embeddings, all_ids, all_metadata), start_batch

        except Exception as e:
            print(f"   ❌ 加载失败: {e}")
            continue

    # 所有检查点都损坏了
    print("⚠️  所有检查点都无效，从头开始")
    return None, 0


def save_checkpoint(all_embeddings, all_ids, all_metadata, batch_idx):
    """保存检查点（改进版：先写临时文件，验证后再重命名，避免损坏）"""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = CHECKPOINT_DIR / f"checkpoint_{batch_idx:06d}.npz"
    temp_path = CHECKPOINT_DIR / f"checkpoint_{batch_idx:06d}.tmp.npz"

    try:
        # 先保存到临时文件
        np.savez_compressed(
            temp_path,
            embeddings=np.array(all_embeddings),
            ids=np.array(all_ids),
            metadata=np.array(all_metadata),
            start_batch=batch_idx
        )

        # 验证临时文件完整性
        if not validate_checkpoint(temp_path):
            temp_path.unlink()
            raise ValueError("临时文件保存后验证失败，已删除")

        # 验证通过，重命名为正式文件
        if checkpoint_path.exists():
            checkpoint_path.unlink()
        temp_path.replace(checkpoint_path)

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n💾 [{timestamp}] 检查点已保存: {checkpoint_path.name} (已处理 {len(all_embeddings)} 条)")

    except Exception as e:
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        print(f"\n❌ 保存检查点失败: {e}")
        raise


# ============================================================
# 🚀 开始运行
# ============================================================
print("=" * 70)
print("🌟 全量医学问答向量生成工具 (GPU加速版)")
print("   修复：增加检查点完整性检查，自动跳过损坏文件")
print("=" * 70)

# ---- 1. 加载全部数据 ----
print("\n[1/4] 📥 加载全量数据集...")
all_data = load_all_datasets(DATASET_DIR)
total_records = len(all_data)
if total_records == 0:
    print("❌ 未找到任何数据！")
    raise SystemExit

# ---- 2. 加载检查点 / 设置起始批次 ----
print("\n[2/4] 🔍 检查断点续传...")

# 初始化
all_embeddings = []
all_ids = []
all_metadata = []
start_batch = 0

# 如果START_FROM_BATCH设置了正数，优先使用（不加载checkpoint，直接跳过前面批次）
if START_FROM_BATCH and START_FROM_BATCH > 0:
    print(f"📌 跳过前面批次，直接从第 {START_FROM_BATCH} 批开始处理（不需要加载旧checkpoint）")
    start_batch = START_FROM_BATCH
else:
    # 正常加载checkpoint逻辑
    checkpoint_data, loaded_start = load_checkpoint()
    if checkpoint_data is not None:
        all_embeddings, all_ids, all_metadata = checkpoint_data
        start_batch = loaded_start

# ---- 3. 加载BGE-M3模型 ----
print("\n[3/4] 🧠 加载BGE-M3模型...")
try:
    model = BGEM3FlagModel(MODEL_PATH, use_fp16=True, device='cuda')
    print("✅ 模型已加载到GPU (cuda)")
except Exception as e:
    print(f"⚠️  GPU加载失败: {e}")
    print("🔄 回退到CPU模式...")
    model = BGEM3FlagModel(MODEL_PATH, use_fp16=True)
    print("✅ 模型已加载到CPU")

# ---- 4. 生成向量 ----
print(f"\n[4/4] ⚡ 开始生成向量 (batch_size={BATCH_SIZE})...")
texts = [item['text'] for item in all_data]
total_batches = (total_records + BATCH_SIZE - 1) // BATCH_SIZE

# 跳过已处理的批次
# 如果是START_FROM_BATCH模式，已处理记录数就是start_batch * BATCH_SIZE
if START_FROM_BATCH is not None and START_FROM_BATCH > 0:
    processed_records = start_batch * BATCH_SIZE
else:
    processed_records = len(all_embeddings)

texts = texts[start_batch * BATCH_SIZE:]
all_data = all_data[start_batch * BATCH_SIZE:]
remaining_batches = total_batches - start_batch
remaining_records = total_records - processed_records

print(f"\n{'='*70}")
print(f"📈 进度概览:")
print(f"   总批次: {total_batches}")
print(f"   已完成批次: {start_batch}")
print(f"   剩余批次: {remaining_batches}")
print(f"   总记录: {total_records}")
print(f"   已完成记录: {processed_records}")
print(f"   剩余记录: {remaining_records}")
if total_records > 0:
    print(f"   整体进度: {processed_records/total_records*100:.1f}%")
print(f"{'='*70}\n")

if remaining_batches == 0:
    print("🎉 所有数据已处理完成！")
    # 保存最终结果
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    embeddings_array = np.stack(all_embeddings, axis=0)
    ids_array = np.array(all_ids)
    metadata_array = np.array(all_metadata)

    np.save(OUTPUT_DIR / "embeddings.npy", embeddings_array)
    np.save(OUTPUT_DIR / "ids.npy", ids_array)
    np.save(OUTPUT_DIR / "metadata.npy", metadata_array)

    print(f"\n📂 最终结果已保存到: {OUTPUT_DIR}")
else:
    # 计时
    start_time = time.time()
    batch_times = []

    # 进度条
    pbar = tqdm(
        range(remaining_batches),
        desc=f"Embedding ({processed_records}/{total_records})",
        unit="batch"
    )

    for local_batch_idx in pbar:
        batch_start_time = time.time()

        global_batch_idx = start_batch + local_batch_idx
        start_idx = local_batch_idx * BATCH_SIZE
        end_idx = min((local_batch_idx + 1) * BATCH_SIZE, len(texts))

        batch_texts = texts[start_idx:end_idx]
        batch_data = all_data[start_idx:end_idx]

        try:
            # 生成向量（GPU加速）
            output = model.encode(
                batch_texts,
                batch_size=len(batch_texts),
                max_length=MAX_LENGTH
            )
            embeddings = output['dense_vecs']

            # 保存结果
            for i, (embedding, data_item) in enumerate(zip(embeddings, batch_data)):
                global_idx = global_batch_idx * BATCH_SIZE + i
                all_embeddings.append(embedding.astype(np.float32))
                all_ids.append(f"vec_{global_idx}")
                all_metadata.append({
                    'department': data_item['department'],
                    'title': data_item['title'],
                    'ask': data_item['ask'],
                    'answer': data_item['answer'],
                    'source': data_item['source']
                })

            # 记录耗时
            batch_time = time.time() - batch_start_time
            batch_times.append(batch_time)

            # 更新进度信息
            current_processed = processed_records + (local_batch_idx + 1) * BATCH_SIZE
            current_processed = min(current_processed, total_records)
            progress_pct = current_processed / total_records * 100

            # 估算剩余时间
            if len(batch_times) >= 5:
                avg_batch_time = np.mean(batch_times[-10:])
                remaining_time_sec = avg_batch_time * (remaining_batches - local_batch_idx - 1)
                eta_str = str(timedelta(seconds=int(remaining_time_sec)))
            else:
                eta_str = "计算中..."

            pbar.set_description(
                f"Embedding ({current_processed}/{total_records}, {progress_pct:.1f}%) | ETA: {eta_str}"
            )

            # 保存检查点
            if (global_batch_idx + 1) % CHECKPOINT_INTERVAL == 0:
                save_checkpoint(all_embeddings, all_ids, all_metadata, global_batch_idx + 1)
                gc.collect()  # 清理内存

        except Exception as e:
            print(f"\n❌ 处理批次 {global_batch_idx} 出错: {e}")
            print("💾 尝试保存检查点后退出...")
            try:
                save_checkpoint(all_embeddings, all_ids, all_metadata, global_batch_idx)
            except Exception as save_e:
                print(f"❌ 保存检查点失败: {save_e}")
            raise

    pbar.close()

    # 保存最终结果
    print("\n💾 保存最终结果...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    embeddings_array = np.stack(all_embeddings, axis=0)
    ids_array = np.array(all_ids)
    metadata_array = np.array(all_metadata)

    np.save(OUTPUT_DIR / "embeddings.npy", embeddings_array)
    np.save(OUTPUT_DIR / "ids.npy", ids_array)
    np.save(OUTPUT_DIR / "metadata.npy", metadata_array)

    # 统计信息
    total_time = time.time() - start_time
    if batch_times:
        avg_time = np.mean(batch_times)
        max_time = np.max(batch_times)
        speed = (total_records - processed_records) / total_time
        print(f"\n{'='*70}")
        print(f"🎉 处理完成!")
        print(f"{'='*70}")
        print(f"   总记录数: {len(all_embeddings)}")
        print(f"   总耗时: {str(timedelta(seconds=int(total_time)))}")
        print(f"   平均速度: {speed:.1f} 条/秒")
        print(f"   平均批次耗时: {avg_time:.2f}s")
        print(f"   最长批次耗时: {max_time:.2f}s")
        print(f"   向量维度: {embeddings_array.shape[1]}")

    print(f"\n📂 保存路径:")
    print(f"   向量: {OUTPUT_DIR / 'embeddings.npy'}  — 形状 {embeddings_array.shape}")
    print(f"   ID: {OUTPUT_DIR / 'ids.npy'}         — 形状 {ids_array.shape}")
    print(f"   元数据: {OUTPUT_DIR / 'metadata.npy'}    — 形状 {metadata_array.shape}")
    print(f"   检查点: {CHECKPOINT_DIR}")
    print("=" * 70)
