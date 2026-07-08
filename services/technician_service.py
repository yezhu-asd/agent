# utils/ai/doctor_service.py

from typing import List, Dict, Any
from db.db_router import DatabaseRouter
import logging

logger = logging.getLogger(__name__)

class TechnicianService:
    """医生服务类 - 管理医生数据和默认初始化"""

    def __init__(self):
        self.db = DatabaseRouter()

        # 默认医生数据（10人，其中有两位擅长内容接近）
        self.default_doctors = [
            {
                "name": "张伟",
                "gender": "男",
                "strength": "擅长深层组织按摩，力气大，善于缓解肩颈腰背酸痛，注重肌肉深层放松"
            },
            {
                "name": "王强",
                "gender": "男",
                "strength": "深层组织按摩专家，手法扎实，专注于运动损伤修复和肌肉放松"
            },
            {
                "name": "李娜",
                "gender": "女",
                "strength": "手法细腻，擅长舒缓放松，适合压力大、睡眠差人群"
            },
            {
                "name": "赵敏",
                "gender": "女",
                "strength": "精通经络推拿，善于调理亚健康，力气适中"
            },
            {
                "name": "刘洋",
                "gender": "男",
                "strength": "泰式按摩高手，拉伸到位，适合喜欢全身放松的客户"
            },
            {
                "name": "孙丽",
                "gender": "女",
                "strength": "芳香精油按摩，舒缓情绪，适合女性客户"
            },
            {
                "name": "周杰",
                "gender": "男",
                "strength": "中医推拿，针对颈椎、腰椎问题有丰富经验"
            },
            {
                "name": "吴婷",
                "gender": "女",
                "strength": "头部按摩和足疗专家，助眠效果好"
            },
            {
                "name": "郑斌",
                "gender": "男",
                "strength": "力气大，适合喜欢重手法的客户，善于肌肉放松"
            },
            {
                "name": "何静",
                "gender": "女",
                "strength": "淋巴引流、面部护理，适合美容养生需求"
            }
        ]

    def initialize_default_doctors(self) -> bool:
        """初始化默认医生数据"""
        try:
            # 检查是否已有医生数据
            existing_doctors = self.db.doctors.get_all_doctors()

            if existing_doctors:
                logger.info(f"数据库中已有 {len(existing_doctors)} 位医生，跳过初始化")
                return True

            logger.info("数据库中无医生数据，开始初始化默认医生")

            # 添加默认医生
            for doc_data in self.default_doctors:
                try:
                    doc_id = self.db.doctors.add_doctor(
                        name=doc_data['name'],
                        gender=doc_data['gender'],
                        strength=doc_data['strength']
                    )
                    logger.debug(f"添加医生: {doc_data['name']} (ID: {doc_id})")

                except Exception as e:
                    logger.error(f"添加医生 {doc_data['name']} 失败: {e}")
                    return False

            # 验证初始化结果
            final_count = len(self.db.doctors.get_all_doctors())
            logger.info(f"医生初始化完成，共添加 {final_count} 位医生")
            return True

        except Exception as e:
            logger.error(f"医生初始化失败: {e}")
            return False

    def get_all_doctors(self) -> List[Dict[str, Any]]:
        """获取所有医生信息"""
        return self.db.doctors.get_all_doctors()

    def get_doctor_by_name(self, name: str) -> Dict[str, Any]:
        """根据姓名获取医生信息"""
        return self.db.doctors.get_doctor_by_name(name)

    def get_doctor_by_id(self, doctor_id: int) -> Dict[str, Any]:
        """根据ID获取医生信息"""
        return self.db.doctors.get_doctor_by_id(doctor_id)

    def get_doctor_schedules(self, doctor_id: int, date) -> List[Dict[str, Any]]:
        """获取医生指定日期的排班信息"""
        return self.db.doctors.get_doctor_schedules(doctor_id, date)

    def is_doctor_available(self, doctor_id: int, start_time, end_time) -> bool:
        """检查医生在指定时间段是否可用"""
        return self.db.doctors.is_doctor_available(doctor_id, start_time, end_time)

    def add_doctor(self, name: str, gender: str = None, strength: str = None) -> int:
        """添加新医生"""
        return self.db.doctors.add_doctor(name, gender, strength)

    def get_doctors_count(self) -> int:
        """获取医生总数"""
        doctors = self.db.doctors.get_all_doctors()
        return len(doctors)

    def get_doctor_by_id(self, doctor_id: int) -> Dict[str, Any]:
        """根据ID获取医生信息"""
        return self.db.doctors.get_doctor_by_id(doctor_id)

    def get_doctor_schedules(self, doctor_id: int, date) -> List[Dict[str, Any]]:
        """获取医生指定日期的排班信息"""
        return self.db.doctors.get_doctor_schedules(doctor_id, date)

    def is_doctor_available(self, doctor_id: int, start_time, end_time) -> bool:
        """检查医生在指定时间段是否可用"""
        return self.db.doctors.is_doctor_available(doctor_id, start_time, end_time)
