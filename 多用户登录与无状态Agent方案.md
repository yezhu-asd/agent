# 多用户登录与无状态 Agent 完整方案

## 1. 目标

本方案面向当前按摩房智能预约系统的多用户改造，目标是：

- 支持手机号 + 验证码登录
- 使用 UUID 作为登录 token
- 登录态和会话态统一使用 Redis 管理
- Agent 尽量保持无状态，减少内存对象膨胀
- 支持多用户并发访问
- 保证同一会话内请求顺序一致，避免状态错乱

## 2. 业务执行流程总览

本方案建议按照“登录 -> 鉴权 -> 会话定位 -> 状态读取 -> Agent 路由 -> 业务执行 -> 状态回写 -> 响应返回”的顺序来组织整个系统。

### 2.1 端到端业务流程

1. 用户输入手机号并完成验证码登录
2. 后端校验验证码，生成 UUID token
3. 前端携带 token 发起后续业务请求
4. API 层先做 token 鉴权，定位当前用户和 conversationId
5. 从 Redis 读取当前会话状态、辅助状态和历史上下文
6. 根据主状态决定路由到分类、咨询或预约 Agent
7. Agent 根据辅助状态继续处理当前流程细节
8. 处理完成后把最新状态和历史回写 Redis
9. 返回结果给前端

### 2.2 各步骤对应模块

| 执行步骤 | 主要职责 | 对应模块 |
|---|---|---|
| 登录与验证码校验 | 验证手机号、发送和校验验证码 | 登录/认证模块、Redis |
| Token 校验 | 校验 UUID token 是否有效 | API 鉴权中间件 |
| 会话定位 | 根据 token 找到用户和 conversationId | 会话管理模块 |
| 状态读取 | 获取主状态和辅助状态 | StateManager、Redis |
| 请求路由 | 判断应该进入哪个 Agent | ClassificationProcessor、AgentRouter |
| 业务执行 | 执行咨询或预约任务 | ConsultantAgent、AppointmentAgent |
| 状态回写 | 保存最新状态、历史和流程标记 | 会话管理模块、Redis |
| 响应返回 | 返回最终结果到前端 | API 层 |

### 2.3 这个顺序的意义

- 先登录，保证身份可信
- 再鉴权，保证后续请求合法
- 再读取会话状态，保证流程连续
- 再按状态路由，避免业务混乱
- 最后回写状态，保证下一次请求还能继续

### 2.4 当前任务分类范围

当前任务分类只保留以下三类：

- `appointment`：预约任务
- `query`：咨询任务
- `other`：其他任务

`pay`、`statistics` 等类别当前不需要，后续如果业务范围变化，再补充扩展。

## 3. 登录与鉴权方案

### 3.1 登录方式

采用手机号 + 验证码登录流程：

1. 用户输入手机号
2. 后端生成验证码并发送
3. 验证码存储到 Redis，设置短 TTL
4. 用户输入验证码
5. 后端校验验证码
6. 校验通过后生成 UUID token
7. 将 token 与用户信息、会话信息存入 Redis
8. 前端保存 token，后续请求携带 token

### 3.2 验证码存储

验证码建议存储到 Redis，不建议存内存。

推荐键：

- `login:code:{phone}`

推荐 value：

```json
{
  "code": "123456",
  "retryCount": 0
}
```

建议设置 3~5 分钟过期时间。

### 3.3 Token 方案

本方案使用 UUID 作为不透明 token，而不是 JWT。

特点：

- token 本身不携带业务信息
- 服务端需要查询 Redis 获取登录态
- 实现简单
- 方便强制失效和退出登录

推荐键：

- `auth:token:{token}`

推荐 value：

```json
{
  "userId": 10001,
  "phone": "138xxxxxx",
  "conversationId": "conv_xxx",
  "expireAt": "2026-05-15T18:00:00"
}
```

### 3.4 鉴权校验

每次请求进入 API 层后，需要完成以下校验：

1. 从请求头中取出 token
2. 去 Redis 查询 `auth:token:{token}`
3. 查到则认为登录有效
4. 查不到则返回未登录或 token 失效

如果后续需要支持退出登录或强制失效，也可以把 token 的标识写入黑名单。

