"""
预约数据库操作器

负责处理预约相关的数据库操作
注意：现在通过Services层访问数据库，符合分层架构
"""
# 作用：提供一个接口来保存预约信息到数据库，并记录用户行为；同时更新内存中的医生忙碌时间段，以便后续预约查询使用。
# 保存的预约信息包括医生ID、预约开始和结束时间、预约历史上下文记录以及会话ID；在保存成功后，还会调用用户行为服务记录用户的预约行为，
# 包括预约时间、项目、偏好等信息；此外，还会更新内存中的医生忙碌时间段，以便后续查询时能够正确判断医生的可用性。
from typing import Dict, Any, Optional
from datetime import datetime
from config.time_config import time_config
from config.constants import busy_periods_dict


class AppointmentDatabase:
    """预约数据库操作器"""
    
    def __init__(self):
        # 延迟导入Services避免循环依赖
        self._appointment_service = None
        self._user_behavior_service = None
    
    @property
    def appointment_service(self):
        """懒加载预约服务"""
        if self._appointment_service is None:
            from services.appointment_service import AppointmentService
            self._appointment_service = AppointmentService()
        return self._appointment_service
    
    @property 
    def user_behavior_service(self):
        """懒加载用户行为服务"""
        if self._user_behavior_service is None:
            from services.user_behavior_service import UserBehaviorService
            self._user_behavior_service = UserBehaviorService()
        return self._user_behavior_service
    
    def save_appointment(self, doctor_id: str, start_time: datetime,
                        end_time: datetime, appointment_history: Dict[str, Any],
                        session_id: str, user_id: str = None,
                        conversation_id: str = None) -> Optional[Dict[str, Any]]:
        """保存预约信息到数据库

        Returns:
            {'appointment_id': int, 'schedule_id': int}，失败返回 None
        """
        try:
            result = self.appointment_service.save_appointment(
                doctor_id, start_time, end_time, appointment_history, session_id,
                user_id=user_id, conversation_id=conversation_id
            )

            if result:
                self._record_user_behavior(start_time, end_time, doctor_id,
                                         appointment_history, session_id)

            return result

        except Exception as e:
            print(f"保存预约信息到数据库失败：{e}")
            return None

    def get_user_active_appointment(self, user_id: str) -> Optional[Dict[str, Any]]:
        """查询用户当前有效预约"""
        try:
            return self.appointment_service.get_user_active_appointment(user_id)
        except Exception as e:
            print(f"查询用户预约失败：{e}")
            return None

    def cancel_appointment(self, appointment_id: int, schedule_id: int,
                           doctor_id: str, start_time: datetime, end_time: datetime) -> bool:
        """取消预约：更新DB释放时间段，同时清理内存缓存"""
        try:
            success = self.appointment_service.cancel_appointment(appointment_id, schedule_id)
            if success:
                self.remove_memory_schedule(doctor_id, start_time, end_time)
            return success
        except Exception as e:
            print(f"取消预约失败：{e}")
            return False

    def remove_memory_schedule(self, doctor_id: str, start_time, end_time):
        """从内存缓存中移除医生的忙碌时间段"""
        start_str = self._format_time_str(start_time, "%H:%M")
        end_str = self._format_time_str(end_time, "%H:%M")
        if not start_str or not end_str:
            return
        for key in [str(doctor_id)]:
            periods = busy_periods_dict.get(key, [])
            busy_periods_dict[key] = [
                p for p in periods
                if not (p.get("start") == start_str and p.get("end") == end_str)
            ]
        # 同时用数字key尝试
        if str(doctor_id).isdigit():
            int_key = int(doctor_id)
            periods_int = busy_periods_dict.get(int_key, [])
            busy_periods_dict[int_key] = [
                p for p in periods_int
                if not (p.get("start") == start_str and p.get("end") == end_str)
            ]

    def update_memory_schedule(self, doctor_id: str, start_time, end_time):
        """更新内存中的医生忙碌时间段"""
        start_str = self._format_time_str(start_time, "%H:%M")
        end_str = self._format_time_str(end_time, "%H:%M")
        if not start_str or not end_str:
            return
        busy_period = {"start": start_str, "end": end_str}
        busy_periods_dict.setdefault(str(doctor_id), []).append(busy_period)

    @staticmethod
    def _format_time_str(t, fmt: str) -> str:
        """将时间（datetime或字符串）格式化为指定格式字符串"""
        from datetime import datetime as dt
        try:
            if isinstance(t, dt):
                return t.strftime(fmt)
            if isinstance(t, str):
                # 尝试解析常见的字符串格式
                for parse_fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]:
                    try:
                        return dt.strptime(t[:19] if 'T' in t else t[:16], parse_fmt).strftime(fmt)
                    except ValueError:
                        continue
                return None
            return None
        except Exception:
            return None
    
    def _record_user_behavior(self, start_time: datetime, end_time: datetime,
                            doctor_id: str, appointment_history: Dict[str, Any],
                            session_id: str):
        """记录用户预约行为"""
        try:
            action_data = {
                'start_time': time_config.format_datetime(start_time, "%Y-%m-%d %H:%M:%S"),
                'end_time': time_config.format_datetime(end_time, "%Y-%m-%d %H:%M:%S"),
                'duration': int((end_time - start_time).total_seconds() / 60),
                'project': appointment_history.get('project', 'massage'),
                'preference': appointment_history.get('preference', ''),
                'technician_id': doctor_id
            }

            # 通过Services层记录用户行为
            self.user_behavior_service.record_behavior(
                user_id="default_user",  # 统一使用default_user作为用户ID
                action_type='appointment',
                action_data=action_data,
                doctor_id=str(doctor_id),
                session_id=session_id
            )
            
        except Exception as behavior_error:
            print(f"记录用户行为失败（但预约仍然成功）：{behavior_error}")
