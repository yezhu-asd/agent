# 校园医务室系统改动详情与 Token 登录方案

本文档用于说明：如何把当前“智能预约助手”项目迁移为“校园医务室问诊预约系统”，以及新增一套基于 Token 的登录与会话定位方案。

## 1. 改造目标

项目需要从“按摩门店预约 + 技师匹配 + 用户偏好分析”迁移为“校园医务室问诊预约 + 风险识别 + 校医值班预约 + 复诊记忆”的多 Agent 系统。

改造后的核心目标：

- 支持学号/手机号登录后进入问诊或预约流程
- 支持症状补充、风险识别、红旗症状升级
- 支持校园医务室预约、改期、取消
- 支持会话隔离、多用户并发、状态无状态化
- 支持健康知识问答，但不再作为门店知识库使用

## 2. 需要改动的文件清单

### 2.1 主流程与 Agent

- [agents/task_classification_agent.py](agents/task_classification_agent.py)
  - 将主路由从“咨询/预约”改成“医生问诊/预约/闲聊/紧急升级”
  - 适配 Token 登录后的 user_id 和 conversation_id
  - 保留流式输出入口，但路由目标要换成校园医务室语义

- [agents/consultant_agent.py](agents/consultant_agent.py)
  - 重构为 DoctorAgent 或替换其职责
  - 增加症状追问、风险评估、红旗症状识别、保守建议输出
  - 禁止输出“无需预约”这类绝对排除结论

- [agents/appointment_agent.py](agents/appointment_agent.py)
  - 从“按摩技师预约”改为“校园医务室预约”
  - 预约槽位改成日期、时段、症状原因、紧急程度、地点
  - 预约结果和冲突检查改成医务室排班逻辑

- [agents/user_behavior_agent.py](agents/user_behavior_agent.py)
  - 从“按摩偏好分析”改成“问诊历史、复诊提醒、风险行为分析”
  - 可作为后台分析模块保留，不作为主路由核心 Agent

### 2.2 分类与状态机

- [agents/task_classification/classification_processor.py](agents/task_classification/classification_processor.py)
  - 任务类别改为：doctor、appointment、faq、emergency、chat
  - 同步/流式分支都要支持紧急升级

- [agents/task_classification/task_classifier.py](agents/task_classification/task_classifier.py)
  - 重写分类提示词与标签体系
  - 识别“我要预约”“我不舒服”“胸痛”“发烧”“先帮我看看”等意图

- [agents/task_classification/agent_router.py](agents/task_classification/agent_router.py)
  - 路由目标从咨询/预约改为医生流程/预约流程
  - 增加 emergency 分支，遇到红旗症状直接升级

- [agents/task_classification/state_manager.py](agents/task_classification/state_manager.py)
  - 状态调整为：CLASSIFY、DOCTOR_ASSESSMENT、APPOINTMENT、COMPLETED、EMERGENCY

- [agents/task_classification/unrelated_handler.py](agents/task_classification/unrelated_handler.py)
  - 兜底话术从门店语义改为校园医务室语义

### 2.3 常量、请求响应与入口

- [config/constants.py](config/constants.py)
  - 补充医务室状态枚举
  - 保留共享状态，但语义改为问诊/预约/紧急升级

- [api/core/response_models.py](api/core/response_models.py)
  - 重命名和重组请求响应模型
  - 增加问诊槽位、预约槽位、风险记录、登录返回模型

- [api/chat_handler.py](api/chat_handler.py)
  - 接入 Token 登录后的用户信息
  - 将请求与 conversation_id 关联

- [api/task.py](api/task.py)
  - 分类接口保留，但返回标签和业务语义要重写

- [api/consultation.py](api/consultation.py)
  - 如果保留，则改名为问诊接口或健康咨询接口

- [api/appointment.py](api/appointment.py)
  - 改为医务室预约接口

- [api/technician.py](api/technician.py)
  - 需要从“技师”改为“校医/医生/值班表”相关接口，建议重构

- [api/user_behavior_analysis.py](api/user_behavior_analysis.py)
  - 改为问诊行为分析、复诊建议、风险回溯接口

- [api/__init__.py](api/__init__.py)
  - 注册新的路由，并移除门店强绑定路由

- [app.py](app.py)
  - 修改应用标题、描述、初始化流程和服务启动内容
  - 若加入鉴权中间件，也应在这里统一挂载

### 2.4 数据层与服务层

- [db/models.py](db/models.py)
  - 建议新增或替换为：users、consultations、appointments、risk_events
  - 原有 technicians、technician_schedules、user_preferences 等门店模型需要迁移或废弃

- [db/db_router.py](db/db_router.py)
  - 跟随新模型调整数据访问入口

- [db/local_db.py](db/local_db.py)
  - 更新初始化表结构与默认数据

- [db/repositories/](db/repositories)
  - 将技师仓库改造为医务室资源仓库、预约仓库、风险事件仓库

- [services/appointment_service.py](services/appointment_service.py)
  - 改造为校园医务室预约服务

- [services/technician_service.py](services/technician_service.py)
  - 改造为校医排班/医生值班服务

- [services/user_behavior_service.py](services/user_behavior_service.py)
  - 改造成问诊行为记录、复诊提醒和风险行为分析服务

- [services/recommendation_service.py](services/recommendation_service.py)
  - 改为问诊后建议、复诊提醒、紧急就医建议

- [services/knowledge_service.py](services/knowledge_service.py)
  - 如果保留知识问答，改成健康知识库

### 2.5 前端页面与模板

- [web/routes.py](web/routes.py)
  - 将页面入口从技师/门店管理改为医务室主页、问诊页、预约页、值班页

