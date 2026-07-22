"""
上传 Embedding 到 Milvus（pymilvus 直连版，不依赖 FAISS）
"""
import numpy as np
import time
import sys
import asyncio
from pathlib import Path
from datetime import timedelta
from tqdm import tqdm

from pymilvus import MilvusClient, DataType
from pymilvus.milvus_client.index import IndexParams

EMBEDDING_DIR = Path(__file__).parent / "embedding_merged"
BATCH_SIZE = 500
CHUNK_SIZE = 50
RETRY_LIMIT = 3
COLLECTION = "campus_medical_knowledge"
URI = "http://localhost:19530"

client = None


def load_embedding_data():
    print("\nLoading embedding data...")
    embeddings = np.load(EMBEDDING_DIR / "embeddings.npy")
    ids = np.load(EMBEDDING_DIR / "ids.npy", allow_pickle=True)
    metadata = np.load(EMBEDDING_DIR / "metadata.npy", allow_pickle=True)
    print(f"  embeddings: {embeddings.shape}, ids: {len(ids)}, meta: {len(metadata)}")
    return embeddings, ids, metadata


def truncate_text(text, max_chars):
    if not text:
        return ""
    safe_len = int(max_chars * 0.7)
    text = str(text)
    return text[:safe_len] if len(text) > safe_len else text


def build_row(idx, embeddings, ids, metadata):
    meta = metadata[idx].item() if hasattr(metadata[idx], 'item') else metadata[idx]
    return {
        "id": str(ids[idx]),
        "embedding": embeddings[idx].tolist(),
        "content": "",
        "department": truncate_text(meta.get('department', ''), 128),
        "title": truncate_text(meta.get('title', ''), 512),
        "ask": truncate_text(meta.get('ask', ''), 4096),
        "answer": truncate_text(meta.get('answer', ''), 65535),
        "source": truncate_text(meta.get('source', ''), 128),
        "category": "",
        "keywords": "",
        "sparse_embedding": {},  # BM25 Function 自动从 ask 字段生成
    }


def rebuild_collection(dim):
    """重建集合，含 BM25 Function + Sparse 向量字段"""
    global client
    cols = client.list_collections()
    if COLLECTION in cols:
        try:
            client.release_collection(COLLECTION)
        except Exception:
            pass
        client.drop_collection(COLLECTION)
        print("  Old collection dropped")

    from pymilvus.orm.schema import FieldSchema, CollectionSchema, Function, FunctionType
    fields = [
        FieldSchema("id", DataType.VARCHAR, is_primary=True, max_length=64),
        FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=dim),
        FieldSchema("content", DataType.VARCHAR, max_length=65535),
        FieldSchema("department", DataType.VARCHAR, max_length=128),
        FieldSchema("title", DataType.VARCHAR, max_length=512),
        FieldSchema("ask", DataType.VARCHAR, max_length=8192),
        FieldSchema("answer", DataType.VARCHAR, max_length=65535),
        FieldSchema("source", DataType.VARCHAR, max_length=128),
        FieldSchema("category", DataType.VARCHAR, max_length=64),
        FieldSchema("keywords", DataType.VARCHAR, max_length=512),
        FieldSchema("sparse_embedding", DataType.SPARSE_FLOAT_VECTOR, nullable=True),
    ]
    schema = CollectionSchema(fields,
        functions=[Function("ask_bm25", FunctionType.BM25, "ask", "sparse_embedding",
                            params={"bm25_k1": 1.5, "bm25_b": 0.75})],
        enable_dynamic_field=False)
    client.create_collection(collection_name=COLLECTION, schema=schema)
    print("  Collection created (with BM25 Function)")

    ip = IndexParams()
    ip.add_index(field_name="embedding", index_type="HNSW", metric_type="IP",
                 params={"M": 16, "efConstruction": 200})
    ip.add_index(field_name="sparse_embedding", index_type="SPARSE_INVERTED_INDEX",
                 metric_type="IP")
    client.create_index(COLLECTION, ip)
    print("  HNSW + SPARSE_INVERTED_INDEX created")
    client.load_collection(COLLECTION)


async def insert_batch(rows, retries=RETRY_LIMIT):
    """插入一批，返回成功数"""
    for attempt in range(retries):
        try:
            result = client.insert(COLLECTION, data=rows)
            insert_count = result.get("insert_count", 0) if isinstance(result, dict) else 0
            if insert_count >= len(rows) * 0.9:
                return len(rows)
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
            continue
    return 0


async def insert_indices(indices, embeddings, ids, metadata):
    """递归插入: 整批失败时二分拆分"""
    n = len(indices)
    if n == 0:
        return []
    rows = [build_row(i, embeddings, ids, metadata) for i in indices]
    ok = await insert_batch(rows)
    if ok >= n:
        return list(indices)
    if n == 1:
        return []
    # 二分
    mid = n // 2
    left_ok = await insert_indices(indices[:mid], embeddings, ids, metadata)
    right_ok = await insert_indices(indices[mid:], embeddings, ids, metadata)
    return left_ok + right_ok


async def main():
    global client
    client = MilvusClient(uri=URI)

    embeddings, ids, metadata = load_embedding_data()
    total = len(embeddings)

    print("\nRebuilding collection...")
    rebuild_collection(embeddings.shape[1])

    start_time = time.time()
    success_count = 0
    failed_count = 0
    indices = list(range(total))

    pbar = tqdm(range(0, total, BATCH_SIZE), desc="Upload", unit="batch")
    for batch_start in pbar:
        batch = indices[batch_start: batch_start + BATCH_SIZE]
        batch_ok = []
        for chunk_start in range(0, len(batch), CHUNK_SIZE):
            chunk = batch[chunk_start: chunk_start + CHUNK_SIZE]
            ok_ids = await insert_indices(chunk, embeddings, ids, metadata)
            batch_ok.extend(ok_ids)
        success_count += len(batch_ok)
        failed_count += len(batch) - len(batch_ok)
        elapsed = time.time() - start_time
        pbar.set_postfix(ok=success_count, fail=failed_count,
                         rate=f"{success_count/max(elapsed,1):.0f}/s")

    pbar.close()
    elapsed = time.time() - start_time

    print(f"\n--- Upload done ---")
    print(f"  Success: {success_count} / {total}")
    print(f"  Failed:  {failed_count}")
    print(f"  Time:    {timedelta(seconds=int(elapsed))}")

    stats = client.get_collection_stats(COLLECTION)
    final_count = stats.get('row_count', 0)
    print(f"\nMilvus final row count: {final_count}")

    client.close()
    return 0 if success_count >= total * 0.99 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