## 4. Redis 数据设计

Redis 统一存放验证码、登录 token、会话状态、会话历史、会话锁等数据。

### 4.1 Redis 数据清单

| 数据类型 | Redis Key | Value 示例 | 主要读写模块 |
|---|---|---|---|
| 登录验证码 | `login:code:{phone}` | `{"code":"123456","retryCount":0}` | 登录/认证模块、验证码校验模块 |
| 登录 token 映射 | `auth:token:{token}` | `{"userId":10001,"phone":"138xxxxxx","conversationId":"conv_xxx"}` | 登录/认证模块、API 鉴权中间件 |
| 会话状态 | `conversation:{conversationId}:state` | `{"state":"APPOINTMENT","awaiting_confirmation":false}` | `StateManager`、`ClassificationProcessor`、`AgentRouter`、`TaskClassificationAgent` |
| 会话历史 | `conversation:{conversationId}:history` | 对话消息列表 / 消息序列化结果 | `AppointmentAgent`、`ConsultantAgent`、`TaskClassificationAgent` |
| 会话锁 | `conversation:{conversationId}:lock` | 锁标记或锁状态 | API 入口层、会话串行控制模块 |
| 技师忙碌时间段 | `technician:{technicianId}:busy_periods` | `[{"start":"15:00","end":"17:00"}]` | `AppointmentDatabase`、`TechnicianFinder`、`AppointmentService` |
| Token 黑名单（可选） | `auth:blacklist:{jti}` 或 `auth:blacklist:{token}` | `1` / `true` | 登录/退出模块、API 鉴权中间件 |
| refresh token（可选） | `auth:refresh:{token}` | `{"userId":10001,"expireAt":"2026-05-15T18:00:00"}` | 登录/刷新模块、退出登录模块 |

### 4.2 模块读写职责说明

- **登录/认证模块**：写入验证码、token、refresh token，处理登录、退出登录和刷新。
- **API 鉴权中间件**：读取 `auth:token:{token}` 校验登录态，必要时读取黑名单。
- **会话管理模块**：根据 token 或用户信息定位 `conversationId`，读写会话状态、历史和锁。
- **预约数据模块**：保存预约记录，并把技师忙碌时间段从内存迁移到 Redis，避免单机内存丢失。
- **StateManager / ClassificationProcessor**：读取和更新会话状态，决定是否需要重新分类以及如何路由。
- **AgentRouter**：根据会话状态把请求分发到咨询 Agent 或预约 Agent。
- **AppointmentAgent / ConsultantAgent**：读取和更新各自处理所需的会话历史、状态或回流标记。
- **退出登录模块**：删除或失效 token、refresh token，并可写入黑名单。

### 4.3 登录态

- `auth:token:{token}` -> 用户信息

### 4.4 会话状态

- `conversation:{conversationId}:state` -> 当前状态（CLASSIFY / CONSULT / APPOINTMENT）

### 4.5 会话历史

- `conversation:{conversationId}:history` -> 对话上下文

### 4.6 会话锁

- `conversation:{conversationId}:lock` -> 会话串行控制

### 4.7 Token 黑名单（可选）

- `auth:blacklist:{jti}` 或 `auth:blacklist:{token}`

用于退出登录或强制失效场景。

### 4.8 知识检索存储分层

咨询链路中的知识检索建议拆成两层存储：

- **MySQL**：保存知识文档的结构化元数据，例如 `id`、`content`、`category`、`keywords`、`created_at`、`updated_at`
- **Pinecone**：保存文档向量并负责向量相似度检索

推荐流程是：

1. 文档入库时，先保存元数据到 MySQL
2. 同时生成 embedding，并 upsert 到 Pinecone
3. 查询时先做关键词检索和向量检索，再融合结果
4. 最后把候选文档交给重排模块进一步筛选

## 5. Agent 无状态设计

### 5.1 Agent 设计原则

Agent 层建议保持无状态，只保留处理逻辑，不长期保存会话上下文。

### 5.2 设计目标

- 不再使用全局 `global_session_id`
- 不在 Agent 内部长期保存用户会话状态
- 不在 Agent 内部维护全局共享上下文
- 每次请求只负责处理当前任务

