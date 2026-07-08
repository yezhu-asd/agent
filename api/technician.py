"""
校园医务室医生值班表 API 端点

职责：
1. 获取医生/校医值班信息
2. 查询每日排班安排
3. 获取医生专科信息
4. 检查医生可用性
"""

import logging
from fastapi import APIRouter, HTTPException, Header, Query
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from api.auth import extract_token_from_header, verify_token
from services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/medical", tags=["医生值班"])


class DoctorScheduleItem(BaseModel):
    """医生值班项目"""
    doctor_id: str
    name: str
    specialty: str  # 专科
    date: str  # 值班日期
    start_time: str  # 开始时间
    end_time: str  # 结束时间
    status: str  # available / busy / offline
    available_slots: int  # 可用时间段数


class DoctorDetailResponse(BaseModel):
    """医生详细信息"""
    doctor_id: str
    name: str
    specialty: str
    license_id: str  # 执业证号
    education: str  # 学历
    experience_years: int  # 从业年数
    available_today: bool


# 模拟医生数据
MOCK_DOCTOR_DATA = [
    {
        "doctor_id": "doc_001",
        "name": "张医生",
        "specialty": "全科",
        "license_id": "执业证001",
        "education": "本科",
        "experience_years": 8,
        "schedule": {
            "monday_to_friday": {"start": "08:00", "end": "18:00"},
            "saturday": {"start": "09:00", "end": "17:00"},
        }
    },
    {
        "doctor_id": "doc_002",
        "name": "李医生",
        "specialty": "心内科",
        "license_id": "执业证002",
        "education": "硕士",
        "experience_years": 12,
        "schedule": {
            "tuesday": {"start": "10:00", "end": "16:00"},
            "thursday": {"start": "10:00", "end": "16:00"},
        }
    },
    {
        "doctor_id": "doc_003",
        "name": "王校医",
        "specialty": "预防保健",
        "license_id": "执业证003",
        "education": "本科",
        "experience_years": 5,
        "schedule": {
            "monday_to_friday": {"start": "09:00", "end": "17:00"},
        }
    },
]


def _get_doctor_by_id(doctor_id: str):
    """根据医生ID获取医生信息"""
    return next((d for d in MOCK_DOCTOR_DATA if d["doctor_id"] == doctor_id), None)


def _get_today_schedules() -> List[DoctorScheduleItem]:
    """获取今天所有医生的值班表"""
    today = datetime.now()
    weekday = today.strftime("%A").lower()
    
    # 简化映射
    weekday_map = {
        "monday": "monday_to_friday",
        "tuesday": "tuesday",
        "wednesday": "monday_to_friday",
        "thursday": "thursday",
        "friday": "monday_to_friday",
        "saturday": "saturday",
        "sunday": "sunday",
    }
    
    schedule_key = weekday_map.get(weekday.replace("monday", "monday").lower(), "monday_to_friday")
    
    schedules = []
    for doctor in MOCK_DOCTOR_DATA:
        if schedule_key in doctor["schedule"]:
            time_range = doctor["schedule"][schedule_key]
            schedules.append(
                DoctorScheduleItem(
                    doctor_id=doctor["doctor_id"],
                    name=doctor["name"],
                    specialty=doctor["specialty"],
                    date=today.strftime("%Y-%m-%d"),
                    start_time=time_range["start"],
                    end_time=time_range["end"],
                    status="available" if time_range["start"] < "17:00" else "busy",
                    available_slots=4,  # 假设每个时段 4 个可用位置
                )
            )
    
    return schedules


