"""
智能体路由器 - 根据医学咨询分类结果路由到对应的处理Agent

职责：
1. 接收医学咨询分类结果，决定使用哪个Agent处理
2. 支持五类路由：doctor（医生）、appointment（预约）、faq（知识）、emergency（紧急）、chat（闲聊）
3. 协调各个医学Agent之间的调用
4. 管理Agent的初始化和状态同步
5. 识别紧急症状并加速处理
"""

import logging
from typing import Any, AsyncGenerator
from .state_manager import StateManager
from services.conversation_memory_service import conversation_memory

logger = logging.getLogger(__name__)


class AgentRouter:
    """医学咨询智能体路由器 - 校园医务室版本"""

    def __init__(
        self,
        appointment_agent: Any = None,
        consultant_agent: Any = None,
        state_manager: StateManager = None,
        knowledge_agent: Any = None,
        chat_agent: Any = None,
        memory_service=None
    ):
        """
        初始化医学咨询路由器

        Args:
            appointment_agent: 预约处理Agent（医学预约）
            consultant_agent: 医生咨询Agent（症状评估、诊断建议）
            state_manager: 状态管理器
            knowledge_agent: 健康知识Agent（FAQ处理）
            chat_agent: 闲聊Agent
            memory_service: 对话记忆服务
        """
        self.appointment_agent = appointment_agent
        self.consultant_agent = consultant_agent  # "医生"Agent
        self.state_manager = state_manager
        self.knowledge_agent = knowledge_agent
        self.chat_agent = chat_agent
        self.memory = memory_service or conversation_memory
        self.conversation_id = state_manager.conversation_id if state_manager else None

        # 设置Agent的共享状态
        self._setup_agent_states()
    
    def _setup_agent_states(self):
        """设置各Agent的共享状态"""
        if self.appointment_agent and hasattr(self.appointment_agent, 'set_shared_state'):
            self.appointment_agent.set_shared_state(self.state_manager.state)
        
        if self.consultant_agent and hasattr(self.consultant_agent, 'set_shared_state'):
            self.consultant_agent.set_shared_state(self.state_manager.state)
        
        if self.knowledge_agent and hasattr(self.knowledge_agent, 'set_shared_state'):
            self.knowledge_agent.set_shared_state(self.state_manager.state)
    
    async def route(self, category: str, task: str) -> AsyncGenerator[str, None]:
        """
        根据医学咨询分类路由到对应Agent
        
        Args:
            category: 分类结果 (doctor, appointment, faq, emergency, chat)
            task: 用户输入的医学咨询内容
            
        Yields:
            str: 流式响应内容
        """
        logger.debug(f"[路由] 分类: {category}, 内容: {task[:50]}...")
        
        # 紧急情况优先级最高 - 立即升级
        if category == 'emergency':
            async for token in self.route_to_emergency(task):
                yield token
        
        # 医生问诊 - 症状评估和诊断建议
        elif category == 'doctor':
            async for token in self.route_to_doctor_consultation(task):
                yield token
        
        # 医学预约 - 挂号预约处理
        elif category == 'appointment':
            async for token in self.route_to_appointment(task):
                yield token
        
        # 健康知识 - FAQ和常见问题
        elif category == 'faq':
            async for token in self.route_to_knowledge(task):
                yield token
        
        # 闲聊/无关 - 通用对话
        elif category == 'chat':
            async for token in self.route_to_chat(task):
                yield token
        
        else:
            async for token in self.handle_unsupported_category(category):
                yield token
    
    async def route_to_emergency(self, task: str) -> AsyncGenerator[str, None]:
        """
        处理紧急医学情况 - 立即上报
        
        Args:
            task: 紧急信息
            
        Yields:
            str: 紧急处理响应
        """
        logger.warning(f"[紧急] 检测到危急情况: {task}")
        
        # 更新状态为紧急
        if self.state_manager:
            self.state_manager.transition_to_emergency()
        
        # 生成紧急提示
        yield "[ALERT][系统紧急]"
        yield "⚠️ 系统检测到可能的医学紧急情况！\n\n"
        yield "立即采取行动：\n"
        yield "1️⃣ 根据情况情况，请立即拨打 120（急救电话）或 999（紧急求助电话）\n"
        yield "2️⃣ 如果在校园内，请立即前往校医务室\n"
        yield "3️⃣ 校医务室电话：请致电校园保卫部或学生工作处获取\n"
        yield "4️⃣ 详细症状：" + task + "\n\n"
        yield "不要延迟！在等待帮助期间，请采取必要的急救措施。"
        
        if self.consultant_agent:
            yield "\n\n[医生提示]"
            try:
                async for token in self.consultant_agent.consult_stream(task):
                    yield token
            except Exception as e:
                logger.error(f"[紧急] 医生评估失败: {str(e)}")
    
    async def route_to_doctor_consultation(self, task: str) -> AsyncGenerator[str, None]:
        """
        路由到医生咨询Agent - 症状评估和诊断建议
        
        Args:
            task: 用户症状描述
            
        Yields:
            str: 流式医学评估内容
        """
        if not self.consultant_agent:
            yield "[ERROR] 医生咨询服务暂时不可用"
            return
        
        # 转换状态
        if self.state_manager:
            self.state_manager.transition_to_doctor_assessment()
        
        logger.info(f"[医生] 开始症状评估: {task[:50]}...")
        
        # 生成思考提示
        yield "[THOUGHT][路由器]"
        yield " 用户报告了症状，我正在连接医生进行评估...\n\n"
        yield "[REPLY][医生]"
        
        # 调用医生咨询Agent
        try:
            async for token in self.consultant_agent.consult_stream(task):
                yield token
        except Exception as e:
            logger.error(f"[医生] 评估失败: {str(e)}")
            yield f"\n\n[ERROR] 医学评估失败: {str(e)}"
            if self.state_manager:
                self.state_manager.reset_to_classify()
    
    async def route_to_appointment(self, task: str) -> AsyncGenerator[str, None]:
        """
        路由到医学预约Agent - 校园医务室预约
        
        Args:
            task: 预约请求内容
            
        Yields:
            str: 流式预约处理内容
        """
        if not self.appointment_agent:
            yield "[ERROR] 预约服务暂时不可用"
            return
        
        # 转换状态
        if self.state_manager:
            self.state_manager.transition_to_appointment()
        
        logger.info(f"[预约] 开始预约流程: {task[:50]}...")
        
        # 生成思考提示
        yield "[THOUGHT][路由器]"
        yield " 用户想要预约医务室，我正在处理预约流程...\n\n"
        yield "[REPLY][预约服务]"
        
        # 调用预约Agent
        try:
            async for token in self.appointment_agent.run_stream(user_input=task):
                yield token
        except Exception as e:
            logger.error(f"[预约] 处理失败: {str(e)}")
            yield f"\n\n[ERROR] 预约处理失败: {str(e)}"
            if self.state_manager:
                self.state_manager.reset_to_classify()
    
    async def route_to_knowledge(self, task: str) -> AsyncGenerator[str, None]:
        """
        路由到健康知识Agent - FAQ和健康常识
        
        Args:
            task: 健康知识问询
            
        Yields:
            str: 流式知识内容
        """
        logger.info(f"[知识] 处理健康知识查询: {task[:50]}...")
        
        if self.state_manager:
            self.state_manager.transition_to_consultation()  # 归类为一般咨询
        
        # 使用医生Agent的知识库功能进行RAG健康知识问答
        async for token in self.consultant_agent.consult_stream(task):
            yield token
    
    async def route_to_chat(self, task: str) -> AsyncGenerator[str, None]:
        """
        处理闲聊/无关对话

        Args:
            task: 用户输入

        Yields:
            str: 闲聊响应
        """
        logger.debug(f"[闲聊] 处理无关对话: {task[:50]}...")

        if self.state_manager:
            # 仅在非分类状态下重置，避免无意义的状态日志（classify -> classify）
            if not self.state_manager.should_classify():
                self.state_manager.reset_to_classify()
        
        yield "[REPLY][助手]"
        
        if self.chat_agent:
            try:
                async for token in self.chat_agent.chat(task):
                    yield token
            except Exception as e:
                logger.error(f"[闲聊] 处理失败: {str(e)}")
                async for token in self._generate_chat_response(task):
                    yield token
        else:
            async for token in self._generate_chat_response(task):
                yield token
    
    async def handle_unsupported_category(self, category: str) -> AsyncGenerator[str, None]:
        """处理不支持的分类"""
        reply = f"抱歉，我不支持分类为 '{category}' 的请求。请咨询医学相关问题或校园医务室事务。"
        yield "[REPLY][助手]"
        for char in reply:
            yield char
    
    async def route_by_state(self, task: str) -> AsyncGenerator[str, None]:
        """
        根据当前会话状态路由（用于多轮对话）
        
        Args:
            task: 用户输入
            
        Yields:
            str: 流式响应
        """
        if not self.state_manager:
            logger.error("[状态] 状态管理器不可用")
            yield "[ERROR] 会话管理失败"
            return
        
        current_state = self.state_manager.get_current_state()
        logger.debug(f"[状态] 当前状态: {current_state}")
        
        # 根据当前状态继续处理
        if self.state_manager.is_in_appointment_flow():
            logger.debug("[状态] 继续预约流程")
            async for token in self.appointment_agent.run_stream(user_input=task):
                yield token
        
        elif self.state_manager.is_in_doctor_assessment():
            logger.debug("[状态] 继续医生评估流程")
            # 输出医生回复标记，前端依赖 [REPLY] 标签显示内容
            yield "[REPLY][医生]"
            async for token in self.consultant_agent.consult_stream(task):
                yield token
            # 医生子流程结束后（回到初始状态），重置全局状态以便下一条消息重新分类
            if self.state_manager and self.consultant_agent.conversation_id:
                from services.conversation_memory_service import conversation_memory
                slots = conversation_memory.get_medical_slots(self.consultant_agent.conversation_id)
                if slots.get("doctor_sub_state") == "initial_assessment":
                    logger.debug("[状态] 医生子流程已结束，重置状态为 CLASSIFY")
                    self.state_manager.reset_to_classify()
        
        elif self.state_manager.is_in_consultation_flow():
            logger.debug("[状态] 继续一般咨询")
            async for token in self.consultant_agent.consult_stream(task):
                yield token
        
        else:
            # 状态异常，重置
            logger.warning("[状态] 状态异常，重置为分类")
            self.state_manager.reset_to_classify()
            yield "[ERROR] 会话状态异常，已重置。请重新开始对话。"
    
    async def _generate_health_knowledge_response(self, task: str) -> AsyncGenerator[str, None]:
        """生成健康知识回复（默认实现）"""
        response = (
            f"关于您的问题 \"{task}\"，这是一个医学常识问题。\n\n"
            "建议：\n"
            "1. 如果这与您的健康情况有关，请咨询合格的医疗专业人士\n"
            "2. 您可以访问校医务室获取专业医学建议\n"
            "3. 如有紧急情况，请立即就医\n\n"
            "您是否需要预约医生进行进一步咨询？"
        )
        for char in response:
            yield char
    
    async def _generate_chat_response(self, task: str) -> AsyncGenerator[str, None]:
        """生成闲聊回复（默认实现）"""
        response = (
            "感谢您的问候！👋\n\n"
            "我是校园医务室的智能助手，专门为您提供医学相关的帮助，包括：\n"
            "• 🏥 医学咨询和症状评估\n"
            "• 📅 医务室预约挂号\n"
            "• 💊 健康知识答疑\n"
            "• 🆘 紧急情况处理\n\n"
            "请告诉我您的医学相关问题，我很乐意帮助！"
        )
        for char in response:
            yield char
    
    def get_available_services(self) -> dict:
        """获取可用的医学服务列表"""
        services = {
            'doctor': self.consultant_agent is not None,
            'appointment': self.appointment_agent is not None,
            'faq': self.knowledge_agent is not None,
            'emergency': True,  # 总是支持
            'chat': self.chat_agent is not None
        }
        return services
