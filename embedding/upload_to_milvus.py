"""
上传 embedding 文件夹中的词向量到 Milvus
处理 107万条医学问答向量数据
"""

import numpy as np
import time
import logging
import sys
from pathlib import Path
from datetime import timedelta
from tqdm import tqdm
from pymilvus.exceptions import MilvusException

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from services.milvus_service import MilvusService


# =======================
# 配置
# =======================
EMBEDDING_DIR = PROJECT_ROOT / "embedding" / "embedding_merged"
BATCH_SIZE = 10000  # 每次上传 10000 条向量（Milvus 已配置 8G 内存，可安全使用大批次）
VERIFY_LIMIT = 100  # 验证前 100 条向量


def load_embedding_data():
    """加载合并后的 embedding 数据"""
    print("\n📂 加载 embedding 数据...")

    if not EMBEDDING_DIR.exists():
        raise FileNotFoundError(f"找不到 embedding 目录: {EMBEDDING_DIR}")

    embeddings = np.load(EMBEDDING_DIR / "embeddings.npy")
    ids = np.load(EMBEDDING_DIR / "ids.npy", allow_pickle=True)
    metadata = np.load(EMBEDDING_DIR / "metadata.npy", allow_pickle=True)

    print(f"   ✅ 向量形状: {embeddings.shape}")
    print(f"   ✅ ID 数量: {len(ids)}")
    print(f"   ✅ 元数据数量: {len(metadata)}")
    print(f"   ✅ 向量维度: {embeddings.shape[1]}")

    return embeddings, ids, metadata


def verify_data(embeddings, ids, metadata):
    """简单验证数据"""
    print("\n🔍 验证样本数据...")

    for i in range(min(VERIFY_LIMIT, len(ids))):
        if i < 5:
            print(f"\n   示例 {i + 1}:")
            print(f"   ID: {ids[i]}")
            print(f"   元数据: {metadata[i]}")
            print(f"   向量 (前5维): {embeddings[i][:5]}")

    # 检查 NaN
    if np.isnan(embeddings).any():
        print("   ⚠️  警告: 发现 NaN 值")
    else:
        print("   ✅ 向量数据无 NaN")

    return True


async def upload_to_milvus(embeddings, ids, metadata, milvus_service):
    """批量上传向量到 Milvus"""
    total = len(embeddings)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n{'=' * 70}")
    print(f"🚀 开始上传到 Milvus")
    print(f"   总记录数: {total}")
    print(f"   批大小: {BATCH_SIZE}")
    print(f"   总批次: {num_batches}")
    print(f"{'=' * 70}\n")

    start_time = time.time()

    success_count = 0
    failed_count = 0

    pbar = tqdm(range(num_batches), desc="上传进度", unit="batch")

    for batch_idx in pbar:
        start_idx = batch_idx * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total)

        # 准备当前批次数据
        batch_embeddings = embeddings[start_idx:end_idx]
        batch_ids = ids[start_idx:end_idx]
        batch_metadata = metadata[start_idx:end_idx]

        # 构造向量列表
        vectors = []
        for i in range(len(batch_ids)):
            meta = batch_metadata[i].item() if hasattr(batch_metadata[i], 'item') else batch_metadata[i]
            vectors.append({
                "id": str(batch_ids[i]),
                "values": batch_embeddings[i].tolist(),
                "metadata": {
                    "content": "",
                    "department": str(meta.get('department', ''))[:256],
                    "title": str(meta.get('title', ''))[:1024],
                    "ask": str(meta.get('ask', ''))[:4096],
                    "answer": str(meta.get('answer', ''))[:4096],
                    "source": str(meta.get('source', ''))[:256],
                    "category": "",
                    "keywords": "",
                }
            })

        # 上传
        try:
            success = await milvus_service.upsert(vectors)
            if success:
                success_count += len(vectors)
                pbar.set_postfix({
                    "成功": f"{success_count}/{total}",
                    "失败": failed_count
                })
            else:
                failed_count += len(vectors)
                print(f"   ❌ 批次 {batch_idx} 上传失败")

        except MilvusException as e:
            # 内存不足时自动拆半重试
            if "Cannot allocate memory" in str(e) and len(vectors) > 10:
                print(f"   ⚠️  批次 {batch_idx} 内存不足，拆分为子批次重试...")
                half = len(vectors) // 2
                for sub_start in range(0, len(vectors), half):
                    sub_vec = vectors[sub_start:sub_start + half]
                    try:
                        sub_ok = await milvus_service.upsert(sub_vec)
                        if sub_ok:
                            success_count += len(sub_vec)
                        else:
                            failed_count += len(sub_vec)
                    except Exception:
                        failed_count += len(sub_vec)
                pbar.set_postfix({
                    "成功": f"{success_count}/{total}",
                    "失败": failed_count
                })
            else:
                failed_count += len(vectors)
                print(f"   ❌ 批次 {batch_idx} 异常: {e}")

        except Exception as e:
            failed_count += len(vectors)
            print(f"   ❌ 批次 {batch_idx} 异常: {e}")

    pbar.close()

    total_time = time.time() - start_time

    print(f"\n{'=' * 70}")
    print(f"🎉 上传完成!")
    print(f"{'=' * 70}")
    print(f"   成功: {success_count}")
    print(f"   失败: {failed_count}")
    print(f"   总耗时: {str(timedelta(seconds=int(total_time)))}")
    print(f"   平均速度: {total / total_time:.1f} 条/秒")
    print(f"{'=' * 70}")

    return success_count


async def verify_milvus(milvus_service):
    """验证 Milvus 中的数据"""
    print("\n🔍 验证 Milvus 数据...")

    stats = await milvus_service.describe_index()
    print(f"   Milvus 向量总数: {stats.get('total_vector_count')}")

    # 尝试搜索
    print("\n   测试查询...")
    # 生成随机向量测试
    import numpy as np
    random_vector = np.random.randn(1024).astype(np.float32).tolist()
    results = await milvus_service.query(random_vector, top_k=3)

    if results:
        print(f"   ✅ 查询成功，返回 {len(results)} 条结果")
        for i, r in enumerate(results):
            print(f"   结果 {i+1}: ID={r['id']}, score={r['score']:.4f}, title={r['metadata']['title']}")
    else:
        print(f"   ⚠️  查询未返回结果")

    return True


async def main():
    print("=" * 70)
    print("🌟 上传 Embedding 到 Milvus")
    print("=" * 70)

    # 1. 加载数据
    embeddings, ids, metadata = load_embedding_data()

    # 2. 验证数据
    verify_data(embeddings, ids, metadata)

    # 3. 初始化 Milvus
    print("\n🔗 连接 Milvus...")
    milvus_service = MilvusService()
    # 检查向量维度
    dim = embeddings.shape[1]
    success = await milvus_service.initialize(dim=dim)

    if not success:
        print("❌ Milvus 连接失败！")
        print("\n请先启动 Milvus 服务:")
        print("   docker-compose -f docker-compose.milvus.yml up -d")
        return 1

    print("   ✅ Milvus 连接成功")

    # 4. 上传数据
    stats = await milvus_service.describe_index()
    if stats.get('total_vector_count', 0) > 0:
        print(f"\n⚠️  Milvus 中已有 {stats['total_vector_count']} 条向量")
        response = input("   继续上传会追加数据，是否继续? (y/n): ")
        if response.lower() != 'y':
            print("   已取消")
            milvus_service.close()
            return 0

    await upload_to_milvus(embeddings, ids, metadata, milvus_service)

    # 5. 验证
    await verify_milvus(milvus_service)

    milvus_service.close()
    print("\n✅ 全部完成!")

    return 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))