### 5.3 状态外置方式

Agent 所需的上下文统一从 Redis 读取：

- 当前会话状态
- 历史消息
- 当前任务阶段
- 必要的路由信息

处理完成后再写回 Redis。

### 5.4 Agent 职责划分

继续保留现有的职责拆分：

- `TaskClassificationAgent`：负责意图识别、状态路由、流程编排
- `ConsultantAgent`：负责咨询与知识检索
- `AppointmentAgent`：负责预约与排班处理

但这些 Agent 本身不保留长期上下文。

## 6. 会话管理方案

### 6.1 会话隔离

每个用户或每次独立对话都应有独立 `conversationId`。

建议：

- 由后端生成
- 或由前端携带并在首轮请求后固定

### 6.2 会话串行

同一会话内的请求建议串行处理，避免状态竞态。

推荐实现：

- `conversationId -> asyncio.Lock`
- 或 Redis 队列
- 或乐观并发控制 + 版本号校验

最简单的实现是会话级锁：

- 同一会话的请求进入时先获取锁
- 处理完成后释放锁
- 不同会话之间仍可并行

### 6.3 状态边界

- 会话边界：区分不同用户或不同会话
- 状态边界：区分同一会话内的不同任务阶段

这样可以保证：

- 会话上下文不混淆
- 状态路由清晰
- 任务执行顺序正确

### 6.4 会话级串行与消息缓冲

为避免用户在系统追问缺失信息时，刚好又补充了相同内容而导致重复追问，建议给同一会话增加串行控制和消息缓冲机制：

- 同一 `conversationId` 同一时间只允许一个请求处理，使用会话锁保证串行
- 每次用户新消息到达时递增 `message_version`，用于区分新旧消息
- 当系统判定信息不足准备追问时，不立即发送追问，而是先检查该会话是否有更新的待处理消息
- 如果发现新消息已经补齐缺失字段，则合并上下文后继续执行，不再追问
- 如果仍然缺失，再将追问标记为 `pending_prompt`，并在真正发出前再次校验版本号，版本变化则取消追问

推荐做法是把会话级消息缓冲区实现为 Redis 中的会话消息箱或待处理消息列表，按 `conversationId` 维度存储，避免不同用户互相影响。

### 6.5 多用户短期记忆设计

如果需要为多用户版本增加短期记忆，建议按会话维度保存，并拆成三层：

#### 6.5.1 咨询对话上下文记忆

用于咨询链路中保留最近几轮问答，帮助模型理解当前话题和指代关系。

建议保存内容：

- 最近若干轮用户和机器人的消息
- 当前咨询主题摘要
- 最近命中的知识类别

推荐 Redis Key：

- `conversation:{conversationId}:consult_memory`

#### 6.5.2 预约结构化槽位记忆

用于预约链路中保存已经抽取出的结构化信息，支撑后续补全、追问和技师匹配。

建议保存内容：

- `start_time`
- `duration`
- `project`
- `gender`
- `preference`
- `technician_name`
- `awaiting_confirmation`
- `confirmed_technician`

推荐 Redis Key：

- `conversation:{conversationId}:appointment_memory`

#### 6.5.3 摘要压缩记忆

当对话轮次较多时，建议把早期上下文压缩成摘要，减少 prompt 长度并保持连续性。

建议保存内容：

- 当前会话的摘要文本
- 已完成的关键步骤
- 当前仍待补充的信息

推荐 Redis Key：

- `conversation:{conversationId}:memory_summary`

#### 6.5.4 记忆使用方式

处理新请求时建议遵循以下顺序：

1. 先读取咨询上下文记忆或预约槽位记忆
2. 再读取最近一段消息缓冲区
3. 如对话过长，则先合并摘要记忆
4. 再交给分类、检索或预约流程继续处理

这样可以保证：

- 咨询问题有上下文连续性
- 预约流程有稳定的槽位信息
- 长对话不会无限膨胀
- 多用户之间完全隔离

## 7. 请求链路

推荐请求链路如下：

