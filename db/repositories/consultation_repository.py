"""
问诊记录和医学行为数据访问对象 - 替代 user_behavior_repository.py

职责：
1. 问诊记录的存储和查询
2. 医学偏好管理
3. 健康建议生成
4. 风险事件跟踪
5. 用户医学统计信息生成
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func
from ..base.session_manager import SessionManager
from ..models import ConsultationRecord, MedicalPreference, HealthRecommendation, RiskEvent, Doctor


class ConsultationRepository:
    """
    问诊和医学行为数据访问对象
    
    职责：
    1. 问诊记录管理
    2. 医学偏好跟踪
    3. 健康建议管理
    4. 风险事件记录
    5. 医学统计分析
    """
    
    def __init__(self, session_manager: SessionManager):
        """
        初始化问诊记录数据仓库
        
        Args:
            session_manager: 会话管理器
        """
        self.session_manager = session_manager

    # ===========================
    # 问诊记录操作
    # ===========================
    
    def record_consultation(self, user_id: str, doctor_id: Optional[int] = None, 
                           consultation_type: str = "initial", symptoms: Optional[List[str]] = None,
                           diagnosis: Optional[str] = None, risk_level: Optional[str] = None,
                           conversation_id: Optional[str] = None, session_id: Optional[str] = None) -> int:
        """
        记录问诊记录
        
        Args:
            user_id: 用户ID
            doctor_id: 医生ID
            consultation_type: 问诊类型（initial/follow_up/emergency）
            symptoms: 症状列表
            diagnosis: 诊断信息
            risk_level: 风险等级（low/medium/high）
            conversation_id: 对话ID
            session_id: 会话ID
            
        Returns:
            新创建的问诊记录ID
        """
        with self.session_manager.session_scope() as session:
            consultation = ConsultationRecord(
                user_id=user_id,
                doctor_id=doctor_id,
                consultation_type=consultation_type,
                symptoms=symptoms,
                diagnosis=diagnosis,
                risk_level=risk_level,
                conversation_id=conversation_id,
                session_id=session_id
            )
            session.add(consultation)
            session.flush()
            return consultation.id

    def get_user_consultation_history(self, user_id: str, days_back: Optional[int] = None,
                                     limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取用户问诊历史
        
        Args:
            user_id: 用户ID
            days_back: 查询多少天内的记录
            limit: 返回记录限制数
            
        Returns:
            问诊记录列表
        """
        with self.session_manager.session_scope() as session:
            query = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id
            )
            
            if days_back:
                cutoff_date = datetime.utcnow() - timedelta(days=days_back)
                query = query.filter(ConsultationRecord.created_at >= cutoff_date)
            
            consultations = query.order_by(
                ConsultationRecord.created_at.desc()
            ).limit(limit).all()
            
            return [self._consultation_to_dict(c) for c in consultations]

    def get_recurring_symptoms(self, user_id: str, min_occurrences: int = 2) -> List[Dict[str, Any]]:
        """
        获取用户反复出现的症状
        
        Args:
            user_id: 用户ID
            min_occurrences: 最少出现次数
            
        Returns:
            反复症状列表
        """
        with self.session_manager.session_scope() as session:
            consultations = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.symptoms != None
            ).all()
            
            symptom_counts = {}
            for c in consultations:
                if c.symptoms:
                    for symptom in c.symptoms:
                        symptom_counts[symptom] = symptom_counts.get(symptom, 0) + 1
            
            recurring = [
                {'symptom': s, 'count': c}
                for s, c in symptom_counts.items()
                if c >= min_occurrences
            ]
            
            return sorted(recurring, key=lambda x: x['count'], reverse=True)

    def mark_consultation_resolved(self, consultation_id: int) -> bool:
        """
        标记问诊为已解决
        
        Args:
            consultation_id: 问诊ID
            
        Returns:
            标记是否成功
        """
        with self.session_manager.session_scope() as session:
            consultation = session.query(ConsultationRecord).filter(
                ConsultationRecord.id == consultation_id
            ).first()
            
            if consultation:
                consultation.resolved = 1
                consultation.resolved_at = datetime.utcnow()
                return True
            return False

    # ===========================
    # 医学偏好操作
    # ===========================
    
    def update_medical_preference(self, user_id: str, preference_type: str, preference_value: str) -> bool:
        """
        更新医学偏好（如偏好的医生、就诊时间等）
        
        Args:
            user_id: 用户ID
            preference_type: 偏好类型（doctor/time/consultation_type等）
            preference_value: 偏好值
            
        Returns:
            更新是否成功
        """
        with self.session_manager.session_scope() as session:
            existing = session.query(MedicalPreference).filter(
                MedicalPreference.user_id == user_id,
                MedicalPreference.preference_type == preference_type,
                MedicalPreference.preference_value == preference_value
            ).first()
            
            if existing:
                existing.confidence_score += 1
                existing.last_updated = datetime.utcnow()
            else:
                preference = MedicalPreference(
                    user_id=user_id,
                    preference_type=preference_type,
                    preference_value=preference_value,
                    confidence_score=1
                )
                session.add(preference)
            
            return True

    def get_medical_preferences(self, user_id: str, preference_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取用户医学偏好
        
        Args:
            user_id: 用户ID
            preference_type: 偏好类型过滤
            
        Returns:
            医学偏好列表
        """
        with self.session_manager.session_scope() as session:
            query = session.query(MedicalPreference).filter(
                MedicalPreference.user_id == user_id
            )
            
            if preference_type:
                query = query.filter(MedicalPreference.preference_type == preference_type)
            
            preferences = query.order_by(
                MedicalPreference.confidence_score.desc()
            ).all()
            
            return [self._preference_to_dict(p) for p in preferences]

    # ===========================
    # 健康建议操作
    # ===========================
    
    def create_health_recommendation(self, user_id: str, recommendation_type: str, content: str,
                                    doctor_id: Optional[int] = None, priority: str = "normal") -> int:
        """
        创建健康建议
        
        Args:
            user_id: 用户ID
            recommendation_type: 建议类型（follow_up/health_tips/appointment_reminder/urgent_care）
            content: 建议内容
            doctor_id: 推荐医生ID
            priority: 优先级（low/normal/urgent）
            
        Returns:
            新创建的建议ID
        """
        with self.session_manager.session_scope() as session:
            recommendation = HealthRecommendation(
                user_id=user_id,
                recommendation_type=recommendation_type,
                content=content,
                doctor_id=doctor_id,
                priority=priority
            )
            session.add(recommendation)
            session.flush()
            return recommendation.id

    def get_pending_recommendations(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取待发送的健康建议
        
        Args:
            user_id: 用户ID
            
        Returns:
            待发送建议列表
        """
        with self.session_manager.session_scope() as session:
            recommendations = session.query(HealthRecommendation).filter(
                HealthRecommendation.user_id == user_id,
                HealthRecommendation.is_sent == 0
            ).order_by(
                HealthRecommendation.priority.desc(),
                HealthRecommendation.created_at.desc()
            ).all()
            
            return [self._recommendation_to_dict(r) for r in recommendations]

    def mark_recommendation_sent(self, recommendation_id: int) -> bool:
        """
        标记健康建议为已发送
        
        Args:
            recommendation_id: 建议ID
            
        Returns:
            标记是否成功
        """
        with self.session_manager.session_scope() as session:
            recommendation = session.query(HealthRecommendation).filter(
                HealthRecommendation.id == recommendation_id
            ).first()
            
            if recommendation:
                recommendation.is_sent = 1
                recommendation.sent_at = datetime.utcnow()
                return True
            return False

    # ===========================
    # 风险事件操作
    # ===========================
    
    def record_risk_event(self, user_id: str, risk_type: str, description: str, risk_score: float = 0.0) -> int:
        """
        记录风险事件
        
        Args:
            user_id: 用户ID
            risk_type: 风险类型（red_flag_symptom/frequent_consultation/chronic_condition）
            description: 风险描述
            risk_score: 风险分数（0-100）
            
        Returns:
            新创建的风险事件ID
        """
        with self.session_manager.session_scope() as session:
            event = RiskEvent(
                user_id=user_id,
                risk_type=risk_type,
                description=description,
                risk_score=max(0.0, min(100.0, risk_score))  # 限制在 0-100 范围内
            )
            session.add(event)
            session.flush()
            return event.id

    def get_active_risk_events(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户未解决的风险事件
        
        Args:
            user_id: 用户ID
            
        Returns:
            活跃风险事件列表
        """
        with self.session_manager.session_scope() as session:
            events = session.query(RiskEvent).filter(
                RiskEvent.user_id == user_id,
                RiskEvent.resolved_at == None
            ).order_by(
                RiskEvent.risk_score.desc(),
                RiskEvent.detected_at.desc()
            ).all()
            
            return [self._risk_event_to_dict(e) for e in events]

    def resolve_risk_event(self, risk_event_id: int) -> bool:
        """
        解决风险事件
        
        Args:
            risk_event_id: 风险事件ID
            
        Returns:
            解决是否成功
        """
        with self.session_manager.session_scope() as session:
            event = session.query(RiskEvent).filter(
                RiskEvent.id == risk_event_id
            ).first()
            
            if event:
                event.resolved_at = datetime.utcnow()
                return True
            return False

    # ===========================
    # 统计分析
    # ===========================
    
    def get_user_health_profile(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户健康档案
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户健康档案
        """
        with self.session_manager.session_scope() as session:
            # 总问诊次数
            total_consultations = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id
            ).count()
            
            # 最近一次问诊
            last_consultation = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id
            ).order_by(ConsultationRecord.created_at.desc()).first()
            
            # 风险等级分布
            high_risk_count = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.risk_level == 'high'
            ).count()
            
            # 活跃风险事件数
            active_risks = session.query(RiskEvent).filter(
                RiskEvent.user_id == user_id,
                RiskEvent.resolved_at == None
            ).count()
            
            # 最常见症状
            recurring_symptoms = self.get_recurring_symptoms(user_id, min_occurrences=1)
            
            return {
                'user_id': user_id,
                'total_consultations': total_consultations,
                'last_consultation_date': last_consultation.created_at if last_consultation else None,
                'high_risk_consultation_count': high_risk_count,
                'active_risk_events': active_risks,
                'recurring_symptoms': recurring_symptoms[:5],  # 前 5 个
                'created_at': datetime.utcnow()
            }

    def get_consultation_statistics(self, user_id: str, days_back: int = 30) -> Dict[str, Any]:
        """
        获取问诊统计信息
        
        Args:
            user_id: 用户ID
            days_back: 统计天数
            
        Returns:
            问诊统计信息
        """
        with self.session_manager.session_scope() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # 问诊总数
            total = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.created_at >= cutoff_date
            ).count()
            
            # 初诊
            initial = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.consultation_type == 'initial',
                ConsultationRecord.created_at >= cutoff_date
            ).count()
            
            # 复诊
            follow_up = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.consultation_type == 'follow_up',
                ConsultationRecord.created_at >= cutoff_date
            ).count()
            
            # 紧急
            emergency = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.consultation_type == 'emergency',
                ConsultationRecord.created_at >= cutoff_date
            ).count()
            
            # 已解决
            resolved = session.query(ConsultationRecord).filter(
                ConsultationRecord.user_id == user_id,
                ConsultationRecord.resolved == 1,
                ConsultationRecord.created_at >= cutoff_date
            ).count()
            
            return {
                'period_days': days_back,
                'total_consultations': total,
                'initial_consultations': initial,
                'follow_up_consultations': follow_up,
                'emergency_consultations': emergency,
                'resolved_consultations': resolved,
                'unresolved_consultations': total - resolved
            }

    # ===========================
    # 辅助方法
    # ===========================
    
    def _consultation_to_dict(self, consultation: ConsultationRecord) -> Dict[str, Any]:
        """将问诊对象转换为字典"""
        return {
            'id': consultation.id,
            'user_id': consultation.user_id,
            'doctor_id': consultation.doctor_id,
            'doctor_name': consultation.doctor.name if consultation.doctor else None,
            'consultation_type': consultation.consultation_type,
            'symptoms': consultation.symptoms,
            'diagnosis': consultation.diagnosis, 
            'prescription': consultation.prescription,
            'risk_level': consultation.risk_level,
            'resolved': bool(consultation.resolved),
            'conversation_id': consultation.conversation_id,
            'session_id': consultation.session_id,
            'created_at': consultation.created_at,
            'resolved_at': consultation.resolved_at
        }

    def _preference_to_dict(self, preference: MedicalPreference) -> Dict[str, Any]:
        """将医学偏好转换为字典"""
        return {
            'id': preference.id,
            'user_id': preference.user_id,
            'preference_type': preference.preference_type,
            'preference_value': preference.preference_value,
            'confidence_score': preference.confidence_score,
            'last_updated': preference.last_updated
        }

    def _recommendation_to_dict(self, recommendation: HealthRecommendation) -> Dict[str, Any]:
        """将健康建议转换为字典"""
        return {
            'id': recommendation.id,
            'user_id': recommendation.user_id,
            'recommendation_type': recommendation.recommendation_type,
            'content': recommendation.content,
            'doctor_id': recommendation.doctor_id,
            'doctor_name': recommendation.doctor.name if recommendation.doctor else None,
            'priority': recommendation.priority,
            'is_sent': bool(recommendation.is_sent),
            'created_at': recommendation.created_at,
            'sent_at': recommendation.sent_at
        }

    def _risk_event_to_dict(self, event: RiskEvent) -> Dict[str, Any]:
        """将风险事件转换为字典"""
        return {
            'id': event.id,
            'user_id': event.user_id,
            'risk_type': event.risk_type,
            'description': event.description,
            'risk_score': event.risk_score,
            'detected_at': event.detected_at,
            'resolved_at': event.resolved_at
        }
