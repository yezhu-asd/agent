# Smart Appointment AI Agent (Campus Medical Edition)

本项目是一个面向校园医务室场景的多 Agent 智能问诊预约系统。系统基于 FastAPI + LangChain + RAG 构建，支持 Token 登录、会话隔离、症状问诊、风险识别、医生值班预约与健康知识问答。

## 快速部署 Milvus 向量数据库

本项目支持本地 Milvus 向量数据库，内置 107万条医学问答向量数据。快速部署步骤：

```bash
# 1. 启动 Milvus 服务
docker-compose -f milvus/docker-compose.milvus.yml up -d

# 2. 等待 30 秒后，上传向量数据
cd embedding
python upload_to_milvus.py
cd ..

# 3. 配置并启动应用
cp .env.example .env
# 编辑 .env，设置 VECTOR_DB_TYPE=milvus
pip install -r requirements.txt
python -m uvicorn app:app --reload
```

**注意：** 首次启动若 Milvus 连接失败（如 `Fail connecting to server on localhost:19530`），可能是 etcd 尚未就绪 Milvus 就尝试连接了。执行 `docker restart milvus-standalone` 后等待 10 秒即可。

**详细文档：** [milvus/MILVUS_DEPLOYMENT.md](milvus/MILVUS_DEPLOYMENT.md)

## 1. 项目定位

系统目标不是替代医生，而是作为校医室的智能前置辅助入口，帮助完成：

- 登录与会话隔离
- 症状收集与追问
- 初步风险识别与红旗症状升级
- 医生预约与排班匹配
- 健康知识检索问答
- 健康追踪与复诊提醒

## 2. 核心能力

- 医学任务分类：自动区分 doctor / appointment / faq / emergency / chat。
- 多 Agent 协作：分类 Agent 协调问诊 Agent 与预约 Agent。
- RAG 健康问答：知识检索 + 模型生成，支持流式输出。
- 风险优先策略：红旗症状优先升级，避免输出绝对否定性医疗结论。
- Token 认证：Bearer Token 鉴权，支持多用户并发会话隔离。
- 医生排班预约：医生可用性查询、时段分配、预约确认。
- 健康追踪：记录问诊记录，支持后续复诊建议。

## 3. 架构分层

```text
Web Layer
  web/routes.py, web/templates/
API Layer
  api/*.py
Agents Layer
  agents/*.py
Services Layer
  services/*.py
DB Layer
  db/*.py
```

调用方向：

- Web -> API
- API -> Agents / Services
- Agents -> Services
- Services -> DB

禁止下层反向依赖上层。

## 4. 关键模块

- [app.py](app.py)：应用入口、路由挂载、启动初始化、健康检查。
- [api/auth.py](api/auth.py)：验证码登录、Token 获取、会话查询、退出登录。
- [api/chat_handler.py](api/chat_handler.py)：流式聊天入口。
- [agents/task_classification_agent.py](agents/task_classification_agent.py)：任务分类与路由。
- [agents/consultant_agent.py](agents/consultant_agent.py)：医生问诊流程控制。
- [agents/appointment_agent.py](agents/appointment_agent.py)：预约流程控制。
- [db/models.py](db/models.py)：Doctor、ConsultationRecord、RiskEvent 等核心模型。

## 5. 项目结构

```text
smart-appointment-ai-agent/
├── app.py
├── README.md
├── requirements.txt
├── agents/
├── api/
├── services/
├── db/
├── config/
├── web/
├── data/
└── tests/
```

## 6. 环境准备

### 6.1 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 6.2 安装依赖

```powershell
pip install -r requirements.txt
```


#### 6.4.1 启动 Milvus 服务

直接使用 Docker Compose:**
```bash
docker-compose -f milvus/docker-compose.milvus.yml up -d
```

Milvus 服务包含：
- Milvus Standalone: 核心向量数据库 (端口 19530)
- etcd: 元数据存储
- MinIO: 对象存储
- Attu: Milvus 图形化管理界面 (http://localhost:8080)

#### 6.4.2 上传医学向量数据

确保 `embedding/embedding_merged/` 目录下有向量数据文件，然后运行：

```bash
cd embedding
python upload_to_milvus.py
cd ..
```

该脚本会上传约 107万条医学问答向量到 Milvus，预计耗时 5-15 分钟。

#### 6.4.3 配置应用使用 Milvus

在 `.env` 文件中设置：

```env
VECTOR_DB_TYPE=milvus
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION_NAME=campus_medical_knowledge
```

#### 6.4.4 测试 Milvus 连接

```bash
python E:\wu\xidian\就业\java\agent项目\smart-appointment-ai-agent-master\milvus\test_milvus.py
```

#### 6.4.5 停止/清理 Milvus

```bash
# 停止服务
docker-compose -f docker-compose.milvus.yml stop

# 完全删除（包括数据）
docker-compose -f docker-compose.milvus.yml down -v
rm -rf milvus_data/
```
# 重启 重启 Milvus 只用 docker-compose down（不带 -v），否则数据会被清空
cd milvus
docker-compose -f docker-compose.milvus.yml down 
docker-compose -f docker-compose.milvus.yml up -d

#### 详细文档：[milvus/MILVUS_DEPLOYMENT.md](milvus/MILVUS_DEPLOYMENT.md)

## 8. 启动与访问

### 8.1 启动服务

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

### 8.2 访问地址

- Web 首页：http://127.0.0.1:8001/
- 登录页：http://127.0.0.1:8001/login
- 健康检查：http://127.0.0.1:8001/health
- Swagger：http://127.0.0.1:8001/docs
- ReDoc：http://127.0.0.1:8001/redoc
- Milvus 管理界面：http://localhost:8080

## 9. 认证流程

1. `POST /api/auth/code` 获取验证码
2. `POST /api/auth/login` 换取 Token
3. 前端保存 Token
4. 调用聊天接口时携带 `Authorization: Bearer <token>`
5. `POST /api/auth/logout` 退出登录

## 10. 前端页面

- [web/templates/login.html](web/templates/login.html)：登录页
- [web/templates/index.html](web/templates/index.html)：问诊聊天主页
- [web/templates/technician.html](web/templates/technician.html)：医生状态页
- [web/templates/technician_schedule.html](web/templates/technician_schedule.html)：医生值班页
- [web/templates/knowledge_management.html](web/templates/knowledge_management.html)：健康知识管理
- [web/templates/user_behavior_analysis.html](web/templates/user_behavior_analysis.html)：问诊历史与健康追踪

## 11. 测试

运行全部测试：

```powershell
python -m pytest -v --tb=short
```

运行 Token 集成测试：

```powershell
python -m pytest tests/test_token_integration.py -v --tb=short
```

## 12. 医疗安全约束

- 系统只做辅助建议，不做最终医疗诊断。
- 出现高风险症状应优先提示尽快就医或急救。
- 不输出“无需预约”等绝对排除性结论。

## 13. 版本说明

当前版本：`2.1.0-milvus`

- 完成本地 Milvus 向量数据库集成
- 支持 107万条医学问答向量检索
- 完成 Pinecone → Milvus 配置切换
- 版本 `2.0.0-medical` 功能：
  - 完成校园医务室语义迁移
  - 完成 Token 登录与会话并发隔离
  - 完成前端页面医学化改造（持续优化中）
