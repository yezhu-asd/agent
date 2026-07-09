"""
稳定版：上传 embedding 到 Milvus
- 自动记录进度（断点续传）
- 字段保守截断，避免超长度
- 小批次上传，出错跳过不卡住
"""
import numpy as np
import time
import sys
import json
from pathlib import Path
from datetime import timedelta
from tqdm import tqdm

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from services.milvus_service import MilvusService


# =======================
# 配置
# =======================
EMBEDDING_DIR = PROJECT_ROOT / "embedding" / "embedding_merged"
PROGRESS_FILE = PROJECT_ROOT / "embedding" / "upload_progress.json"
BATCH_SIZE = 1000
CHUNK_SIZE = 100  # 出错时用小块重试，跳过坏记录


def load_embedding_data():
    """加载 embedding 数据"""
    print("\n📂 加载 embedding 数据...")

    if not EMBEDDING_DIR.exists():
        raise FileNotFoundError(f"找不到 embedding 目录: {EMBEDDING_DIR}")

    embeddings = np.load(EMBEDDING_DIR / "embeddings.npy")
    ids = np.load(EMBEDDING_DIR / "ids.npy", allow_pickle=True)
    metadata = np.load(EMBEDDING_DIR / "metadata.npy", allow_pickle=True)

    print(f"   ✅ 向量形状: {embeddings.shape}")
    print(f"   ✅ 向量维度: {embeddings.shape[1]}")
    print(f"   ✅ ID 数量: {len(ids)}")

    return embeddings, ids, metadata


def load_progress():
    """加载上传进度"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress = json.load(f)
        return set(progress.get('uploaded_indices', []))
    return set()


def save_progress(uploaded_set):
    """保存上传进度"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump({
            'uploaded_indices': list(uploaded_set),
            'last_update': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f)


def truncate_text(text, max_chars):
    """保守截断文本，考虑UTF-8中文字符占3字节"""
    if not text:
        return ""
    # 按字符截断到 max_chars * 0.7，确保中文字符也不会超字节限制
    safe_len = int(max_chars * 0.7)
    text = str(text)
    if len(text) <= safe_len:
        return text
    return text[:safe_len]


def build_vector(idx, embeddings, ids, metadata):
    """构建单条向量，保守截断所有字段"""
    meta = metadata[idx].item() if hasattr(metadata[idx], 'item') else metadata[idx]
    return {
        "id": str(ids[idx]),
        "values": embeddings[idx].tolist(),
        "metadata": {
            "content": "",
            "department": truncate_text(meta.get('department', ''), 128),
            "title": truncate_text(meta.get('title', ''), 512),
            "ask": truncate_text(meta.get('ask', ''), 4096),
            "answer": truncate_text(meta.get('answer', ''), 65535),
            "source": truncate_text(meta.get('source', ''), 128),
            "category": "",
            "keywords": "",
        }
    }


async def upload_indices(indices, embeddings, ids, metadata, milvus_service):
    """上传一批索引，成功的返回索引列表，失败的跳过"""
    vectors = [build_vector(i, embeddings, ids, metadata) for i in indices]
    try:
        success = await milvus_service.upsert(vectors)
        if success:
            return indices
        return []
    except Exception as e:
        # 整批失败，如果还能拆分就拆分，否则单条上传跳过坏的
        if len(indices) > 1:
            mid = len(indices) // 2
            left_ok = await upload_indices(indices[:mid], embeddings, ids, metadata, milvus_service)
            right_ok = await upload_indices(indices[mid:], embeddings, ids, metadata, milvus_service)
            return left_ok + right_ok
        else:
            # 单条失败，跳过
            print(f"\n   ⚠️  记录 {indices[0]} 跳过: {str(e)[:80]}")
            return []


async def main():
    print("=" * 70)
    print("🌟 稳定版：上传 Embedding 到 Milvus")
    print("=" * 70)

    # 1. 加载数据
    embeddings, ids, metadata = load_embedding_data()
    total = len(embeddings)

    # 2. 连接 Milvus
    print("\n🔗 连接 Milvus...")
    milvus_service = MilvusService()
    success = await milvus_service.initialize(dim=embeddings.shape[1])

    if not success:
        print("❌ Milvus 连接失败！请先启动 Milvus")
        return 1

    print("   ✅ Milvus 连接成功")

    # 3. 检查当前状态
    stats = await milvus_service.describe_index()
    current_count = stats.get('total_vector_count', 0)
    print(f"\n📊 当前 Milvus 已有: {current_count} 条向量")

    # 4. 加载进度
    uploaded_set = load_progress()
    if uploaded_set:
        print(f"📋 找到进度文件，已记录 {len(uploaded_set)} 条已上传")

    # 5. 找出未上传的
    all_indices = [i for i in range(total) if i not in uploaded_set]
    print(f"   待上传: {len(all_indices)} 条")

    if not all_indices:
        print("\n✅ 所有向量已上传完成！")
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
        milvus_service.close()
        return 0

    # 6. 开始上传
    print(f"\n{'=' * 70}")
    print(f"🚀 开始上传")
    print(f"{'=' * 70}\n")

    start_time = time.time()
    success_count = len(uploaded_set)
    failed_count = 0
    last_save = time.time()

    pbar = tqdm(range(0, len(all_indices), BATCH_SIZE), desc="上传进度", unit="batch")

    for batch_start in pbar:
        batch_indices = all_indices[batch_start : batch_start + BATCH_SIZE]

        # 这批按 CHUNK_SIZE 分块上传
        for chunk_start in range(0, len(batch_indices), CHUNK_SIZE):
            chunk = batch_indices[chunk_start : chunk_start + CHUNK_SIZE]
            ok_indices = await upload_indices(chunk, embeddings, ids, metadata, milvus_service)

            if ok_indices:
                uploaded_set.update(ok_indices)
                success_count += len(ok_indices)
            failed_count += len(chunk) - len(ok_indices)

        # 每5秒保存一次进度
        if time.time() - last_save > 5:
            save_progress(uploaded_set)
            last_save = time.time()

        pbar.set_postfix({
            "成功": success_count,
            "失败": failed_count,
            "进度": f"{success_count/total*100:.1f}%"
        })

    pbar.close()

    # 最终保存
    save_progress(uploaded_set)

    # 7. 统计
    total_time = time.time() - start_time

    print(f"\n{'=' * 70}")
    print(f"🎉 上传完成!")
    print(f"{'=' * 70}")
    print(f"   成功: {success_count} / {total}")
    print(f"   失败: {failed_count}")
    print(f"   总耗时: {str(timedelta(seconds=int(total_time)))}")
    if success_count > 0 and total_time > 0:
        print(f"   平均速度: {success_count / total_time:.1f} 条/秒")
    print(f"{'=' * 70}")

    # 8. 验证
    stats = await milvus_service.describe_index()
    final_count = stats.get('total_vector_count', 0)
    print(f"\n📊 Milvus 最终向量数: {final_count}")

    milvus_service.close()

    # 如果成功率 >= 99%，删除进度文件
    if success_count >= total * 0.99:
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()
            print("\n🗑️  进度文件已删除")
        print("\n✅ 上传成功！")
        return 0
    else:
        print(f"\n⚠️  部分数据失败，可重新运行脚本继续上传")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
