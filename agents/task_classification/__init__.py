"""
TaskClassification 医学分类模块 - 校园医务室版本

提供医学咨询任务分类相关的模块化组件：
- TaskClassifier: 医学任务分类器 - 判断用户医学咨询类型（doctor/appointment/faq/emergency/chat）
- StateManager: 会话状态管理器 - 管理医学对话状态流转和持久化
- AgentRouter: 医学智能体路由器 - 根据分类结果路由到对应医学Agent
- UnrelatedHandler: 医学无关请求处理器 - 处理与医学咨询无关的请求
- ClassificationProcessor: 医学分类流程处理器 - 协调整个医学咨询分类流程

核心功能：
✓ 5类医学分类：doctor(医生问诊), appointment(预约), faq(健康知识), emergency(紧急), chat(闲聊)
✓ 紧急症状识别和快速升级
✓ 会话状态持久化（Redis/内存）
✓ 多轮对话上下文管理
✓ 医学安全提示和声明
"""

from .task_classifier import TaskClassifier
from .state_manager import StateManager
from .agent_router import AgentRouter
from .unrelated_handler import UnrelatedHandler
from .classification_processor import ClassificationProcessor

__all__ = [
    'TaskClassifier',
    'StateManager', 
    'AgentRouter',
    'UnrelatedHandler',
    'ClassificationProcessor'
]
