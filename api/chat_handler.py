"""
聊天处理器 - 整合 Token 认证和会话管理

职责：
1. 验证 Token 和用户身份
2. 创建或恢复会话状态
3. 注入用户上下文到 Agent
4. 处理流式输出
"""

import uuid
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatSession:
    """聊天会话信息"""
    
    def __init__(self, user_id: str, conversation_id: str, user_info: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.user_info = user_info or {}
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        logger.info(f"[ChatSession] 创建新会话: user={user_id}, conv={conversation_id}")
    
    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = datetime.now()


def _build_task_agent(user_id: str, conversation_id: str):
    """
    为给定的用户和会话创建任务分类 Agent
    
    Args:
        user_id: 用户ID（已通过 Token 验证）
        conversation_id: 会话ID
    
    Returns:
        TaskClassificationAgent 实例
    """
    from agents.task_classification_agent import TaskClassificationAgent
    from agents.appointment_agent import AppointmentAgent
    from agents.consultant_agent import ConsultantAgent

    # 为此会话创建全局 session_id
    global_session_id = str(uuid.uuid4())
    
    logger.debug(f"[Agent] 创建 Agent 实例: session={global_session_id}, user={user_id}, conv={conversation_id}")
    
    return TaskClassificationAgent(
        AppointmentAgent(session_id=global_session_id, user_id=user_id, conversation_id=conversation_id),
        ConsultantAgent(session_id=global_session_id, user_id=user_id, conversation_id=conversation_id),
        user_id=user_id,
        conversation_id=conversation_id,
    )


def _validate_session(token: Optional[str], user_id: Optional[str], conversation_id: Optional[str]) -> bool:
    """
    验证会话有效性（Token + 用户身份 + 会话ID）
    
    通常在实际应用中会验证 Token 格式、过期时间等
    这里简化为基础检查
    
    Args:
        token: 访问 Token
        user_id: 用户ID
        conversation_id: 会话ID
    
    Returns:
        验证是否通过
    """
    if not token or not user_id or not conversation_id:
        logger.warning(f"[Session] 会话验证失败: token={bool(token)}, user={bool(user_id)}, conv={bool(conversation_id)}")
        return False
    
    # Token 通常由 auth_service.py 的 verify_token() 方法验证
    # 这里仅作基础检查
    if len(token) < 10:  # UUID Token 应该是合理长度
        logger.warning(f"[Session] Token 格式无效")
        return False
    
    return True


async def process_user_input_stream(
    user_input: str,
    token: Optional[str] = None,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    user_info: Optional[Dict[str, Any]] = None,
    state: Optional[Any] = None,
    context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """
    处理用户输入并流式返回回复 - 校园医务室版本
    
    执行流程：
    1. 验证 Token 和会话有效性
    2. 创建/恢复会话状态
    3. 初始化或恢复 Agent
    4. 执行分类和路由
    5. 流式返回回复
    
    Args:
        user_input: 用户输入文本（必需）
        token: 访问 Token（通过登录获得）
        user_id: 用户ID（从 Token 解析，如手机号）
        conversation_id: 会话ID（同一用户的多个会话）
        user_info: 用户信息字典 (phone, name, role 等)
        state: 当前对话状态（用于状态路由）
        context: 可选上下文信息（上一轮对话记录等）
    
    Yields:
        流式生成的回复文本片段
    
    Raises:
        ValueError: Session 验证失败
        RuntimeError: Agent 初始化失败
    """
    
    # 【步骤 1】验证会话有效性
    if not _validate_session(token, user_id, conversation_id):
        raise ValueError("会话验证失败：无效的 Token 或会话信息")
    
    # 【步骤 2】创建会话对象
    session = ChatSession(user_id=user_id, conversation_id=conversation_id, user_info=user_info)
    
    # 【步骤 3】初始化上下文（如果未提供）
    if context is None:
        context = {}
    
    # 【步骤 4】注入用户认证信息到上下文
    context['user_auth'] = {
        'user_id': user_id,
        'conversation_id': conversation_id,
        'token': token,
        'user_info': user_info or {},
        'timestamp': datetime.now().isoformat(),
    }
    
    # 【步骤 5】注入医学特定的上下文
    context['medical_context'] = {
        'state': state,  # 当前医学状态 (CLASSIFY, DOCTOR_ASSESSMENT, APPOINTMENT, EMERGENCY等)
        'requires_emergency_check': True,  # 是否需要进行紧急症状检查
    }
    
    logger.info(f"[ChatHandler] 处理请求: user={user_id}, conv={conversation_id}, input_len={len(user_input)}")
    
    try:
        # 【步骤 6】为此会话创建 Agent 实例
        task_agent = _build_task_agent(user_id=user_id, conversation_id=conversation_id)
        
        # 【步骤 7】执行分类和路由，流式返回结果
        async for token in task_agent.classify_task_stream(user_input):
            session.update_activity()  # 更新活动时间
            yield token
        
        logger.debug(f"[ChatHandler] 请求完成: user={user_id}, conv={conversation_id}")
        
    except Exception as e:
        logger.error(f"[ChatHandler] 处理失败: {str(e)}", exc_info=True)
        yield f"[ERROR] 处理用户输入失败: {str(e)}"


# 向后兼容别名
async def ProcessUserInput_stream(
    user_input,
    state=None,
    context=None,
    user_id=None,
    conversation_id=None,
    user_info=None,
    token=None
):
    """向后兼容的旧函数名"""
    async for chunk in process_user_input_stream(
        user_input=user_input,
        token=token,
        user_id=user_id,
        conversation_id=conversation_id,
        user_info=user_info,
        state=state,
        context=context,
    ):
        yield chunk
