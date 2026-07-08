"""
医生查找器

负责根据用户需求查找合适的医生
"""
#从上下文解析预约信息，包括医生姓名、性别、偏好、预约时间和时长等；优先查找指定医生的可用性，
#如果不可用则查找相似医生；如果没有指定医生，则根据性别和偏好筛选医生并查找可用医生；整个过程中提供思考提示以增强用户体验。
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from services.text_embedding import find_best_match_indices


class DoctorFinder:
    """医生查找器"""
    
    def __init__(self):
        pass
    
    def parse_time_and_duration(self, start_time_str: str, duration_str: str) -> tuple:
        """解析预约时间和时长"""
        if not start_time_str or start_time_str == "未知":
            return None, None, None

        if not duration_str or duration_str == "未知":
            return None, None, None

        try:
            from config.time_config import time_config
            start_time = time_config.parse_datetime(start_time_str)
            if start_time is None:
                return None, None, None
            
            # 从字符串中提取数字作为时长（分钟）
            duration_min = int(''.join(filter(str.isdigit, str(duration_str))))
            if duration_min <= 0:
                return None, None, None

            end_time = start_time + timedelta(minutes=duration_min)
            return start_time, end_time, duration_min
        except Exception:
            return None, None, None
    
    def find_specific_doctor(self, doctor_name: str, start_time: datetime,
                               end_time: datetime, yield_func: Optional[Callable] = None) -> Optional[Dict]:
        """查找指定医生的可用性"""
        # 通过Services层访问数据库
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()

        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 用户指定了医生：{doctor_name}，正在查询该医生信息...\n")

        specific_doc = appointment_service.get_technician_by_name(doctor_name)
        if specific_doc:
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] 找到医生：{specific_doc['name']}，正在检查档期...\n")

            if appointment_service.is_technician_available(specific_doc["id"], start_time, end_time):
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] {doctor_name}医生在指定时间有空\n")
                return specific_doc
            else:
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] {doctor_name}医生在指定时间不空闲\n")
                return None
        else:
            if yield_func:
                yield_func(f"[THOUGHT][预约机器人] 未找到名为'{doctor_name}'的医生\n")
            return None

    def find_similar_available_doctor(self, target_doctor: Dict[str, Any],
                                        start_time: datetime, end_time: datetime,
                                        yield_func: Optional[Callable] = None) -> Optional[Dict]:
        """根据目标医生的专长查找相似且可用的医生"""
        # 通过Services层访问数据库
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()
        
        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 正在根据{target_doctor['name']}的专长查找相似医生...\n")

        # 获取所有医生
        all_docs = appointment_service.get_all_technicians()
        if not all_docs:
            return None

        # 排除目标医生本身
        other_docs = [doc for doc in all_docs if doc['id'] != target_doctor['id']]
        if not other_docs:
            return None

        # 获取目标医生的专长
        target_strength = target_doctor.get('strength', '')
        if not target_strength:
            return None

        # 使用文本嵌入找到最相似的医生
        strengths = [doc.get('strength', '') for doc in other_docs]
        indices = find_best_match_indices(target_strength, strengths)

        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 根据专长相似度排序，准备检查可用性...\n")

        # 按相似度顺序检查医生可用性
        for index in indices:
            similar_doc = other_docs[index]
            if appointment_service.is_technician_available(similar_doc["id"], start_time, end_time):
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] 找到相似且可用的医生：{similar_doc['name']}\n")
                return similar_doc

        if yield_func:
            yield_func(f"[THOUGHT][预约机器人] 没有找到相似且可用的医生\n")
        return None
    
    def filter_doctors_by_preference(self, all_docs: list, preference: str) -> list:
        """根据偏好筛选医生"""
        if not preference or preference == "无":
            return all_docs

        strengths = [doc.get("strength", "") for doc in all_docs]
        indices = find_best_match_indices(preference, strengths)
        return [all_docs[i] for i in indices]

    def filter_doctors_by_gender(self, all_docs: list, gender: str) -> list:
        """根据性别筛选医生"""
        if not gender or gender == "未知" or gender == "无":
            return all_docs

        # 标准化性别表示
        gender = gender.strip().lower()
        if gender in ["男", "男性", "男医生", "male"]:
            target_gender = "男"
        elif gender in ["女", "女性", "女医生", "female"]:
            target_gender = "女"
        else:
            return all_docs

        # 筛选匹配性别的医生
        filtered_docs = []
        for doc in all_docs:
            doc_gender = doc.get("gender", "").strip()
            if doc_gender == target_gender:
                filtered_docs.append(doc)

        return filtered_docs if filtered_docs else all_docs  # 如果没有匹配的，返回所有医生
    
    def find_available_doctor(self, filtered_docs: list, all_docs: list,
                                start_time: datetime, end_time: datetime,
                                preference: str, gender: str = None, yield_func: Optional[Callable] = None) -> Optional[Dict]:
        """在医生列表中查找可用医生"""
        # 通过Services层访问数据库
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()

        if yield_func:
            yield_func("[THOUGHT][预约机器人] 正在查找空闲医生...\n")

        # 先在筛选后的医生中查找
        for doc in filtered_docs:
            if appointment_service.is_technician_available(doc["id"], start_time, end_time):
                if yield_func:
                    yield_func(f"[THOUGHT][预约机器人] 找到空闲医生：{doc['name']}\n")
                return doc

        # 如果有偏好但没找到，再在所有医生中查找
        if preference and preference != "无" and filtered_docs != all_docs:
            if yield_func:
                yield_func("[THOUGHT][预约机器人] 偏好医生无空闲，尝试查找所有医生...\n")
            for doc in all_docs:
                if appointment_service.is_technician_available(doc["id"], start_time, end_time):
                    if yield_func:
                        yield_func(f"[THOUGHT][预约机器人] 找到空闲医生：{doc['name']}\n")
                    return doc

        if yield_func:
            yield_func("[THOUGHT][预约机器人] 没有找到空闲医生\n")
        return None
    
    def find_doctor_with_thought(self, appointment_history: Dict[str, Any],
                                   yield_func: Optional[Callable] = None) -> Optional[Dict]:
        """带思考提示的医生检索流程"""
        # 通过Services层访问数据库
        from services.appointment_service import AppointmentService
        appointment_service = AppointmentService()
        
        preference = appointment_history.get("preference")
        gender = appointment_history.get("gender")
        start_time_str = appointment_history.get("start_time")
        duration_str = appointment_history.get("duration")
        technician_name = appointment_history.get("technician_name")

        # 解析时间和时长
        start_time, end_time, duration_min = self.parse_time_and_duration(start_time_str, duration_str)
        if not start_time or not end_time:
            if yield_func:
                yield_func("[THOUGHT][预约机器人] 预约时间或时长信息不完整，无法检索医生\n")
            return None

        if yield_func:
            yield_func("[THOUGHT][预约机器人] 正在解析预约时间和时长...\n")

        # 优先处理指定医生
        if technician_name and technician_name != "未知":
            specific_doc = self.find_specific_doctor(technician_name, start_time, end_time, yield_func)
            
            # 如果指定医生可用，直接返回
            if specific_doc:
                return specific_doc
            
            # 如果指定医生不可用，查找相似医生并返回推荐信息
            target_doc = appointment_service.get_technician_by_name(technician_name)
            if target_doc:
                similar_doc = self.find_similar_available_doctor(target_doc, start_time, end_time, yield_func)
                if similar_doc:
                    # 返回包含推荐信息的结果，但标记为需要用户确认
                    return {
                        'is_recommendation': True,
                        'original_doctor': target_doc,
                        'recommended_doctor': similar_doc,
                        'requires_confirmation': True
                    }
            
            # 如果没有找到目标医生或相似医生，返回None
            return None

        # 通用查询逻辑
        if yield_func:
            yield_func("[THOUGHT][预约机器人] 正在检索所有医生数据...\n")
        
        all_docs = appointment_service.get_all_technicians()
        if not all_docs:
            if yield_func:
                yield_func("[THOUGHT][预约机器人] 没有找到任何医生数据\n")
            return None

        # 先根据性别筛选医生
        gender_filtered_docs = self.filter_doctors_by_gender(all_docs, gender)
        if yield_func and gender and gender != "未知":
            yield_func(f"[THOUGHT][预约机器人] 根据性别'{gender}'筛选医生，找到{len(gender_filtered_docs)}位医生\n")

        # 再根据偏好筛选医生
        filtered_docs = self.filter_doctors_by_preference(gender_filtered_docs, preference)
        if yield_func and preference and preference != "无":
            yield_func(f"[THOUGHT][预约机器人] 根据偏好'{preference}'进一步筛选，找到{len(filtered_docs)}位医生\n")
        
        # 查找可用医生
        return self.find_available_doctor(filtered_docs, gender_filtered_docs, start_time, end_time, preference, gender, yield_func)
