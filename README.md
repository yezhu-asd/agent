#CampusCare_Agent

本项目是一个面向校园医务室场景的多 Agent 智能问诊预约系统。系统基于 FastAPI + LangChain + RAG 构建，支持 Token 登录、会话隔离、症状问诊、风险识别、医生值班预约与健康知识问答。

## 快速部署（Zilliz Cloud 向量数据库）

本项目使用 **Zilliz Cloud** 云托管向量数据库（Milvus 托管版），内置 100 万条医学问答向量数据（768 维，PCA 降维后）。无需本地安装 Docker Milvus。

### 快速启动步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建配置文件
cp .env.example .env
# 编辑 .env，填入你的 Zilliz Cloud 连接信息（URI / 用户名 / 密码）

# 3. 启动应用
python -m uvicorn app:app --reload
```

### 准备向量数据（首次使用）

向量数据需从网盘下载后解压到 `embedding/embedding_st/`（见 [13.3 大文件下载](#133-大文件下载与使用说明)），然后上传到 Zilliz Cloud：

```bash
cd embedding
python upload_embeddings.py
cd ..
```

上传完成后即可用于医学知识 RAG 检索。

> **注意**：查询时需保持 `EMBEDDING_PROVIDER=local`，确保查询向量和存储向量使用同一 BGE-M3 模型 + PCA 降维，否则检索结果不相关。

**本地 Docker Milvus 部署说明**（可选，已降级为附录）：[milvus/MILVUS_DEPLOYMENT.md](milvus/MILVUS_DEPLOYMENT.md)

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
CampusCare/
├── app.py
├── README.md
├── requirements.txt
├── agents/
├── api/
├── services/
├── db/
├── config/
├── web/
├── embedding/          # 向量数据与上传脚本
├── models/             # BGE-M3 模型权重（gitignore 排除）
├── milvus/             # 本地 Milvus 部署配置（可选）
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


#### 6.3 配置向量数据库（Zilliz Cloud）

本项目使用 **Zilliz Cloud**（Milvus 云托管版）存储医学向量。需先注册 Zilliz Cloud 获取连接信息。

##### 6.3.1 创建 Zilliz Cloud 集群

1. 访问 https://cloud.zilliz.com 注册登录
2. 创建集群（免费档 Sandbox 即可容纳 100 万条 768 维向量）
3. 在集群详情页的 **Connect** 中获取：
   - **Public Endpoint**（格式：`https://in03-xxx.serverless.ali-cn-hangzhou.cloud.zilliz.com.cn`）
   - **用户名 / 密码**（Token）

##### 6.3.2 配置 .env

```env
VECTOR_DB_TYPE=milvus
MILVUS_URI=https://in03-xxx.serverless.ali-cn-hangzhou.cloud.zilliz.com.cn
MILVUS_COLLECTION_NAME=campus_care_st
MILVUS_USER=你的Zilliz用户名
MILVUS_PASSWORD=你的Zilliz密码
```

> **注意**：`MILVUS_URI` 必须是 Zilliz Cloud 的 **Public Endpoint**（https），不是本地 `http://localhost:19530`。

##### 6.3.3 上传医学向量数据

