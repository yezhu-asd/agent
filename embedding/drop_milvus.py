"""
清空 Milvus 集合（删除后数据无法恢复）
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()


def drop_collection():
    """删除 Milvus 集合"""
    print("=" * 70)
    print("   清空 Milvus 集合")
    print("=" * 70)

    confirm = input("\n⚠️  此操作会删除所有向量数据，是否继续？(yes/no): ")
    if confirm.lower() != 'yes':
        print("已取消")
        return False

    try:
        from pymilvus import connections, utility

        uri = "http://localhost:19530"
        collection_name = "campus_medical_knowledge"

        print(f"\n[1/3] 连接 Milvus: {uri}")
        connections.connect(uri=uri)
        print("   ✅ 连接成功")

        print(f"\n[2/3] 检查集合: {collection_name}")
        if utility.has_collection(collection_name):
            print(f"   集合存在，准备删除...")
            utility.drop_collection(collection_name)
            print("   ✅ 集合已删除")
        else:
            print("   集合不存在，无需删除")

        print("\n[3/3] 断开连接")
        connections.disconnect("default")
        print("   ✅ 已断开")

        print("\n" + "=" * 70)
        print("   Milvus 已清空！")
        print("   请运行: python upload_embeddings.py 重新上传")
        print("=" * 70)
        return True

    except Exception as e:
        print(f"\n❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = drop_collection()
    sys.exit(0 if success else 1)
