# 多用户登录与无状态 Agent + 智能预约系统完整架构方案

## 1. 项目目标

本方案基于当前 Smart Appointment AI Agent 项目进行完整升级，融合：

- 原有 README 中的多 Agent、RAG、预约调度、行为分析等系统设计
- 多用户登录方案中的 Redis 会话、UUID Token、无状态 Agent、多用户隔离等核心架构

最终形成一套：

- 支持多用户登录
- 支持高并发会话隔离
- 支持无状态 Agent
- 支持 RAG 知识问答
- 支持智能预约调度
- 支持用户行为分析
- 支持 Redis 会话管理
- 支持向量检索与混合检索
- 支持未来生产化扩展

的完整 AI Agent 工程化方案。

---

# 2. 系统定位

Smart Appointment AI Agent 是一个面向服务行业的智能预约与咨询系统。

系统核心目标并不是简单实现预约表单，而是模拟真实前台业务流程：

- 理解用户意图
- 判断用户是在咨询还是预约
- 自动匹配服务人员
- 自动管理会话状态
- 自动维护上下文记忆
- 自动生成个性化推荐
- 自动完成预约流程

项目采用：

- FastAPI
- LangChain
- Redis
- FAISS / Pinecone
- SQLite / MySQL
- 多 Agent 架构
- 无状态 Agent 设计

实现完整 AI Agent 工程化方案。

---

# 3. 核心能力

## 3.1 智能任务分类

系统自动识别用户属于：

- 预约任务
- 咨询任务
- 其他任务

并路由到对应 Agent。

当前任务分类：

- `appointment`
- `query`
- `other`

后续可扩展：

- pay
- statistics
- crm
- recommendation

---

## 3.2 多 Agent 协作

系统采用多 Agent 架构：

| Agent | 职责 |
|---|---|
| TaskClassificationAgent | 意图识别与主路由 |
| ConsultantAgent | RAG 咨询与知识问答 |
| AppointmentAgent | 智能预约与排班 |
| UserBehaviorAgent | 用户行为分析与推荐 |

每个 Agent 仅负责自己的职责。

---

## 3.3 RAG 知识问答

系统支持：

- Embedding
- 向量检索
- 混合检索
- 重排
- Prompt 构建
- 流式回答

知识问答链路：

```text
用户问题
    ↓
任务分类
    ↓
关键词检索 + 向量检索
    ↓
RRF 融合
    ↓
Jina-Reranker 重排
    ↓
Prompt 构建
    ↓
LLM 回答
```

---

## 3.4 智能预约管理

预约 Agent 支持：

- 预约信息抽取
- 咨询师匹配
- 时间冲突检查
- 多轮补全
- 自动确认
- 个性化提醒

支持结构化槽位记忆。

---

## 3.5 多用户登录与会话管理

系统支持：

- 手机号 + 验证码登录
- UUID Token
- Redis 登录态
- 会话隔离
- 多用户并发
- 会话串行控制
- 无状态 Agent

---

## 3.6 用户行为分析

系统支持：

- 用户偏好分析
- 行为记录
- 推荐逻辑
- 主动提醒
- 历史行为建模

---

## 3.7 短期记忆与上下文管理

支持：

- 咨询上下文记忆
- 预约槽位记忆
- 摘要压缩记忆
- Redis 消息缓冲区
- 长对话摘要压缩

---

# 4. 总体架构

## 4.1 五层架构

系统采用严格五层架构：

```text
Web & Application Layer
    ↓
API Layer
    ↓
Agents Layer
    ↓
Services Layer
    ↓
DB Layer
```

---

## 4.2 各层职责

### Web & Application Layer

负责：

- Web 页面
- 前端入口
- 系统启动
- 静态资源

对应目录：

```text
app.py
web/
```

---

### API Layer

负责：

- API 接口
- 请求编排
- Token 鉴权
- 请求路由
- 响应封装

对应目录：

```text
api/
```

---

### Agents Layer

负责：

- 多 Agent 协作
- 任务分类
- 对话流程
- Prompt 调度
- 状态路由

对应目录：

```text
agents/
```

---

### Services Layer

负责：

- 业务逻辑
- 推荐算法
- 向量处理
- Embedding
- 会话管理

对应目录：

```text
services/
```

---

### DB Layer

负责：

