"""
医生查找器（替换旧的技师查找器）

负责根据用户需求查找合适的医生（医院/校医）
"""
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timedelta
from services.text_embedding import find_best_match_indices


class DoctorFinder:
    """医生查找器（兼具原技师查找逻辑）"""
    def __init__(self):
        pass

    def parse_time_and_duration(self, start_time_str: str, duration_str: str) -> tuple:
        if not start_time_str or start_time_str == "未知":
            return None, None, None

        if not duration_str or duration_str == "未知":
            return None, None, None

        try:
            from config.time_config import time_config
            start_time = time_config.parse_datetime(start_time_str)
            if start_time is None:
                return None, None, None

            duration_min = int(''.join(filter(str.isdigit, str(duration_str))))
            if duration_min <= 0:
                return None, None, None

            end_time = start_time + timedelta(minutes=duration_min)
            return start_time, end_time, duration_min
        except Exception:
            return None, None, None

    def find_specific_technician(self, doctor_name: str, start_time: datetime,
                               end_time: datetime, yield_func: Optional[Callable] = None) -> Optional[Dict]:
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()

        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 用户指定了医生：{doctor_name}，正在查询该医生信息...\n")

        specific = appointment_service.get_doctor_by_name(doctor_name)
        if specific:
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] 找到医生：{specific['name']}（{specific.get('specialty', '')}），正在检查档期...\n")

            if appointment_service.is_doctor_available(specific["id"], start_time, end_time):
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] {doctor_name}医生在指定时间有空\n")
                return specific
            else:
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] {doctor_name}医生在指定时间不空闲\n")
                return None
        else:
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] 未找到名为'{doctor_name}'的医生\n")
            return None

    def find_similar_available_technician(self, target_technician: Dict[str, Any],
                                        start_time: datetime, end_time: datetime,
                                        yield_func: Optional[Callable] = None) -> Optional[Dict]:
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()

        target_specialty = target_technician.get('specialty', '') or target_technician.get('strength', '')
        duration_min = int((end_time - start_time).total_seconds() / 60) if end_time and start_time else 30

        # 1. 优先找该医生自己最近的空闲时间
        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] {target_technician['name']}医生当前时段无空闲，正在查找该医生最近可预约时间...\n")
        next_slot = self._find_next_available_slot(target_technician['id'], start_time, duration_min)
        if next_slot:
            from config.time_config import time_config
            time_str = time_config.format_datetime(next_slot, "%m月%d日%H:%M")
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] 找到{target_technician['name']}医生最近可预约时间：{time_str}\n")
            return {
                'is_time_recommendation': True,
                'original_time': start_time,
                'recommended_doctor': target_technician,
                'recommended_time': next_slot,
                'requires_confirmation': True
            }

        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 正在查找{target_specialty}科室其他医生的可预约时间...\n")

        # 2. 找同科室其他医生
        all_techs = appointment_service.get_all_doctors()
        same_specialty = [t for t in all_techs
                          if t['id'] != target_technician['id']
                          and (t.get('specialty', '') == target_specialty
                               or t.get('strength', '') == target_specialty)]
        if same_specialty:
            nearest = self._find_nearest_available_for_specialty(same_specialty, start_time, duration_min, yield_func)
            if nearest:
                return nearest

        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 没有找到可用的医生\n")
        return None

    def filter_doctors_by_specialty(self, all_techs: list, project: str) -> list:
        """按科室（specialty）筛选医生，精确匹配优先，模糊匹配兜底"""
        if not project or project == "未知":
            return all_techs

        project = project.strip()

        # 1. 精确匹配科室
        exact = [t for t in all_techs if t.get('specialty', '') == project]
        if exact:
            return exact

        # 2. 包含匹配（如"内科"匹配"消化内科"、"心内科"等）
        contains = [t for t in all_techs if project in t.get('specialty', '') or t.get('specialty', '') in project]
        if contains:
            return contains

        # 3. 语义相似度匹配
        specialties = [t.get('specialty', '') for t in all_techs]
        indices = find_best_match_indices(project, specialties)
        if indices:
            # 返回相似度最高的几个
            return [all_techs[i] for i in indices[:max(3, len(all_techs) // 2)]]

        return all_techs

    def filter_technicians_by_gender(self, all_techs: list, gender: str) -> list:
        if not gender or gender == "未知" or gender == "无":
            return all_techs

        gender = gender.strip().lower()
        if gender in ["男", "男性", "male"]:
            target_gender = "男"
        elif gender in ["女", "女性", "female"]:
            target_gender = "女"
        else:
            return all_techs

        filtered = []
        for tech in all_techs:
            tech_gender = tech.get("gender", "").strip()
            if tech_gender == target_gender:
                filtered.append(tech)

        return filtered if filtered else all_techs

    def _find_next_available_slot(self, doctor_id: int, start_time: datetime,
                                  duration_min: int, search_days: int = 7) -> Optional[datetime]:
        """
        查找某医生在指定时间之后最近的可预约时间段（按30分钟步长推进）

        Args:
            doctor_id: 医生ID
            start_time: 用户期望的起始时间
            duration_min: 预约时长（分钟）
            search_days: 最多向后搜索多少天

        Returns:
            最近可用的开始时间，找不到返回None
        """
        from services.appointment_service import AppointmentService
        from config.time_config import time_config
        appointment_service = AppointmentService()

        step = timedelta(minutes=30)
        max_search = start_time + timedelta(days=search_days)
        candidate = start_time

        while candidate < max_search:
            # 检查是否在营业时间内
            weekday = candidate.weekday()
            if weekday < 5:
                open_hour, close_hour = time_config.get_business_hours()
                lunch_start, lunch_end = 12, 14  # 工作日午休
            else:
                open_hour, close_hour = time_config.get_weekend_business_hours()
                lunch_start, lunch_end = None, None  # 周末无午休

            # 早于营业时间开始：对齐到当日营业时间开头
            if candidate.hour < open_hour:
                candidate = candidate.replace(hour=open_hour, minute=0)
                continue

            # 工作日：如果候选时间在午休时段，跳到下午14:00
            if lunch_start is not None and lunch_start <= candidate.hour < lunch_end:
                candidate = candidate.replace(hour=lunch_end, minute=0)
                continue

            cand_end = candidate + timedelta(minutes=duration_min)
            cand_end_hour = cand_end.hour + cand_end.minute / 60.0

            # 工作日：如果开始在上午但结束跨进了午休，跳到下午
            if (lunch_start is not None
                    and candidate.hour < lunch_start
                    and cand_end_hour > lunch_start):
                candidate = candidate.replace(hour=lunch_end, minute=0)
                continue

            # 时间段超出当日营业时间，跳到下一个营业日开头
            if cand_end_hour > close_hour:
                candidate = candidate.replace(hour=open_hour, minute=0) + timedelta(days=1)
                continue

            # 检查可用性
            end_time = candidate + timedelta(minutes=duration_min)
            if appointment_service.is_doctor_available(doctor_id, candidate, end_time):
                return candidate

            candidate += step

        return None

    def _find_nearest_available_for_specialty(self, doctors: List[Dict], start_time: datetime,
                                               duration_min: int,
                                               yield_func: Optional[Callable] = None) -> Optional[Dict]:
        """
        在同科室医生列表中，找到最近可预约的医生和时间

        Returns:
            {
                'is_time_recommendation': True,
                'original_time': start_time,
                'recommended_doctor': doctor_dict,
                'recommended_time': datetime,
                'requires_confirmation': True
            } 或 None
        """
        best_result = None
        best_time = None

        for doc in doctors:
            slot = self._find_next_available_slot(doc['id'], start_time, duration_min)
            if slot is not None:
                if best_time is None or slot < best_time:
                    best_time = slot
                    best_result = {
                        'is_time_recommendation': True,
                        'original_time': start_time,
                        'recommended_doctor': doc,
                        'recommended_time': slot,
                        'requires_confirmation': True
                    }

        if best_result and yield_func:
            from config.time_config import time_config
            time_str = time_config.format_datetime(best_time, "%m月%d日%H:%M")
            yield_func(f"[THOUGHT][预约机器人] 同科室最近可预约时间：{best_result['recommended_doctor']['name']}医生 {time_str}\n")

        return best_result

    def find_available_doctor(self, filtered_techs: list, start_time: datetime, end_time: datetime,
                              yield_func: Optional[Callable] = None) -> Optional[Dict]:
        """从候选医生中找第一个在指定时间段有排班且空闲的医生"""
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()

        for tech in filtered_techs:
            if appointment_service.is_doctor_available(tech["id"], start_time, end_time):
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] 找到可用医生：{tech['name']}（{tech.get('specialty', tech.get('strength', ''))}）\n")
                return tech

        return None

    def find_doctor_with_thought(self, appointment_history, yield_func=None):
        return self.find_technician_with_thought(appointment_history, yield_func)

    def find_technician_with_thought(self, appointment_history: Dict[str, Any],
                                   yield_func: Optional[Callable] = None) -> Optional[Dict]:
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()

        project = appointment_history.get("project")  # 科室
        gender = appointment_history.get("gender")
        start_time_str = appointment_history.get("start_time")
        duration_str = appointment_history.get("duration")
        doctor_name = appointment_history.get("doctor_name")

        start_time, end_time, duration_min = self.parse_time_and_duration(start_time_str, duration_str)
        if not start_time or not end_time:
            if yield_func:
                yield_func("[THOUGHT][预约机器人] 预约时间或时长信息不完整，无法检索医生\n")
            return None

        if yield_func:
            yield_func("[THOUGHT][预约机器人] 正在解析预约时间和时长...\n")

        # 1. 用户指定了医生姓名：优先匹配指定医生
        if doctor_name and doctor_name != "未知":
            specific_tech = self.find_specific_technician(doctor_name, start_time, end_time, yield_func)
            if specific_tech:
                # 校验指定医生的科室是否匹配（如果用户同时说了科室）
                if project and project != "未知":
                    doc_specialty = specific_tech.get('specialty', '')
                    if doc_specialty and project not in doc_specialty and doc_specialty not in project:
                        # 科室不匹配，提醒但仍然返回（尊重用户指名）
                        if yield_func:
                            yield_func(f"[THOUGHT][预约机器人] 注意：{doctor_name}医生的科室是{doc_specialty}，与您选择的{project}不同\n")
                return specific_tech

            # 指定医生没空，推荐同医生最近时间或同科室其他医生最近时间
            target_tech = appointment_service.get_doctor_by_name(doctor_name)
            if target_tech:
                similar_tech = self.find_similar_available_technician(target_tech, start_time, end_time, yield_func)
                if similar_tech:
                    # similar_tech 本身已经是完整的推荐结构体（含 requires_confirmation）
                    similar_tech['original_doctor'] = target_tech
                    return similar_tech

            return None

        # 2. 未指定医生：按科室+性别筛选
        if yield_func:
            yield_func("[THOUGHT][预约机器人] 正在检索医生数据...\n")

        all_techs = appointment_service.get_all_doctors()
        if not all_techs:
            if yield_func:
                yield_func("[THOUGHT][预约机器人] 没有找到任何医生数据\n")
            return None

        # 2.1 先按科室筛选（核心：必须匹配科室）
        specialty_filtered = self.filter_doctors_by_specialty(all_techs, project)
        if yield_func and project and project != "未知":
            yield_func(f"[THOUGHT][预约机器人] 根据科室'{project}'筛选，找到{len(specialty_filtered)}位相关医生\n")

        # 2.2 再按性别筛选
        final_candidates = self.filter_technicians_by_gender(specialty_filtered, gender)
        if yield_func and gender and gender != "未知":
            yield_func(f"[THOUGHT][预约机器人] 根据性别'{gender}'进一步筛选\n")

        # 2.3 从候选中查找可用医生
        found = self.find_available_doctor(final_candidates, start_time, end_time, yield_func)
        if found:
            return found

        # 2.4 科室+性别筛选后无空闲，放宽性别限制，在同科室里找
        if gender and gender != "未知" and final_candidates != specialty_filtered:
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] {gender}医生暂无空闲，正在{project or '所有'}科室中查找其他医生...\n")
            found = self.find_available_doctor(specialty_filtered, start_time, end_time, yield_func)
            if found:
                return found

        # 2.5 同科室完全没空闲，推荐同科室医生最近可预约时间
        duration_min = int((end_time - start_time).total_seconds() / 60) if end_time and start_time else 30

        if project and project != "未知":
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] {project}科室当前时段无空闲医生，正在查找最近可预约时间...\n")
            nearest = self._find_nearest_available_for_specialty(
                specialty_filtered, start_time, duration_min, yield_func
            )
            if nearest:
                return nearest

        if yield_func:
            yield_func("[THOUGHT][预约机器人] 没有找到空闲医生\n")
        return None
