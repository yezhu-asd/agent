"""
常量定义和全局配置

包含：
1. 状态枚举（StateEnum）
2. 状态存储系统（支持内存和 Redis）
3. 业务常量
"""

import json
import logging
import os
import time
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

busy_periods_dict = {}  # { technician_id: [ {"start": "...", "end": "..."} ] }


class StateEnum(Enum):
    """对话状态枚举"""
    CLASSIFY = "classify"
    APPOINTMENT = "appointment"
    CONSULT = "consult"
    DOCTOR_ASSESSMENT = "doctor_assessment"
    EMERGENCY = "emergency"
    OTHER = "other"


class SharedState:
    """内存状态对象（向后兼容）"""
    def __init__(self):
        self.value = StateEnum.CLASSIFY


# ===========================
# State Storage System (Redis)
# ===========================

class StateStorageBase:
    """会话状态存储基类"""
    
    def get_state(self, user_id: str, conversation_id: str) -> Optional[StateEnum]:
        """获取会话状态"""
        raise NotImplementedError
    
    def set_state(self, user_id: str, conversation_id: str, state: StateEnum, ttl_seconds: int = 86400) -> None:
        """设置会话状态"""
        raise NotImplementedError
    
    def delete_state(self, user_id: str, conversation_id: str) -> None:
        """删除会话状态"""
        raise NotImplementedError


class InMemoryStateStorage(StateStorageBase):
    """内存会话状态存储"""
    
    def __init__(self):
        self._states: Dict[str, Dict[str, str]] = {}  # {user_id: {conversation_id: state_value}}
    
    @staticmethod
    def _make_key(user_id: str, conversation_id: str) -> str:
        return f"{user_id}::{conversation_id}"
    
    def get_state(self, user_id: str, conversation_id: str) -> Optional[StateEnum]:
        """获取会话状态"""
        key = self._make_key(user_id, conversation_id)
        state_value = self._states.get(key)
        if state_value:
            try:
                return StateEnum(state_value)
            except (ValueError, KeyError):
                return StateEnum.CLASSIFY
        return StateEnum.CLASSIFY
    
    def set_state(self, user_id: str, conversation_id: str, state: StateEnum, ttl_seconds: int = 86400) -> None:
        """设置会话状态"""
        key = self._make_key(user_id, conversation_id)
        self._states[key] = state.value
        logger.debug(f"[State] 内存存储: {user_id}/{conversation_id} -> {state.value}")
    
    def delete_state(self, user_id: str, conversation_id: str) -> None:
        """删除会话状态"""
        key = self._make_key(user_id, conversation_id)
        if key in self._states:
            del self._states[key]