- 数据持久化
- Repository
- 数据模型
- Redis
- MySQL

对应目录：

```text
db/
```

---

## 4.3 调用规则

允许：

- Web → API
- API → Agents / Services
- Agents → Services
- Services → DB

禁止：

- 下层调用上层
- Agent 直接访问 DB
- Web 直接访问 DB
- Service 调用 Agent

---

# 5. 多用户登录方案

## 5.1 登录流程

采用：

- 手机号 + 验证码
- UUID Token
- Redis 登录态

完整流程：

```text
用户输入手机号
    ↓
发送验证码
    ↓
Redis 保存验证码
    ↓
用户输入验证码
    ↓
后端校验
    ↓
生成 UUID Token
    ↓
Redis 保存 Token
    ↓
前端携带 Token 请求
```

---

## 5.2 Token 方案

采用 UUID Token，而不是 JWT。

原因：

- 实现简单
- 服务端可控
- 易于强制下线
- 易于多端管理
- 易于黑名单控制

Redis Key：

```text
auth:token:{token}
```

示例：

```json
{
  "userId": 10001,
  "phone": "138xxxxxx",
  "conversationId": "conv_xxx"
}
```

---

## 5.3 API 鉴权流程

```text
请求进入 API
    ↓
读取 Header Token
    ↓
查询 Redis
    ↓
校验登录态
    ↓
定位 conversationId
    ↓
进入 Agent 流程
```

---

# 6. Redis 数据设计

Redis 统一管理：

- 登录态
- 会话状态
- 会话历史
- 会话锁
- 消息缓冲区
- 咨询师排班时间
- 短期记忆

---

## 6.1 Redis Key 设计

| 类型 | Redis Key |
|---|---|
| 验证码 | `login:code:{phone}` |
| Token | `auth:token:{token}` |
| 会话状态 | `conversation:{id}:state` |
| 会话历史 | `conversation:{id}:history` |
| 会话锁 | `conversation:{id}:lock` |
| 咨询记忆 | `conversation:consult:{id}:consult_memory`  key-field-value:id-agent-memory |
| 预约记忆 | `conversation:appointment：{id}:appointment_memory` 每个agent有独立的memory |
| 分类记忆 | `conversation:classification：{id}:classification_memory` |
| 会话历史 | `conversation:{id}:history_memory` 全量会话历史，用于备份，检查等 |
| 摘要记忆 | `conversation:{id}:memory_summary`全量会话历史的摘要 |
| 消息缓冲区 | `conversation:{id}:message_queue` |
| 咨询师忙碌时间 | `technician:{id}:busy_periods` |

---

# 7. 无状态 Agent 架构

## 7.1 核心原则

Agent 不保存长期上下文。

所有状态统一存储于：

- Redis
- 数据库

Agent 仅负责：

- 当前请求处理
- Prompt 编排
- 状态流转
- 结果生成

---

## 7.2 无状态设计收益

### 支持多用户并发

避免：

- 全局 session
- 全局共享状态
- 用户串会话

---

### 支持水平扩容

支持：

- Docker
- Kubernetes
- 多实例部署

---

### 提高稳定性

即使单实例重启：

- 会话状态不丢失
- 登录态不丢失
- 上下文不丢失

---

# 8. 会话管理方案

## 8.1 conversationId

每个会话独立 conversationId。

作用：

- 隔离用户上下文
- 隔离消息历史
- 隔离状态

---

## 8.2 会话串行控制

同一会话：

- 串行处理：

  slot更新冲突：如果两个请求并发执行，可能同时读取旧 slot，分别更新不同字段，最后后写覆盖前写；

  重复追问：Agent 正准备追问具体信息，但是实际是用户已经自行补充，如果没有串行控制，系统仍然会继续，用户重复回答，对话体验变差追问；

  状态机错乱：当前请求把状态置为分类，但是后续请求又把状态置为预约，导致状态错乱；

不同会话：

- 并行处理

实现方式：

```text
conversation:{id}:lock
```

支持：

- asyncio.Lock
- Redis 分布式锁

---

## 8.3 消息缓冲机制

解决：

- 用户补充信息时重复追问
- 状态竞态
- 多请求并发问题

流程：

