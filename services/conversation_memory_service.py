"""
会话记忆服务

统一管理对话历史、槽位数据、摘要记忆、行为记忆和风险事件。
Redis 优先，自动降级到内存存储。

Redis Key 设计（需求文档第 8 节）：
    conversation:{id}:history          — List[Dict]  对话历史
    conversation:{id}:medical_slots    — JSON String  问诊槽位（9 字段）
    conversation:{id}:appointment_slots — JSON String 预约槽位（6 字段）
    conversation:{id}:summary_memory   — JSON String  摘要记忆
    conversation:{id}:behavior_memory  — JSON String  行为记忆
    conversation:{id}:risk_events      — List[Dict]   风险事件
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from config.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# 默认 TTL：7 天
DEFAULT_TTL = 86400 * 7

# ===========================
# 槽位模板
# ===========================

MEDICAL_SLOTS_TEMPLATE: Dict[str, Any] = {
    "user_id": "",
    "name": "",
    "role": "student",
    "grade_or_department": "",
    "chief_complaint": "",
    "symptom_duration": "",
    "accompanying_symptoms": [],
    "allergy_history": [],
    "past_medical_history": [],
    "fever": False,
    "trauma": False,
    "medication_taken": [],
    "red_flags": [],
    # 子状态机字段
    "doctor_sub_state": "initial_assessment",  # initial_assessment | awaiting_confirmation | collecting_symptoms | providing_advice
    "pending_symptom_query": "",  # 暂存的原始问题，用于确认后处理
    "confirmed_symptom": False,  # 用户是否确认有症状
    "pending_questions": [],
    "asked_questions": [],
}

APPOINTMENT_SLOTS_TEMPLATE: Dict[str, Any] = {
    "service_type": "campus_clinic_visit",
    "preferred_date": "",
    "preferred_time_period": "",
    "urgency": "normal",
    "appointment_reason": "",
    "location": "campus_clinic",
    # 子状态机字段
    "appointment_sub_state": "collect_slot",
}


class ConversationMemoryService:
    """会话记忆服务"""

    def __init__(self):
        self.redis = get_redis_client()
        self._memory_fallback: Dict[str, Any] = {}

    # ===========================
    # 对话历史
    # ===========================

    def _history_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:history"

    def append_message(self, conversation_id: str, role: str, content: str) -> None:
        """追加一条消息到对话历史"""
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        payload = json.dumps(message, ensure_ascii=False)

        if self.redis:
            key = self._history_key(conversation_id)
            self.redis.rpush(key, payload)
            self.redis.expire(key, DEFAULT_TTL)
        else:
            fallback_key = self._history_key(conversation_id)
            self._memory_fallback.setdefault(fallback_key, []).append(message)

    def get_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近 N 条对话历史"""
        if self.redis:
            key = self._history_key(conversation_id)
            raw_list = self.redis.lrange(key, -limit, -1)
            return [json.loads(item) for item in raw_list]

        fallback_key = self._history_key(conversation_id)
        history = self._memory_fallback.get(fallback_key, [])
        return history[-limit:]

    def clear_history(self, conversation_id: str) -> None:
        """清除对话历史"""
        if self.redis:
            self.redis.delete(self._history_key(conversation_id))
        else:
            fallback_key = self._history_key(conversation_id)
            self._memory_fallback.pop(fallback_key, None)

    # ===========================
    # 医疗槽位（问诊槽位）
    # ===========================

    def _medical_slots_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:medical_slots"

    def init_medical_slots(self, conversation_id: str) -> Dict[str, Any]:
        """初始化医疗槽位（首次使用时调用）"""
        slots = dict(MEDICAL_SLOTS_TEMPLATE)
        self._set_json(self._medical_slots_key(conversation_id), slots)
        return slots

    def get_medical_slots(self, conversation_id: str) -> Dict[str, Any]:
        """获取医疗槽位，不存在时自动初始化"""
        slots = self._get_json(self._medical_slots_key(conversation_id))
        if slots is None:
            slots = self.init_medical_slots(conversation_id)
        return slots

    def set_medical_slots(self, conversation_id: str, slots: Dict[str, Any]) -> None:
        """设置医疗槽位（全量覆盖）"""
        self._set_json(self._medical_slots_key(conversation_id), slots)

    def merge_medical_slots(self, conversation_id: str, partial: Dict[str, Any]) -> Dict[str, Any]:
        """部分合并医疗槽位（不覆盖已有非空字段）"""
        current = self.get_medical_slots(conversation_id)
        for key, value in partial.items():
            if value is not None and value != "" and value != []:
                current[key] = value
        self.set_medical_slots(conversation_id, current)
        return current

    # ===========================
    # 预约槽位
    # ===========================

    def _appointment_slots_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:appointment_slots"

    def init_appointment_slots(self, conversation_id: str) -> Dict[str, Any]:
        """初始化预约槽位"""
        slots = dict(APPOINTMENT_SLOTS_TEMPLATE)
        self._set_json(self._appointment_slots_key(conversation_id), slots)
        return slots

    def get_appointment_slots(self, conversation_id: str) -> Dict[str, Any]:
        """获取预约槽位，不存在时自动初始化"""
        slots = self._get_json(self._appointment_slots_key(conversation_id))
        if slots is None:
            slots = self.init_appointment_slots(conversation_id)
        return slots

    def set_appointment_slots(self, conversation_id: str, slots: Dict[str, Any]) -> None:
        """设置预约槽位（全量覆盖）"""
        self._set_json(self._appointment_slots_key(conversation_id), slots)

    def merge_appointment_slots(self, conversation_id: str, partial: Dict[str, Any]) -> Dict[str, Any]:
        """部分合并预约槽位"""
        current = self.get_appointment_slots(conversation_id)
        for key, value in partial.items():
            if value is not None and value != "":
                current[key] = value
        self.set_appointment_slots(conversation_id, current)
        return current

    # ===========================
    # 摘要记忆
    # ===========================

    def _summary_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:summary_memory"

    def get_summary(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取会话摘要记忆"""
        return self._get_json(self._summary_key(conversation_id))

    def set_summary(self, conversation_id: str, summary: Dict[str, Any]) -> None:
        """设置会话摘要记忆"""
        self._set_json(self._summary_key(conversation_id), summary)

    # ===========================
    # 行为记忆
    # ===========================

    def _behavior_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:behavior_memory"

    def get_behavior_memory(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取行为记忆"""
        return self._get_json(self._behavior_key(conversation_id))

    def set_behavior_memory(self, conversation_id: str, behavior: Dict[str, Any]) -> None:
        """设置行为记忆"""
        self._set_json(self._behavior_key(conversation_id), behavior)

    # ===========================
    # 风险事件
    # ===========================

    def _risk_events_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:risk_events"

    def add_risk_event(self, conversation_id: str, event: Dict[str, Any]) -> None:
        """追加一条风险事件"""
        event["timestamp"] = event.get("timestamp", time.time())
        payload = json.dumps(event, ensure_ascii=False)

        if self.redis:
            key = self._risk_events_key(conversation_id)
            self.redis.rpush(key, payload)
            self.redis.expire(key, DEFAULT_TTL)
        else:
            fallback_key = self._risk_events_key(conversation_id)
            self._memory_fallback.setdefault(fallback_key, []).append(event)

    def get_risk_events(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取所有风险事件"""
        if self.redis:
            key = self._risk_events_key(conversation_id)
            raw_list = self.redis.lrange(key, 0, -1)
            return [json.loads(item) for item in raw_list]

        fallback_key = self._risk_events_key(conversation_id)
        return self._memory_fallback.get(fallback_key, [])

    def clear_risk_events(self, conversation_id: str) -> None:
        """清除风险事件"""
        if self.redis:
            self.redis.delete(self._risk_events_key(conversation_id))
        else:
            fallback_key = self._risk_events_key(conversation_id)
            self._memory_fallback.pop(fallback_key, None)

    # ===========================
    # 会话摘要自动生成
    # ===========================

    def generate_summary_from_history(self, conversation_id: str) -> Dict[str, Any]:
        """
        从对话历史和槽位数据生成会话摘要

        Args:
            conversation_id: 会话ID

        Returns:
            会话摘要字典，包含关键信息
        """
        # 获取对话历史（最近20条）
        history = self.get_history(conversation_id, limit=20)
        # 获取槽位数据
        medical_slots = self.get_medical_slots(conversation_id)
        appointment_slots = self.get_appointment_slots(conversation_id)

        # 构建摘要
        summary = {
            "conversation_id": conversation_id,
            "last_updated": time.time(),
            "total_messages": len(history),
            "user_info": {
                "user_id": medical_slots.get("user_id"),
                "name": medical_slots.get("name"),
                "role": medical_slots.get("role"),
                "grade_or_department": medical_slots.get("grade_or_department")
            },
            "medical_summary": {
                "chief_complaint": medical_slots.get("chief_complaint"),
                "symptoms": medical_slots.get("accompanying_symptoms", []),
                "has_fever": medical_slots.get("fever", False),
                "has_trauma": medical_slots.get("trauma", False),
                "allergy_history": medical_slots.get("allergy_history", []),
                "past_medical_history": medical_slots.get("past_medical_history", [])
            },
            "appointment_summary": {
                "service_type": appointment_slots.get("service_type"),
                "preferred_date": appointment_slots.get("preferred_date"),
                "preferred_time_period": appointment_slots.get("preferred_time_period"),
                "urgency": appointment_slots.get("urgency"),
                "appointment_reason": appointment_slots.get("appointment_reason")
            },
            "recent_messages": []
        }

        # 添加最近的消息摘要
        for msg in history[-5:]:
            summary["recent_messages"].append({
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": msg.get("timestamp")
            })

        # 清理空值
        summary["user_info"] = {k: v for k, v in summary["user_info"].items() if v}
        summary["medical_summary"] = {k: v for k, v in summary["medical_summary"].items() if v and (v is not False and v != [] and v != "")}
        summary["appointment_summary"] = {k: v for k, v in summary["appointment_summary"].items() if v and v != ""}

        return summary

    def generate_and_save_summary(self, conversation_id: str) -> Dict[str, Any]:
        """
        生成会话摘要并保存到记忆

        Args:
            conversation_id: 会话ID

        Returns:
            生成的摘要
        """
        summary = self.generate_summary_from_history(conversation_id)
        self.set_summary(conversation_id, summary)
        return summary

    def get_or_generate_summary(self, conversation_id: str) -> Dict[str, Any]:
        """
        获取已保存的摘要，如果不存在则自动生成

        Args:
            conversation_id: 会话ID

        Returns:
            会话摘要
        """
        summary = self.get_summary(conversation_id)
        if not summary:
            summary = self.generate_and_save_summary(conversation_id)
        return summary

    # ===========================
    # 跨会话历史管理
    # ===========================

    def get_user_conversations(self, user_id: str) -> List[str]:
        """
        获取指定用户的所有会话ID

        Args:
            user_id: 用户ID

        Returns:
            会话ID列表
        """
        if self.redis:
            conversation_ids = []
            # 扫描所有历史记录key
            for key in self.redis.scan_iter(match="conversation:*:history"):
                key_str = key.decode("utf-8")
                conv_id = key_str.split(":")[1]

                # 检查该会话的用户ID
                medical_slots = self.get_medical_slots(conv_id)
                if medical_slots.get("user_id") == user_id:
                    conversation_ids.append(conv_id)

            # 去重
            return list(set(conversation_ids))
        else:
            # 内存模式下遍历所有key
            conversation_ids = []
            for key in self._memory_fallback:
                if key.startswith("conversation:") and key.endswith(":history"):
                    conv_id = key.split(":")[1]
                    medical_slots = self.get_medical_slots(conv_id)
                    if medical_slots.get("user_id") == user_id:
                        conversation_ids.append(conv_id)

            return list(set(conversation_ids))

    def merge_conversation_history(self, target_conversation_id: str, source_conversation_id: str) -> None:
        """
        将源会话的历史、槽位数据合并到目标会话

        Args:
            target_conversation_id: 目标会话ID
            source_conversation_id: 源会话ID
        """
        # 合并对话历史
        source_history = self.get_history(source_conversation_id)
        for msg in source_history:
            self.append_message(
                target_conversation_id,
                msg.get("role"),
                msg.get("content")
            )

        # 合并医疗槽位
        source_medical_slots = self.get_medical_slots(source_conversation_id)
        self.merge_medical_slots(target_conversation_id, source_medical_slots)

        # 合并预约槽位
        source_appointment_slots = self.get_appointment_slots(source_conversation_id)
        self.merge_appointment_slots(target_conversation_id, source_appointment_slots)

        # 生成合并后的摘要
        self.generate_and_save_summary(target_conversation_id)

    def load_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        加载会话历史（兼容现有接口，实际和get_history一样，保留此方法用于未来扩展）

        Args:
            conversation_id: 会话ID
            limit: 最多加载的消息数

        Returns:
            对话历史列表
        """
        return self.get_history(conversation_id, limit=limit)

    # ===========================
    # 内部 Redis JSON 读写
    # ===========================

    def _get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """从 Redis 读取 JSON，内存模式回退"""
        if self.redis:
            raw = self.redis.get(key)
            if raw:
                return json.loads(raw)
            return None

        return self._memory_fallback.get(key)

    def _set_json(self, key: str, data: Dict[str, Any]) -> None:
        """将 JSON 写入 Redis / 内存"""
        payload = json.dumps(data, ensure_ascii=False, default=str)
        if self.redis:
            self.redis.setex(key, DEFAULT_TTL, payload)
        else:
            self._memory_fallback[key] = data

    def _delete(self, key: str) -> None:
        """删除指定 key（Redis / 内存）"""
        try:
            if self.redis:
                self.redis.delete(key)
            if key in self._memory_fallback:
                del self._memory_fallback[key]
        except Exception:
            pass


# 全局单例
conversation_memory = ConversationMemoryService()
