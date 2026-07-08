"""
无关请求处理器 - 处理与医学咨询无关的用户请求（校园医务室版本）

职责：
1. 识别和处理与医学咨询、医务室预约业务无关的请求
2. 提供医学安全和隐私提示
3. 友好地引导用户回到医学相关的对话轨道
4. 重置对话状态，准备处理下一个医学咨询

医学语境说明：
- 系统在处理无关请求时需要说明其作为医学助手的角色
- 应多次强调隐私保护和专业医学渠道的重要性
- 可以礼貌地推荐咨询真实医生或校医务室
"""

import logging
from typing import AsyncGenerator
from .state_manager import StateManager

logger = logging.getLogger(__name__)


class UnrelatedHandler:
    """无关请求处理器 - 校园医务室医学咨询版本"""
    
    def __init__(self, state_manager: StateManager):
        """
        初始化无关请求处理器
        
        Args:
            state_manager: 状态管理器
        """
        self.state_manager = state_manager
        
        # 医学语境下的无关请求回复
        self._default_replies = [
            (
                "感谢您的对话。我注意到这个话题与医学咨询无关。\n\n"
                "我是校园医务室的智能助手，专注于医学相关的帮助，包括：\n"
                "• 症状评估和医学建议\n"
                "• 医务室预约和挂号\n"
                "• 健康知识和常见问题\n\n"
                "📋 重要提示：本系统提供的任何医学信息仅为参考，不能替代专业医生的诊断和建议。\n"
                "如有紧急情况，请立即就医或拨打 120 寻求帮助。\n\n"
                "您是否有医学相关的问题需要咨询？"
            ),
            (
                "理解您的提问。出于医学专业性考虑，我只能回复与健康和医学相关的问题。\n\n"
                "我可以帮您：\n"
                "✓ 评估您的症状并提供初步建议\n"
                "✓ 预约校园医务室的医生\n"
                "✓ 解答常见的健康知识问题\n"
                "✓ 在有紧急症状时立即上报\n\n"
                "🏥 校医务室随时准备为您服务。\n\n"
                "请告诉我您的医学问题吧！"
            ),
            (
                "感谢提问，但这个话题与医学健康无关。\n\n"
                "我是专业的医学咨询助手，致力于：\n"
                "• 帮助识别健康问题\n"
                "• 提供医学初步评估\n"
                "• 协助安排医务室预约\n"
                "• 提供可靠的健康信息\n\n"
                "⚕️ 如果您有任何健康相关的关切，我很乐意帮助。\n"
                "如果需要专业诊断，我可以帮您预约医生。\n\n"
                "请问今天有什么健康问题我可以帮您解决吗？"
            )
        ]
        self._reply_index = 0
        self._medical_safety_tips = [
            "💊 用药提示：请在医生指导下用药，不要自行用药。",
            "🆘 紧急情况：若出现胸痛、呼吸困难等症状，请立即拨打120",
            "👨⚕️ 专业建议：本系统仅供参考，确诊需求医生面诊。",
            "📞 校医务室热线：请保存校医务室的联系方式，有需要随时可以联系。"
        ]
    
    async def handle_unrelated_sync(self, user_input: str) -> str:
        """
        同步处理无关请求（返回字符串）
        
        Args:
            user_input: 用户输入内容
            
        Returns:
            str: 处理结果
        """
        logger.info(f"[无关处理] 处理无关请求: {user_input[:50]}...")
        
        # 重置状态为分类状态，准备处理下一个输入
        if self.state_manager:
            self.state_manager.reset_to_classify()
        
        # 返回友好的提示回复
        return self._get_next_reply()
    
    async def handle_unrelated_async(self, user_input: str) -> AsyncGenerator[str, None]:
        """
        异步处理无关请求（返回流式响应）
        
        Args:
            user_input: 用户输入内容
            
        Yields:
            str: 流式响应内容
        """
        logger.info(f"[无关处理-流式] 处理无关请求: {user_input[:50]}...")
        
        # 重置状态为分类状态
        if self.state_manager:
            self.state_manager.reset_to_classify()
        
        # 生成流式回复
        reply = self._get_next_reply()
        yield "[REPLY][医学助手]"
        for char in reply:
            yield char
    
    async def handle_unrelated_with_medical_context(
        self, 
        user_input: str
    ) -> AsyncGenerator[str, None]:
        """
        带医学语境的无关请求处理 - 提供医学安全提示
        
        Args:
            user_input: 用户输入内容
            
        Yields:
            str: 流式响应内容（包含医学安全信息）
        """
        logger.info(f"[无关+医学] 处理并添加医学提示: {user_input[:50]}...")
        
        if self.state_manager:
            self.state_manager.reset_to_classify()
        
        # 主回复
        reply = self._get_next_reply()
        yield "[REPLY][医学助手]"
        for char in reply:
            yield char
        
        # 添加医学安全提示
        yield "\n\n"
        yield "[医学提示]"
        import random
        safety_tip = random.choice(self._medical_safety_tips)
        for char in safety_tip:
            yield char
    
    def _get_next_reply(self) -> str:
        """获取下一个回复内容（轮换使用不同回复）"""
        reply = self._default_replies[self._reply_index]
        self._reply_index = (self._reply_index + 1) % len(self._default_replies)
        return reply
    
    def add_custom_reply(self, reply: str) -> None:
        """添加自定义回复"""
        if reply and reply not in self._default_replies:
            self._default_replies.append(reply)
            logger.debug(f"[无关处理] 添加自定义回复: {reply[:50]}...")
    
    def add_safety_tip(self, tip: str) -> None:
        """添加医学安全提示"""
        if tip and tip not in self._medical_safety_tips:
            self._medical_safety_tips.append(tip)
            logger.debug(f"[无关处理] 添加医学提示: {tip[:50]}...")
    
    def set_business_context(self, context_name: str = "校园医务室") -> None:
        """
        设置业务上下文（医学语境版本）
        
        Args:
            context_name: 业务上下文名称，如"校园医务室"、"学生卫生中心"等
        """
        self._default_replies = [
            (
                f"感谢您的对话。我注意到这个话题与医学咨询无关。\n\n"
                f"我是{context_name}的智能助手，专注于医学相关的帮助，包括：\n"
                "• 症状评估和医学建议\n"
                "• 医务室预约和挂号\n"
                "• 健康知识和常见问题\n\n"
                "请问您有医学相关的问题需要咨询？"
            ),
            (
                f"理解您的提问。出于医学专业性考虑，我只能回复与健康和医学相关的问题。\n\n"
                f"我是{context_name}的医学咨询助手，可以帮您安排就诊。\n\n"
                "请告诉我您的医学问题吧！"
            ),
            (
                f"感谢提问，但这个话题与医学健康无关。\n\n"
                f"我是{context_name}的医学咨询系统，专注于医学相关问题。\n\n"
                "请问今天有什么健康问题我可以帮您解决吗？"
            )
        ]
        logger.info(f"[无关处理] 业务上下文已设置为: {context_name}")
    
    def get_available_replies(self) -> list:
        """获取所有可用的回复模板"""
        return self._default_replies.copy()
    
    def get_safety_tips(self) -> list:
        """获取所有医学安全提示"""
        return self._medical_safety_tips.copy()
    
    def reset_reply_rotation(self) -> None:
        """重置回复轮换索引"""
        self._reply_index = 0
        logger.debug("[无关处理] 回复轮换已重置")