1. 用户登录，获取 UUID token
2. 前端保存 token
3. 后续请求携带 token
4. API 层校验 token
5. 根据 token 找到用户和 conversationId
6. 从 Redis 读取会话状态、辅助状态和历史
7. 根据主状态路由到分类、咨询或预约 Agent
8. Agent 根据辅助状态继续处理当前流程细节
9. 处理完成后将新的状态和历史写回 Redis
10. 返回前端

## 8. 状态设计：主状态 + 少量辅助状态

### 8.1 设计原则

在多用户无状态 Agent 架构中，状态分成两类：

- **主状态**：用于决定请求路由到哪个 Agent
- **辅助状态**：用于表达当前流程中的细节条件

其中，辅助状态不宜过多，只需要满足当前流程需求即可，避免状态枚举膨胀和路由逻辑复杂化。

### 8.2 主状态建议

主状态建议保持为 3 个核心值：

- `CLASSIFY`：分类阶段
- `CONSULT`：咨询阶段
- `APPOINTMENT`：预约阶段

主状态只负责大方向路由。

### 8.3 辅助状态建议

辅助状态建议以布尔值或少量标志位的形式存储，不要扩展成过多主状态。

建议的辅助字段包括：

- `awaiting_confirmation`：是否正在等待用户确认技师或预约结果
- `waiting_for_phone_code`：是否正在等待验证码
- `login_verified`：是否已完成登录校验
- `finished`：当前业务流程是否已完成
- `need_retry`：是否需要重试或重新路由

### 8.4 辅助状态的作用

辅助状态用于：

- 判断当前主状态下的具体流程分支
- 决定是否继续追问、是否回流、是否结束流程
- 提升对话连续性和用户体验
- 防止把所有细节都塞进主状态枚举中

### 8.5 Redis 存储示例

建议将主状态和辅助状态共同存入同一个会话上下文中，例如：

```json
{
  "state": "APPOINTMENT",
  "awaiting_confirmation": true,
  "waiting_for_phone_code": false,
  "login_verified": true,
  "finished": false,
  "selectedTechnician": "张三"
}
```

### 8.6 使用方式

处理请求时建议遵循以下顺序：

1. 先看主状态，决定路由到哪个 Agent
2. 再看辅助状态，判断当前流程细节
3. 根据组合结果决定是继续执行、重新分类、还是兜底返回

### 8.7 方案收益

- 主状态简单，便于维护
- 辅助状态够用即可，不会过度膨胀
- 路由逻辑清晰
- 适合多用户无状态 Agent 架构

### 8.8 默认状态

新请求进入系统时，默认状态建议如下：

- **主状态**：`CLASSIFY`
- **辅助状态**：默认全部为 `false` 或 `null`

示例：

```json
{
  "state": "CLASSIFY",
  "awaiting_confirmation": false,
  "waiting_for_phone_code": false,
  "login_verified": false,
  "finished": false,
  "selectedTechnician": null
}
```

说明：

- 主状态默认进入分类阶段，先识别用户意图
- 辅助状态默认表示“尚未进入对应流程”
- 只有用户进入具体步骤后，才逐步更新对应字段

## 9. 当前项目需要调整的地方

### 9.1 去掉全局 session

当前代码中存在全局 `global_session_id`，这会导致：

- 所有用户共用同一个会话
- 状态和上下文无法隔离
- 不符合多用户模式

需要改成按请求获取 `conversationId`。

### 9.2 Agent 不再全局单例持有状态

当前 `TaskClassificationAgent`、`AppointmentAgent`、`ConsultantAgent` 的状态是内存式的，需要改造成：

- 每次请求从 Redis 读取会话状态
- 处理后写回 Redis
- Agent 尽量只保留逻辑，不保留上下文

### 9.3 增加登录鉴权

在 API 入口增加：

- 手机号 + 验证码登录接口
- UUID token 校验中间件
- 会话获取逻辑

### 9.4 迁移技师忙碌时间段存储

当前技师忙碌时间段先存于内存，后续需要改成 Redis 存储：

- 把 `busy_periods_dict` 这类内存结构替换为 Redis Key
- 预约成功后直接写入 Redis，保证多用户和多实例场景下一致
- 技师查空闲时优先读 Redis，避免单机内存重启后丢失忙碌状态

### 9.5 收缩任务分类范围

当前任务分类只保留 `appointment`、`query` 和 `other` 三类：

