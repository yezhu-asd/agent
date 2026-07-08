"""
用户输入解析器

负责解析用户输入并提取预约相关信息
"""
#作用：将历史对话与用户输入合并为prompts，提取有效信息为json，再转换为字典结构，提交给后续流程；
import json
from typing import Dict, Any, Generator
from langchain.prompts import PromptTemplate
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage


class InputParser:
    """用户输入解析器"""
    
    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self.prompt = self._create_prompt_template()
        self.chain = self.prompt | self.llm
    
    def _create_prompt_template(self) -> PromptTemplate:
        """创建预约信息提取的Prompt模板（时间相关字段为占位符，每次调用时动态注入）"""
        return PromptTemplate(
            input_variables=["current_date", "current_datetime", "history", "user_input"],
            template=(
                "你是一个预约机器人，负责帮用户预约校园医务室服务。\n"
                "当前日期是{current_date}，当前北京时间是{current_datetime}。\n"
                "当前已知信息：{history}\n"
                "用户输入：{user_input}\n"
                "特别注意：如果用户输入是对推荐医生确认问题的回应（如\"是\"、\"好\"、\"可以\"、\"不\"、\"不要\"等简短回复），请优先识别为confirmation，而不要标记为unrelated。\n"
                "重要：请你只输出纯JSON格式，不要添加任何markdown标记如```json或```，不要添加任何其他文字说明，直接输出JSON：\n"
                "{{\n"
                '  "gender": "医生性别（如男/女/未知）。特别注意：如果用户提到"女医生"或"男医生"，这里必须填对应的性别而不是填未知",\n'
                '  "start_time": "预约起始时间，必须转换为标准格式YYYY-MM-DD HH:MM。如果用户说今天下午3点，转换为当前日期 15:00；如果说明天上午10点，转换为明天日期 10:00。如果只说时间没说日期，默认为今天。如果完全没有时间信息则为未知",\n'
                '  "duration": "就诊时长，统一转换为分钟数格式，如30分钟、60分钟。如果没有明确时长则为未知",\n'
                '  "project": "就诊科室（如内科/外科/耳鼻喉科/未知）",\n'
                '  "preference": "用户倾向（如无）",\n'
                '  "technician_name": "指定医生姓名（如果用户明确提到医生名字，如张伟、李医生等，否则为未知）。注意："女医生""男医生"不是姓名，请填到gender字段",\n'
                '  "confirmation": "如果用户在回应医生推荐的确认问题，提取用户的回复内容（如是/好/可以/不/不要等），否则为未知",\n'
                '  "cancel_intent": "如果用户明确要取消预约（如取消预约、退号、不想去了、不去了等），则为true，否则为false",\n'
                '  "cancel_confirmation": "如果用户在回应取消预约确认问题，提取用户回复（如确认取消/是/好/不/算了等），否则为未知",\n'
                '  "info_complete": "根据实际情况判断：1)如果指定了医生名且不为未知，需要start_time、project都不为未知；2)如果没指定医生名，需要start_time、project、gender都不为未知",\n'
                '  "unrelated": "如果用户的问题和预约无关（如问天气、聊天等），则为true，否则为false。注意：对推荐医生的确认回复（是/不等）不应标记为unrelated",\n'
                '  "missing_info": "如果info_complete为false，请列出缺少的关键信息，如[start_time, project]等"\n'
                "}}\n"
                "判断逻辑：\n"
                "1. 如果用户明确指定了医生姓名（如\"张伟医生\"、\"预约李医生\"等），请务必提取technician_name\n"
                "2. \"女医生\"或\"男医生\"表示性别偏好，应填入gender字段，不要填入technician_name\n"
                "3. 如果用户在回应推荐医生的确认问题（如回复\"是\"、\"好\"、\"可以\"、\"不\"、\"不要\"等），请提取到confirmation字段，并且不要将其标记为unrelated\n"
                "4. 必需信息判断：\n"
                "   - 如果指定了医生名：需要start_time、project\n"
                "   - 如果没指定医生名：需要start_time、project、gender\n"
                "5. 只有当所有必需信息都不是'未知'时，info_complete才为true\n"
                "6. duration（时长）不是必需字段，系统默认30分钟\n"
                "7. 如果用户的问题和预约无关，请将unrelated设为true\n"
                "再次强调：只输出纯JSON，不要有任何代码块标记或其他文字。"
            )
        )
    
    def parse_stream(self, user_input: str, chat_history: InMemoryChatMessageHistory) -> Generator[str, None, str]:
        """流式解析用户输入"""
        # 添加用户消息到历史
        chat_history.add_message(HumanMessage(content=user_input))

        # 构建历史字符串
        history_str = "\n".join(
            [f"用户：{m.content}" if m.type == "human" else f"机器人：{m.content}"
             for m in chat_history.messages]
        )

        # 每次调用时动态获取当前时间，确保LLM看到的是实时时间
        from config.time_config import time_config
        current_date = time_config.current_date_str()
        current_datetime = time_config.current_datetime_str()

        # 流式调用LLM（注入实时时间）
        response_stream = self.chain.stream({
            "current_date": current_date,
            "current_datetime": current_datetime,
            "history": history_str,
            "user_input": user_input,
        })
        ai_content = ""
        
        for chunk in response_stream:
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            ai_content += token
            yield token
        
        # 添加AI回复到历史
        chat_history.add_message(AIMessage(content=ai_content))
        return ai_content
    
    def parse_data(self, ai_content: str) -> Dict[str, Any]:
        """解析AI返回的JSON数据，兼容 markdown 包裹"""
        try:
            content = ai_content.strip()
            # 去除可能的 ```json ... ``` 包裹
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]  # 去掉第一行 ```json
                content = content.rsplit("```", 1)[0]  # 去掉末尾 ```
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, Exception):
            return {
                "gender": "未知",
                "start_time": "未知",
                "duration": "未知",
                "project": "未知",
                "preference": "未知",
                "technician_name": "未知",
                "confirmation": "未知",
                "cancel_intent": False,
                "cancel_confirmation": "未知",
                "info_complete": False,
                "unrelated": False,
                "missing_info": ["所有信息"]
            }

    @staticmethod
    def detect_cancel_intent_fast(user_input: str) -> bool:
        """关键词快速检测取消意图，不依赖LLM，用于入口快速拦截"""
        import re
        cancel_keywords = ['取消预约', '退号', '取消挂号', '不想去了', '不去了', '退预约', '取消']
        # "取消"必须和"预约"上下文结合才触发，单独的"取消"可能是取消其他操作
        if any(kw in user_input for kw in ['取消预约', '退号', '取消挂号', '退预约']):
            return True
        if '不想去了' in user_input or '不去了' in user_input:
            return True
        # "取消"+"预约/号"组合
        if '取消' in user_input and ('预约' in user_input or '号' in user_input):
            return True
        return False

    @staticmethod
    def detect_reschedule_intent_fast(user_input: str) -> bool:
        """关键词快速检测改期/修改预约意图，不依赖LLM"""
        import re
        reschedule_keywords = [
            '改期', '改时间', '改个时间', '换个时间', '换时间',
            '重新预约', '重新约', '修改预约', '调整预约', '换个医生',
            '改预约', '换预约', '变更预约'
        ]
        for kw in reschedule_keywords:
            if kw in user_input:
                return True
        # "改/换/调整/变更" + "预约/时间/医生"组合
        if re.search(r'(改|换|调整|变更).*(预约|时间|医生)', user_input):
            return True
        if re.search(r'(预约|时间|医生).*(改|换|调整|变更)', user_input):
            return True
        return False
