from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# ===========================
# 医学核心表
# ===========================

class Doctor(Base):
    """医生表 - 替代 Technician"""
    __tablename__ = 'doctors'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    gender = Column(String(10), nullable=True)                # 医生性别
    specialty = Column(String(100), nullable=False)            # 专科：内科、外科、皮肤科等
    license_number = Column(String(50), unique=True)          # 医生执业证号
    education = Column(String(50), nullable=True)             # 教育背景：博士、硕士等
    years_of_experience = Column(Integer, default=0)      # 从业年数
    consultation_rating = Column(Float, default=5.0)      # 问诊评分（1-5）
    max_daily_appointments = Column(Integer, default=20)  # 每天最多预约数
    schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")
    consultations = relationship("ConsultationRecord", back_populates="doctor")

class Appointment(Base):
    """预约主表 - 以用户为中心的预约记录"""
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, index=True)
    conversation_id = Column(String(100), nullable=True)
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=False)
    schedule_id = Column(Integer, ForeignKey('doctor_schedules.id'), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default='confirmed')  # 'confirmed' / 'cancelled'
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)
    doctor = relationship("Doctor")

class DoctorSchedule(Base):
    """医生值班表 - 替代 TechnicianSchedule"""
    __tablename__ = 'doctor_schedules'
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False)  # 'busy', 'free', 'on_leave'
    appointment_id = Column(Integer, nullable=True)
    shift_type = Column(String(20), nullable=True)  # 'morning', 'afternoon', 'evening'
    doctor = relationship("Doctor", back_populates="schedules")

class KnowledgeDocument(Base):
    """医学知识文库"""
    __tablename__ = 'knowledge_documents'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)                 # 文档标题
    content = Column(Text, nullable=False)                 # 医学内容
    category = Column(String(100), nullable=False)              # 分类：症状、预防、治疗、营养等
    keywords = Column(JSON, nullable=True)                 # 关键词列表
    embedding = Column(JSON, nullable=True)                # 嵌入向量
    medical_tags = Column(JSON, nullable=True)             # 医学标签：['心脏病', '高血压']
    source = Column(String(200), nullable=True)                 # 信息来源
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Integer, default=1)

class ConsultationRecord(Base):
    """问诊记录 - 替代 UserBehavior"""
    __tablename__ = 'consultation_records'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, default='default_user')
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=True)
    consultation_type = Column(String(20), nullable=False)  # 'initial', 'follow_up', 'emergency'
    symptoms = Column(JSON, nullable=True)               # 症状列表
    diagnosis = Column(Text, nullable=True)              # 诊断
    prescription = Column(JSON, nullable=True)           # 处方（药物列表）
    risk_level = Column(String(20), nullable=True)           # 'low', 'medium', 'high'
    resolved = Column(Integer, default=0)                # 是否已解决
    conversation_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    doctor = relationship("Doctor", back_populates="consultations")

class MedicalPreference(Base):
    """医学偏好 - 替代 UserPreference"""
    __tablename__ = 'medical_preferences'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, default='default_user')
    preference_type = Column(String(50), nullable=False)  # 'doctor', 'appointment_time', 'consultation_type'
    preference_value = Column(String(200), nullable=False)
    confidence_score = Column(Integer, default=1)        # 偏好置信度
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HealthRecommendation(Base):
    """健康建议 - 替代 UserRecommendation"""
    __tablename__ = 'health_recommendations'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, default='default_user')
    recommendation_type = Column(String(50), nullable=False)  # 'follow_up', 'health_tips', 'appointment_reminder', 'urgent_care'
    content = Column(Text, nullable=False)
    doctor_id = Column(Integer, ForeignKey('doctors.id'), nullable=True)
    priority = Column(String(20), default='normal')  # 'low', 'normal', 'urgent'
    is_sent = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    doctor = relationship("Doctor")

class RiskEvent(Base):
    """风险事件记录 - 用于风险评估"""
    __tablename__ = 'risk_events'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(100), nullable=False, default='default_user')
    risk_type = Column(String(100), nullable=False)        # 'red_flag_symptom', 'frequent_consultation', 'chronic_condition'
    description = Column(Text)
    risk_score = Column(Float, default=0.0)           # 风险分数 0-100
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ===========================
# 向后兼容别名
# ===========================

# 旧名称别名 - 允许现有代码继续导入 Technician
Technician = Doctor
TechnicianSchedule = DoctorSchedule

# 旧名称别名 - 允许现有代码继续导入 UserBehavior
UserBehavior = ConsultationRecord
UserPreference = MedicalPreference
UserRecommendation = HealthRecommendation