```text
用户消息进入
    ↓
写入消息缓冲区
    ↓
更新 message_version
    ↓
系统准备追问前
    ↓
检查是否有新消息
    ↓
如有则重新解析
```

---

# 9. 状态机设计

## 9.1 主状态

仅保留：

| 状态 | 作用 |
|---|---|
| CLASSIFY | 分类阶段 |
| CONSULT | 咨询阶段 |
| APPOINTMENT | 预约阶段 |

---

## 9.2 辅助状态

辅助状态采用布尔字段：

```json
{
  "awaiting_confirmation": true,
  "waiting_for_phone_code": false,
  "login_verified": true,
  "finished": false
}
```

---

## 9.3 状态流转

```text
CLASSIFY
    ↓
CONSULT / APPOINTMENT
    ↓
finished = true
    ↓
重新回到 CLASSIFY
```

---

# 10. 短期记忆与结构化状态设计

## 10.1 当前架构升级方向

当前项目原有方案更偏向：

```text
history + prompt 驱动
```

即：

- Agent 依赖完整聊天历史
- LLM 自行理解上下文
- 每轮重新推断缺失信息

该方案在 Demo 阶段可行，但在多用户、高并发、长对话场景下会逐渐暴露问题：

- Prompt 长度膨胀
- Token 成本越来越高
- 不同 Agent 上下文污染
- LLM 容易遗漏历史信息
- 多轮预约流程容易重复追问
- 会话越长稳定性越差

因此系统需要升级为：

```text
结构化状态驱动 + 槽位记忆 + 少量上下文
```

即：

```text
State
+
Slot Memory
+
Summary Memory
+
Recent Messages
```

共同驱动 Agent。

这也是当前生产级 Agent 系统更主流的架构方向。

---

## 10.2 主历史与 Agent 局部记忆拆分

系统不建议所有 Agent 共用同一份完整 history。

推荐采用：

```text
一份主历史 + 多份 Agent 工作记忆
```

结构如下：

```text
全局会话
│
├── 主消息历史
├── Consultant Memory
├── Appointment Slot Memory
├── User Behavior Memory
└── Summary Memory
```

---

## 10.3 主历史（Main History）

主历史只保存：

- 用户原始输入
- 系统最终回复

示例：

```json
[
  {
    "role": "user",
    "content": "我想预约明天下午"
  },
  {
    "role": "assistant",
    "content": "请问您想预约什么项目？"
  }
]
```

作用：

- 对话审计
- 会话回放
- 长期总结
- 用户行为分析
- 后续摘要压缩

但不建议：

```text
直接把全部历史塞进 LLM Prompt
```

---

## 10.4 Consultant Memory

ConsultantAgent 使用独立咨询记忆。

保存：

- 当前咨询主题
- 最近知识命中
- 用户情绪
- 当前咨询摘要

示例：

```json
{
  "current_topic": "睡眠问题",
  "recent_knowledge_ids": [12, 18],
  "emotion": "anxious",
  "summary": "用户最近在咨询失眠问题"
}
```

Redis Key：

```text
conversation:{conversationId}:consult_memory
```

作用：

- 保持咨询连续性
- 提升 RAG 召回质量
- 避免预约 Agent 被咨询内容污染

---

## 10.5 Appointment Slot Memory（预约槽位记忆）

预约槽位记忆是预约 Agent 的核心状态。

本质：

```text
LLM 提取出的结构化预约信息
```

例如用户：

```text
我想明天下午找个女咨询师心理咨询
```

系统抽取：

```json
{
  "date": "2026-05-24",
  "time_period": "afternoon",
  "project": "心理咨询",
  "gender_preference": "female"
}
```

这些结构化字段即为：

```text
slot（槽位）
```

Redis Key：

```text
conversation:{conversationId}:appointment_slots
```

---

## 10.6 为什么必须引入槽位记忆

真实预约流程中：

用户不会一次性说完所有信息。

例如：

```text
用户：我想预约一下
系统：请问什么时候？
用户：明天下午
系统：想做什么项目？
用户：情感咨询
系统：对咨询师有要求吗？
用户：女咨询师
```

信息是：

```text
多轮逐步补全
```

因此系统必须支持：

```text
Slot Filling（槽位填充）
```

即：

- 每轮抽取新增信息
- 更新结构化槽位
- 判断缺失字段
- 决定下一步追问