确保 `embedding/embedding_st/` 目录下有向量数据文件（从网盘下载，见 [13.3](#133-大文件下载与使用说明)），然后运行：

```bash
cd embedding
python upload_embeddings.py
cd ..
```

该脚本会上传约 100万条医学问答向量到 Zilliz Cloud，预计耗时 1-2 小时。

##### 6.3.4 验证检索

运行相关性测试，确认查询能返回相关医学内容：

```bash
python embedding/test_relevance.py
```

##### 6.3.5 本地 Docker Milvus（可选）

如需本地自建 Milvus 而非使用云托管，见 [milvus/MILVUS_DEPLOYMENT.md](milvus/MILVUS_DEPLOYMENT.md)。注意本地 Milvus 资源有限，100 万条 768 维向量需要至少 16GB 内存。

## 7. 启动与访问

### 7.1 启动服务

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8001 --reload
```

### 7.2 访问地址

- Web 首页：http://127.0.0.1:8001/
- 登录页：http://127.0.0.1:8001/login
- 健康检查：http://127.0.0.1:8001/health
- Swagger：http://127.0.0.1:8001/docs
- ReDoc：http://127.0.0.1:8001/redoc

## 8. 认证流程

1. `POST /api/auth/code` 获取验证码
2. `POST /api/auth/login` 换取 Token
3. 前端保存 Token
4. 调用聊天接口时携带 `Authorization: Bearer <token>`
5. `POST /api/auth/logout` 退出登录

## 9. 前端页面

- [web/templates/login.html](web/templates/login.html)：登录页
- [web/templates/index.html](web/templates/index.html)：问诊聊天主页
- [web/templates/technician.html](web/templates/technician.html)：医生状态页
- [web/templates/technician_schedule.html](web/templates/technician_schedule.html)：医生值班页
- [web/templates/knowledge_management.html](web/templates/knowledge_management.html)：健康知识管理
- [web/templates/user_behavior_analysis.html](web/templates/user_behavior_analysis.html)：问诊历史与健康追踪

## 10. 测试

运行全部测试：

```powershell
python -m pytest -v --tb=short
```

运行 Token 集成测试：

```powershell
python -m pytest tests/test_token_integration.py -v --tb=short
```

## 11. 医疗安全约束

- 系统只做辅助建议，不做最终医疗诊断。
- 出现高风险症状应优先提示尽快就医或急救。
- 不输出“无需预约”等绝对排除性结论。

## 12. 版本说明

当前版本：`2.2.0-milvus`

### v2.2.0 功能更新

- **症状追问式诊断**：复杂症状（腹痛/头痛/胸痛等）启动结构化追问（最多 3 轮），基于已收集信息给出诊断可能性，再给建议；简单症状直接给建议
- **预约流程增强**：
  - 症状确认后**按症状智能推荐科室**（肚子疼→内科、牙疼→口腔科等），推荐结果跨请求保留
  - 追问/问诊任意阶段用户说"需要/不需要"均可流转到预约流程（全局状态切换 APPOINTMENT）
  - 预约必填时间：用户未明确时间时拒绝 LLM 编造的时间，强制询问
  - 预约信息解析接入 **GLM JSON Mode** 结构化输出，字段结构稳定、杜绝臆造科室/时间
- **红旗症状紧急处理**：
  - 弹窗不可一键关闭，提供"拨打 120"和"我已了解，立即就医"按钮
  - 确认后**强制进入紧急模式**，会话持续走急救引导，直到用户表示已就医
  - 风险事件写入 MySQL `risk_events` 表 + Redis 标记（双持久化）
- **医生值班/状态页**：
  - 忙闲状态改查 **MySQL 预约表**（重启不丢失）
  - 值班时间轴按半小时细分（8:00-18:00），整点显示时间标签
  - 预约成功后值班页显示忙碌时间段、状态页显示"忙碌（有预约）"
- **前端清新简约风重构**：薄荷绿医疗配色，替换原紫蓝高饱和渐变（聊天页/登录页/医生状态页/值班页统一）
- **系统修正**：移除登录页演示验证码泄露、清理过时测试脚本、修复 GBK 编码导致的服务启动崩溃

### 历史版本

- 向量数据库切换至 **Zilliz Cloud**（Milvus 云托管版）
- 向量数据重新生成：100万条，FlagEmbedding BGE-M3 → PCA 降维至 768 维（解释方差 0.9968）
- 检索链路：FlagEmbedding 查询向量 → PCA 降维 → Zilliz Milvus 检索 → RRF 融合（向量 + LIKE 关键词）
- 支持 100万条医学问答向量检索
- 版本 `2.0.0-medical` 功能：
  - 完成校园医务室语义迁移
  - 完成 Token 登录与会话并发隔离
  - 完成前端页面医学化改造

## 13. 推送到 GitHub

### 13.1 开始前准备

远程仓库已配置为：

```bash
git remote add origin https://github.com/yezhu-asd/agent.git
```

> 推荐使用 **HTTPS** 协议。SSH 在国内网络环境下经常连接被 reset（端口 22/443 被阻断），HTTPS 配合代理更稳定。

### 13.2 配置代理（必须）

国内直连 GitHub 不稳定，需要先设置代理。假设你的代理软件本地端口为 `7890`：

```bash
git config --global http.proxy  http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```

此配置为 **全局永久生效**，无需每次设置。查看当前代理：

```bash
git config --global --get http.proxy
git config --global --get https.proxy
```

> 如果换了代理端口，重新执行上面两条命令即可更新。想取消代理：
> ```bash
> git config --global --unset http.proxy
> git config --global --unset https.proxy
> ```

### 13.3 大文件下载与使用说明

以下文件体积过大，不放在 GitHub，请通过网盘下载后放到项目根目录。

#### 下载链接

| 文件 | 大小 | 说明 | 下载链接 |
|------|------|------|----------|
| `embedding_st.zip` | ~3.7 GB | 医学问答向量数据（100 万条，768 维，PCA 降维后），供 Zilliz Cloud 检索使用 | [百度网盘](https://pan.baidu.com/s/16lB_EP62HrcAyq7G3NDuPg?pwd=djgf) 提取码：`djgf` |
| `models.7z` | ~2.1 GB | BGE-M3 嵌入模型权重，供本地离线 embedding 使用 | [百度网盘](https://pan.baidu.com/s/1btG4FcYFbX-rrNVN04z_RQ?pwd=swew) 提取码：`swew` |

#### 下载后操作步骤

下载完成后，分别解压到对应目录：

**① embedding_st.zip — 向量数据**

解压后应得到 `embedding/embedding_st/` 目录，里面包含 4 个文件：
- `embeddings.npy` — 100 万条 768 维向量
- `ids.npy` — 向量 ID
- `metadata.npy` — 元数据
- `pca_model.pkl` — PCA 降维模型（查询时用）

```bash
# 解压后确认目录结构：
# embedding/embedding_st/
# ├── embeddings.npy   (约 2.9 GB)
# ├── ids.npy          (42 MB)
# ├── metadata.npy     (730 MB)
# └── pca_model.pkl    (6 MB)
```

**② models.7z — BGE-M3 模型权重**

解压后应得到 `models/bge-m3/` 目录。项目中的 embedding 代码会自动检测到该目录并使用本地模型，无需联网下载：

```bash
# 解压后确认目录结构如下：
# models/bge-m3/
# ├── config.json
# ├── tokenizer.json
# ├── pytorch_model.bin      (约 2GB)
# └── ...
```

> **注意**：解压路径需与 `.env` 中的 `LOCAL_EMBEDDING_MODEL` 一致（默认指向项目根目录的 `models/bge-m3/`）。

> **验证**：运行 `python services/text_embedding.py`，若输出 embedding 向量且无报错，说明模型加载成功。

#### 其他已排除的内容

- `.venv/`、`__pycache__/` — 虚拟环境，本地自动生成
- `.env` — 密钥等敏感信息，需自行创建（参考 `.env.example`，已提供模板）
- `models/bge-m3/` — 模型权重，从 models.7z 解压获得
- `embedding/embedding_st/` — 向量数据，从 embedding_st.zip 解压获得
- `embedding/embedding_merged/` — 原始未降维向量数据

如果之前不小心提交了大文件到 Git 历史，需要用 `git filter-repo` 清除：

```bash
pip install git-filter-repo
git filter-repo --invert --path models/
```

### 13.4 日常推送流程

```bash
# 1. 查看更改
git status

# 2. 添加所有更改
git add -A

# 3. 提交
git commit -m "本次更新的简要说明"

# 4. 推送到 GitHub
git push origin main
```

第一次推送时会出现登录框：
- 选择 **「Use a personal access token」**
- 令牌获取地址：https://github.com/settings/tokens → Generate new token (classic) → 勾选 `repo` 权限

### 13.5 第一次从零推送（完整流程）

```bash
# 初始化仓库
git init
git branch -M main

# 配置远程仓库（HTTPS）
git remote add origin https://github.com/你的用户名/仓库名.git

# 配置代理
git config --global http.proxy  http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 排除大文件（编辑 .gitignore，然后）
git add -A
git commit -m "Initial commit"
git push -u origin main
```

### 13.6 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| `Connection reset` / `Couldn't connect` | 未配置代理，连不上 GitHub | 设置 `http.proxy` 和 `https.proxy` |
| `HTTP 408` 超时 | 单次推送数据量过大（>100MB） | 用 `git filter-repo` 清除历史大文件 |
| `Permission denied (publickey)` | SSH 密钥未配置 | 改用 HTTPS，或配置 SSH 密钥 |
| `remote: Not Found` | GitHub 仓库不存在 | 先在 GitHub 网站上创建仓库 |