- `appointment`：预约流程
- `query`：咨询流程
- `other`：无关请求兜底

`pay`、`statistics` 等类型后续如果继续扩展业务，再重新加回分类器和路由层。

### 9.6 引入会话级消息缓冲区

为了解决“系统刚准备追问，用户同时补充了信息，导致重复回答”的竞态问题，后续需要引入会话级消息缓冲区，并与会话锁、版本号一起使用：

- 使用 `conversationId` 作为缓冲区分组键
- 用户每发一条消息，就写入缓冲区并更新消息版本号
- 处理预约信息不完整时，先查缓冲区是否有更新消息
- 如果有更新消息，则先合并上下文，再重新判断是否还需要追问
- 如果没有更新消息，才将追问进入待发送状态，并在发送前再次校验版本号

这样可以保证：

- 不会重复追问用户已经补充的信息
- 不会把旧追问发给已经更新过上下文的会话
- 同一会话内的消息处理顺序更稳定

## 10. 心理咨询预约版改造清单（按文件）

下面这一节是把当前按摩门店场景真正改成心理咨询预约场景时，建议逐个文件处理的清单。建议按 P0、P1、P2 的顺序推进，先保证主流程语义正确，再补页面和文案，最后做测试和细节优化。

### 10.1 P0：必须先改的核心文件

- [README.md](README.md)
  - 把项目定位从“按摩门店智能预约”改成“心理咨询师预约与咨询系统”
  - 把核心能力里的“技师匹配、推拿项目、天气提醒”改成“咨询师匹配、咨询主题、隐私与危机兜底”
  - 重写项目背景、技术亮点和示例说明

- [app.py](app.py)
  - 修改应用标题、描述和启动日志中的行业词
  - 把“技师初始化”改成“咨询师初始化”或“咨询资源初始化”
  - 如果保留推荐调度逻辑，改成面向复约提醒或咨询随访，而不是门店回访

- [db/models.py](db/models.py)
  - 将 `Technician`、`TechnicianSchedule` 改为咨询师语义的模型名
  - 把 `strength` 改为 `specialty`、`expertise` 或 `counseling_style`
  - 增加适合心理咨询的字段，例如咨询方向、执业资质、线上/线下、适配人群
  - 取消或弱化和按摩直接绑定的字段设计

- [services/technician_service.py](services/technician_service.py)
  - 重写默认数据，删除按摩师画像
  - 新增咨询师基础数据，例如擅长领域、咨询流派、服务形式、适配人群
  - 同步修改类名、方法名和返回字段语义

- [agents/appointment_agent.py](agents/appointment_agent.py)
  - 重写预约历史字段，把 `project`、`technician_name`、`gender` 这类按摩场景槽位改成咨询场景槽位
  - 建议改成：咨询主题、咨询师偏好、会谈时长、线上/线下、是否首次咨询
  - 删除和按摩无关的成功话术和天气联动逻辑

- [agents/appointment/appointment_processor.py](agents/appointment/appointment_processor.py)
  - 重写信息补全、推荐确认、成功提示三条主流程
  - 加入心理咨询场景下的隐私提示、预约须知和危机关键词兜底
  - 移除“北京天气”这类门店附加逻辑

- [agents/appointment/input_parser.py](agents/appointment/input_parser.py)
  - 重写预约信息抽取 schema
  - 识别咨询主题、咨询目标、时长、咨询形式、咨询师偏好等字段

- [agents/appointment/technician_finder.py](agents/appointment/technician_finder.py)
  - 把“技师匹配”改成“咨询师匹配”
  - 把筛选条件从“性别、力气、按摩专长”改成“咨询方向、流派、擅长问题、资质、形式偏好”

### 10.2 P0：咨询和分类链路必须同步改

- [agents/task_classification_agent.py](agents/task_classification_agent.py)
  - 修改默认业务上下文
  - 增加“危机干预/紧急求助”的分流意识
  - 保证分类结果适配咨询场景，而不是按摩门店场景

- [agents/task_classification/task_classifier.py](agents/task_classification/task_classifier.py)
  - 重写分类提示词和标签定义
  - 让分类器识别“预约咨询、知识问答、危机求助、其他”

