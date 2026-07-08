"""
健康追踪模块

提供健康追踪相关的核心组件（简化版）：
- BehaviorRecorder: 记录器 - 记录追踪数据
- PatternAnalyzer: 模式分析器 - 分析健康追踪数据和生成随访提醒
- PreferenceManager: 偏好管理器 - 管理健康偏好数据
"""

from .behavior_recorder import BehaviorRecorder
from .pattern_analyzer import PatternAnalyzer
from .preference_manager import PreferenceManager

__all__ = [
    'BehaviorRecorder',
    'PatternAnalyzer',
    'PreferenceManager'
]
