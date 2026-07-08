"""
校园医务室 API 响应模型 - 医学化版本

模型分类：
1. 基础模型：通用响应、错误、分页
2. 用户认证模型：登录请求/响应、Token
3. 医学分类模型：任务分类、医学标签
4. 问诊模型：问诊请求、症状记录、医生评估
5. 预约模型：预约请求、医生信息、预约确认
6. 健康追踪模型：诊疗记录、复诊建议、风险评估
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List
from datetime import datetime
from enum import Enum
from config.time_config import time_config
from config.constants import MedicalClassification, RedFlagSymptoms


# ===========================
# 基础响应模型
# ===========================

class BaseResponse(BaseModel):
    """基础响应模型"""
    message: str
    timestamp: datetime = Field(default_factory=time_config.now)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseResponse):
    """错误响应模型"""
    error_code: str = "UNKNOWN_ERROR"
    error_detail: Optional[str] = None


class DataResponse(BaseResponse):
    """数据响应模型"""
    data: Any


# ===========================
# 用户认证模型
# ===========================

class LoginRequest(BaseModel):
    """登录请求"""
    phone_number: str = Field(..., description="手机号")
    verification_code: str = Field(..., description="验证码")


class Token(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="Token 类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user_id: str = Field(..., description="用户ID")


class LoginResponse(DataResponse):
    """登录成功响应"""
    data: Token


# ===========================
# 医学分类模型
# ===========================

class TaskClassificationRequest(BaseModel):
    """医学任务分类请求"""
    text: str = Field(..., description="用户输入的自然语言文本")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")


class TaskClassificationResponse(DataResponse):
    """医学任务分类响应"""
    
    class ClassificationData(BaseModel):
        classification: str = Field(..., description="分类结果 (doctor/appointment/faq/emergency/chat)")
        is_emergency: bool = Field(..., description="是否为紧急症状")
        description: str = Field(..., description="分类的中文描述")
        confidence: float = Field(default=0.95, description="置信度 (0-1)")
        detected_symptoms: Optional[List[str]] = Field(None, description="检测到的症状关键词")
    
    data: ClassificationData


# ===========================
# 问诊模型
# ===========================

class SymptomRecord(BaseModel):
    """症状记录"""
    symptom: str = Field(..., description="症状描述")
    duration: Optional[str] = Field(None, description="持续时间")
    severity: Optional[str] = Field(None, description="严重程度 (mild/moderate/severe)")
    timestamp: datetime = Field(default_factory=time_config.now, description="记录时间")


class DoctorAssessmentRequest(BaseModel):
    """医生评估请求（问诊）"""
    user_id: str = Field(..., description="用户ID")
    conversation_id: str = Field(..., description="对话ID")
    symptoms: List[SymptomRecord] = Field(..., description="症状记录列表")
    medical_history: Optional[str] = Field(None, description="既往史")
    allergies: Optional[str] = Field(None, description="过敏史")
    current_medications: Optional[str] = Field(None, description="当前用药")


class DoctorAssessmentResponse(DataResponse):
    """医生评估响应"""
    
    class AssessmentData(BaseModel):
        assessment_id: str = Field(..., description="评估ID")
        preliminary_diagnosis: Optional[str] = Field(None, description="初步诊断")
        recommendations: str = Field(..., description="医生建议")
        risk_level: str = Field(..., description="风险等级 (low/medium/high/critical)")
        suggested_next_steps: List[str] = Field(..., description="建议的后续步骤")
        needs_appointment: bool = Field(..., description="是否需要预约挂号")
    
    data: AssessmentData


# ===========================
# 预约模型
# ===========================

class DoctorInfo(BaseModel):
    """医生/校医信息"""
    doctor_id: str = Field(..., description="医生ID")
    name: str = Field(..., description="医生名字")
    specialty: str = Field(..., description="专科 (general/cardiology/neurology等)")
    available_slots: List[str] = Field(..., description="可选时间段列表")


class AppointmentRequest(BaseModel):
    """预约请求"""
    user_id: str = Field(..., description="用户ID")
    conversation_id: str = Field(..., description="对话ID")
    doctor_id: Optional[str] = Field(None, description="指定医生ID（可选）")
    preferred_time: str = Field(..., description="期望时间")
    reason: str = Field(..., description="就诊原因")
    notes: Optional[str] = Field(None, description="备注")


class AppointmentResponse(DataResponse):
    """预约确认响应"""
    
    class AppointmentData(BaseModel):
        appointment_id: str = Field(..., description="预约ID")
        doctor_info: DoctorInfo = Field(..., description="医生信息")
        scheduled_time: str = Field(..., description="预约时间")
        location: str = Field(..., description="就诊位置")
        status: str = Field(..., description="预约状态")
        confirmation_code: str = Field(..., description="确认码")
        reminder_time: Optional[str] = Field(None, description="提醒时间")
    
    data: AppointmentData


# ===========================
# 健康追踪与推荐模型
# ===========================

class ConsultationRecord(BaseModel):
    """诊疗记录"""
    consultation_id: str = Field(..., description="咨询ID")
    timestamp: datetime = Field(..., description="时间")
    symptoms: List[str] = Field(..., description="症状列表")
    diagnosis: Optional[str] = Field(None, description="诊断")
    treatment: Optional[str] = Field(None, description="处理方案")


class ReconsultationRecommendation(BaseModel):
    """复诊建议"""
    reason: str = Field(..., description="建议原因")
    recommended_time: str = Field(..., description="建议时间")
    priority: str = Field(..., description="优先级 (low/medium/high)")


class RiskAssessment(BaseModel):
    """风险评估"""
    risk_level: str = Field(..., description="风险等级 (low/medium/high/critical)")
    risk_factors: List[str] = Field(..., description="风险因素列表")
    recommendations: str = Field(..., description="建议")


class UserBehaviorAnalysisResponse(DataResponse):
    """健康追踪响应"""
    
    class BehaviorData(BaseModel):
        user_id: str = Field(..., description="用户ID")
        total_consultations: int = Field(..., description="总咨询次数")
        recent_consultations: List[ConsultationRecord] = Field(..., description="最近咨询记录")
        reconsultation_recommendations: Optional[List[ReconsultationRecommendation]] = Field(None, description="复诊建议")
        risk_assessment: Optional[RiskAssessment] = Field(None, description="风险评估")
    
    data: BehaviorData


# ===========================
# 聊天和无关请求模型
# ===========================

class ChatMessage(BaseModel):
    """聊天消息"""
    user_id: str = Field(..., description="用户ID")
    conversation_id: str = Field(..., description="对话ID")
    message: str = Field(..., description="消息内容")
    message_type: str = Field(default="text", description="消息类型 (text/image/file)")


class UnrelatedRequestResponse(DataResponse):
    """无关请求响应"""
    
    class UnrelatedData(BaseModel):
        response: str = Field(..., description="系统回复")
        medical_tips: Optional[str] = Field(None, description="医学提示")
        redirect_suggestion: Optional[str] = Field(None, description="重定向建议")
    
    data: UnrelatedData


# ===========================
# 通用健康咨询模型
# ===========================

class HealthInquiryRequest(BaseModel):
    """健康知识咨询请求"""
    user_id: str = Field(..., description="用户ID")
    conversation_id: str = Field(..., description="对话ID")
    question: str = Field(..., description="问题")
    category: Optional[str] = Field(None, description="知识类别 (prevention/treatment/nutrition等)")


class HealthInquiryResponse(DataResponse):
    """健康知识咨询响应"""
    
    class InquiryData(BaseModel):
        question: str = Field(..., description="问题")
        answer: str = Field(..., description="回答")
        sources: Optional[List[str]] = Field(None, description="参考来源")
        disclaimer: str = Field(..., description="医学免责声明")
        related_services: Optional[List[str]] = Field(None, description="相关医务室服务")
    
    data: InquiryData


# ===========================
# 向后兼容别名
# ===========================

# 旧接口兼容性：将 HealthInquiry 模型别名为 Consultation
ConsultationRequest = HealthInquiryRequest
ConsultationResponse = HealthInquiryResponse