而不是每轮重新让 LLM 理解全部历史。

---

## 10.7 槽位记忆的核心作用

### 避免信息丢失

例如系统不会忘记：

```text
用户之前已经指定女咨询师
```

---

### 避免重复追问

不会反复问：

```text
请问预约时间？
```

---

### 控制 Prompt 长度

无需不断重复全部历史。

---

### 支撑状态机流程

系统真正驱动预约流程的并不是 history。

而是：

```text
slot state
```

例如：

```json
{
  "date": true,
  "project": true,
  "technician": false
}
```

系统即可判断：

```text
下一步应该询问咨询师偏好
```

---

## 10.8 AppointmentAgent 架构升级

当前项目原有结构更偏：

```text
history → LLM 理解 → 推断缺失信息
```

升级后建议改为：

```text
extract_slots()
    ↓
update_slot_memory()
    ↓
missing_slots()
    ↓
next_question()
```

即：

- 先抽取结构化信息
- 再更新 Redis 槽位状态
- 再判断缺失字段
- 再生成下一步问题

从：

```text
history 驱动
```

升级为：

```text
slot-driven architecture
```

---

## 10.9 Summary Memory（摘要压缩记忆）

长对话不能无限累积。

因此需要：

```text
summary memory
```

用于：

- 压缩长历史
- 控制 Prompt 长度
- 保持长期上下文连续性

Redis Key：

```text
conversation:{conversationId}:memory_summary
```

示例：

```json
{
  "summary": "用户最近连续咨询睡眠问题，并尝试预约心理咨询。"
}
```

---

## 10.10 User Behavior Memory

用户行为 Agent 使用独立行为记忆。

保存：

- 用户偏好
- 常用项目
- 常用时间段
- 历史预约倾向
- 推荐特征

Redis Key：

```text
conversation:{conversationId}:behavior_memory
```

---

## 10.11 推荐的最终记忆结构

最终推荐：

```text
Redis
│
├── history
├── consult_memory
├── appointment_slots
├── summary_memory
├── behavior_memory
└── state
```

---

## 10.12 当前项目最推荐的演进路线

### 第一步（必须）

增加：

```text
appointment_slots
```

Redis Key：

```text
conversation:{conversationId}:appointment_slots
```

---

### 第二步

把 AppointmentAgent 升级为：

```text
slot-filling architecture
```

即：

```text
extract_slots()
missing_slots()
next_question()
```

---

### 第三步

增加：

```text
summary_memory
```

---

### 第四步

后续可继续演进为：

- LangGraph
- Workflow Engine
- Agent Runtime
- 多 Agent 工作流编排

---

# 11. RAG 与混合检索方案

## 11.1 检索架构

采用：

- BM25
- 向量检索
- RRF
- Jina-Reranker

完整链路：

```text
用户问题
    ↓
BM25 检索
    ↓
向量检索
    ↓
RRF 融合
    ↓
Jina-Reranker
    ↓
Top-K 上下文
    ↓
LLM 回答
```

---

## 11.2 存储分层

### MySQL

保存：

- 文档元数据
- 分类
- 标签
- 时间

---

### Pinecone

保存：

- Embedding 向量
- 相似度索引

---

# 12. 技术栈

## 后端

- FastAPI
- Uvicorn
- SQLAlchemy

---

## AI

- LangChain
- OpenAI Compatible API
- Qwen
- DeepSeek
- Zhipu
- Azure OpenAI

---

## 向量检索

- Pinecone

---

## 数据库

- Redis
- MySQL

---

## 前端

- Jinja2
- HTML
- CSS

---

## 工具

- python-dotenv
- schedule

---

# 13. 项目目录结构

```text
Smart appointment AI agent/
├── agents/
├── api/
├── services/
├── db/
├── config/
├── web/
├── data/
├── tests/
├── app.py
├── requirements.txt
└── README.md
```

---

# 14. 请求链路

完整请求流程：

```text
用户登录
    ↓
获取 UUID Token
    ↓
携带 Token 请求
    ↓
API 鉴权
    ↓
定位 conversationId
    ↓
读取 Redis 状态
    ↓
读取短期记忆
    ↓
TaskClassificationAgent
    ↓
路由到对应 Agent
    ↓
执行业务
    ↓
写回 Redis
    ↓
返回结果
```
