"""
状态管理器 - 专门负责管理对话状态的流转（支持 Redis 持久化）

职责：
1. 维护当前对话状态（CLASSIFY, APPOINTMENT, CONSULT等）
2. 从 Redis 加载/保存状态
3. 管理状态转换逻辑
4. 提供状态查询和重置功能
5. 确保状态转换的正确性和安全性
"""

import logging
from typing import Optional
from config.constants import StateEnum, StateStorageBase, get_state_storage

logger = logging.getLogger(__name__)


class StateManager:
    """状态管理器 - 从 Redis 中管理对话流程中的状态转换"""

    def __init__(self, user_id: str, conversation_id: str, state_storage: Optional[StateStorageBase] = None):
        """
        初始化状态管理器

        Args:
            user_id: 用户ID（手机号）
            conversation_id: 对话ID（唯一标识一个会话）
            state_storage: 状态存储后端（如为None则自动选择 Redis 或内存）
        """
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.state_storage = state_storage or get_state_storage()

        # 从存储加载初始状态
        self.current_state = self.state_storage.get_state(self.user_id, self.conversation_id)
        logger.debug(f"[StateManager] 初始化: user={user_id}, conv={conversation_id}, state={self.current_state.value}")
    
    @property
    def state(self):
        """向后兼容：返回 SharedState 对象"""
        from config.constants import SharedState
        shared_state = SharedState()
        shared_state.value = self.current_state
        return shared_state
    
    def get_current_state(self) -> StateEnum:
        """获取当前状态"""
        # 从存储重新加载，以防其他进程修改了状态
        self.current_state = self.state_storage.get_state(self.user_id, self.conversation_id)
        return self.current_state
    
    def set_state(self, new_state: StateEnum) -> None:
        """设置新状态并保存到存储"""
        old_state = self.current_state
        self.current_state = new_state
        self.state_storage.set_state(self.user_id, self.conversation_id, new_state)
        logger.info(f"[StateManager] 状态转换: {self.user_id}/{self.conversation_id}: {old_state.value} -> {new_state.value}")
    
    def reset_to_classify(self) -> None:
        """重置状态到分类状态"""
        self.set_state(StateEnum.CLASSIFY)
    
    def should_classify(self) -> bool:
        """判断是否应该进行任务分类"""
        current_state = self.get_current_state()
        return current_state == StateEnum.CLASSIFY or current_state is None
    
    def is_in_appointment_flow(self) -> bool:
        """判断是否在预约流程中"""
        return self.get_current_state() == StateEnum.APPOINTMENT
    
    def is_in_consultation_flow(self) -> bool:
        """判断是否在咨询流程中"""
        return self.get_current_state() == StateEnum.CONSULT
    
    def is_in_doctor_assessment(self) -> bool:
        """判断是否在医生评估流程中"""
        return self.get_current_state() == StateEnum.DOCTOR_ASSESSMENT
    
    def is_emergency(self) -> bool:
        """判断是否在紧急状态"""
        return self.get_current_state() == StateEnum.EMERGENCY
    
    def transition_to_appointment(self) -> None:
        """转换到医生预约状态"""
        self.set_state(StateEnum.APPOINTMENT)
    
    def transition_to_consultation(self) -> None:
        """转换到咨询状态"""
        self.set_state(StateEnum.CONSULT)
    
    def transition_to_doctor_assessment(self) -> None:
        """转换到医生评估状态"""
        self.set_state(StateEnum.DOCTOR_ASSESSMENT)
    
    def transition_to_emergency(self) -> None:
        """转换到紧急状态"""
        self.set_state(StateEnum.EMERGENCY)
    
    def get_state_description(self) -> str:
        """获取当前状态的描述"""
        state = self.get_current_state()
        descriptions = {
            StateEnum.CLASSIFY: "任务分类状态 - 等待识别用户意图",
            StateEnum.APPOINTMENT: "医生预约流程状态 - 正在处理预约请求",
            StateEnum.CONSULT: "咨询流程状态 - 正在处理医学咨询请求",
            StateEnum.DOCTOR_ASSESSMENT: "医生评估状态 - 医生正在评估症状",
            StateEnum.EMERGENCY: "紧急状态 - 检测到红旗症状"
        }
        return descriptions.get(state, "未知状态")
    
    def can_transition_to(self, target_state: StateEnum) -> bool:
        """检查是否可以转换到目标状态"""
        current_state = self.get_current_state()
        
        # 定义允许的状态转换
        allowed_transitions = {
            StateEnum.CLASSIFY: [StateEnum.APPOINTMENT, StateEnum.CONSULT, StateEnum.EMERGENCY, StateEnum.DOCTOR_ASSESSMENT],
            StateEnum.APPOINTMENT: [StateEnum.CLASSIFY, StateEnum.EMERGENCY],
            StateEnum.CONSULT: [StateEnum.CLASSIFY, StateEnum.EMERGENCY, StateEnum.DOCTOR_ASSESSMENT],
            StateEnum.DOCTOR_ASSESSMENT: [StateEnum.APPOINTMENT, StateEnum.CLASSIFY, StateEnum.EMERGENCY],
            StateEnum.EMERGENCY: [StateEnum.CLASSIFY]
        }
        
        return target_state in allowed_transitions.get(current_state, [])
    
    def force_reset(self) -> None:
        """强制重置状态（用于错误恢复）"""
        logger.warning(f"[StateManager] 强制重置状态: {self.user_id}/{self.conversation_id}")
        self.reset_to_classify()
    
    def get_state_info(self) -> dict:
        """获取状态信息（用于调试和日志）"""
        return {
            'user_id': self.user_id,
            'conversation_id': self.conversation_id,
            'current_state': self.get_current_state().value,
            'description': self.get_state_description()
        }
