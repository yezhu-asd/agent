"""
快速测试 Milvus 连接和向量数据
"""

import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

import asyncio


async def test_milvus_connection():
    """测试 Milvus 连接"""
    print("=" * 70)
    print("   Milvus 连接测试")
    print("=" * 70)

    try:
        from services.milvus_service import MilvusService

        print("\n[1/4] 初始化 Milvus 服务...")
        milvus = MilvusService()
        success = await milvus.initialize(dim=1024)

        if not success:
            print("   [FAIL] Milvus 连接失败")
            print("\n请检查:")
            print("   1. Milvus 服务是否已启动")
            print("   2. .env 中 MILVUS_URI 配置是否正确")
            print("   3. 端口 19530 是否可访问")
            return False

        print("   [OK] Milvus 连接成功")

        print("\n[2/4] 获取集合统计...")
        stats = await milvus.describe_index()
        print(f"   集合名称: {stats.get('collection_name')}")
        print(f"   向量总数: {stats.get('total_vector_count')}")

        if stats.get('total_vector_count', 0) == 0:
            print("\n   [WARN] Milvus 中没有向量数据")
            print("   请运行: cd embedding && python upload_to_milvus.py")
        else:
            print("   [OK] 向量数据已存在")

        print("\n[3/4] 测试搜索...")
        import numpy as np
        random_vec = np.random.randn(1024).tolist()
        results = await milvus.query(random_vec, top_k=3)

        if results:
            print(f"   [OK] 搜索成功，返回 {len(results)} 条结果")
            for i, r in enumerate(results):
                print(f"   结果 {i+1}:")
                print(f"      ID: {r['id']}")
                print(f"      分数: {r['score']:.4f}")
                title = r['metadata'].get('title', '')[:50]
                print(f"      标题: {title}")
        else:
            print("   [WARN] 搜索未返回结果")

        print("\n[4/4] 关闭连接...")
        milvus.close()
        print("   [OK] 连接已关闭")

        print("\n" + "=" * 70)
        print("   测试完成!")
        print("=" * 70)

        return True

    except ImportError as e:
        print(f"   [FAIL] 导入失败: {e}")
        print("\n请安装依赖: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"   [FAIL] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_milvus_connection())
    sys.exit(0 if success else 1)