"""
Redis State Persistence 集成测试

验证会话状态能够跨 Agent 实例持久化
"""
import pytest
from config.constants import StateEnum
from agents.task_classification.state_manager import StateManager


class TestRedisStatePersistence:
    """测试状态持久化功能"""
    
    def test_state_persistence_across_instances(self):
        """测试：会话状态应该在不同 Agent 实例间持久化"""
        # 准备
        user_id = "test_user_persistence_001"
        conversation_id = "conv_persistence_abc123"
        
        # 第一个实例 - 初始化和转换状态
        sm1 = StateManager(user_id, conversation_id)
        assert sm1.get_current_state() == StateEnum.CLASSIFY
        
        sm1.transition_to_doctor_assessment()
        assert sm1.get_current_state() == StateEnum.DOCTOR_ASSESSMENT
        
        # 第二个实例 - 应该读取到持久化的状态
        sm2 = StateManager(user_id, conversation_id)
        assert sm2.get_current_state() == StateEnum.DOCTOR_ASSESSMENT, \
            "新实例应该读取到上一个实例设置的状态"
        
        # 第三个实例 - 继续转换状态
        sm3 = StateManager(user_id, conversation_id)
        sm3.transition_to_appointment()
        assert sm3.get_current_state() == StateEnum.APPOINTMENT
        
        # 第四个实例 - 应该读取最新状态
        sm4 = StateManager(user_id, conversation_id)
        assert sm4.get_current_state() == StateEnum.APPOINTMENT, \
            "应该读取到最新的持久化状态"
    
    def test_different_conversations_have_different_states(self):
        """测试：不同会话应该有不同的状态"""
        # 准备
        user_id = "test_user_multi_conv"
        conv1 = "conv_001"
        conv2 = "conv_002"
        
        # 创建两个不同会话的状态管理器
        sm1 = StateManager(user_id, conv1)
        sm2 = StateManager(user_id, conv2)
        
        # 转换状态
        sm1.transition_to_doctor_assessment()
        sm2.transition_to_appointment()
        
        # 验证状态不同
        assert sm1.get_current_state() == StateEnum.DOCTOR_ASSESSMENT
        assert sm2.get_current_state() == StateEnum.APPOINTMENT
        
        # 重新加载验证状态依然不同
        sm1_reload = StateManager(user_id, conv1)
        sm2_reload = StateManager(user_id, conv2)
        
        assert sm1_reload.get_current_state() == StateEnum.DOCTOR_ASSESSMENT
        assert sm2_reload.get_current_state() == StateEnum.APPOINTMENT
    
    def test_state_reset_persistence(self):
        """测试：状态重置应该也能持久化"""
        # 准备
        user_id = "test_user_reset"
        conversation_id = "conv_reset_123"
        
        # 创建实例并设置状态
        sm1 = StateManager(user_id, conversation_id)
        sm1.transition_to_emergency()
        
        # 重置状态
        sm1.reset_to_classify()
        assert sm1.get_current_state() == StateEnum.CLASSIFY
        
        # 新实例应该读取重置后的状态
        sm2 = StateManager(user_id, conversation_id)
        assert sm2.get_current_state() == StateEnum.CLASSIFY, \
            "新实例应该读取到重置后的状态"
    
    def test_concurrent_conversations(self):
        """测试：并发处理多个用户的多个会话"""
        # 准备
        users_and_convs = [
            ("user_1", "conv_1", StateEnum.DOCTOR_ASSESSMENT),
            ("user_1", "conv_2", StateEnum.APPOINTMENT),
            ("user_2", "conv_1", StateEnum.CONSULT),
            ("user_2", "conv_3", StateEnum.CLASSIFY),
        ]
        
        # 设置所有状态
        managers = []
        for user_id, conv_id, target_state in users_and_convs:
            sm = StateManager(user_id, conv_id)
            if target_state != StateEnum.CLASSIFY:
                # 简单的状态转换
                sm.set_state(target_state)
            managers.append((user_id, conv_id, target_state))
        
        # 验证所有状态正确持久化
        for user_id, conv_id, expected_state in managers:
            sm_verify = StateManager(user_id, conv_id)
            assert sm_verify.get_current_state() == expected_state, \
                f"用户 {user_id} 的会话 {conv_id} 状态应该是 {expected_state.value}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
