import logging

from config.constants import SharedState, StateEnum

logger = logging.getLogger(__name__)

try:
    from .appointment_agent import AppointmentAgent
except Exception as exc:
    logger.warning("AppointmentAgent 加载失败，已降级为空: %s", exc)
    AppointmentAgent = None

try:
    from .consultant_agent import ConsultantAgent
except Exception as exc:
    logger.warning("ConsultantAgent 加载失败，已降级为空: %s", exc)
    ConsultantAgent = None

try:
    from .task_classification_agent import TaskClassificationAgent
except Exception as exc:
    logger.warning("TaskClassificationAgent 加载失败，已降级为空: %s", exc)
    TaskClassificationAgent = None

__all__ = [
    'AppointmentAgent',
    'ConsultantAgent', 
    'TaskClassificationAgent',
    'SharedState',
    'StateEnum'
]
