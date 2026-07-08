"""
Token 集成测试 - 验证 user_id 和 conversation_id 的正确传递
"""
import asyncio
import pytest
from agents.task_classification_agent import TaskClassificationAgent
from agents.appointment_agent import AppointmentAgent
from agents.consultant_agent import ConsultantAgent


class TestTokenIntegration:
    """测试 Token 登录信息集成"""
    
    def test_should_create_agent_with_user_id_and_conversation_id(self):
        """测试：应该能创建带有 user_id 和 conversation_id 的 Agent"""
        # 准备
        user_id = "13800138000"
        conversation_id = "conv_123456"
        
        appointment_agent = AppointmentAgent(user_id=user_id, conversation_id=conversation_id)
        consultant_agent = ConsultantAgent(user_id=user_id, conversation_id=conversation_id)
        
        # 执行
        agent = TaskClassificationAgent(
            appointment_agent=appointment_agent,
            consultant_agent=consultant_agent,
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        # 验证
        assert agent.user_id == user_id, "user_id 应该被正确设置"
        assert agent.conversation_id == conversation_id, "conversation_id 应该被正确设置"
        assert agent.appointment_agent.user_id == user_id, "appointment_agent 的 user_id 应该被正确设置"
        assert agent.appointment_agent.conversation_id == conversation_id, "appointment_agent 的 conversation_id 应该被正确设置"
        assert agent.consultant_agent.user_id == user_id, "consultant_agent 的 user_id 应该被正确设置"
        assert agent.consultant_agent.conversation_id == conversation_id, "consultant_agent 的 conversation_id 应该被正确设置"
    
    def test_should_support_set_user_context(self):
        """测试：应该能动态设置用户上下文"""
        # 准备
        appointment_agent = AppointmentAgent()
        consultant_agent = ConsultantAgent()
        agent = TaskClassificationAgent(
            appointment_agent=appointment_agent,
            consultant_agent=consultant_agent
        )
        
        # 初始状态
        assert agent.user_id is None, "初始 user_id 应该为 None"
        assert agent.conversation_id is None, "初始 conversation_id 应该为 None"
        
        # 执行
        user_id = "13800138000"
        conversation_id = "conv_789012"
        agent.set_user_context(user_id, conversation_id)
        
        # 验证
        assert agent.user_id == user_id, "user_id 应该被正确设置"
        assert agent.conversation_id == conversation_id, "conversation_id 应该被正确设置"
    
    def test_should_maintain_backward_compatibility(self):
        """测试：应该保持向后兼容性（不传入 user_id 和 conversation_id）"""
        # 准备
        appointment_agent = AppointmentAgent()
        consultant_agent = ConsultantAgent()
        
        # 执行 - 不传入 user_id 和 conversation_id
        agent = TaskClassificationAgent(
            appointment_agent=appointment_agent,
            consultant_agent=consultant_agent
        )
        
        # 验证
        assert agent.user_id is None, "如果不传入，user_id 应该为 None"
        assert agent.conversation_id is None, "如果不传入，conversation_id 应该为 None"
        # 应该能正常调用 reset_conversation
        try:
            agent.reset_conversation()
        except Exception as e:
            pytest.fail(f"重置对话时出错：{e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
