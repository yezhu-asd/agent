# Milvus 部署指南

本文档说明如何部署本地 Milvus 向量数据库，上传 107万条医学问答向量数据，并将校园医务室项目配置为使用 Milvus。

## 📋 前提条件

- Docker 和 Docker Compose 已安装
- Python 3.8+
- 足够的磁盘空间（embedding 数据约 5GB）

## 🚀 三步骤部署

### 第一步：部署本地 Milvus

#### 1.1 启动 Milvus 服务

项目根目录已有 `milvus/docker-compose.milvus.yml` 配置文件，执行：

```bash
# 启动 Milvus 及其依赖（etcd, minio）
docker-compose -f milvus/docker-compose.milvus.yml up -d

# 查看服务状态
docker-compose -f milvus/docker-compose.milvus.yml ps
```

#### 1.2 访问图形化界面（可选）

- Milvus 管理界面 (Attu): http://localhost:8000
- Milvus gRPC 端口: 19530
- Milvus HTTP 端口: 9091

#### 1.3 验证 Milvus 服务

等待约 30 秒，访问 http://localhost:8000 能看到 Attu 界面即表示成功。

> **首次启动提示：** 若 Milvus 连不上，执行 `docker restart milvus-standalone` 后等待 10 秒即可。这是因为 `depends_on` 默认只保证容器已启动、不保证 etcd 已就绪，Milvus 可能会在 etcd 完全启动前尝试连接。

---

### 第二步：上传向量数据

#### 2.1 安装依赖

```bash
# 确保虚拟环境已激活
pip install -r requirements.txt
```

#### 2.2 配置环境变量

复制 `.env.example` 为 `.env`，确保 Milvus 配置正确：

```env
# 向量数据库类型
VECTOR_DB_TYPE=milvus

# Milvus 配置
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_NAME=campus_medical_knowledge
```

#### 2.3 上传向量到 Milvus

```bash
cd embedding
python upload_to_milvus.py
```

这个脚本会：
1. 加载 `embedding/embedding_merged/` 目录下的向量数据
2. 连接到 Milvus
3. 创建集合（如果不存在）
4. 批量上传 107万条向量
5. 验证上传结果

**预计时间**：约 5-15 分钟，取决于硬件性能

---

### 第三步：配置项目使用 Milvus

这一步已经在代码中完成，现在 `KnowledgeService` 会自动检测配置并优先使用 Milvus。

确认以下内容：

1. `.env` 文件中 `VECTOR_DB_TYPE=milvus`
2. 已安装依赖：`pip install -r requirements.txt`（包括 `pymilvus>=2.4.0`）

启动应用后，日志会显示：
```
使用 Milvus 向量数据库
知识库服务初始化完成 (后端: milvus)
```

---

## 📂 文件说明

```
.
├── milvus/
│   ├── docker-compose.milvus.yml  # Milvus Docker Compose 配置
│   ├── start_milvus.bat          # Windows 启动脚本
│   ├── start_milvus.sh           # Linux/Mac 启动脚本
│   └── MILVUS_DEPLOYMENT.md      # 部署文档
├── embedding/
│   ├── embedding_merged/      # 合并后的向量数据
│   │   ├── embeddings.npy     # 向量数组 (107万 x 1024维)
│   │   ├── ids.npy            # ID 数组
│   │   └── metadata.npy       # 元数据数组
│   └── upload_to_milvus.py    # 上传脚本
└── services/
    ├── milvus_service.py      # Milvus 服务类
    └── knowledge_service.py   # 知识库服务（已支持 Milvus）
```

---

## 🔧 常用操作

### 查看 Milvus 服务日志

```bash
docker-compose -f milvus/docker-compose.milvus.yml logs -f milvus
```

### 停止 Milvus 服务

```bash
docker-compose -f milvus/docker-compose.milvus.yml stop
```

### 完全删除 Milvus 数据（谨慎！）

```bash
docker-compose -f milvus/docker-compose.milvus.yml down -v
# 数据存储在 ./milvus_data/ 目录，也可手动删除
```

### 验证向量数据

启动应用后，通过聊天测试医学知识问答是否正常工作。

也可以用 Attu 界面 (http://localhost:8080) 查看：
1. 连接到 `milvus:19530`
2. 选择 `campus_medical_knowledge` 集合
3. 查看向量统计

---

## 🚀 快速启动

如果所有配置已完成，一键启动流程：

```bash
# 1. 启动 Milvus
docker-compose -f milvus/docker-compose.milvus.yml up -d

# 2. 等待服务启动（约30秒）

# 3. 上传向量（首次运行）
cd embedding
python upload_to_milvus.py
cd ..

# 4. 启动应用
python -m uvicorn app:app --reload
```

---

## 💡 故障排查

### Milvus 无法连接
- 检查 Docker 容器是否运行：`docker ps`
- 查看 Milvus 日志：`docker logs milvus-standalone`
- 确认端口 19530 没有被占用
- **首次启动时**若 Milvus 报 `Fail connecting to server on localhost:19530`，通常是 etcd 尚末就绪 Milvus 就尝试连接了，执行 `docker restart milvus-standalone` 后等待 10 秒即可

### 向量上传失败
- 检查 `.env` 文件中 Milvus 配置
- 确保 embedding 数据文件完整（约 5GB）
- 检查磁盘空间是否足够

### 查询返回空结果
- 确认上传脚本成功完成
- 检查集合中向量数量（在 Attu 中查看）
- 查看应用日志中的错误信息

---

## 📊 数据统计

| 项目 | 数值 |
|------|------|
| 向量总数 | 1,070,000+ |
| 向量维度 | 1024 (BGE-M3) |
| 数据来源 | Chinese Medical Dialogue Dataset |
| 存储空间 | 约 5GB |
| 涵盖科室 | 多个科室（内科、外科、儿科等） |

---

## 🔄 回退到 FAISS 或 Pinecone

如果需要回退到其他向量数据库，修改 `.env`：

```env
# 使用 FAISS（本地索引，无额外依赖）
VECTOR_DB_TYPE=faiss

# 或使用 Pinecone
VECTOR_DB_TYPE=pinecone
PINECONE_API_KEY=your_key
```