class RedisStateStorage(StateStorageBase):
    """Redis 会话状态存储"""
    
    def __init__(self, redis_client: Any):
        self.redis = redis_client
    
    @staticmethod
    def _make_key(user_id: str, conversation_id: str) -> str:
        return f"state:{user_id}:{conversation_id}"
    
    def get_state(self, user_id: str, conversation_id: str) -> Optional[StateEnum]:
        """获取会话状态"""
        key = self._make_key(user_id, conversation_id)
        try:
            state_value = self.redis.get(key)
            if state_value:
                if isinstance(state_value, bytes):
                    state_value = state_value.decode('utf-8')
                return StateEnum(state_value)
        except Exception as e:
            logger.warning(f"[State] Redis 读取失败: {e}")
        return StateEnum.CLASSIFY
    
    def set_state(self, user_id: str, conversation_id: str, state: StateEnum, ttl_seconds: int = 86400) -> None:
        """设置会话状态"""
        key = self._make_key(user_id, conversation_id)
        try:
            ttl = max(1, ttl_seconds)
            self.redis.setex(key, ttl, state.value)
            logger.debug(f"[State] Redis 存储: {user_id}/{conversation_id} -> {state.value} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"[State] Redis 写入失败: {e}")
    
    def delete_state(self, user_id: str, conversation_id: str) -> None:
        """删除会话状态"""
        key = self._make_key(user_id, conversation_id)
        try:
            self.redis.delete(key)
        except Exception as e:
            logger.warning(f"[State] Redis 删除失败: {e}")


def get_state_storage() -> StateStorageBase:
    """获取全局 State 存储实例（自动选择 Redis 或内存）- 单例模式"""
    global _state_storage_instance

    if '_state_storage_instance' not in globals():
        from config.redis_client import get_redis_client
        redis_client = get_redis_client()
        if redis_client:
            try:
                _state_storage_instance = RedisStateStorage(redis_client)
                logger.info("✓ 使用 Redis State 存储")
            except Exception as e:
                logger.warning(f"Redis State 存储不可用: {e}，降级到内存存储")
                _state_storage_instance = InMemoryStateStorage()
        else:
            logger.info("使用内存 State 存储")
            _state_storage_instance = InMemoryStateStorage()

    return _state_storage_instance


# ===========================
# 校园医务室 - 医学分类标签
# ===========================

class MedicalClassification:
    """医学任务分类标签 - 用于任务分类和文本标签化"""
    
    # 5 种分类
    DOCTOR = "doctor"                    # 医生问诊 - 用户报告症状需要医生评估
    APPOINTMENT = "appointment"          # 医生预约 - 用户想预约挂号
    FAQ = "faq"                         # 健康咨询 - 用户询问医学知识（不是个人症状）
    EMERGENCY = "emergency"              # 紧急升级 - 检测到危急症状，需要立即处理
    CHAT = "chat"                       # 闲聊/无关 - 与医学无关的请求
    
    # 所有分类
    ALL_CLASSIFICATIONS = {DOCTOR, APPOINTMENT, FAQ, EMERGENCY, CHAT}
    
    # 分类描述
    DESCRIPTIONS = {
        DOCTOR: "医生问诊 - 用户报告症状，需要医生评估和建议",
        APPOINTMENT: "医生预约 - 用户明确要预约看医生",
        FAQ: "健康咨询 - 用户询问医学知识（如何预防感冒、骨折恢复时间等）",
        EMERGENCY: "紧急升级 - 检测到危急症状（胸痛、呼吸困难等），需要立即处理",
        CHAT: "闲聊/无关 - 与医学无关的请求（天气、食堂位置等）"
    }
    
    @staticmethod
    def is_valid(classification: str) -> bool:
        """检查分类是否有效"""
        return classification in MedicalClassification.ALL_CLASSIFICATIONS
    
    @staticmethod
    def get_description(classification: str) -> str:
        """获取分类的人类可读描述"""
        return MedicalClassification.DESCRIPTIONS.get(
            classification,
            f"未知分类: {classification}"
        )


# ===========================
# 校园医务室 - 红旗症状关键词
# ===========================

class RedFlagSymptoms:
    """紧急症状关键词 - 用于快速检测危急情况"""
    
    # 胸/心脏相关
    CHEST_RELATED = {'胸痛', '左胸痛', '右胸痛', '心梗', '心脏', '心绞痛'}
    
    # 呼吸相关
    BREATHING_RELATED = {'呼吸困难', '喘不上气', '窒息', '呼吸急促'}
    
    # 意识相关
    CONSCIOUSNESS_RELATED = {'晕倒', '昏迷', '失去意识', '不省人事'}
    
    # 出血相关
    BLEEDING_RELATED = {'大出血', '严重出血', '失血', '大量出血'}
    
    # 神经相关
    NEUROLOGICAL_RELATED = {'脑中风', '中风', '卒中', '瘫痪', '半身不遂'}
    
    # 自伤相关
    SELF_HARM_RELATED = {'割腕', '自杀', '服毒', '中毒', '吞药'}
    
    # 外伤相关
    TRAUMA_RELATED = {'尖锐物扎', '刀砍', '枪伤', '烧伤', '触电', '意外', '创伤', '外伤', '骨折', '脱臼'}
    
    # 所有红旗症状
    ALL_SYMPTOMS = (CHEST_RELATED | BREATHING_RELATED | CONSCIOUSNESS_RELATED |
                    BLEEDING_RELATED | NEUROLOGICAL_RELATED | SELF_HARM_RELATED |
                    TRAUMA_RELATED)
    
    @staticmethod
    def is_emergency(text: str) -> bool:
        """检查文本是否包含红旗症状"""
        text_lower = text.lower()
        for symptom in RedFlagSymptoms.ALL_SYMPTOMS:
            if symptom in text_lower:
                return True
        return False
    
    @staticmethod
    def get_category(symptom: str) -> str:
        """获取症状属于的类别"""
        if symptom in RedFlagSymptoms.CHEST_RELATED:
            return "胸/心脏"
        elif symptom in RedFlagSymptoms.BREATHING_RELATED:
            return "呼吸系统"
        elif symptom in RedFlagSymptoms.CONSCIOUSNESS_RELATED:
            return "意识系统"
        elif symptom in RedFlagSymptoms.BLEEDING_RELATED:
            return "出血"
        elif symptom in RedFlagSymptoms.NEUROLOGICAL_RELATED:
            return "神经系统"
        elif symptom in RedFlagSymptoms.SELF_HARM_RELATED:
            return "自伤"
        elif symptom in RedFlagSymptoms.TRAUMA_RELATED:
            return "外伤"
        return "未知"


# ===========================
# 校园医务室服务信息
# ===========================

class MedicalFacilityInfo:
    """校园医务室设施信息"""
    
    # 医务室基本信息
    NAME = "校园医务室"
    LOCATION = "校园医务楼一楼"
    
    # 紧急联系
    EMERGENCY_HOTLINE = "120"
    CAMPUS_MEDICAL_PHONE = "学校医务室电话"
    
    # 服务时间示例
    SERVICE_HOURS = "周一至周五 8:00-18:00，周六日 9:00-17:00"
    
    # 医学免责声明
    MEDICAL_DISCLAIMER = "本系统仅供参考，确诊需要医生面诊，不能全部替代医生诊断。"
    
    # 紧急情况处理建议
    EMERGENCY_INSTRUCTIONS = (
        "如果出现以下症状，请立即拨打 120 或直接前往医院：\n"
        "• 胸痛、呼吸困难\n"
        "• 意识模糊、昏迷\n"
        "• 严重出血\n"
        "• 中风症状（口歪眼斜、半身瘫痪）\n"
        "• 其他可能危及生命的症状"
    )
