"""
Repositories Module - 医学化版本

数据访问对象模块，包含：
- 医生数据仓库（替代技师仓库）
- 知识库数据仓库  
- 问诊记录与健康追踪数据仓库
"""

from .doctor_repository import DoctorRepository, TechnicianRepository
from .knowledge_repository import KnowledgeRepository
from .consultation_repository import ConsultationRepository
from .user_behavior_repository import UserBehaviorRepository

__all__ = [
    'DoctorRepository',
    'TechnicianRepository',  # 向后兼容别名
    'KnowledgeRepository',
    'ConsultationRepository',
    'UserBehaviorRepository'  # 向后兼容别名
]
