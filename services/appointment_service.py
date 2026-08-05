"""
预约服务层

职责：
1. 封装预约相关的数据库操作
2. 处理预约业务逻辑
3. 提供预约相关的数据服务
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from db.db_router import DatabaseRouter
import logging

logger = logging.getLogger(__name__)

class AppointmentService:
    """预约服务类"""

    def __init__(self, db_url: str = None):
        self.db_router = DatabaseRouter(db_url)
        self.technician_repo = self.db_router.technicians

        # 兼容/新命名：提供 doctor_repo 别名指向相同仓库
        self.doctor_repo = self.technician_repo

    def save_appointment(self, doctor_id: str, start_time: datetime,
                        end_time: datetime, appointment_history: Dict[str, Any],
                        session_id: str, user_id: str = None,
                        conversation_id: str = None) -> Optional[Dict[str, Any]]:
        """保存预约信息到数据库，同时写入 appointments 主表和 doctor_schedules 表

        Returns:
            {'appointment_id': int, 'schedule_id': int} ，失败返回 None
        """
        try:
            # 1. 先写入 doctor_schedules 表（标记医生时间段为busy）
            schedule_id = self.technician_repo.add_schedule(
                doctor_id=int(doctor_id),
                start_time=start_time,
                end_time=end_time,
                status="busy",
                appointment_id=None
            )

            # 2. 写入 appointments 主表（使用真实的schedule_id）
            real_appointment_id = None
            if user_id:
                real_appointment_id = self.technician_repo.create_appointment(
                    user_id=user_id,
                    doctor_id=int(doctor_id),
                    schedule_id=schedule_id,
                    start_time=start_time,
                    end_time=end_time,
                    conversation_id=conversation_id,
                    reason=appointment_history.get('reason', '')
                )
                # 3. 回填 doctor_schedules 的 appointment_id
                if real_appointment_id:
                    self.technician_repo.update_schedule_appointment_id(
                        schedule_id, real_appointment_id
                    )

            logger.info(f"预约信息已保存到数据库：医生ID={doctor_id}, 时间={start_time} 到 {end_time}, 预约ID={real_appointment_id}")
            return {'appointment_id': real_appointment_id, 'schedule_id': schedule_id}

        except Exception as e:
            logger.error(f"保存预约信息到数据库失败：{e}")
            return None

    def get_user_active_appointment(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户当前有效的预约"""
        try:
            return self.technician_repo.get_user_active_appointment(user_id)
        except Exception as e:
            logger.error(f"查询用户预约失败：{e}")
            return None

    def cancel_appointment(self, appointment_id: int, schedule_id: int) -> bool:
        """取消预约（更新DB，释放时间段）"""
        try:
            return self.technician_repo.cancel_appointment_txn(appointment_id, schedule_id)
        except Exception as e:
            logger.error(f"取消预约失败：{e}")
            return False
    
    def get_doctor_by_id(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取医生信息"""
        try:
            return self.technician_repo.get_technician_by_id(doctor_id)
        except Exception as e:
            logger.error(f"获取医生信息失败：{e}")
            return None

    def get_doctor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据姓名获取医生信息"""
        try:
            return self.technician_repo.get_technician_by_name(name)
        except Exception as e:
            logger.error(f"获取医生信息失败：{e}")
            return None

    def get_all_doctors(self) -> List[Dict[str, Any]]:
        """获取所有医生信息"""
        try:
            return self.technician_repo.get_all_technicians()
        except Exception as e:
            logger.error(f"获取医生列表失败：{e}")
            return []

    def get_doctors_by_gender(self, gender: str) -> List[Dict[str, Any]]:
        """根据性别获取医生信息"""
        try:
            return self.technician_repo.get_technicians_by_gender(gender)
        except Exception as e:
            logger.error(f"根据性别获取医生信息失败：{e}")
            return []

    def get_doctor_schedules(self, doctor_id: int, date) -> List[Dict[str, Any]]:
        """获取医生排班信息"""
        try:
            return self.technician_repo.get_technician_schedules(doctor_id, date)
        except Exception as e:
            logger.error(f"获取医生排班信息失败：{e}")
            return []

    def get_doctor_appointments_by_date(self, doctor_id: int, date) -> List[Dict[str, Any]]:
        """查询医生在指定日期的所有预约（用于值班页显示忙碌时段）"""
        try:
            return self.technician_repo.get_doctor_appointments_by_date(doctor_id, date)
        except Exception as e:
            logger.error(f"获取医生预约失败：{e}")
            return []

    def is_doctor_available(self, doctor_id: int, start_time: datetime, end_time: datetime) -> bool:
        """检查医生是否可用"""
        try:
            return self.technician_repo.is_technician_available(doctor_id, start_time, end_time)
        except Exception as e:
            logger.error(f"检查医生可用性失败：{e}")
            return False

    def add_doctor(self, name: str, gender: str = None, strength: str = None) -> Optional[int]:
        """添加新医生"""
        try:
            return self.technician_repo.add_technician(name, gender, strength)
        except Exception as e:
            logger.error(f"添加医生失败：{e}")
            return None

    def get_all_strengths(self) -> List[str]:
        """获取所有医生的专长列表"""
        try:
            return self.technician_repo.get_all_strengths()
        except Exception as e:
            logger.error(f"获取医生专长列表失败：{e}")
            return []
