"""
校园医务室预约 API 端点

职责：
1. 处理医务室预约请求
2. 检查医生/校医可用性
3. 处理时间冲突
4. 生成预约确认码
5. 发送预约提醒
"""

import logging
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import uuid
from datetime import datetime, timedelta

from api.core.response_models import (
    AppointmentRequest,
    AppointmentResponse,
    DoctorInfo,
)
from api.auth import extract_token_from_header, verify_token
from services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/medical", tags=["医务室预约"])


# 模拟医生数据（实际应从数据库查询）
MOCK_DOCTORS = [
    # ========== 内科（2位）==========
    {
        "doctor_id": "doc_001",
        "name": "李明医生",
        "gender": "男",
        "specialty": "内科",
        "education": "硕士",
        "years_of_experience": 8,
        "consultation_rating": 4.8,
        "available_slots": ["2026-06-12 09:00", "2026-06-12 10:00", "2026-06-12 14:00"],
    },
    {
        "doctor_id": "doc_002",
        "name": "王芳医生",
        "gender": "女",
        "specialty": "内科",
        "education": "硕士",
        "years_of_experience": 6,
        "consultation_rating": 4.9,
        "available_slots": ["2026-06-12 09:30", "2026-06-12 11:00", "2026-06-12 15:00"],
    },

    # ========== 外科（2位）==========
    {
        "doctor_id": "doc_003",
        "name": "张刚医生",
        "gender": "男",
        "specialty": "外科",
        "education": "博士",
        "years_of_experience": 10,
        "consultation_rating": 4.7,
        "available_slots": ["2026-06-12 08:00", "2026-06-12 13:00", "2026-06-12 16:00"],
    },
    {
        "doctor_id": "doc_004",
        "name": "陈媛医生",
        "gender": "女",
        "specialty": "外科",
        "education": "硕士",
        "years_of_experience": 7,
        "consultation_rating": 4.6,
        "available_slots": ["2026-06-12 09:30", "2026-06-12 14:30"],
    },

    # ========== 皮肤科（2位）==========
    {
        "doctor_id": "doc_005",
        "name": "刘强医生",
        "gender": "男",
        "specialty": "皮肤科",
        "education": "硕士",
        "years_of_experience": 5,
        "consultation_rating": 4.8,
        "available_slots": ["2026-06-12 10:00", "2026-06-12 11:30", "2026-06-12 15:30"],
    },
    {
        "doctor_id": "doc_006",
        "name": "杨萍医生",
        "gender": "女",
        "specialty": "皮肤科",
        "education": "硕士",
        "years_of_experience": 4,
        "consultation_rating": 4.9,
        "available_slots": ["2026-06-12 10:30", "2026-06-12 14:00"],
    },

    # ========== 五官科（眼科+耳鼻喉）（2位）==========
    {
        "doctor_id": "doc_007",
        "name": "赵建医生",
        "gender": "男",
        "specialty": "眼科",
        "education": "硕士",
        "years_of_experience": 9,
        "consultation_rating": 4.9,
        "available_slots": ["2026-06-12 10:30", "2026-06-12 15:00", "2026-06-12 16:00"],
    },
    {
        "doctor_id": "doc_008",
        "name": "林晓医生",
        "gender": "女",
        "specialty": "耳鼻喉科",
        "education": "硕士",
        "years_of_experience": 6,
        "consultation_rating": 4.7,
        "available_slots": ["2026-06-12 09:00", "2026-06-12 13:30"],
    },

    # ========== 妇科（2位）==========
    {
        "doctor_id": "doc_009",
        "name": "钱军医生",
        "gender": "男",
        "specialty": "妇科",
        "education": "硕士",
        "years_of_experience": 8,
        "consultation_rating": 4.7,
        "available_slots": ["2026-06-12 11:00", "2026-06-12 14:00", "2026-06-12 15:30"],
    },
    {
        "doctor_id": "doc_010",
        "name": "周倩医生",
        "gender": "女",
        "specialty": "妇科",
        "education": "硕士",
        "years_of_experience": 7,
        "consultation_rating": 4.8,
        "available_slots": ["2026-06-12 10:00", "2026-06-12 14:30"],
    },

    # ========== 儿科（2位）==========
    {
        "doctor_id": "doc_011",
        "name": "吴涛医生",
        "gender": "男",
        "specialty": "儿科",
        "education": "硕士",
        "years_of_experience": 6,
        "consultation_rating": 4.6,
        "available_slots": ["2026-06-12 09:00", "2026-06-12 10:30", "2026-06-12 14:00"],
    },
    {
        "doctor_id": "doc_012",
        "name": "徐静医生",
        "gender": "女",
        "specialty": "儿科",
        "education": "学士",
        "years_of_experience": 4,
        "consultation_rating": 4.9,
        "available_slots": ["2026-06-12 09:30", "2026-06-12 13:00"],
    },

    # ========== 中医科（2位）==========
    {
        "doctor_id": "doc_013",
        "name": "何明医生",
        "gender": "男",
        "specialty": "中医科",
        "education": "硕士",
        "years_of_experience": 9,
        "consultation_rating": 4.8,
        "available_slots": ["2026-06-12 08:30", "2026-06-12 13:00", "2026-06-12 15:00"],
    },
    {
        "doctor_id": "doc_014",
        "name": "宋红医生",
        "gender": "女",
        "specialty": "中医科",
        "education": "硕士",
        "years_of_experience": 5,
        "consultation_rating": 4.7,
        "available_slots": ["2026-06-12 10:00", "2026-06-12 14:30"],
    },

    # ========== 全科医学（2位）==========
    {
        "doctor_id": "doc_015",
        "name": "高力医生",
        "gender": "男",
        "specialty": "全科",
        "education": "学士",
        "years_of_experience": 3,
        "consultation_rating": 4.5,
        "available_slots": ["2026-06-12 08:30", "2026-06-12 13:30", "2026-06-12 16:00"],
    },
    {
        "doctor_id": "doc_016",
        "name": "马杰医生",
        "gender": "女",
        "specialty": "全科",
        "education": "学士",
        "years_of_experience": 3,
        "consultation_rating": 4.5,
        "available_slots": ["2026-06-12 09:00", "2026-06-12 14:00"],
    },
]


