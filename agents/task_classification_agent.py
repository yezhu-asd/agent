from dotenv import load_dotenv
from config.model_provider import create_chat_model
from config.constants import StateEnum
from services.conversation_memory_service import conversation_memory
from .task_classification import (
    TaskClassifier,
    StateManager,
    AgentRouter,
    UnrelatedHandler,
    ClassificationProcessor
)

load_dotenv()


class TaskClassificationAgent:
    """
    任务分类代理主控制器 (校园医务室版本)

    职责：
    1. 初始化各个分类组件
    2. 提供统一的任务分类接口
    3. 管理与其他Agent的协调
    4. 支持医生问诊、预约、闲聊、紧急升级的路由
    5. 支持 Token 登录后的 user_id 和 conversation_id
    6. 集成对话记忆服务，持久化对话历史和槽位
    """

    def __init__(self, appointment_agent, consultant_agent, user_id=None, conversation_id=None):
        # 基础设置
        self.appointment_agent = appointment_agent
        self.consultant_agent = consultant_agent

        # Token 登录信息
        self.user_id = user_id or "anonymous"
        self.conversation_id = conversation_id or f"conv_{id(self)}"

        # 初始化LLM
        self.llm = self._initialize_llm()

        # 用于状态管理的实际 ID（非 None 时使用）
        _user_id = self.user_id
        _conversation_id = self.conversation_id

        # 初始化组件 - 现在 StateManager 需要 user_id 和 conversation_id
        self.state_manager = StateManager(_user_id, _conversation_id)
        self.task_classifier = TaskClassifier(self.llm)
        self.agent_router = AgentRouter(
            appointment_agent,
            consultant_agent,
            self.state_manager,
            memory_service=conversation_memory  # 传入记忆服务
        )
        self.unrelated_handler = UnrelatedHandler(self.state_manager)
        self.classification_processor = ClassificationProcessor(
            self.task_classifier,
            self.state_manager,
            self.agent_router,
            self.unrelated_handler,
            conversation_memory  # 传入记忆服务
        )

        # 设置回调函数
        self._setup_callbacks()

        # 保持向后兼容的state属性
        self.state = self.state_manager.state

        # 设置校园医务室业务上下文（替代推拿服务）
        self._initialize_campus_clinic_context()

    def _initialize_llm(self):
        """初始化通用聊天模型"""
        return create_chat_model(temperature=0)
    
    def _setup_callbacks(self):
        """设置Agent的回调函数"""
        if self.appointment_agent and hasattr(self.appointment_agent, 'unrelated_callback'):
            self.appointment_agent.unrelated_callback = self.handle_unrelated_async
        
        if self.consultant_agent and hasattr(self.consultant_agent, 'set_unrelated_callback'):
            self.consultant_agent.set_unrelated_callback(self.handle_unrelated_async)
    
    def _initialize_campus_clinic_context(self):
        """初始化校园医务室业务上下文"""
        # 设置业务上下文为校园医务室（而不是推拿服务）
        if hasattr(self.unrelated_handler, 'set_business_context'):
            self.unrelated_handler.set_business_context("校园医务室问诊预约")
        
        # 如果还有其他需要设置的上下文，可以在这里添加
        self.business_type = "campus_clinic"  # 业务类型标记
    
    def set_user_context(self, user_id: str, conversation_id: str):
        """设置用户登录后的上下文信息"""
        self.user_id = user_id
        self.conversation_id = conversation_id
        # 初始化医疗槽位
        slots = conversation_memory.init_medical_slots(conversation_id)
        slots["user_id"] = user_id
        conversation_memory.set_medical_slots(conversation_id, slots)

    def set_business_context(self, service_name: str = "校园医务室问诊预约"):
        """设置业务上下文（保持向后兼容）"""
        if hasattr(self.unrelated_handler, 'set_business_context'):
            self.unrelated_handler.set_business_context(service_name)
        self.business_type = "campus_clinic" if "校园医务室" in service_name or "医务室" in service_name else "other"

    def _clean_response(self, response: str) -> str:
        """清理响应中的格式标记，只保留实际内容"""
        import re
        # 移除 [REPLY][机器人名] 格式标记
        cleaned = re.sub(r'\[REPLY\]\[[^\]]+\]', '', response)
        # 移除 [SIGNAL] 标记
        cleaned = re.sub(r'\[SIGNAL\][^\s]+', '', cleaned)
        return cleaned.strip()

    # ===========================================
    # 主要接口方法 - 保持与原版本的兼容性
    # ===========================================
    
    async def classify_task(self, task: str) -> str:
        """分类任务（向后兼容方法）"""
        # 保存用户消息到历史
        conversation_memory.append_message(self.conversation_id, "user", task)
        result = await self.classification_processor.process_task_sync(task)
        # 保存AI回复到历史
        conversation_memory.append_message(self.conversation_id, "assistant", result)
        return result

    async def classify_task_stream(self, task: str):
        """流式分类任务（主要入口）
        支持的路由类型：
        - doctor: 医生问诊 - 症状评估
        - appointment: 校园医务室预约
        - chat: 闲聊 - 一般咨询
        - emergency: 紧急升级 - 红旗症状
        - faq: 健康知识问答
        """
        # 保存用户消息到历史
        conversation_memory.append_message(self.conversation_id, "user", task)

        full_response = ""
        async for token in self.classification_processor.process_task_stream(task):
            full_response += token
            yield token

        # 保存AI回复到历史（需要清理格式标记）
        clean_response = self._clean_response(full_response)
        conversation_memory.append_message(self.conversation_id, "assistant", clean_response)

        # 自动生成并保存会话摘要
        conversation_memory.generate_and_save_summary(self.conversation_id)

    async def handle_unrelated(self, user_input):
        """处理无关请求（同步版本）"""
        # 重新进行任务分类
        result = ""
        async for token in self.classification_processor.process_task_stream(user_input):
            result += token
        return result

    async def handle_unrelated_async(self, user_input):
        """处理无关请求（异步流版本）"""
        # 重新进行任务分类
        async for token in self.classification_processor.process_task_stream(user_input):
            yield token

    # ===========================================
    # 扩展功能方法
    # ===========================================
    
    def get_classification_info(self):
        """获取分类系统信息"""
        return {
            **self.classification_processor.get_current_state_info(),
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'business_type': self.business_type
        }
    
    def reset_conversation(self):
        """重置对话状态"""
        self.classification_processor.reset_conversation()
    
    def get_supported_intents(self):
        """获取支持的识别意图列表"""
        return {
            'doctor': ['我不舒服', '胸痛', '发烧', '请帮我看看', '症状补充'],
            'appointment': ['我要预约', '预约医生', '改期', '取消预约'],
            'chat': ['闲聊', '一般咨询', '其他话题'],
            'emergency': ['红旗症状', '紧急就医', '呼吸困难', '昏迷'],
            'faq': ['健康知识', '常见问题', '预防建议']
        }
