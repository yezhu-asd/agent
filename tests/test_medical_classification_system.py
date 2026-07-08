"""
医学分类系统集成测试 - 验证 Section 2.2 子模块重构

测试场景：
1. 医学任务分类 - 验证5类分类正确性
2. 紧急症状识别 - 验证红旗症状检测
3. 医学路由流程 - 验证各类路由是否正确
4. 无关请求处理 - 验证医学语境下的无关请求处理
5. 会话状态管理 - 验证状态转换和持久化
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from agents.task_classification.task_classifier import TaskClassifier
from agents.task_classification.state_manager import StateManager
from agents.task_classification.agent_router import AgentRouter
from agents.task_classification.unrelated_handler import UnrelatedHandler
from agents.task_classification.classification_processor import ClassificationProcessor


class TestMedicalTaskClassifier:
    """测试医学任务分类器"""
    
    @pytest.fixture
    def mock_llm(self):
        """创建模拟LLM"""
        llm = Mock()
        return llm
    
    @pytest.fixture
    def classifier(self, mock_llm):
        """创建分类器实例"""
        return TaskClassifier(mock_llm)
    
    @pytest.mark.asyncio
    async def test_classify_doctor_consultation(self, classifier):
        """测试医生问诊分类"""
        # 创建mock响应对象
        mock_response = Mock()
        mock_response.content = "doctor"
        
        # 直接替换chain为AsyncMock（使用__dict__绕过Pydantic限制）
        classifier.__dict__['chain'] = AsyncMock(ainvoke=AsyncMock(return_value=mock_response))
        
        # 使用不包含红旗症状的输入来测试LLM分类
        result = await classifier.classify_task("我感冒了，需要医生看一下")
        assert result == 'doctor'
    
    @pytest.mark.asyncio
    async def test_classify_appointment(self, classifier):
        """测试预约分类"""
        mock_response = Mock()
        mock_response.content = "appointment"
        
        classifier.__dict__['chain'] = AsyncMock(ainvoke=AsyncMock(return_value=mock_response))
        
        result = await classifier.classify_task("我想预约看医生")
        assert result == 'appointment'
    
    @pytest.mark.asyncio
    async def test_classify_faq(self, classifier):
        """测试健康知识分类"""
        mock_response = Mock()
        mock_response.content = "faq"
        
        classifier.__dict__['chain'] = AsyncMock(ainvoke=AsyncMock(return_value=mock_response))
        
        result = await classifier.classify_task("感冒应该怎么预防")
        assert result == 'faq'
    
    @pytest.mark.asyncio
    async def test_classify_emergency(self, classifier):
        """测试紧急症状分类"""
        # 应该通过红旗症状快速检测
        result = await classifier.classify_task("我胸痛")
        assert result == 'emergency'
    
    @pytest.mark.asyncio
    async def test_classify_chat(self, classifier):
        """测试闲聊分类"""
        mock_response = Mock()
        mock_response.content = "chat"
        async def mock_invoke(inputs):
            return mock_response
        classifier.chain = AsyncMock(side_effect=mock_invoke)
        
        result = await classifier.classify_task("你好")
        assert result == 'chat'
    
    def test_red_flag_detection(self, classifier):
        """测试红旗症状检测"""
        assert classifier._is_emergency("我胸痛") == True
        assert classifier._is_emergency("呼吸困难") == True
        assert classifier._is_emergency("大出血") == True
        assert classifier._is_emergency("头疼") == False
    
    def test_category_description(self, classifier):
        """测试分类描述"""
        desc = classifier.get_category_description('doctor')
        assert '医生' in desc or '症状' in desc
        
        desc = classifier.get_category_description('emergency')
        assert '紧急' in desc or '危急' in desc


class TestMedicalStateManager:
    """测试医学状态管理器"""
    
    @pytest.fixture
    def state_manager(self):
        """创建状态管理器"""
        return StateManager(user_id="test_user", conversation_id="test_conv")
    
    def test_initial_state_is_classify(self, state_manager):
        """测试初始状态为分类"""
        assert state_manager.should_classify() == True
    
    def test_transition_to_doctor_assessment(self, state_manager):
        """测试医生评估状态转换"""
        state_manager.transition_to_doctor_assessment()
        assert state_manager.is_in_doctor_assessment() == True
        assert state_manager.should_classify() == False
    
    def test_transition_to_appointment(self, state_manager):
        """测试预约状态转换"""
        state_manager.transition_to_appointment()
        assert state_manager.is_in_appointment_flow() == True
    
    def test_transition_to_emergency(self, state_manager):
        """测试紧急状态转换"""
        from config.constants import StateEnum
        state_manager.transition_to_emergency()
        assert state_manager.get_current_state() == StateEnum.EMERGENCY
    
    def test_state_persistence_save_and_load(self, state_manager):
        """测试状态持久化"""
        # 设置状态
        state_manager.transition_to_doctor_assessment()
        saved_state = state_manager.get_current_state()
        
        # 创建新实例并验证状态加载
        new_manager = StateManager(user_id="test_user", conversation_id="test_conv")
        loaded_state = new_manager.get_current_state()
        
        assert saved_state == loaded_state


class TestMedicalAgentRouter:
    """测试医学路由器"""
    
    @pytest.fixture
    def router(self):
        """创建路由器"""
        mock_appointment_agent = Mock()
        mock_consultant_agent = Mock()
        mock_state_manager = Mock()
        mock_state_manager.transition_to_emergency = Mock()
        mock_state_manager.transition_to_doctor_assessment = Mock()
        mock_state_manager.transition_to_appointment = Mock()
        
        return AgentRouter(
            appointment_agent=mock_appointment_agent,
            consultant_agent=mock_consultant_agent,
            state_manager=mock_state_manager
        )
    
    @pytest.mark.asyncio
    async def test_route_to_emergency(self, router):
        """测试紧急路由"""
        # 模拟紧急响应
        async def mock_emergency():
            yield "⚠️ 紧急处理"
        
        router.consultant_agent.assess_emergency = AsyncMock(side_effect=mock_emergency)
        
        # 收集所有响应
        responses = []
        async for token in router.route_to_emergency("我胸痛"):
            responses.append(token)
        
        # 验证包含紧急提示
        full_response = "".join(responses)
        assert "⚠️" in full_response or "紧急" in full_response or "120" in full_response
    
    @pytest.mark.asyncio
    async def test_route_to_doctor_consultation(self, router):
        """测试医生咨询路由"""
        async def mock_assessment():
            yield "医生评估结果"
        
        router.consultant_agent.assess_symptoms = AsyncMock(side_effect=mock_assessment)
        
        responses = []
        async for token in router.route_to_doctor_consultation("我头疼"):
            responses.append(token)
        
        assert len(responses) > 0
    
    @pytest.mark.asyncio
    async def test_route_to_appointment(self, router):
        """测试预约路由"""
        async def mock_appointment():
            yield "预约成功"
        
        router.appointment_agent.run_stream = AsyncMock(side_effect=mock_appointment)
        
        responses = []
        async for token in router.route_to_appointment("我想预约"):
            responses.append(token)
        
        assert len(responses) > 0


class TestUnrelatedHandler:
    """测试无关请求处理器"""
    
    @pytest.fixture
    def handler(self):
        """创建无关请求处理器"""
        mock_state_manager = Mock()
        return UnrelatedHandler(mock_state_manager)
    
    @pytest.mark.asyncio
    async def test_handle_unrelated_async(self, handler):
        """测试异步处理无关请求"""
        responses = []
        async for token in handler.handle_unrelated_async("你好"):
            responses.append(token)
        
        full_response = "".join(responses)
        # 应该包含医学语境提示
        assert "医学" in full_response or "医务室" in full_response or "健康" in full_response
    
    @pytest.mark.asyncio
    async def test_handle_unrelated_sync(self, handler):
        """测试同步处理无关请求"""
        result = await handler.handle_unrelated_sync("你好")
        assert isinstance(result, str)
        assert len(result) > 0


class TestClassificationProcessor:
    """测试医学分类流程处理器"""
    
    @pytest.fixture
    def processor(self):
        """创建分类流程处理器"""
        mock_classifier = Mock(spec=TaskClassifier)
        mock_state_manager = Mock(spec=StateManager)
        mock_router = Mock(spec=AgentRouter)
        mock_handler = Mock(spec=UnrelatedHandler)
        
        mock_state_manager.should_classify.return_value = True
        mock_state_manager.get_current_state.return_value = 'CLASSIFY'
        
        return ClassificationProcessor(
            mock_classifier,
            mock_state_manager,
            mock_router,
            mock_handler
        )
    
    @pytest.mark.asyncio
    async def test_get_state_info(self, processor):
        """测试获取状态信息"""
        processor.agent_router.get_available_services = Mock(return_value={'doctor': True})
        
        info = processor.get_current_state_info()
        assert 'current_state' in info
        assert 'available_medical_services' in info
        assert 'classification_stats' in info
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, processor):
        """测试统计信息追踪"""
        stats = processor.get_statistics()
        assert 'total_classifications' in stats
        assert 'emergencies_detected' in stats
        
        # 初始应该是0
        assert stats['total_classifications'] == 0
        assert stats['emergencies_detected'] == 0


class TestMedicalClassificationIntegration:
    """医学分类系统集成测试"""
    
    @pytest.mark.asyncio
    async def test_doctor_inquiry_flow(self):
        """测试医生问诊流程"""
        mock_llm = Mock()
        classifier = TaskClassifier(mock_llm)
        
        # 模拟医生问诊分类
        mock_response = Mock()
        mock_response.content = "doctor"
        
        classifier.__dict__['chain'] = AsyncMock(ainvoke=AsyncMock(return_value=mock_response))
        
        category = await classifier.classify_task("我最近感冒了")
        assert category == 'doctor'
    
    @pytest.mark.asyncio
    async def test_emergency_detection_and_escalation(self):
        """测试紧急症状检测和升级"""
        mock_llm = Mock()
        classifier = TaskClassifier(mock_llm)
        
        # 直接检测红旗症状（不调用LLM）
        category = await classifier.classify_task("我胸痛严重")
        assert category == 'emergency'
    
    @pytest.mark.asyncio  
    async def test_state_persistence_across_requests(self):
        """测试跨请求的状态持久化"""
        state1 = StateManager(user_id="user1", conversation_id="conv1")
        state1.transition_to_doctor_assessment()
        state1_status = state1.get_current_state()
        
        # 模拟新请求中加载状态
        state2 = StateManager(user_id="user1", conversation_id="conv1")
        state2_status = state2.get_current_state()
        
        assert state1_status == state2_status
        assert state2.is_in_doctor_assessment() == True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