def _get_available_doctors(preferred_time: Optional[str] = None):
    """
    获取可用的医生列表
    
    可以根据首选时间过滤医生
    """
    if not preferred_time:
        return MOCK_DOCTORS
    
    # 简略实现：返回在该时间段有空位的医生
    available = []
    for doc in MOCK_DOCTORS:
        if any(slot.startswith(preferred_time.split()[0]) for slot in doc["available_slots"]):
            available.append(doc)
    return available or MOCK_DOCTORS  # 如果没有匹配的，返回全部


def _generate_confirmation_code():
    """生成预约确认码"""
    return f"APPT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8].upper()}"


@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(
    request: AppointmentRequest,
    authorization: Optional[str] = Header(default=None),
) -> AppointmentResponse:
    """
    创建医务室预约
    
    流程：
    1. 验证用户身份（Token）
    2. 选择医生（自动匹配或使用指定医生）
    3. 检查时间可用性
    4. 创建预约记录
    5. 生成确认码及提醒
    
    Args:
        request: 预约请求（包含症状、首选时间等）
        authorization: Bearer Token
    
    Returns:
        AppointmentResponse: 预约确认信息（包括医生、时间、确认码）
    
    Raises:
        HTTPException: 验证失败、无可用时间段等
    """
    
    try:
        # 【步骤 1】验证 Token
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="未登录，请先使用手机号验证码登录"
            )
        
        user_id = verify_token(token)
        if not user_id:
            raise HTTPException(status_code=401, detail="Token 已失效，请重新登录")
        
        session = auth_service.get_session(token)
        if not session:
            raise HTTPException(status_code=401, detail="会话已失效")
        
        conversation_id = session.get('conversation_id')
        
        logger.info(f"[预约] 新请求: user={user_id}, reason={request.reason}")
        
        # 【步骤 2】选择医生
        if request.doctor_id:
            # 使用指定医生
            selected_doctor = next(
                (d for d in MOCK_DOCTORS if d["doctor_id"] == request.doctor_id),
                None
            )
            if not selected_doctor:
                raise HTTPException(
                    status_code=404,
                    detail=f"医生 {request.doctor_id} 不存在"
                )
        else:
            # 自动匹配医生
            available_doctors = _get_available_doctors(request.preferred_time)
            if not available_doctors:
                raise HTTPException(
                    status_code=400,
                    detail="该时间段无可用医生，请选择其他时间"
                )
            selected_doctor = available_doctors[0]  # 选择第一个可用医生
        
        # 【步骤 3】检查选定医生在首选时间的可用性
        doctor_info = DoctorInfo(
            doctor_id=selected_doctor["doctor_id"],
            name=selected_doctor["name"],
            specialty=selected_doctor["specialty"],
            available_slots=selected_doctor["available_slots"],
        )
        
        # 确定预约时间
        if request.preferred_time in selected_doctor["available_slots"]:
            scheduled_time = request.preferred_time
        else:
            # 使用医生的第一个可用时间
            scheduled_time = selected_doctor["available_slots"][0] if selected_doctor["available_slots"] else None
            if not scheduled_time:
                raise HTTPException(
                    status_code=400,
                    detail="该医生当前无可用时间"
                )
        
        # 【步骤 4】创建预约记录
        appointment_id = f"apt_{uuid.uuid4().hex[:12]}"
        confirmation_code = _generate_confirmation_code()
        
        # 【步骤 5】计算提醒时间（预约前 30 分钟）
        scheduled_dt = datetime.fromisoformat(scheduled_time)
        reminder_time = (scheduled_dt - timedelta(minutes=30)).isoformat()
        
        logger.info(f"[预约] 成功: id={appointment_id}, doctor={selected_doctor['name']}, time={scheduled_time}")
        
        # 【步骤 6】构建响应
        return AppointmentResponse(
            message="预约成功，请妥善保管确认码",
            data=AppointmentResponse.AppointmentData(
                appointment_id=appointment_id,
                doctor_info=doctor_info,
                scheduled_time=scheduled_time,
                location="校园医务楼一楼",
                status="confirmed",
                confirmation_code=confirmation_code,
                reminder_time=reminder_time,
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[预约] 错误: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"预约创建失败: {str(e)}"
        )


@router.get("/doctors")
async def get_available_doctors(
    preferred_time: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    """
    获取可用医生列表
    
    用于预约前的医生选择
    """
    try:
        # 验证 Token
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")
        
        if not verify_token(token):
            raise HTTPException(status_code=401, detail="Token 已失效")
        
        # 获取可用医生
        available_doctors = _get_available_doctors(preferred_time)
        
        return {
            "message": "医生列表获取成功",
            "data": [
                {
                    "doctor_id": doc["doctor_id"],
                    "name": doc["name"],
                    "specialty": doc["specialty"],
                    "available_slots_count": len(doc["available_slots"]),
                }
                for doc in available_doctors
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[医生列表] 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