@router.get("/doctor-schedules", response_model=List[DoctorScheduleItem])
async def get_doctor_schedules(
    date: Optional[str] = Query(None, description="查询日期 (YYYY-MM-DD)，不提供则查询今天"),
    specialty: Optional[str] = Query(None, description="筛选专科"),
    authorization: Optional[str] = Header(default=None),
):
    """
    获取医生值班表
    
    可按日期和专科筛选。用于用户浏览可用医生和时间段。
    
    Args:
        date: 查询日期，格式 YYYY-MM-DD（可选，默认今天）
        specialty: 筛选专科（可选）
        authorization: Bearer Token
    
    Returns:
        医生值班表列表
    """
    
    try:
        # 【步骤 1】验证 Token
        token = extract_token_from_header(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")
        
        if not verify_token(token):
            raise HTTPException(status_code=401, detail="Token 已失效")
        
        logger.info(f"[值班表] 查询: date={date}, specialty={specialty}")
        
        # 【步骤 2】获取值班表
        schedules = _get_today_schedules()
        
        # 【步骤 3】按专科筛选（如果提供）
        if specialty:
            schedules = [s for s in schedules if s.specialty == specialty]
        
        logger.info(f"[值班表] 返回 {len(schedules)} 条记录")
        
        return schedules
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[值班表] 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doctors/{doctor_id}", response_model=DoctorDetailResponse)
async def get_doctor_detail(
    doctor_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """
    获取医生详细信息
    
    包括医生基本信息、专科、从业资质等
    """
    
    try:
        # 验证 Token
        token = extract_token_from_header(authorization)
        if not token or not verify_token(token):
            raise HTTPException(status_code=401, detail="未登录")
        
        # 获取医生信息
        doctor = _get_doctor_by_id(doctor_id)
        if not doctor:
            raise HTTPException(status_code=404, detail="医生不存在")
        
        # 检查今天是否值班
        today_schedules = _get_today_schedules()
        available_today = any(s.doctor_id == doctor_id for s in today_schedules)
        
        return DoctorDetailResponse(
            doctor_id=doctor["doctor_id"],
            name=doctor["name"],
            specialty=doctor["specialty"],
            license_id=doctor["license_id"],
            education=doctor["education"],
            experience_years=doctor["experience_years"],
            available_today=available_today,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[医生详情] 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doctors")
async def list_all_doctors(
    authorization: Optional[str] = Header(default=None),
):
    """
    获取所有医生列表
    
    用于用户浏览医务室的所有医生
    """
    
    try:
        # 验证 Token
        token = extract_token_from_header(authorization)
        if not token or not verify_token(token):
            raise HTTPException(status_code=401, detail="未登录")
        
        doctors = [
            {
                "doctor_id": d["doctor_id"],
                "name": d["name"],
                "specialty": d["specialty"],
                "experience_years": d["experience_years"],
            }
            for d in MOCK_DOCTOR_DATA
        ]
        
        return {
            "message": "医生列表获取成功",
            "data": doctors,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[医生列表] 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Compatibility layer: 为现有路由提供 backward-compatible 函数
# ============================================================


async def get_all_technicians():
    """兼容函数: 获取所有医生列表 (别名)"""
    result = await list_all_doctors()
    return result.get("data", []) if isinstance(result, dict) else []


async def get_all_technicians_schedule_today():
    """获取所有医生今日排班信息"""
    try:
        from services.technician_service import TechnicianService
        from config.time_config import time_config

        technician_service = TechnicianService()
        technician_service.initialize_default_technicians()

        all_doctors = technician_service.get_all_technicians()
        today = time_config.today()

        schedules_data = []
        for doctor in all_doctors:
            doctor_id = doctor["id"]
            doctor_name = doctor["name"]

            doctor_schedules = technician_service.get_technician_schedules(doctor_id, today)

            busy_periods = []
            for sched in doctor_schedules:
                if sched.get("status") == "busy":
                    busy_periods.append({
                        "start": sched["start_time"].strftime("%H:%M") if hasattr(sched["start_time"], 'strftime') else str(sched["start_time"]),
                        "end": sched["end_time"].strftime("%H:%M") if hasattr(sched["end_time"], 'strftime') else str(sched["end_time"]),
                        "appointment_id": sched.get("appointment_id")
                    })

            schedules_data.append({
                "doctor_id": doctor_id,
                "doctor_name": doctor_name,
                "busy_periods": busy_periods
            })

        return schedules_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取医生排班信息失败: {str(e)}")
