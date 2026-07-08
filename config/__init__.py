"""
配置模块

提供应用程序所需的常量、基本配置和环境变量管理
"""

from .constants import StateEnum, SharedState, busy_periods_dict
from .constants import MedicalClassification, RedFlagSymptoms, MedicalFacilityInfo
from .settings import settings

__all__ = [
    # 常量和状态
    'StateEnum',
    'SharedState',
    'busy_periods_dict',

    # 医学分类
    'MedicalClassification',
    'RedFlagSymptoms',
    'MedicalFacilityInfo',

    # 全局设置
    'settings'
]
