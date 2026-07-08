"""
校园医务室健康知识咨询 API 端点

职责：
1. 回答用户的医学健康问题
2. 提供健康建议和预防措施
3. 基于 RAG 知识库进行问答
4. 添加医学免责声明
"""

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from api.core.response_models import (
    HealthInquiryRequest,
    HealthInquiryResponse,
)
from api.auth import extract_token_from_header, verify_token
from services.auth_service import auth_service
from config.constants import MedicalFacilityInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/medical", tags=["健康知识"])


@router.post("/health-inquiries", response_model=HealthInquiryResponse)
async def create_health_inquiry(
    request: HealthInquiryRequest,
    authorization: Optional[str] = Header(default=None),
) -> HealthInquiryResponse:
    """
    健康知识咨询端点
    
    用户可以询问关于健康、疾病预防、营养等通用医学知识
    系统使用 RAG（检索增强生成）基于知识库提供回答
    
    示例问题：
    - "感冒应该怎么预防？"
    - "骨折需要多久才能恢复？"
    - "如何进行心肺复苏？"
    - "高血压的日常管理方法"
    
    Args:
        request: 咨询请求
        authorization: Bearer Token
    
    Returns:
        HealthInquiryResponse: 回答、参考来源和相关服务建议
    
    Raises:
        HTTPException: 验证失败或处理出错
    """
    
    try:
        # 【步骤 1】验证 Token
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")
        
        user_id = verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 已失效")
        
        session = auth_service.get_session(token)
        if not session:
            raise HTTPException(status_code=401, detail="会话已失效")
        
        logger.info(f"[健康咨询] 新询问: user={user_id}, category={request.category}")
        
        # 【步骤 2】使用 RAG 系统查询知识库
        # 这里简化实现，实际应调用 ConsultantAgent 或 RAG 服务
        answer = _get_health_answer(request.question, request.category)
        
        # 【步骤 3】构建相关服务建议
        related_services = _get_related_services(request.question, request.category)
        
        logger.info(f"[健康咨询] 完成: 返回 {len(answer)} 字符的回答")
        
        # 【步骤 4】返回响应
        return HealthInquiryResponse(
            message="健康知识咨询成功",
            data=HealthInquiryResponse.InquiryData(
                question=request.question,
                answer=answer,
                sources=["校园医务室知识库", "医学教科书", "WHO 健康指南"],
                disclaimer=MedicalFacilityInfo.MEDICAL_DISCLAIMER,
                related_services=related_services,
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[健康咨询] 错误: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理咨询失败: {str(e)}")


def _get_health_answer(question: str, category: Optional[str] = None) -> str:
    """
    获取健康知识回答（简化实现）
    
    实际应调用 RAG 检索系统和 LLM
    """
    
    # 这里是简化的响应示例
    response_templates = {
        "prevention": "预防 {subject} 的方法包括：1. 保持良好的卫生习惯 2. 增强体质锻炼 3. 定期体检 4. 合理饮食 5. 充足睡眠",
        "treatment": "关于 {subject} 的治疗，建议立即咨询校医或专科医生，不要自行用药。",
        "nutrition": "健康饮食建议：1. 均衡各类营养 2. 适量补充维生素 3. 避免过度进补 4. 多吃蔬菜水果 5. 控制盐糖摄入",
        "exercise": "适度运动好处多：1. 增强心肺功能 2. 改善睡眠质量 3. 缓解压力 4. 维持健康体重 5. 预防慢性病",
    }
    
    # 简化逻辑：根据问题关键词返回相应模板
    question_lower = question.lower()
    
    if "预防" in question or "prevention" in category or category == "prevention":
        # 提取主题词
        subject = "相关疾病"
        if "感冒" in question:
            subject = "感冒"
        elif "流感" in question:
            subject = "流感"
        elif "高血压" in question:
            subject = "高血压"
        return response_templates["prevention"].format(subject=subject)
    
    elif "治疗" in question or "吃药" in question:
        return response_templates["treatment"].format(subject="该疾病")
    
    elif "饮食" in question or "营养" in question or category == "nutrition":
        return response_templates["nutrition"]
    
    elif "运动" in question or "锻炼" in question or category == "exercise":
        return response_templates["exercise"]
    
    else:
        # 默认回答
        return (f"感谢您的提问：{question}\n\n"
                "本系统仅提供一般性的健康知识，对于您的具体情况，建议咨询校医或医生。\n"
                f"\n{MedicalFacilityInfo.EMERGENCY_INSTRUCTIONS}")


def _get_related_services(question: str, category: Optional[str] = None) -> list:
    """
    获取相关的医务室服务建议
    """
    
    related = []
    question_lower = question.lower()
    
    # 基于问题关键词推荐服务
    if any(word in question_lower for word in ["症状", "疼痛", "不适", "生病", "医生"]):
        related.append("预约医生咨询")
    
    if any(word in question_lower for word in ["预防", "体检", "检查"]):
        related.append("预防保健咨询")
    
    if any(word in question_lower for word in ["时间", "位置", "怎么", "如何", "怎样"]):
        related.append("医务室详细信息")
    
    # 总是推荐紧急帮助
    if any(word in question_lower for word in ["紧急", "痛", "急", "112", "120", "火急"]):
        related.append("紧急医疗帮助")
    
    return related if related else ["预约医生咨询", "健康体检"]


# 向后兼容别名
from api.core.response_models import ConsultationRequest, ConsultationResponse, DataResponse


@router.post("/consultation/ask")
async def ask_consultation_compat(
    request: ConsultationRequest,
    authorization: Optional[str] = Header(default=None),
):
    """向后兼容的旧接口"""
    inquiry_request = HealthInquiryRequest(
        user_id="compat_user",
        conversation_id="compat_conv",
        question=request.question,
        category=request.category,
    )
    return await create_health_inquiry(inquiry_request, authorization)
