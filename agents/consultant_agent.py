import uuid
from config.model_provider import create_chat_model
from services.conversation_memory_service import conversation_memory
from .consultant import (
    KnowledgeRetriever,
    ConsultationClassifier,
    ResponseGenerator,
    ConsultationProcessor
)


class ConsultantAgent:
    """
    医生问诊机器人主控制器 (校园医务室版本)
    
    役割：
    1. 初始化各个医学知识和咨询组件
    2. 管理医学咨询会话状态
    3. 协调整个医学问诊流程
    
    核心功能：
    - 医学症状评估和分析
    - 基于校园医识库的医学知识检索
    - 医学风险识别和红旗症状检测
    - 保守的医学建议生成（倾向于建议求医而非自治）
    - 支持多轮医学沟通和症状追问
    
    重要原则：
    - 避免绝对或自信的诊断结论
    - 所有症状建议都应倾向于"建议看医生"而非"不需要看医生"
    - 识别红旗症状并启动紧急升级流程
    """
    
    def __init__(self, session_id=None, user_id=None, conversation_id=None):
        # 基础设置
        self.session_id = session_id or str(uuid.uuid4())

        # Token 登录信息
        self.user_id = user_id
        self.conversation_id = conversation_id

        self.shared_state = None
        self.unrelated_callback = None

        # 业务类型标记（医学咨询）
        self.business_type = "medical_consultation"

        # 初始化LLM（医学咨询需要谨慎，使用较低temperature）
        self.llm = self._initialize_llm()

        # 初始化组件
        self.knowledge_retriever = KnowledgeRetriever()
        self.consultation_classifier = ConsultationClassifier(self.llm)
        self.response_generator = ResponseGenerator(self.llm)
        self.consultation_processor = ConsultationProcessor(
            self.knowledge_retriever,
            self.consultation_classifier,
            self.response_generator,
            conversation_memory,
            self.conversation_id
        )

        # 如果有conversation_id，确保医疗槽位存在，同时设置user_id
        if self.conversation_id:
            if self.user_id:
                slots = conversation_memory.get_medical_slots(self.conversation_id)
                slots["user_id"] = self.user_id
                conversation_memory.set_medical_slots(self.conversation_id, slots)

        # 初始化医学模式标志
        self._initialize_medical_context()

    def _initialize_medical_context(self):
        """初始化医学咨询上下文"""
        # 这里可以设置医学咨询的特殊参数
        # 例如：启用红旗症状检测、启用风险评估等
        self.enable_red_flag_detection = True  # 启用红旗症状检测
        self.enable_risk_assessment = True  # 启用风险评估
        self.conservative_mode = True  # 启用保守建议模式

    def _initialize_llm(self):
        """初始化医学咨询用的聊天模型
        
        医学咨询需要谨慎和准确的回答，所以使用温度 0.3 
        （比通用 0 稍高，允许一定的多样性，但保持相对保守）
        """
        return create_chat_model(temperature=0.3)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.knowledge_retriever.initialize()
        print(f"医生问诊机器人已启动（用户ID: {self.user_id}, 会话ID: {self.conversation_id[:8]}）")
        print("医学知识库 RAG 模式已启用")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """异步上下文管理器出口"""
        pass

    def set_shared_state(self, shared_state):
        """设置共享状态"""
        self.shared_state = shared_state

    def set_unrelated_callback(self, callback):
        """设置处理非医学问题的回调函数"""
        self.unrelated_callback = callback

    def set_user_context(self, user_id: str, conversation_id: str):
        """设置用户登录后的上下文信息"""
        self.user_id = user_id
        self.conversation_id = conversation_id
        # 确保医疗槽位存在，设置user_id
        if conversation_id and conversation_memory:
            slots = conversation_memory.get_medical_slots(conversation_id)
            slots["user_id"] = user_id
            conversation_memory.set_medical_slots(conversation_id, slots)
        # 更新processor中的conversation_id
        if hasattr(self.consultation_processor, 'conversation_id'):
            self.consultation_processor.conversation_id = conversation_id

    async def consult(self, user_input: str) -> str:
        """
        基础医学咨询功能

        用于非流式的简单医学咨询场景
        """
        # 保存到对话历史
        if self.conversation_id and conversation_memory:
            conversation_memory.append_message(self.conversation_id, "user", user_input)
        result = await self.consultation_processor.process_consultation(user_input)
        # 保存回复到对话历史
        if self.conversation_id and conversation_memory:
            conversation_memory.append_message(self.conversation_id, "assistant", result)
        return result

    async def consult_stream(self, user_input: str):
        """
        流式输出医学问诊结果

        注意：此入口由主分类器路由到医生/咨询路径后调用，无需在此处做二次分类。
        二次分类（is_consultation_related）对纯名词（如"前列腺炎"）会误判为 NO，
        触发 unrelated_callback → 主分类器 → 再次进入此处 → 无限递归。
        所有用户意图判断由 consultation_processor 内部处理（知识类 vs 症状类）。
        """
        # 保存用户输入到对话历史
        if self.conversation_id and conversation_memory:
            conversation_memory.append_message(self.conversation_id, "user", user_input)

        full_response = ""
        async for token in self.consultation_processor.process_consultation_stream(
            user_input, self.session_id
        ):
            full_response += token
            yield token

        if self.conversation_id and conversation_memory:
            conversation_memory.append_message(self.conversation_id, "assistant", full_response)
            conversation_memory.generate_and_save_summary(self.conversation_id)

        self._reset_state_after_consultation()

    def _reset_state_after_consultation(self):
        """医学问诊完成后重置状态"""
        if self.shared_state:
            from config.constants import StateEnum
            self.shared_state.value = StateEnum.CLASSIFY
    
    def get_medical_context(self):
        """获取医学咨询上下文信息"""
        return {
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'business_type': self.business_type,
            'red_flag_detection': self.enable_red_flag_detection,
            'risk_assessment': self.enable_risk_assessment,
            'conservative_mode': self.conservative_mode
        }