- [agents/task_classification/agent_router.py](agents/task_classification/agent_router.py)
  - 重新定义路由规则
  - 把请求分发到咨询 Agent、预约 Agent 或兜底处理器

- [agents/task_classification/unrelated_handler.py](agents/task_classification/unrelated_handler.py)
  - 重写无关请求回复文案
  - 在高风险表达下提供安全兜底，而不是继续按普通咨询处理

- [agents/consultant_agent.py](agents/consultant_agent.py)
  - 将咨询范围改成心理咨询预约说明、咨询师介绍、保密原则、预约规则
  - 检查是否需要支持危机干预或人工转接

- [agents/consultant/consultation_classifier.py](agents/consultant/consultation_classifier.py)
  - 调整咨询相关判断标准
  - 避免把心理健康类问题误判为普通问答

- [agents/consultant/prompt_builder.py](agents/consultant/prompt_builder.py)
  - 清理所有门店和按摩场景提示词
  - 改成心理咨询语境下的分类、回答和追问提示

- [agents/consultant/response_generator.py](agents/consultant/response_generator.py)
  - 调整回答风格为温和、专业、非诊断式
  - 避免输出越权医疗建议

- [agents/consultant/knowledge_retriever.py](agents/consultant/knowledge_retriever.py)
  - 知识检索内容改成心理咨询 FAQ、咨询流派、隐私协议、预约须知

### 10.3 P1：API、服务和页面同步改

- [api/appointment.py](api/appointment.py)
  - 把接口返回消息和请求字段改成咨询预约语义

- [api/task.py](api/task.py)
  - 保证任务分类接口输出的是心理咨询预约相关结果

- [api/consultation.py](api/consultation.py)
  - 把咨询接口内容换成心理咨询知识服务

- [api/technician.py](api/technician.py)
  - 建议改名为 `counselor.py` 或 `therapist.py`
  - 接口名、返回模型名、路由标签全部改成咨询师语义

- [api/knowledge.py](api/knowledge.py)
  - 知识库管理页和接口改成心理咨询知识库管理

- [api/user_behavior_analysis.py](api/user_behavior_analysis.py)
  - 将行为分析维度改成咨询偏好、复约倾向、主题偏好

- [services/appointment_service.py](services/appointment_service.py)
  - 保存预约、查询可用性、获取人员信息等接口都改成咨询师语义

- [services/recommendation_service.py](services/recommendation_service.py)
  - 推荐对象从“合适技师”改成“合适咨询师”或“复约提醒”

- [services/knowledge_service.py](services/knowledge_service.py)
  - 导入和维护的知识文档改成心理咨询内容

- [services/user_behavior_service.py](services/user_behavior_service.py)
  - 行为标签改成咨询相关行为，而不是按摩预约行为

- [web/routes.py](web/routes.py)
  - 页面路由重命名
  - `/technician`、`/technician_schedule` 之类路径改成咨询师相关路径

- [web/templates/index.html](web/templates/index.html)
  - 首页标题、按钮、介绍文案全部改成心理咨询预约场景

- [web/templates/technician.html](web/templates/technician.html)
  - 改成咨询师介绍页

- [web/templates/technician_schedule.html](web/templates/technician_schedule.html)
  - 改成咨询师可预约时段页

- [web/templates/knowledge_management.html](web/templates/knowledge_management.html)
  - 改成心理咨询知识库管理页

- [web/templates/user_behavior_analysis.html](web/templates/user_behavior_analysis.html)
  - 改成咨询偏好和复约分析页

- [web/static/styles.css](web/static/styles.css)
  - 如果这里有门店风格、按摩风格或旧图标，也要一起替换

### 10.4 P2：测试、数据和文档收尾

- [tests/test_appointment_agent.py](tests/test_appointment_agent.py)
  - 把测试输入和断言改成咨询预约场景

- [tests/test_consultant_agent.py](tests/test_consultant_agent.py)
  - 补心理咨询知识问答和知识检索测试

- [tests/test_task_classification_agent.py](tests/test_task_classification_agent.py)
  - 更新分类标签和路由断言

- [tests/test_user_behavior_agent.py](tests/test_user_behavior_agent.py)
  - 调整为咨询偏好和复约行为测试

