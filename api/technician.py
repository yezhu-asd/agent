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

        # 统一从 MOCK_DOCTORS 读取真实医生数据（与预约流程同源）
        from api.appointment import MOCK_DOCTORS
        doctors = []
        for d in MOCK_DOCTORS:
            doctors.append({
                "doctor_id": d.get("doctor_id"),
                "name": d.get("name"),
                "gender": d.get("gender"),
                "specialty": d.get("specialty"),
                "education": d.get("education"),
                "years_of_experience": d.get("years_of_experience"),
                "consultation_rating": d.get("consultation_rating"),
                "available_slots": d.get("available_slots", []),
            })

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
    from api.appointment import MOCK_DOCTORS
    from datetime import datetime
    # 建立医生姓名 → 数据库整数 ID 的映射
    db_id_by_name = {}
    try:
        from services.appointment_service import AppointmentService
        apt_service = AppointmentService()
        for db_doc in apt_service.get_all_doctors():
            db_id_by_name[str(db_doc.get("name"))] = str(db_doc.get("id"))
    except Exception:
        apt_service = None

    # 查询今日所有医生的预约，标记忙碌状态
    busy_doctor_ids = set()
    if apt_service:
        try:
            today = datetime.now().date()
            for db_name, db_id in db_id_by_name.items():
                appointments = apt_service.get_doctor_appointments_by_date(db_id, today)
                if appointments:
                    busy_doctor_ids.add(db_name)
        except Exception:
            pass

    # 转成 technician.html 模板需要的字段结构
    doctors = []
    for d in MOCK_DOCTORS:
        doctors.append({
            "id": d.get("doctor_id"),
            "name": d.get("name"),
            "gender": d.get("gender"),
            "specialty": d.get("specialty"),
            "strength": d.get("specialty"),  # 模板的"力气/倾向"列显示科室
            "education": d.get("education"),
            "years_of_experience": d.get("years_of_experience"),
            "status": "busy" if d.get("name") in busy_doctor_ids else "available",
        })
    return doctors


async def get_all_technicians_schedule_today():
    """获取所有医生今日排班信息

    数据来源：
    1. 医生基础信息来自 MOCK_DOCTORS（与预约流程同源）
    2. 忙碌时间段从 MySQL appointments 表查询（预约持久化，重启不丢失）
    """
    try:
        from api.appointment import MOCK_DOCTORS
        from datetime import datetime

        today_str = datetime.now().strftime("%Y-%m-%d")
        today = datetime.now().date()
        schedules_data = []

        # 建立 MOCK doctor_id → 数据库整数 ID 的映射
        db_id_map = {}
        try:
            from services.appointment_service import AppointmentService
            apt_service = AppointmentService()
            for db_doc in apt_service.get_all_doctors():
                db_id_map[str(db_doc.get("id"))] = db_doc.get("name")
        except Exception:
            apt_service = None

        for doctor in MOCK_DOCTORS:
            doctor_id = doctor.get("doctor_id")
            doctor_name = doctor.get("name")
            specialty = doctor.get("specialty", "")

            # 收集忙碌时间段：从 MySQL appointments 表查询
            busy_periods = []

            # 找到该医生的数据库整数 ID
            db_id = None
            for db_id_key, db_name in db_id_map.items():
                if db_name == doctor_name:
                    db_id = db_id_key
                    break

            if db_id and apt_service:
                try:
                    appointments = apt_service.get_doctor_appointments_by_date(db_id, today)
                    for apt in appointments:
                        start = apt.get("start_time")
                        end = apt.get("end_time")
                        busy_periods.append({
                            "start": start.strftime("%H:%M") if hasattr(start, 'strftime') else str(start),
                            "end": end.strftime("%H:%M") if hasattr(end, 'strftime') else str(end),
                        })
                except Exception:
                    pass  # 数据库查询失败不影响展示

            # 去重（按时间段）
            seen = set()
            unique_periods = []
            for p in busy_periods:
                key = f"{p['start']}-{p['end']}"
                if key not in seen:
                    seen.add(key)
                    unique_periods.append(p)

            schedules_data.append({
                "doctor_id": doctor_id,
                "doctor_name": doctor_name,
                "specialty": specialty,
                "busy_periods": unique_periods,
                "date": today_str,
            })

        return schedules_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取医生排班信息失败: {str(e)}")
