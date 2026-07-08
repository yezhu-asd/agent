from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class BaseDoctorRepository(ABC):
    """
    医生数据访问抽象接口（替代 BaseTechnicianRepository）
    
    定义医生相关的所有数据操作方法
    """
    
    @abstractmethod
    def add_doctor(self, name: str, specialty: str, license_number: str, 
                   gender: Optional[str] = None, education: Optional[str] = None, 
                   years_of_experience: int = 0) -> int:
        """添加医生"""
        pass

    @abstractmethod
    def get_doctor_by_id(self, doctor_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取医生信息"""
        pass

    @abstractmethod
    def get_doctor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据姓名获取医生信息"""
        pass

    @abstractmethod
    def get_all_doctors(self) -> List[Dict[str, Any]]:
        """获取所有医生"""
        pass

    @abstractmethod
    def get_doctors_by_specialty(self, specialty: str) -> List[Dict[str, Any]]:
        """根据专科获取医生"""
        pass

    @abstractmethod
    def get_top_rated_doctors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """获取评分最高的医生"""
        pass

    @abstractmethod
    def update_doctor(self, doctor_id: int, **updates) -> bool:
        """更新医生信息"""
        pass

    @abstractmethod
    def delete_doctor(self, doctor_id: int) -> bool:
        """删除医生"""
        pass

    @abstractmethod
    def update_doctor_rating(self, doctor_id: int, rating: float) -> bool:
        """更新医生评分"""
        pass


class BaseScheduleRepository(ABC):
    """
    医生值班表数据访问抽象接口
    
    定义排班相关的所有数据操作方法
    """
    
    @abstractmethod
    def add_schedule(self, doctor_id: int, start_time: datetime, end_time: datetime, 
                    status: str, shift_type: Optional[str] = None, 
                    appointment_id: Optional[int] = None) -> int:
        """添加排班"""
        pass

    @abstractmethod
    def get_doctor_schedules(self, doctor_id: int, date: datetime) -> List[Dict[str, Any]]:
        """获取医生指定日期的排班"""
        pass

    @abstractmethod
    def is_doctor_available(self, doctor_id: int, start_time: datetime, end_time: datetime) -> bool:
        """检查医生时间段是否可用"""
        pass

    @abstractmethod
    def update_schedule_status(self, schedule_id: int, status: str, appointment_id: Optional[int] = None) -> bool:
        """更新排班状态"""
        pass

    @abstractmethod
    def get_available_doctors_at_time(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """获取指定时间段可用的医生列表"""
        pass

    @abstractmethod
    def delete_schedule(self, schedule_id: int) -> bool:
        """删除排班"""
        pass


# 向后兼容别名
BaseTechnicianRepository = BaseDoctorRepository


class BaseKnowledgeRepository(ABC):
    """
    知识库数据访问抽象接口
    
    定义知识库相关的所有数据操作方法
    """
    
    @abstractmethod
    def add_document(self, content: str, category: str, keywords: Optional[List[str]] = None, 
                    embedding: Optional[List[float]] = None) -> int:
        """添加知识文档"""
        pass
    
    @abstractmethod
    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """获取指定文档"""
        pass
    
    @abstractmethod
    def get_all_documents(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """获取所有文档"""
        pass
    
    @abstractmethod
    def update_document(self, doc_id: int, content: Optional[str] = None, category: Optional[str] = None, 
                       keywords: Optional[List[str]] = None, embedding: Optional[List[float]] = None) -> bool:
        """更新文档"""
        pass
    
    @abstractmethod
    def delete_document(self, doc_id: int, soft_delete: bool = True) -> bool:
        """删除文档（支持软删除）"""
        pass
    
    @abstractmethod
    def search_documents_by_category(self, category: str) -> List[Dict[str, Any]]:
        """按分类搜索文档"""
        pass
    
    @abstractmethod
    def search_documents_by_keywords(self, keywords: List[str]) -> List[Dict[str, Any]]:
        """按关键词搜索文档"""
        pass
    
    @abstractmethod
    def get_all_categories(self) -> List[str]:
        """获取所有分类"""
        pass
    
    @abstractmethod
    def get_documents_count(self) -> int:
        """获取文档总数"""
        pass


class BaseUserBehaviorRepository(ABC):
    """
    健康追踪数据访问抽象接口
    
    定义问诊记录、偏好和建议相关的数据操作方法
    """
    
    @abstractmethod
    def record_behavior(self, user_id: str, action_type: str, action_data: Optional[Dict[str, Any]] = None, 
                       technician_id: Optional[int] = None, session_id: Optional[str] = None) -> int:
        """记录追踪数据"""
        pass

    @abstractmethod
    def get_user_behaviors(self, user_id: str, action_type: Optional[str] = None, 
                          days_back: Optional[int] = None) -> List[Dict[str, Any]]:
        """获取追踪历史"""
        pass

    @abstractmethod
    def update_user_preference(self, user_id: str, preference_type: str, preference_value: str) -> bool:
        """更新用户偏好"""
        pass

    @abstractmethod
    def get_user_preferences(self, user_id: str, preference_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取用户偏好"""
        pass

    @abstractmethod
    def create_recommendation(self, user_id: str, recommendation_type: str, content: str, 
                            technician_id: Optional[int] = None) -> int:
        """创建推荐"""
        pass

    @abstractmethod
    def get_pending_recommendations(self, user_id: str) -> List[Dict[str, Any]]:
        """获取待发送的推荐"""
        pass

    @abstractmethod
    def mark_recommendation_sent(self, recommendation_id: int) -> bool:
        """标记推荐为已发送"""
        pass

    @abstractmethod
    def get_user_statistics(self, user_id: str, days_back: int = 30) -> Dict[str, Any]:
        """获取用户统计信息"""
        pass
