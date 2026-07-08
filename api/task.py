"""
医学任务分类 API 端点

职责：
1. 对用户输入进行医学分类（doctor/appointment/faq/emergency/chat）
2. 检测紧急症状并快速升级
3. 返回分类结果和诊疗建议
4. 更新会话状态
"""

import logging
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
import uuid

from api.core.response_models import (
    TaskClassificationRequest,
    TaskClassificationResponse,
    ErrorResponse,
)
from api.auth import extract_token_from_header, verify_token
from services.auth_service import auth_service
from config.constants import MedicalClassification, RedFlagSymptoms
from agents.task_classification.task_classifier import TaskClassifier
from agents.task_classification.state_manager import StateManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/medical", tags=["医学分类"])


@router.post("/classify", response_model=TaskClassificationResponse)
async def classify_task(
    request: TaskClassificationRequest,
    authorization: Optional[str] = Header(default=None),
) -> TaskClassificationResponse:
    """
    医学任务分类端点
    
    对用户输入进行医学分类，返回分类标签、症状检测和后续建议。
    
    分类结果:
    - doctor: 医生问诊 - 用户报告症状，需要医生评估
    - appointment: 医生预约 - 用户明确要预约
    - faq: 健康咨询 - 用户询问医学知识
    - emergency: 紧急症状 - 检测到危急症状，需要立即处理
    - chat: 闲聊/无关 - 与医学无关的请求
    
    Args:
        request: 分类请求（包含用户输入文本）
        authorization: Bearer Token（通过登录获得）
    
    Returns:
        TaskClassificationResponse: 分类结果和医学建议
    
    Raises:
        HTTPException: 未登录、Token 失效或处理失败
    """
    
    try:
        # 【步骤 1】验证并解析 Token
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="未登录或 Token 格式错误，请使用 'Authorization: Bearer <token>'"
            )
        
        # 【步骤 2】验证 Token 有效性
        user_id = verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 已失效或无效，请重新登录")
        
        # 【步骤 3】获取或创建 conversation_id
        session = auth_service.get_session(token)
        if not session:
            raise HTTPException(status_code=401, detail="会话已失效")
        
        conversation_id = session.get('conversation_id') or str(uuid.uuid4())
        
        logger.info(f"[分类] 新请求: user={user_id}, conv={conversation_id}, text_len={len(request.text)}")
        
        # 【步骤 4】创建或加载状态管理器
        state_manager = StateManager(user_id=user_id, conversation_id=conversation_id)
        current_state = state_manager.get_current_state()
        
        # 【步骤 5】创建分类器实例
        from config.model_provider import create_chat_model
        llm = create_chat_model()
        classifier = TaskClassifier(llm)
        
        # 【步骤 6】执行分类
        classification = await classifier.classify_task(request.text)
        
        # 【步骤 7】检测症状和紧急标志
        is_emergency = classifier._is_emergency(request.text)
        detected_symptoms = []
        
        if is_emergency:
            # 识别具体的红旗症状
            text_lower = request.text.lower()
            for symptom in RedFlagSymptoms.ALL_SYMPTOMS:
                if symptom in text_lower:
                    detected_symptoms.append(symptom)
        
        # 【步骤 8】根据分类结果更新状态
        if classification == MedicalClassification.DOCTOR:
            state_manager.transition_to_doctor_assessment()
        elif classification == MedicalClassification.APPOINTMENT:
            state_manager.transition_to_appointment()
        elif classification == MedicalClassification.EMERGENCY:
            state_manager.transition_to_emergency()
        else:
            # FAQ 和 CHAT 保持在 CLASSIFY 状态
            state_manager.reset_to_classify()
        
        # 【步骤 9】构建响应
        logger.info(f"[分类] 完成: classification={classification}, emergency={is_emergency}, state={state_manager.get_current_state().value}")
        
        return TaskClassificationResponse(
            message="医学分类成功",
            data=TaskClassificationResponse.ClassificationData(
                classification=classification,
                is_emergency=is_emergency,
                description=MedicalClassification.get_description(classification),
                confidence=0.95,  # 实际应由分类器返回
                detected_symptoms=detected_symptoms if detected_symptoms else None,
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[分类] 错误: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"分类失败: {str(e)}"
        )


@router.post("/classify-sync")
async def classify_task_sync(
    request: TaskClassificationRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    同步版本的医学任务分类端点
    
    如果 /classify 是异步的，这个端点提供同步版本
    """
    return await classify_task(request, authorization)
