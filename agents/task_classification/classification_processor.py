"""
医学分类流程处理器 - 协调整个医学咨询任务分类流程（校园医务室版本）

职责：
1. 协调任务分类器、状态管理器、路由器等医学组件
2. 实现完整的医学咨询分类处理流程
3. 识别紧急医学情况并优先处理
4. 处理医学语境下的异常情况和边界场景
5. 支持五类医学分类：doctor, appointment, faq, emergency, chat

医学流程特点：
- 紧急症状（emergency）优先级最高
- 支持多轮医学对话上下文
- 包含医学安全提示和声明
"""

import logging
from typing import AsyncGenerator, Optional, Union
from .task_classifier import TaskClassifier
from .state_manager import StateManager
from .agent_router import AgentRouter
from .unrelated_handler import UnrelatedHandler
from services.conversation_memory_service import conversation_memory

logger = logging.getLogger(__name__)


class ClassificationProcessor:
    """医学分类流程处理器 - 校园医务室版本"""

    def __init__(self,
                 task_classifier: TaskClassifier,
                 state_manager: StateManager,
                 agent_router: AgentRouter,
                 unrelated_handler: UnrelatedHandler,
                 memory_service=None):
        """
        初始化医学分类流程处理器

        Args:
            task_classifier: 医学任务分类器
            state_manager: 状态管理器（医学版本）
            agent_router: 医学智能体路由器
            unrelated_handler: 医学无关请求处理器
            memory_service: 对话记忆服务（可选，默认使用全局实例）
        """
        self.task_classifier = task_classifier
        self.state_manager = state_manager
        self.agent_router = agent_router
        self.unrelated_handler = unrelated_handler
        self.memory = memory_service or conversation_memory
        self.conversation_id = state_manager.conversation_id

        # 统计信息
        self.classification_count = 0
        self.emergency_count = 0
    
    async def process_task_stream(self, task: str) -> AsyncGenerator[str, None]:
        """
        流式处理医学咨询任务分类和路由
        
        Args:
            task: 用户输入的医学咨询内容
            
        Yields:
            str: 流式响应内容
        """
        try:
            logger.debug(f"[分类流程] 开始处理任务: {task[:50]}...")
            
            # 检查是否需要进行分类（或处于分类状态）
            if self.state_manager.should_classify():
                logger.debug("[分类流程] 需要进行分类")
                
                # 进行医学任务分类
                category = await self.task_classifier.classify_task(task)
                logger.info(f"[分类流程] 分类结果: {category}")
                
                self.classification_count += 1
                
                # 根据医学分类结果路由
                if category == 'emergency':
                    self.emergency_count += 1
                    logger.warning(f"[分类流程] 检测到紧急情况 - 第{self.emergency_count}个")
                    async for token in self.agent_router.route(category, task):
                        yield token
                
                elif category == 'doctor':
                    logger.info("[分类流程] 路由到医生咨询")
                    async for token in self.agent_router.route(category, task):
                        yield token
                
                elif category == 'appointment':
                    logger.info("[分类流程] 路由到预约处理")
                    async for token in self.agent_router.route(category, task):
                        yield token
                
                elif category == 'faq':
                    logger.info("[分类流程] 路由到健康知识")
                    async for token in self.agent_router.route(category, task):
                        yield token
                
                elif category == 'chat':
                    logger.debug("[分类流程] 路由到闲聊")
                    async for token in self.agent_router.route(category, task):
                        yield token
                
                else:
                    logger.warning(f"[分类流程] 未知分类: {category}")
                    async for token in self.agent_router.route(category, task):
                        yield token
            
            else:
                # 根据当前状态继续处理（多轮对话）
                logger.debug("[分类流程] 根据当前状态继续处理")
                async for token in self.agent_router.route_by_state(task):
                    yield token
                    
        except Exception as e:
            logger.error(f"[分类流程] 处理任务时发生异常: {str(e)}", exc_info=True)
            # 区分 API 限流错误和其他错误，给出友好提示
            error_msg = str(e)
            if "429" in error_msg or "TooManyRequests" in error_msg or "SetLimitExceeded" in error_msg:
                yield "[REPLY][助手] 抱歉，模型服务当前负载过高，请稍后再试。"
            else:
                yield f"[ERROR] 处理任务时发生错误: {str(e)}"
            self.state_manager.reset_to_classify()
    
    async def process_task_sync(self, task: str) -> str:
        """
        同步处理医学咨询任务分类和路由（非流式）
        
        Args:
            task: 用户输入的医学咨询内容
            
        Returns:
            str: 处理结果
        """
        try:
            logger.debug(f"[分类流程-同步] 开始处理: {task[:50]}...")
            
            if self.state_manager.should_classify():
                category = await self.task_classifier.classify_task(task)
                self.classification_count += 1
                
                if category == 'emergency':
                    self.emergency_count += 1
                    logger.warning("[分类流程-同步] 检测到紧急情况")
                    return await self._handle_emergency_sync(task)
                
                elif category == 'doctor':
                    return await self._handle_doctor_consultation_sync(task)
                
                elif category == 'appointment':
                    return await self._handle_appointment_sync(task)
                
                elif category == 'faq':
                    return await self._handle_knowledge_sync(task)
                
                elif category == 'chat':
                    return await self._handle_chat_sync(task)
                
                else:
                    logger.warning(f"[分类流程-同步] 未知分类: {category}")
                    return f"分类结果未知: {category}"
            
            else:
                # 根据当前状态继续处理
                current_state = self.state_manager.get_current_state()
                logger.debug(f"[分类流程-同步] 当前状态: {current_state}")
                
                if self.state_manager.is_in_doctor_assessment_flow():
                    return await self._handle_doctor_consultation_sync(task)
                elif self.state_manager.is_in_appointment_flow():
                    return await self._handle_appointment_sync(task)
                elif self.state_manager.is_in_consultation_flow():
                    return await self._handle_knowledge_sync(task)
                else:
                    return "会话状态异常，请重新开始。"
                    
        except Exception as e:
            logger.error(f"[分类流程-同步] 异常: {str(e)}", exc_info=True)
            self.state_manager.reset_to_classify()
            return f"处理任务时发生错误: {str(e)}"
    
    # 医学特定的同步处理方法（辅助）
    async def _handle_emergency_sync(self, task: str) -> str:
        """处理紧急情况（同步）"""
        self.state_manager.transition_to_emergency()
        return (
            f"⚠️ 紧急！检测到可能的医学紧急情况！\n\n"
            f"症状：{task}\n\n"
            f"立即行动：\n"
            f"1. 拨打 120 或 999\n"
            f"2. 如在校园，立即前往校医务室\n"
            f"3. 告知医务人员所有症状\n\n"
            f"不要延迟！"
        )
    
    async def _handle_doctor_consultation_sync(self, task: str) -> str:
        """处理医生咨询（同步）"""
        if self.agent_router.consultant_agent:
            self.state_manager.transition_to_doctor_assessment()
            try:
                return await self.agent_router.consultant_agent.assess_symptoms(task)
            except Exception as e:
                logger.error(f"医生咨询失败: {str(e)}")
                return f"医学评估失败: {str(e)}"
        return "医生咨询服务暂时不可用"
    
    async def _handle_appointment_sync(self, task: str) -> str:
        """处理预约（同步）"""
        if self.agent_router.appointment_agent:
            self.state_manager.transition_to_appointment()
            try:
                return await self.agent_router.appointment_agent.run(user_input=task)
            except Exception as e:
                logger.error(f"预约处理失败: {str(e)}")
                return f"预约处理失败: {str(e)}"
        return "预约服务暂时不可用"
    
    async def _handle_knowledge_sync(self, task: str) -> str:
        """处理健康知识（同步）"""
        if self.agent_router.knowledge_agent:
            return await self.agent_router.knowledge_agent.answer_query(task)
        return "我是校园医务室的智能助手。请告诉我您的健康问题。"
    
    async def _handle_chat_sync(self, task: str) -> str:
        """处理闲聊（同步）"""
        if self.agent_router.chat_agent:
            return await self.agent_router.chat_agent.chat(task)
        return "感谢您的问候。请问有什么医学问题我可以帮助吗？"
    
    def get_current_state_info(self) -> dict:
        """获取当前医学处理状态信息"""
        return {
            'current_state': self.state_manager.get_current_state(),
            'state_description': self.state_manager.get_state_description(),
            'available_medical_services': self.agent_router.get_available_services(),
            'can_classify': self.state_manager.should_classify(),
            'classification_stats': {
                'total_classified': self.classification_count,
                'emergencies_detected': self.emergency_count
            }
        }
    
    def reset_conversation(self) -> None:
        """重置医学对话状态"""
        logger.info("[分类流程] 重置对话状态")
        self.state_manager.reset_to_classify()
        self.unrelated_handler.reset_reply_rotation()
    
    async def handle_unrelated_request(
        self, 
        user_input: str, 
        async_mode: bool = True,
        include_medical_tips: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        处理医学无关的请求
        
        Args:
            user_input: 用户输入
            async_mode: 是否使用异步模式
            include_medical_tips: 是否包含医学安全提示
            
        Returns:
            流式响应内容
        """
        logger.info(f"[分类流程] 处理无关请求: {user_input[:50]}...")
        
        if async_mode:
            if include_medical_tips:
                async for token in self.unrelated_handler.handle_unrelated_with_medical_context(user_input):
                    yield token
            else:
                async for token in self.unrelated_handler.handle_unrelated_async(user_input):
                    yield token
        else:
            result = await self.unrelated_handler.handle_unrelated_sync(user_input)
            yield result
    
    def get_statistics(self) -> dict:
        """获取分类处理的统计信息"""
        return {
            'total_classifications': self.classification_count,
            'emergencies_detected': self.emergency_count,
            'emergency_rate': (
                f"{(self.emergency_count / self.classification_count * 100):.1f}%" 
                if self.classification_count > 0 
                else "N/A"
            )
        }
