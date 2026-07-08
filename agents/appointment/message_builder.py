"""
消息构建器

负责构建各种响应消息
"""

from typing import Dict, Any, List
from config.time_config import time_config


class MessageBuilder:
    """消息构建器"""

    def __init__(self):
        self.missing_info_prompts = {
            "gender": "您希望选择男医生还是女医生呢？",
            "start_time": "请问您想预约的时间是？",
            "project": "请问您想挂哪个科室？比如内科、外科、耳鼻喉科？",
            "preference": "您对医生有什么特殊偏好吗？"
        }
    
    def create_appointment_success_message(self, tech: Dict[str, Any]) -> str:
        """创建预约成功消息"""
        # 检查是否是推荐医生
        if tech.get('is_recommendation'):
            original_tech = tech.get('original_technician', {})
            return (f"\n机器人：已为您预约医生：{tech['name']}，性别：{tech['gender']}。预约成功！"
                    f"（原指定的{original_tech.get('name', '')}医生时间冲突，{tech['name']}在相同科室方面同样专业）"
                    "预约成功，请按时到校医务室就诊。\n")
        else:
            return (f"\n机器人：已为您预约医生：{tech['name']}，性别：{tech['gender']}。预约成功！"
                    "预约成功，请按时到校医务室就诊。\n")

    def create_doctor_recommendation_message(self, original_tech: Dict[str, Any],
                                               recommended_tech: Dict[str, Any],
                                               appointment_history: Dict[str, Any],
                                               llm=None) -> str:
        """创建医生推荐消息，使用LLM生成个性化措辞"""
        project = appointment_history.get('project', '就诊')
        start_time = appointment_history.get('start_time', '')

        if llm:
            try:
                # 构建LLM提示
                prompt = f"""
作为一个专业的预约助手，用户想预约{original_tech['name']}医生做{project}，但{original_tech['name']}医生在{start_time}这个时间段没有排班。

我找到了一位相似的医生：
- 姓名：{recommended_tech['name']}
- 性别：{recommended_tech['gender']}
- 科室：{recommended_tech.get('specialty', '')}

原医生科室：{original_tech.get('specialty', '')}

请帮我生成一段温馨、专业的推荐话术，告诉用户原医生没空，但推荐医生在相同科室同样专业，这个时间段有空，询问用户是否愿意预约推荐医生。

要求：
1. 语气温和、专业
2. 突出推荐医生的专业性
3. 明确询问用户意愿
4. 字数控制在80字以内
"""
                
                response = llm.invoke(prompt)
                if hasattr(response, 'content'):
                    generated_msg = response.content.strip()
                    if generated_msg:
                        return f"\n机器人：{generated_msg}\n"
                
            except Exception as e:
                print(f"LLM生成推荐消息失败: {e}")
        
        # 如果LLM失败，使用默认消息
        return (f"\n机器人：抱歉，{original_tech['name']}医生在{start_time}这个时间段没有排班。"
                f"不过{recommended_tech['name']}医生（{recommended_tech.get('gender', '')}）在{project}方面同样专业，"
                f"这个时间段有空，请问您愿意让我帮您预约{recommended_tech['name']}医生吗？\n")

    def create_time_recommendation_message(self, recommended_doc: Dict[str, Any],
                                            recommended_time, original_time,
                                            llm=None) -> str:
        """创建时间推荐消息——同医生或同科室其他医生的最近可预约时间"""
        from datetime import datetime
        time_str = time_config.format_datetime(recommended_time, "%m月%d日%H:%M") if isinstance(recommended_time, datetime) else str(recommended_time)
        doctor_name = recommended_doc.get('name', '')
        specialty = recommended_doc.get('specialty', '') or recommended_doc.get('strength', '')
        gender = recommended_doc.get('gender', '')
        gender_str = f"（{gender}）" if gender else ""

        if llm:
            try:
                prompt = f"""
作为校园医务室预约助手，用户想预约的时间段没有空闲，我找到了一个可预约的时段：
- 医生：{doctor_name}{gender_str}
- 科室：{specialty}
- 可预约时间：{time_str}

请生成一段温馨专业的话术，告诉用户原时段已满，推荐这个最近的可预约时间，询问是否接受。

要求：
1. 语气温和、专业
2. 明确说明推荐的时间和医生
3. 询问用户是否愿意预约该时段
4. 字数控制在80字以内
"""
                response = llm.invoke(prompt)
                if hasattr(response, 'content'):
                    generated_msg = response.content.strip()
                    if generated_msg:
                        return f"\n机器人：{generated_msg}\n"
            except Exception as e:
                print(f"LLM生成时间推荐消息失败: {e}")

        return (f"\n机器人：抱歉，您选择的时间段{specialty}科室医生都已约满。"
                f"为您找到最近可预约时间：{doctor_name}医生{gender_str}，{time_str}。"
                f"请问是否为您预约这个时段？\n")

    def create_recommendation_declined_message(self, llm=None) -> str:
        """创建用户拒绝推荐时的消息"""
        if llm:
            try:
                prompt = """
用户拒绝了我推荐的医生，请帮我生成一段专业、温馨的回复，表达理解并提供其他选择建议。

要求：
1. 表达理解用户的选择
2. 提供其他解决方案（如换时间、重新选择等）
3. 保持专业和友好的语气
4. 字数控制在60字以内
"""
                response = llm.invoke(prompt)
                if hasattr(response, 'content'):
                    generated_msg = response.content.strip()
                    if generated_msg:
                        return f"\n机器人：{generated_msg}\n"
            except Exception as e:
                print(f"LLM生成拒绝消息失败: {e}")
        
        # 默认消息
        return "\n机器人：好的，我理解您的选择。您可以选择其他时间段，或者我可以为您重新推荐其他医生。请问您还有其他需要吗？\n"
    
    def create_appointment_failure_message(self, technician_name: str) -> str:
        """创建预约失败消息"""
        if technician_name and technician_name != "未知":
            # 通过Services层访问数据库
            from services.appointment_service import AppointmentService
            appointment_service = AppointmentService()
            specific_tech = appointment_service.get_technician_by_name(technician_name)
            if specific_tech:
                return f"\n机器人：抱歉，{technician_name}医生在您选择的时间段没有排班。请选择其他营业时间（周一至周五 8:00-18:00，周六日 9:00-17:00），或者我可以为您推荐其他医生。\n"
            else:
                return f"\n机器人：抱歉，没有找到名为'{technician_name}'的医生。请确认医生姓名，或者我可以为您推荐其他医生。\n"
        else:
            return "\n机器人：抱歉，该时间段没有合适的医生排班。请选择其他营业时间（周一至周五 8:00-18:00，周六日 9:00-17:00）或调整科室/性别偏好，告诉我您新的选择。\n"
    
    def create_missing_info_questions(self, missing_info: List[str]) -> str:
        """根据缺失信息创建询问"""
        questions = [self.missing_info_prompts.get(field, f"请补充{field}信息") for field in missing_info]
        return "\n" + " ".join(questions) + "\n"
    
    def create_unrelated_message(self) -> str:
        """创建无关请求的消息"""
        return "[REPLY][预约机器人]抱歉，我无法处理这个问题。我只能帮您处理医务室预约相关的服务。请问您需要预约就诊吗？\n"
    
    def create_parse_error_message(self) -> str:
        """创建解析错误消息"""
        return "[REPLY][预约机器人]\n机器人：抱歉，我没有理解您的预约信息，请重新描述您想预约的科室和时间。\n"
    
    def create_save_failure_message(self) -> str:
        """创建保存失败消息"""
        return "\n机器人：抱歉，预约保存失败，请重试。\n"
