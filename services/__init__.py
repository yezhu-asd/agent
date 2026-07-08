"""
业务服务层模块

包含：
- 知识库服务
- 技师服务
- 预约服务
- 健康追踪服务
- 推荐调度服务
- 文本嵌入工具
- 会话记忆服务（Redis 优先）
"""

import logging

logger = logging.getLogger(__name__)

try:
    from .text_embedding import (
        embed_input,
        find_best_match_indices,
        save_doctor_embeddings as save_technician_embeddings,
        load_doctor_embeddings as load_technician_embeddings,
    )
except Exception as exc:
    logger.warning("文本嵌入工具加载失败，已降级为空实现: %s", exc)

    def _missing_dependency(*args, **kwargs):
        raise RuntimeError("文本嵌入工具不可用，请先安装 faiss 等依赖")

    embed_input = _missing_dependency
    find_best_match_indices = _missing_dependency
    save_technician_embeddings = _missing_dependency
    load_technician_embeddings = _missing_dependency

try:
    from .knowledge_service import KnowledgeService
except Exception as exc:
    logger.warning("KnowledgeService 加载失败，已降级为空: %s", exc)
    KnowledgeService = None

try:
    from .technician_service import TechnicianService
except Exception as exc:
    logger.warning("TechnicianService 加载失败，已降级为空: %s", exc)
    TechnicianService = None

try:
    from .appointment_service import AppointmentService
except Exception as exc:
    logger.warning("AppointmentService 加载失败，已降级为空: %s", exc)
    AppointmentService = None

try:
    from .user_behavior_service import UserBehaviorService
except Exception as exc:
    logger.warning("UserBehaviorService 加载失败，已降级为空: %s", exc)
    UserBehaviorService = None

try:
    from .recommendation_service import RecommendationService
except Exception as exc:
    logger.warning("RecommendationService 加载失败，已降级为空: %s", exc)
    RecommendationService = None

try:
    from .conversation_memory_service import ConversationMemoryService, conversation_memory
except Exception as exc:
    logger.warning("ConversationMemoryService 加载失败，已降级为空: %s", exc)
    ConversationMemoryService = None
    conversation_memory = None

__all__ = [
    'embed_input',
    'find_best_match_indices',
    'save_technician_embeddings',
    'load_technician_embeddings',
    'KnowledgeService',
    'TechnicianService',
    'AppointmentService',
    'UserBehaviorService',
    'RecommendationService',
    'ConversationMemoryService',
    'conversation_memory',
]
