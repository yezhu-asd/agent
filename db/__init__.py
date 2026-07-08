"""
Database Module

校园医务室数据库模块，包含：
- 数据模型（Doctor、DoctorSchedule、ConsultationRecord 等）
- 数据仓库（DoctorRepository、ConsultationRepository、KnowledgeRepository）
- 数据库路由器（DatabaseRouter）
- 基础会话管理
"""

from .db_router import DatabaseRouter, TechnicianDBRouter, DoctorDBRouter, KnowledgeDBRouter, UserBehaviorDBRouter
from .repositories import (
    DoctorRepository, TechnicianRepository, KnowledgeRepository,
    ConsultationRepository, UserBehaviorRepository,
)
from .base import SessionManager
from .models import (
    Base,
    Doctor, DoctorSchedule, KnowledgeDocument,
    ConsultationRecord, MedicalPreference, HealthRecommendation, RiskEvent,
    # 向后兼容别名
    Technician, TechnicianSchedule,
    UserBehavior, UserPreference, UserRecommendation,
)

__all__ = [
    # 主要入口
    'DatabaseRouter',

    # 路由器
    'TechnicianDBRouter', 'DoctorDBRouter', 'KnowledgeDBRouter', 'UserBehaviorDBRouter',

    # 核心仓库
    'DoctorRepository', 'KnowledgeRepository', 'ConsultationRepository',

    # 向后兼容仓库别名
    'TechnicianRepository', 'UserBehaviorRepository',

    # 基础设施
    'SessionManager',

    # 核心模型
    'Base',
    'Doctor', 'DoctorSchedule', 'KnowledgeDocument',
    'ConsultationRecord', 'MedicalPreference', 'HealthRecommendation', 'RiskEvent',

    # 向后兼容模型别名
    'Technician', 'TechnicianSchedule',
    'UserBehavior', 'UserPreference', 'UserRecommendation',
]