- [data/](data/)
  - 清理旧按摩知识库和旧预约数据
  - 重新生成适配心理咨询场景的向量索引和样例数据

- [多用户登录与无状态Agent方案.md](多用户登录与无状态Agent方案.md)
  - 当前这份方案后续也建议把“技师”与“按摩”相关示例统一改成“咨询师”与“心理咨询”

### 10.5 推荐改造顺序

1. 先改入口和文案：`README.md`、`app.py`、`web/routes.py`、`web/templates/index.html`
2. 再改核心业务：`db/models.py`、`services/technician_service.py`、`agents/appointment_agent.py`、`agents/appointment/appointment_processor.py`
3. 然后改分类和咨询链路：`agents/task_classification_agent.py`、`agents/consultant_agent.py` 及其子模块
4. 最后补测试、样例数据和页面细节

### 10.6 改造完成后的目标状态

- 用户输入的不是“预约按摩”，而是“预约心理咨询”
- 系统匹配的不是“技师”，而是“咨询师”
- 知识库回答的不是按摩注意事项，而是心理咨询预约说明和常见问题
- 页面、接口、数据库、日志和测试都统一为心理咨询场景
- 多用户登录和无状态 Agent 机制保持不变，只是业务语义整体切换

### 9.7 多用户短期记忆落地方式

短期记忆后续需要和无状态多用户架构一起落到 Redis 中，不再依赖 Agent 实例内存：

- 咨询对话上下文记忆：保存最近几轮消息、主题摘要和最近命中类别
- 预约结构化槽位记忆：保存预约所需字段和当前确认状态
- 摘要压缩记忆：保存长对话的压缩摘要，控制上下文长度

推荐的访问顺序是：

1. 先读当前会话的结构化记忆
2. 再读最近消息缓存
3. 必要时读摘要记忆补全上下文
4. 再进入咨询检索或预约处理

这样做可以在保留短期上下文的同时，避免 prompt 过长和上下文串会话。

### 9.8 知识检索升级为混合检索

当前咨询链路中的知识检索后续需要升级为混合检索，而不是只依赖单一路径：

- **关键词检索**：基于倒排索引和 BM25，对用户问题做文本匹配，补充精确命中能力
- **向量检索**：基于 Pinecone 做语义相似度召回，补充语义泛化能力
- **结果融合**：使用 RRF（Reciprocal Rank Fusion）融合多路检索结果，得到统一候选集

这样做的目的是同时兼顾：

- 关键词精确匹配
- 语义召回能力
- 多路结果稳定融合

### 9.9 引入 Jina-Reranker 做重排

在混合检索得到候选集后，后续需要增加重排步骤，建议使用 Jina-Reranker：

- 先用关键词检索、向量检索和 RRF 生成候选文档
- 再将候选文档和用户问题一起送入 Jina-Reranker
- 按相关性得分重新排序，取 Top-N 作为最终上下文

重排层的作用是进一步提升咨询回答的命中率和上下文质量，避免仅靠召回结果直接回答带来的噪声。

## 10. 推荐实现组合

### 登录认证

- 手机号 + 验证码
- UUID token
- Redis 保存验证码和 token 映射

### Agent 层

- 无状态 Agent
- 会话状态外置到 Redis
- 同会话请求串行处理

### 会话层

- 每个会话独立 `conversationId`
- 每个会话独立状态、历史和锁

## 11. 结论

本方案适合当前项目的多用户改造方向：

- 登录简单
- token 校验清晰
- 会话状态统一管理
- Agent 保持无状态
- 多用户并发更容易扩展

整体实现建议遵循以下原则：

- 业务执行流程前置统一入口，先登录再鉴权，再进入会话和路由处理
- Redis 统一保存验证码、token、会话状态、历史和锁
- Agent 保持无状态，只关注当前请求的处理逻辑
- 同一会话串行，不同会话并行，保证路由正确与流程连续
- 主状态只保留少量核心值，辅助状态仅保留流程所需字段，避免状态膨胀

如果后续需要，还可以在此基础上继续扩展：

- refresh token
- token 黑名单
- 会话过期清理
- 多实例部署
- Redis 分布式锁
