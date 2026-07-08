from .base import SessionManager
from .repositories import TechnicianRepository, KnowledgeRepository, UserBehaviorRepository, ConsultationRepository
from typing import Optional

from config.settings import settings


class DatabaseRouter:
    """
    数据库路由器

    职责：
    1. 管理数据库连接和会话（MySQL / SQLite）
    2. 提供统一的数据访问入口
    3. 协调各个Repository的操作
    """

    def __init__(self, db_url: str | None = None):
        """
        初始化数据库路由器

        Args:
            db_url: 数据库连接 URL，默认使用 settings.DATABASE_URL
        """
        db_url = db_url or settings.DATABASE_URL
        self.session_manager = SessionManager(db_url)

        # 初始化各个Repository
        self.technician_repo = TechnicianRepository(self.session_manager)
        self.knowledge_repo = KnowledgeRepository(self.session_manager)
        self.user_behavior_repo = UserBehaviorRepository(self.session_manager)
        self.consultation_repo = ConsultationRepository(self.session_manager)

    @property
    def technicians(self) -> TechnicianRepository:
        """获取医生数据仓库"""
        return self.technician_repo

    @property
    def doctors(self) -> TechnicianRepository:
        """获取医生数据仓库（technicians 的别名）"""
        return self.technician_repo

    @property
    def knowledge(self) -> KnowledgeRepository:
        """获取知识库数据仓库"""
        return self.knowledge_repo

    @property
    def user_behavior(self) -> UserBehaviorRepository:
        """获取用户行为数据仓库"""
        return self.user_behavior_repo

    @property
    def consultations(self) -> ConsultationRepository:
        """获取问诊记录数据仓库"""
        return self.consultation_repo

    def close(self):
        """关闭数据库连接"""
        self.session_manager.close()


# 为了兼容性，保留原有的类名
class TechnicianDBRouter:
    """
    医生数据库路由器（兼容性类）

    为保持向后兼容，继续支持原有的接口
    """

    def __init__(self, db_type='local', **kwargs):
        self.db_router = DatabaseRouter(**kwargs)
        self.doctor_repo = self.db_router.technicians

    # 医生相关方法
    def add_doctor(self, name, gender=None, strength=None) -> None:
        return self.doctor_repo.add_technician(name, gender, strength)

    def get_doctor_by_name(self, name: str):
        return self.doctor_repo.get_technician_by_name(name)

    def get_doctor_by_id(self, doctor_id: int):
        return self.doctor_repo.get_technician_by_id(doctor_id)

    def get_all_doctors(self):
        return self.doctor_repo.get_all_technicians()

    def get_all_strengths(self):
        return self.doctor_repo.get_all_strengths()

    # 排班相关方法
    def add_schedule(self, doctor_id: int, start_time, end_time, status, appointment_id=None) -> None:
        return self.doctor_repo.add_schedule(doctor_id, start_time, end_time, status, appointment_id)

    def get_doctor_schedules(self, doctor_id: int, date):
        return self.doctor_repo.get_technician_schedules(doctor_id, date)

    def is_doctor_available(self, doctor_id: int, start_time, end_time) -> bool:
        return self.doctor_repo.is_technician_available(doctor_id, start_time, end_time)

    def get_doctors_by_gender(self, gender: str):
        return self.doctor_repo.get_technicians_by_gender(gender)


class DoctorDBRouter:
    """
    医生数据库路由器（新的命名）

    保留与 TechnicianDBRouter 相同的接口以便平滑迁移，代码应逐步切换到使用 DoctorDBRouter。
    """

    def __init__(self, db_type='local', **kwargs):
        self.db_router = DatabaseRouter(**kwargs)
        self.doctor_repo = self.db_router.technicians

    # 医生相关方法（与旧的接口一一对应）
    def add_doctor(self, name, gender=None, strength=None) -> None:
        return self.doctor_repo.add_technician(name, gender, strength)

    def get_doctor_by_name(self, name: str):
        return self.doctor_repo.get_technician_by_name(name)

    def get_doctor_by_id(self, doctor_id: int):
        return self.doctor_repo.get_technician_by_id(doctor_id)

    def get_all_doctors(self):
        return self.doctor_repo.get_all_technicians()

    def get_all_strengths(self):
        return self.doctor_repo.get_all_strengths()

    # 排班相关方法
    def add_schedule(self, doctor_id: int, start_time, end_time, status, appointment_id=None) -> None:
        return self.doctor_repo.add_schedule(doctor_id, start_time, end_time, status, appointment_id)

    def get_doctor_schedules(self, doctor_id: int, date):
        return self.doctor_repo.get_technician_schedules(doctor_id, date)

    def is_doctor_available(self, doctor_id: int, start_time, end_time) -> bool:
        return self.doctor_repo.is_technician_available(doctor_id, start_time, end_time)

    def get_doctors_by_gender(self, gender: str):
        return self.doctor_repo.get_technicians_by_gender(gender)


class KnowledgeDBRouter:
    """
    知识库数据库路由器（兼容性类）

    为保持向后兼容，继续支持原有的接口
    """

    def __init__(self, db_type='local', **kwargs):
        self.db_router = DatabaseRouter(**kwargs)
        self.knowledge_repo = self.db_router.knowledge

    def add_document(self, content: str, category: str, keywords=None, embedding=None) -> int:
        return self.knowledge_repo.add_document(content, category, keywords, embedding)

    def get_document(self, doc_id: int):
        return self.knowledge_repo.get_document(doc_id)

    def get_all_documents(self, include_inactive: bool = False):
        return self.knowledge_repo.get_all_documents(include_inactive)

    def update_document(self, doc_id: int, content=None, category=None, keywords=None, embedding=None) -> bool:
        return self.knowledge_repo.update_document(doc_id, content, category, keywords, embedding)

    def delete_document(self, doc_id: int, soft_delete: bool = True) -> bool:
        return self.knowledge_repo.delete_document(doc_id, soft_delete)

    def search_documents_by_category(self, category: str):
        return self.knowledge_repo.search_documents_by_category(category)

    def search_documents_by_keywords(self, keywords):
        return self.knowledge_repo.search_documents_by_keywords(keywords)

    def get_all_categories(self):
        return self.knowledge_repo.get_all_categories()

    def get_documents_count(self) -> int:
        return self.knowledge_repo.get_documents_count()


class UserBehaviorDBRouter:
    """
    用户行为数据库路由器（兼容性类）

    为保持向后兼容，继续支持原有的接口
    """

    def __init__(self, db_type='local', **kwargs):
        self.db_router = DatabaseRouter(**kwargs)
        self.user_behavior_repo = self.db_router.user_behavior

    def record_behavior(self, user_id: str, action_type: str, action_data=None, technician_id=None, session_id=None) -> int:
        return self.user_behavior_repo.record_behavior(user_id, action_type, action_data, technician_id, session_id)

    def get_user_behaviors(self, user_id: str, action_type=None, days_back=None):
        return self.user_behavior_repo.get_user_behaviors(user_id, action_type, days_back)

    def get_user_preferences(self, user_id: str):
        return self.user_behavior_repo.get_user_preferences(user_id)

    def update_user_preference(self, user_id: str, preference_type: str, preference_value: str, confidence_score: int = 1) -> bool:
        return self.user_behavior_repo.update_user_preference(user_id, preference_type, preference_value, confidence_score)