- [web/templates/index.html](web/templates/index.html)
  - 改为校园医务室聊天首页

- [web/templates/technician.html](web/templates/technician.html)
  - 改为校医/医生信息页，或直接删除

- [web/templates/technician_schedule.html](web/templates/technician_schedule.html)
  - 改为校医值班表

- [web/templates/knowledge_management.html](web/templates/knowledge_management.html)
  - 改为健康知识管理页面

- [web/templates/user_behavior_analysis.html](web/templates/user_behavior_analysis.html)
  - 改为问诊历史和复诊分析页面

- [web/static/styles.css](web/static/styles.css)
  - 如需要统一视觉风格，建议改成校园医务室主题

### 2.6 文档与说明

- [README.md](README.md)
  - 已完成改写：项目背景、架构说明、能力介绍、启动说明均已切换为校园医务室语义

- [校园医务室系统.md](校园医务室系统.md)
  - 已完成整理：保留需求蓝图并补充正式需求说明文档信息（类型、版本、状态、适用范围）

2.6 完成状态：✅ 已完成

## 3. 改造优先级建议

### P0：必须先改

- 状态机与路由
- DoctorAgent / 问诊逻辑
- AppointmentAgent 的医务室化
- 数据模型和预约记录
- Token 登录与会话并发控制

### P1：必须同步改

- API 请求响应模型
- Web 页面文案与入口
- 服务层的业务命名和数据访问
- 风险升级规则

### P2：可后置

- 知识库页面的视觉重构
- 用户行为分析页面的深度分析
- 统计报表和后台管理页

## 4. Token 登录功能设计

这里采用“UUID Token + Redis 会话映射”的方案，不使用 JWT 作为首版实现。

### 4.1 登录流程

```text
用户输入学号/手机号/验证码
  ↓
后端校验验证码或身份信息
  ↓
生成 UUID token
  ↓
将 token 与 user_id、phone、conversation_id 写入 Redis
  ↓
前端保存 token
  ↓
后续请求统一携带 token
```

### 4.2 推荐的 API

- `POST /api/auth/login`
  - 入参：phone、code 或 student_id、password
  - 出参：token、user_info、conversation_id

- `POST /api/auth/logout`
  - 删除或失效 token

- `GET /api/auth/me`
  - 根据 token 返回当前登录用户信息

- `POST /api/auth/refresh`
  - 如果后续需要 refresh token，可追加这个接口

### 4.3 Redis Key 设计

| 类型 | Key | 说明 |
| --- | --- | --- |
| 登录验证码 | `login:code:{phone}` | 保存验证码和过期时间 |
| 登录 token 映射 | `auth:token:{token}` | 保存 userId、phone、conversationId |
| Token 黑名单（可选） | `auth:blacklist:{token}` | 退出登录或强制失效时使用 |
| 会话状态 | `conversation:{id}:state` | 当前状态机状态 |
| 会话历史 | `conversation:{id}:history` | 多轮对话记录 |
| 问诊槽位 | `conversation:{id}:medical_slots` | 症状、持续时间、红旗标记等 |
| 预约槽位 | `conversation:{id}:appointment_slots` | 预约日期、时间段、原因等 |
| 摘要记忆 | `conversation:{id}:summary_memory` | 长会话摘要 |
| 行为记忆 | `conversation:{id}:behavior_memory` | 复诊和行为分析 |
| 会话锁 | `conversation:{id}:lock` | 同一会话串行处理 |

### 4.4 Token 校验规则

- 从请求头读取 token，建议使用 `Authorization: Bearer <token>`
- 先检查黑名单，再查 `auth:token:{token}`
- 查到则恢复当前用户和 conversation_id
- 查不到则返回未登录或 token 失效

### 4.5 与 Agent 的结合方式

- 登录后，API 层先解析 token
- 根据 token 找到当前用户和 conversation_id
- 将 user_id、conversation_id、登录态写入共享上下文
- Agent 只处理当前会话，不保存全局用户状态

### 4.6 会话串行与并行控制

- 同一 conversation_id 内的请求必须串行处理
- 不同 conversation_id 之间可以并行处理
- 会话锁按 conversation_id 粒度控制
- 会话状态、历史、槽位、风险记录统一外置到 Redis / 数据库
- 推荐使用 Redis 分布式锁或短 TTL 锁，避免同会话并发串话

### 4.7 安全和会话建议

- Token 采用足够长度的 UUID 或随机字符串
- 设定过期时间，避免永久有效
- 支持退出登录后立即失效
- 必要时增加黑名单机制
- 同一 conversationId 加锁，避免并发串话

## 5. 医疗安全规则补充

问诊流程必须加上以下限制：

- 不输出“你没事”“不用预约”这类绝对排除性结论
- 只做建议，不做最终医疗判断
- 遇到红旗症状必须升级
- 输出应偏保守，优先建议进一步评估或预约

红旗症状建议包括：

- 呼吸困难
- 胸痛
- 昏迷
- 抽搐
- 大出血
- 严重过敏
- 高热不退
- 严重外伤

## 6. 预期产出

完成上述改造后，项目将具备以下能力：

- Token 登录和会话定位
- 校园医务室问诊与预约一体化流程
- 风险识别和紧急升级
- 多用户并发与无状态 Agent 运行
- 可持续扩展的健康知识问答模块

## 7. 下一步建议

如果继续推进，建议按下面顺序实施：

1. 先落地 Token 登录和会话定位
2. 再重构状态机和任务分类
3. 然后改 DoctorAgent 和 AppointmentAgent
4. 最后同步数据库、API 和前端页面
