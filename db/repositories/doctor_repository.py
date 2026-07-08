"""
医生数据访问对象 - 替代 technician_repository.py

职责：
1. 医生信息的 CRUD 操作
2. 医生排班的管理
3. 医生可用性检查
4. 医学特定的查询和分析
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from ..base.interfaces import BaseDoctorRepository, BaseScheduleRepository
from ..base.session_manager import SessionManager
from ..models import Doctor, DoctorSchedule, Appointment


class DoctorRepository(BaseDoctorRepository, BaseScheduleRepository):
    """
    医生数据访问对象
    
    职责：
    1. 医生信息的 CRUD 操作
    2. 医生排班的管理
    3. 医生可用性检查
    4. 医学特定的查询（按专科、评分等）
    """
    
    def __init__(self, session_manager: SessionManager):
        """
        初始化医生数据仓库
        
        Args:
            session_manager: 会话管理器
        """
        self.session_manager = session_manager

    # ===========================
    # 医生 CRUD 操作
    # ===========================
    
    def add_doctor(self, name: str, specialty: str, license_number: str, 
                   gender: Optional[str] = None, education: Optional[str] = None, 
                   years_of_experience: int = 0) -> int:
        """
        添加医生
        
        Args:
            name: 医生姓名
            specialty: 专科
            license_number: 执业证号
            gender: 性别
            education: 教育背景
            years_of_experience: 从业年数
            
        Returns:
            新创建的医生 ID
        """
        with self.session_manager.session_scope() as session:
            doctor = Doctor(
                name=name,
                specialty=specialty,
                license_number=license_number,
                gender=gender,
                education=education,
                years_of_experience=years_of_experience
            )
            session.add(doctor)
            session.flush()
            return doctor.id

    def get_doctor_by_id(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """
        根据ID获取医生信息
        
        Args:
            doctor_id: 医生ID
            
        Returns:
            医生信息字典，如果不存在返回 None
        """
        with self.session_manager.session_scope() as session:
            doctor = session.query(Doctor).filter(
                Doctor.id == doctor_id
            ).first()
            
            if not doctor:
                return None
                
            return self._doctor_to_dict(doctor)

    def get_doctor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据姓名获取医生信息
        
        Args:
            name: 医生姓名
            
        Returns:
            医生信息字典，如果不存在返回 None
        """
        with self.session_manager.session_scope() as session:
            doctor = session.query(Doctor).filter(
                Doctor.name == name
            ).first()
            
            if not doctor:
                return None
                
            return self._doctor_to_dict(doctor)

    def get_all_doctors(self) -> List[Dict[str, Any]]:
        """
        获取所有医生信息
        
        Returns:
            医生信息列表
        """
        with self.session_manager.session_scope() as session:
            doctors = session.query(Doctor).all()
            return [self._doctor_to_dict(doc) for doc in doctors]

    def get_doctors_by_specialty(self, specialty: str) -> List[Dict[str, Any]]:
        """
        根据专科获取医生
        
        Args:
            specialty: 医学专科
            
        Returns:
            医生信息列表
        """
        with self.session_manager.session_scope() as session:
            doctors = session.query(Doctor).filter(
                Doctor.specialty == specialty
            ).all()
            return [self._doctor_to_dict(doc) for doc in doctors]

    def get_top_rated_doctors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取评分最高的医生
        
        Args:
            limit: 返回数量
            
        Returns:
            医生信息列表（按评分降序）
        """
        with self.session_manager.session_scope() as session:
            doctors = session.query(Doctor).order_by(
                Doctor.consultation_rating.desc()
            ).limit(limit).all()
            return [self._doctor_to_dict(doc) for doc in doctors]

    def update_doctor(self, doctor_id: int, **updates) -> bool:
        """
        更新医生信息
        
        Args:
            doctor_id: 医生ID
            **updates: 要更新的字段
            
        Returns:
            更新是否成功
        """
        with self.session_manager.session_scope() as session:
            doctor = session.query(Doctor).filter(
                Doctor.id == doctor_id
            ).first()
            
            if not doctor:
                return False
                
            for key, value in updates.items():
                if hasattr(doctor, key):
                    setattr(doctor, key, value)
                    
            return True

    def delete_doctor(self, doctor_id: int) -> bool:
        """
        删除医生
        
        Args:
            doctor_id: 医生ID
            
        Returns:
            删除是否成功
        """
        with self.session_manager.session_scope() as session:
            doctor = session.query(Doctor).filter(
                Doctor.id == doctor_id
            ).first()
            
            if not doctor:
                return False
                
            session.delete(doctor)
            return True

    def update_doctor_rating(self, doctor_id: int, rating: float) -> bool:
        """
        更新医生评分
        
        Args:
            doctor_id: 医生ID
            rating: 新评分（1-5）
            
        Returns:
            更新是否成功
        """
        if not 1.0 <= rating <= 5.0:
            return False
            
        return self.update_doctor(doctor_id, consultation_rating=rating)

    # ===========================
    # 排班操作
    # ===========================
    
    def add_schedule(self, doctor_id: int, start_time: datetime, end_time: datetime, 
                    status: str, shift_type: Optional[str] = None, 
                    appointment_id: Optional[int] = None) -> int:
        """
        添加医生排班
        
        Args:
            doctor_id: 医生ID
            start_time: 开始时间
            end_time: 结束时间
            status: 状态（'busy', 'free', 'on_leave'）
            shift_type: 班次类型（'morning', 'afternoon', 'evening'）
            appointment_id: 预约ID
            
        Returns:
            新创建的排班ID
        """
        with self.session_manager.session_scope() as session:
            schedule = DoctorSchedule(
                doctor_id=doctor_id,
                start_time=start_time,
                end_time=end_time,
                status=status,
                shift_type=shift_type,
                appointment_id=appointment_id
            )
            session.add(schedule)
            session.flush()
            return schedule.id

    def update_schedule_appointment_id(self, schedule_id: int, appointment_id: int) -> bool:
        """回填 doctor_schedules 表的 appointment_id 字段"""
        with self.session_manager.session_scope() as session:
            schedule = session.query(DoctorSchedule).filter(
                DoctorSchedule.id == schedule_id
            ).first()
            if schedule:
                schedule.appointment_id = appointment_id
                return True
            return False

    def get_doctor_schedules(self, doctor_id: int, date: datetime) -> List[Dict[str, Any]]:
        """
        获取医生指定日期的排班
        
        Args:
            doctor_id: 医生ID
            date: 查询日期
            
        Returns:
            排班信息列表
        """
        with self.session_manager.session_scope() as session:
            start = datetime(date.year, date.month, date.day)
            end = start + timedelta(days=1)
            
            schedules = session.query(DoctorSchedule).filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.start_time >= start,
                DoctorSchedule.end_time < end
            ).all()
            
            return [self._schedule_to_dict(schedule) for schedule in schedules]

    def is_doctor_available(self, doctor_id: int, start_time: datetime, end_time: datetime) -> bool:
        """
        检查医生在指定时间段是否可用：
        1. 时间段在营业时间内（用规则判断，不依赖free排班记录是否存在）
        2. 没有busy/on_leave排班与该时间段冲突

        注意：不再要求free排班记录存在，因为free排班只在预约时用来标记busy，
        未来日期的空闲状态通过"营业时间 - busy冲突"来推导。

        Args:
            doctor_id: 医生ID
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            是否可用
        """
        from config.time_config import time_config

        # 1. 检查是否在营业时间内（快速规则判断）
        weekday = start_time.weekday()  # 0=周一..6=周日
        if weekday < 5:
            open_hour, close_hour = time_config.get_business_hours()
            # 工作日有午休 12:00-14:00
            lunch_start, lunch_end = 12, 14
        else:
            open_hour, close_hour = time_config.get_weekend_business_hours()
            lunch_start, lunch_end = None, None  # 周末无午休（按配置）

        start_hour = start_time.hour + start_time.minute / 60.0
        end_hour = end_time.hour + end_time.minute / 60.0

        # 开始时间早于营业时间
        if start_hour < open_hour:
            return False
        # 结束时间晚于营业时间
        if end_hour > close_hour:
            return False
        # 工作日午休时段
        if lunch_start is not None:
            # 开始时间在午休内
            if lunch_start <= start_hour < lunch_end:
                return False
            # 结束时间在午休内（跨午休）
            if start_hour < lunch_start and end_hour > lunch_start:
                return False

        # 2. 检查是否有冲突的busy/on_leave记录
        with self.session_manager.session_scope() as session:
            conflict = session.query(DoctorSchedule).filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.status.in_(["busy", "on_leave"]),
                DoctorSchedule.start_time < end_time,
                DoctorSchedule.end_time > start_time
            ).first()
            if conflict:
                return False

        return True

    def find_free_schedule(self, doctor_id: int, start_time: datetime, end_time: datetime):
        """
        查找覆盖指定时间段的free排班记录

        Returns:
            排班ID（int），未找到返回None
        """
        with self.session_manager.session_scope() as session:
            schedule = session.query(DoctorSchedule).filter(
                DoctorSchedule.doctor_id == doctor_id,
                DoctorSchedule.status == "free",
                DoctorSchedule.start_time <= start_time,
                DoctorSchedule.end_time >= end_time
            ).first()
            return schedule.id if schedule else None

    def mark_schedule_busy(self, schedule_id: int, appointment_id: int) -> bool:
        """将指定free排班更新为busy状态并关联appointment_id"""
        with self.session_manager.session_scope() as session:
            schedule = session.query(DoctorSchedule).filter(
                DoctorSchedule.id == schedule_id
            ).first()
            if schedule and schedule.status == 'free':
                schedule.status = 'busy'
                schedule.appointment_id = appointment_id
                return True
            return False

    def update_schedule_status(self, schedule_id: int, status: str, appointment_id: Optional[int] = None) -> bool:
        """
        更新排班状态
        
        Args:
            schedule_id: 排班ID
            status: 新状态
            appointment_id: 预约ID
            
        Returns:
            更新是否成功
        """
        with self.session_manager.session_scope() as session:
            schedule = session.query(DoctorSchedule).filter(
                DoctorSchedule.id == schedule_id
            ).first()
            
            if not schedule:
                return False
                
            schedule.status = status
            if appointment_id is not None:
                schedule.appointment_id = appointment_id
                
            return True

    def delete_schedule(self, schedule_id: int) -> bool:
        """
        删除排班

        Args:
            schedule_id: 排班ID

        Returns:
            删除是否成功
        """
        with self.session_manager.session_scope() as session:
            schedule = session.query(DoctorSchedule).filter(
                DoctorSchedule.id == schedule_id
            ).first()

            if not schedule:
                return False

            session.delete(schedule)
            return True

    # ===========================
    # 预约主表操作
    # ===========================

    def create_appointment(self, user_id: str, doctor_id: int, schedule_id: int,
                           start_time: datetime, end_time: datetime,
                           conversation_id: Optional[str] = None,
                           reason: Optional[str] = None) -> int:
        """
        创建预约记录

        Returns:
            新预约ID
        """
        with self.session_manager.session_scope() as session:
            appointment = Appointment(
                user_id=user_id,
                doctor_id=doctor_id,
                schedule_id=schedule_id,
                start_time=start_time,
                end_time=end_time,
                conversation_id=conversation_id,
                reason=reason,
                status='confirmed'
            )
            session.add(appointment)
            session.flush()
            return appointment.id

    def get_user_active_appointment(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户当前有效的预约（status=confirmed 且未过期）

        Returns:
            预约信息字典（含医生姓名），无有效预约返回 None
        """
        now = datetime.now()
        with self.session_manager.session_scope() as session:
            appointment = session.query(Appointment).filter(
                Appointment.user_id == user_id,
                Appointment.status == 'confirmed'
            ).first()

            if not appointment:
                return None

            doctor = session.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()

            return {
                'id': appointment.id,
                'user_id': appointment.user_id,
                'doctor_id': appointment.doctor_id,
                'doctor_name': doctor.name if doctor else '未知医生',
                'schedule_id': appointment.schedule_id,
                'start_time': appointment.start_time,
                'end_time': appointment.end_time,
                'reason': appointment.reason,
                'created_at': appointment.created_at,
                'is_expired': appointment.end_time < now
            }

    def cancel_appointment_txn(self, appointment_id: int, schedule_id: int) -> bool:
        """
        事务性取消预约：同时更新 appointments 表和 doctor_schedules 表

        Args:
            appointment_id: 预约ID（可以为None，此时仅释放schedule）
            schedule_id: 对应排班ID

        Returns:
            是否成功
        """
        with self.session_manager.session_scope() as session:
            updated = False

            if appointment_id:
                appointment = session.query(Appointment).filter(
                    Appointment.id == appointment_id
                ).first()
                if appointment and appointment.status != 'cancelled':
                    appointment.status = 'cancelled'
                    appointment.cancelled_at = datetime.now()
                    updated = True
                elif appointment and appointment.status == 'cancelled':
                    updated = True  # 已经取消过，继续释放schedule

            if schedule_id:
                schedule = session.query(DoctorSchedule).filter(
                    DoctorSchedule.id == schedule_id
                ).first()
                if schedule and schedule.status != 'free':
                    schedule.status = 'free'
                    schedule.appointment_id = None
                    updated = True

            return updated

    def get_available_doctors_at_time(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        获取指定时间段可用的医生列表
        
        Args:
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            医生信息列表
        """
        with self.session_manager.session_scope() as session:
            # 查找在指定时间段没有冲突的医生
            busy_doctors = session.query(DoctorSchedule.doctor_id).filter(
                DoctorSchedule.status.in_(["busy", "on_leave"]),
                DoctorSchedule.start_time < end_time,
                DoctorSchedule.end_time > start_time
            ).all()
            
            busy_doctor_ids = [d[0] for d in busy_doctors]
            
            doctors = session.query(Doctor).filter(
                ~Doctor.id.in_(busy_doctor_ids) if busy_doctor_ids else True
            ).all()
            
            return [self._doctor_to_dict(doc) for doc in doctors]

    # ===========================
    # 辅助方法
    # ===========================
    
    def _doctor_to_dict(self, doctor: Doctor) -> Dict[str, Any]:
        """将医生对象转换为字典"""
        return {
            'id': doctor.id,
            'name': doctor.name,
            'gender': doctor.gender,
            'specialty': doctor.specialty,
            'license_number': doctor.license_number,
            'education': doctor.education,
            'years_of_experience': doctor.years_of_experience,
            'consultation_rating': doctor.consultation_rating,
            'max_daily_appointments': doctor.max_daily_appointments
        }

    def _schedule_to_dict(self, schedule: DoctorSchedule) -> Dict[str, Any]:
        """将排班对象转换为字典"""
        return {
            'id': schedule.id,
            'doctor_id': schedule.doctor_id,
            'start_time': schedule.start_time,
            'end_time': schedule.end_time,
            'status': schedule.status,
            'shift_type': schedule.shift_type,
            'appointment_id': schedule.appointment_id
        }


# 向后兼容别名
class TechnicianRepository(DoctorRepository):
    """向后兼容别名 - 将 Technician 映射到 Doctor"""

    def add_technician(self, name: str, gender: Optional[str] = None, strength: Optional[str] = None) -> int:
        """向后兼容：添加医生"""
        specialty = strength or "General"
        return self.add_doctor(name=name, specialty=specialty, license_number=f"LIC-{name}", gender=gender)

    def get_technician_by_id(self, technician_id: int) -> Optional[Dict[str, Any]]:
        """向后兼容：根据ID获取医生"""
        return self.get_doctor_by_id(technician_id)

    def get_all_technicians(self) -> List[Dict[str, Any]]:
        """向后兼容：获取所有医生"""
        return self.get_all_doctors()

    def get_technician_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """向后兼容：根据姓名获取医生"""
        return self.get_doctor_by_name(name)

    def get_technicians_by_gender(self, gender: str) -> List[Dict[str, Any]]:
        """向后兼容：根据性别获取医生"""
        return self.get_doctors_by_gender(gender)

    def get_technician_schedules(self, doctor_id: int, date) -> List[Dict[str, Any]]:
        """向后兼容：获取医生排班"""
        return self.get_doctor_schedules(doctor_id, date)

    def is_technician_available(self, technician_id: int, start_time: datetime, end_time: datetime) -> bool:
        """向后兼容：检查医生是否可用"""
        return self.is_doctor_available(technician_id, start_time, end_time)
