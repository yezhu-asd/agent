"""
咨询流程处理器 - 重构版

核心逻辑：
1. 新对话包含症状词时，先询问用户是否自己有症状
2. 用户确认 → 医学问诊流程（收集结构化信息，建议预约）
3. 用户否认 → 健康知识RAG问答
"""

import re
import logging
from typing import AsyncGenerator, Dict, Any
from .knowledge_retriever import KnowledgeRetriever
from .consultation_classifier import ConsultationClassifier
from .response_generator import ResponseGenerator

logger = logging.getLogger(__name__)


class ConsultationProcessor:
    """咨询流程处理器"""

    # 症状关键词 - 识别是否需要确认
    SYMPTOM_WORDS = {
        '肚子疼', '肚子痛', '腹痛', '腹泻', '拉肚子',
        '头疼', '头痛', '头晕', '头疼得',
        '发烧', '发热', '高烧', '低烧',
        '咳嗽', '咳痰', '嗓子疼', '喉咙痛',
        '流鼻涕', '鼻塞', '打喷嚏',
        '恶心', '呕吐', '想吐',
        '胸口疼', '胸痛', '胸闷', '心慌',
        '腰疼', '背痛', '肩膀疼',
        '关节疼', '肌肉疼', '腿疼',
        '皮疹', '过敏', '痒', '起疙瘩',
        '失眠', '睡不着', '睡不好',
        '牙疼', '牙龈肿',
        '眼睛疼', '眼睛红',
        '感冒', '流感', '中暑',
        '不舒服', '难受', '疼', '痛',
    }

    # 否认词 - 用户表示没有症状（优先级高于确认词，长词优先匹配）
    DENY_WORDS = {
        '不是我', '不是的', '没有啊', '没有呢', '没怎么', '我没有',
        '只是问问', '随便问问', '问问而已', '就是问问', '没什么大',
        '不用了', '不需要', '不是那个意思', '不是那意思',
        '没有', '不是', '没', '不'
    }

    # 确认词 - 用户表示有症状（长词优先匹配）
    CONFIRM_WORDS = {
        '是的是的', '是的', '是啊', '是我', '有啊', '有的',
        '对的', '对啊', '没错', '确实', '自己有',
        '我有', '我是', '就是', '对，我',
        '需要', '要的', '需要的', '可以的', '好的',
        '嗯', '嗯嗯', '是', '有', '对', '要'
    }

    # 复杂症状追问表：复杂症状 → 追问维度清单（最多3轮）
    # 每个维度: (字段名, 追问问题)
    COMPLEX_SYMPTOM_PROBES = {
        '肚子疼': [
            ('location', '请问疼痛主要在哪个位置？是上腹、下腹还是肚脐周围？'),
            ('nature', '是绞痛、刺痛、胀痛还是隐痛？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随发烧、恶心、腹泻等情况？'),
        ],
        '肚子痛': [
            ('location', '请问疼痛主要在哪个位置？是上腹、下腹还是肚脐周围？'),
            ('nature', '是绞痛、刺痛、胀痛还是隐痛？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随发烧、恶心、腹泻等情况？'),
        ],
        '腹痛': [
            ('location', '请问疼痛主要在哪个位置？是上腹、下腹还是肚脐周围？'),
            ('nature', '是绞痛、刺痛、胀痛还是隐痛？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随发烧、恶心、腹泻等情况？'),
        ],
        '头疼': [
            ('location', '请问头痛主要在哪个部位？是前额、后脑勺还是太阳穴两侧？'),
            ('nature', '是胀痛、刺痛、搏动性疼痛还是紧绷感？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随恶心、畏光、视力模糊等情况？'),
        ],
        '头痛': [
            ('location', '请问头痛主要在哪个部位？是前额、后脑勺还是太阳穴两侧？'),
            ('nature', '是胀痛、刺痛、搏动性疼痛还是紧绷感？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随恶心、畏光、视力模糊等情况？'),
        ],
        '胸痛': [
            ('location', '请问胸痛主要在哪个位置？是左胸、右胸还是胸骨后？'),
            ('nature', '是压榨样疼痛、刺痛还是闷痛？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随呼吸困难、出汗、心慌等情况？'),
        ],
        '胸口疼': [
            ('location', '请问胸痛主要在哪个位置？是左胸、右胸还是胸骨后？'),
            ('nature', '是压榨样疼痛、刺痛还是闷痛？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随呼吸困难、出汗、心慌等情况？'),
        ],
        '胸闷': [
            ('location', '请问胸闷主要在哪个部位？'),
            ('nature', '是闷胀感、压迫感还是呼吸不畅？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随心慌、气短、头晕等情况？'),
        ],
        '咳嗽': [
            ('nature', '是干咳还是有痰的咳嗽？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随发烧、咽痛、流鼻涕等情况？'),
        ],
        '胃疼': [
            ('location', '请问胃疼主要在哪个位置？是上腹部吗？'),
            ('nature', '是隐痛、绞痛还是烧灼样痛？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随反酸、恶心、食欲不振等情况？'),
        ],
        '恶心': [
            ('nature', '是持续想吐还是偶尔恶心？'),
            ('duration', '这个情况持续多久了？'),
            ('concomitant', '有没有伴随呕吐、腹痛、头晕等情况？'),
        ],
    }

    # 复杂症状关键词（用于检测哪些输入触发追问）
    COMPLEX_SYMPTOM_KEYS = list(COMPLEX_SYMPTOM_PROBES.keys())

    def __init__(self, knowledge_retriever: KnowledgeRetriever,
                 consultation_classifier: ConsultationClassifier,
                 response_generator: ResponseGenerator,
                 memory_service=None,
                 conversation_id=None,
                 appointment_agent=None,
                 shared_state=None,
                 state_manager=None):
        self.knowledge_retriever = knowledge_retriever
        self.consultation_classifier = consultation_classifier
        self.response_generator = response_generator
        self.memory = memory_service
        self.conversation_id = conversation_id
        self.appointment_agent = appointment_agent
        self.shared_state = shared_state
        self.state_manager = state_manager

    def _get_slots(self) -> Dict[str, Any]:
        if self.memory and self.conversation_id:
            return self.memory.get_medical_slots(self.conversation_id)
        return {}

    def _set_slots(self, slots: Dict[str, Any]):
        if self.memory and self.conversation_id:
            self.memory.set_medical_slots(self.conversation_id, slots)

    def _reset_doctor_substate(self):
        slots = self._get_slots()
        slots["doctor_sub_state"] = "initial_assessment"
        slots["pending_symptom_query"] = ""
        slots["confirmed_symptom"] = False
        self._set_slots(slots)

    def _needs_symptom_confirmation(self, user_input: str) -> bool:
        """判断是否需要先确认用户是否有症状

        规则：
        - 第一人称表述（我+症状）→ 不需要确认，直接问诊
        - 明确知识类问题（如何预防、什么是）→ 不需要确认，直接RAG
        - 包含症状词的其他情况 → 需要确认
        """
        # 明确的健康知识问题（不含第一人称）→ 不需要确认，直接RAG
        knowledge_patterns = ['如何预防', '怎么预防', '什么是', '如何治疗', '怎么治疗',
                              '注意事项', '能吃吗', '有什么用', '是什么原因',
                              '怎么回事', '为什么会']
        is_knowledge_question = any(p in user_input for p in knowledge_patterns)
        if is_knowledge_question:
            return False

        # 第一人称 + 症状 → 不需要确认，直接问诊
        first_person_patterns = ['我', '本人']
        has_first_person = any(p in user_input for p in first_person_patterns)
        has_symptom = any(word in user_input for word in self.SYMPTOM_WORDS)
        if has_first_person and has_symptom:
            return False

        # 包含症状词 → 需要确认
        return has_symptom

    @staticmethod
    def _is_query_text(text: str) -> bool:
        """判断文本是否属于提问（用户问句），而非医学知识回答。

        知识库 content/ask 字段常存用户提问原文，若作为知识传入 prompt，
        会导致 LLM 把提问内容误当成用户描述的症状。
        """
        if not text or len(text) < 5:
            return True
        # 提问特征：含疑问词、第一人称求助、请求治疗建议等
        query_markers = [
            '怎么办', '怎么治', '什么药', '怎么处理', '能治好吗', '吃什么药',
            '是怎么回事', '是什么原因', '如何', '为啥', '为什么',
            '请问', '医生', '你好', '大夫', '专家',
            '我该怎么办', '帮我', '请教', '求助', '求解',
            '？', '?', '无', '没有', '不知道'
        ]
        for marker in query_markers:
            if marker in text:
                return True
        # 第一人称求助句式（"我...了" "我...病"）
        if re.search(r'我.{0,20}(病|疼|痛|了|查出|诊断)', text):
            return True
        return False

    def _is_confirmation_reply(self, user_input: str) -> str:
        """判断用户回复是确认还是否认
        返回: 'confirm' | 'deny' | 'unclear'

        匹配策略：长词优先，否认词优先级高于确认词
        """
        text = user_input.strip().lower()

        # 先匹配否认（长词优先）
        deny_sorted = sorted(self.DENY_WORDS, key=len, reverse=True)
        for word in deny_sorted:
            if word in text:
                return 'deny'

        # 再匹配确认（长词优先）
        confirm_sorted = sorted(self.CONFIRM_WORDS, key=len, reverse=True)
        for word in confirm_sorted:
            if word in text:
                return 'confirm'

        return 'unclear'

    async def process_consultation_stream(self, user_input: str, session_id: str) -> AsyncGenerator[str, None]:
        """处理流式咨询主入口"""
        try:
            if not self.conversation_id or not self.memory:
                async for token in self._do_rag_answer(user_input, session_id):
                    yield token
                return

            slots = self._get_slots()
            current_substate = slots.get("doctor_sub_state", "initial_assessment")

            # 复杂症状判断（优先于确认流程）
            knowledge_patterns = ['如何预防', '怎么预防', '什么是', '如何治疗', '怎么治疗',
                                  '注意事项', '能吃吗', '有什么用', '是什么原因',
                                  '怎么回事', '为什么会']
            is_knowledge_question = any(p in user_input for p in knowledge_patterns)
            complex_symptom = self._detect_complex_symptom(user_input) if not is_knowledge_question else ""

            # 处于追问收集状态 → 继续追问流程（最高优先级）
            if current_substate == "collecting_symptoms":
                async for token in self._probe_symptom_flow(user_input, session_id):
                    yield token
                return

            # 新输入含复杂症状 → 触发追问诊断
            if complex_symptom:
                async for token in self._probe_symptom_flow(user_input, session_id):
                    yield token
                return

            # 如果处于等待确认状态 → 处理用户回复
            if current_substate == "awaiting_confirmation":
                reply_type = self._is_confirmation_reply(user_input)
                # 用户输入的不是确认/否认词（比如是新症状），说明是残留状态，覆盖重置
                if reply_type == 'unclear' and self._needs_symptom_confirmation(user_input):
                    logger.info(f"[症状确认] 残留确认状态被新症状输入覆盖，重置: {user_input}")
                    self._reset_doctor_substate()
                    slots = self._get_slots()  # 重新获取已重置的槽位
                else:
                    async for token in self._handle_confirmation_reply(user_input, session_id):
                        yield token
                    return

            # 新输入 - 判断是否需要确认
            if self._needs_symptom_confirmation(user_input):
                async for token in self._start_confirmation_flow(user_input):
                    yield token
                return

            if is_knowledge_question:
                async for token in self._do_rag_answer(user_input, session_id, is_knowledge_only=True):
                    yield token
                return

            # 默认：第一人称症状描述 → 医学问诊流程
            async for token in self._do_doctor_consultation(user_input, user_input, session_id):
                yield token

        except Exception as e:
            logger.error(f"咨询处理异常: {e}", exc_info=True)
            error_msg = f"抱歉，处理您的问题时出现了错误：{str(e)}"
            for char in error_msg:
                yield char

    async def process_consultation(self, user_input: str) -> str:
        """同步版本 - 非流式"""
        result = ""
        async for token in self.process_consultation_stream(user_input, session_id="sync"):
            result += token
        return result

    async def _start_confirmation_flow(self, user_input: str) -> AsyncGenerator[str, None]:
        """开始确认流程：先输出RAG健康知识，再询问是否自己有症状"""
        slots = self._get_slots()
        slots["doctor_sub_state"] = "awaiting_confirmation"
        slots["pending_symptom_query"] = user_input
        self._set_slots(slots)

        mentioned_symptom = self._extract_mentioned_symptom(user_input)
        logger.info(f"[症状确认] 进入确认流程，提及症状: {mentioned_symptom}")

        # 先检索RAG健康知识
        knowledge_docs = await self.knowledge_retriever.search_knowledge(user_input, top_k=3)
        has_relevant_knowledge = False
        if knowledge_docs:
            try:
                prompt = (
                    "你是校园医务室的健康知识助手，用户询问了以下症状相关的知识。\n"
                    "请严格基于下面提供的【相关医学知识】来回答，把知识中的具体病因、"
                    "常见表现、日常调理建议等要点融入回答，不要泛泛而谈。\n"
                    "回答要求：先简要复述用户症状，再结合知识给出 2-4 句具体科普内容。\n\n"
                )
                prompt += "【相关医学知识】\n"
                for i, doc in enumerate(knowledge_docs, 1):
                    # 只用 answer（医生回答），避免把 ask（用户提问）当成知识传入
                    content = doc.get('answer', '')
                    if not content:
                        content = doc.get('content', '')
                    # 过滤掉疑似提问的文本（包含"怎么办/什么药/怎么治/我是/我..."等提问特征）
                    if content and not self._is_query_text(content):
                        prompt += f"{i}. {content}\n"
                prompt += (
                    f"\n【用户问题】{user_input}\n\n"
                    "请结合上面的医学知识给出具体、有信息量的回答。"
                )
                response = await self.response_generator.llm.ainvoke([{"role": "user", "content": prompt}])
                content = response.content.strip()
                if content:
                    has_relevant_knowledge = True
                    yield content + "\n\n"
            except Exception:
                pass

        if not has_relevant_knowledge:
            yield f"关于「{mentioned_symptom or user_input}」，这是校园常见症状之一。注意休息，如症状持续建议就医检查。\n\n"

        # 询问是否需要预约校医务室
        question = (
            f"如果您的「{mentioned_symptom or '相关'}」症状持续或加重，建议及时到校医务室就诊检查。\n"
            f"需不需要我帮您预约校医务室呢？\n"
            f"[BUTTONS]需要,不需要\n"
        )
        for char in question:
            yield char

    def _extract_mentioned_symptom(self, user_input: str) -> str:
        """从用户输入中提取提到的症状词"""
        for word in sorted(self.SYMPTOM_WORDS, key=len, reverse=True):
            if word in user_input:
                return word
        return ""

    # 症状 → 推荐科室映射（用于预约时主动推荐科室）
    SYMPTOM_DEPARTMENT_MAP = [
        (('牙疼', '牙龈肿', '牙齿', '牙痛', '智齿', '口腔'), '口腔科'),
        (('眼睛疼', '眼睛红', '视力', '眼', '近视', '结膜炎'), '眼科'),
        (('耳朵', '耳鸣', '听力', '耳痛', '中耳炎', '鼻塞', '鼻炎', '喉咙痛', '嗓子疼', '咽喉', '扁桃体', '咳嗽'), '耳鼻喉科'),
        (('皮疹', '过敏', '痒', '起疙瘩', '荨麻疹', '湿疹', '皮炎', '痘痘'), '皮肤科'),
        (('妇科', '月经', '白带', '痛经', '阴道'), '妇科'),
        (('宝宝', '孩子', '儿童', '小儿', '婴儿'), '儿科'),
        (('失眠', '睡不着', '焦虑', '抑郁', '心理', '情绪', '压力'), '心理科'),
        (('腰疼', '腰痛', '腰', '背痛', '颈椎', '腰椎', '关节', '肌肉', '骨头', '扭伤'), '骨科'),
        (('肚子疼', '腹痛', '胃', '腹泻', '拉肚子', '恶心', '呕吐', '腹胀', '消化不良', '便秘'), '内科'),
        (('头疼', '头痛', '头晕', '偏头痛', '神经', '中风', '脑'), '神经内科'),
        (('胸痛', '胸口疼', '胸闷', '心慌', '心悸', '心脏', '呼吸'), '内科'),
        (('发烧', '发热', '感冒', '流感', '高烧', '低烧'), '内科'),
        (('外伤', '创伤', '骨折', '伤口', '出血', '缝合'), '外科'),
    ]

    @classmethod
    def _recommend_department(cls, query: str) -> str:
        """根据症状文本推荐预约科室"""
        for keywords, dept in cls.SYMPTOM_DEPARTMENT_MAP:
            for kw in keywords:
                if kw in query:
                    return dept
        return ""

    async def _handle_confirmation_reply(self, user_input: str, session_id: str) -> AsyncGenerator[str, None]:
        """处理用户对症状确认的回复"""
        reply_type = self._is_confirmation_reply(user_input)
        slots = self._get_slots()
        original_query = slots.get("pending_symptom_query", user_input)

        if reply_type == 'confirm':
            # 用户确认有症状 → 流转到预约流程
            logger.info(f"[症状确认] 用户确认有症状，流转到预约: {original_query}")
            self._reset_doctor_substate()

            # 把全局状态切换到 APPOINTMENT，让后续输入由预约流程接管
            if self.state_manager is not None:
                try:
                    self.state_manager.transition_to_appointment()
                    logger.info("[症状确认] 全局状态切换为 APPOINTMENT")
                except Exception as e:
                    logger.warning(f"[症状确认] 切换全局状态失败: {e}")
            elif self.shared_state is not None:
                try:
                    from config.constants import StateEnum
                    self.shared_state.value = StateEnum.APPOINTMENT
                except Exception as e:
                    logger.warning(f"[症状确认] 切换 shared_state 失败: {e}")

            # 如果注入了预约 Agent，直接流转到预约流程
            if self.appointment_agent is not None:
                # 把用户症状作为预约背景传给预约 Agent，并根据症状推荐科室
                if self.conversation_id and self.memory:
                    slots = self.memory.get_appointment_slots(self.conversation_id)
                    slots['appointment_reason'] = original_query
                    slots['symptoms'] = original_query
                    recommended = self._recommend_department(original_query)
                    if recommended:
                        slots['project'] = recommended
                        slots['recommended_department'] = recommended
                        # 同步到预约 Agent 的 appointment_history，让流程直接使用推荐科室
                        if hasattr(self.appointment_agent, 'appointment_history'):
                            self.appointment_agent.appointment_history['project'] = recommended
                            # 同步到 Redis，确保跨请求恢复时科室保留
                            if hasattr(self.appointment_agent, '_sync_to_memory_slots'):
                                try:
                                    self.appointment_agent._sync_to_memory_slots()
                                except Exception as e:
                                    logger.warning(f"[症状确认] 同步预约科室到 Redis 失败: {e}")
                    self.memory.set_appointment_slots(self.conversation_id, slots)

                # 通知用户即将开始预约
                if self.conversation_id and self.memory:
                    slots = self.memory.get_appointment_slots(self.conversation_id)
                    recommended = slots.get('recommended_department')
                    if recommended:
                        transition = f"好的，我帮您预约校医务室。根据您描述的「{original_query}」，建议挂{recommended}科室。\n请告诉我您希望预约的时间和医生偏好（如男/女医生）。\n\n"
                    else:
                        transition = "好的，我帮您预约校医务室。请告诉我您希望预约的时间、科室和医生偏好。\n\n"
                else:
                    transition = "好的，我帮您预约校医务室。请告诉我您希望预约的时间、科室和医生偏好。\n\n"
                for char in transition:
                    yield char

                # 将控制权交给预约 Agent。
                # 注意：不能把症状词（如"肚子疼"）作为输入传给预约解析器，
                # 否则 LLM 会臆造科室/医生。用预约引导语初始化预约流程。
                async for token in self.appointment_agent.run_stream(user_input="我想预约校医务室就诊"):
                    yield token
                return

            # 未注入预约 Agent 时的兜底
            reply = (
                "了解，如果您有这方面的不适，建议及时到校医务室就诊检查。\n\n"
                "需要我帮您预约校医务室吗？回复「预约」即可。"
            )
            for char in reply:
                yield char

        elif reply_type == 'deny':
            # 用户否认 → 礼貌确认，并询问是否还有其他需要帮助
            self._reset_doctor_substate()
            logger.info(f"[症状确认] 用户否认有症状，询问其他需求: {original_query}")

            reply = (
                "好的，明白了。如果之后有任何健康问题需要咨询，随时都可以问我。\n\n"
                "请问还有其他我可以帮助您的吗？比如：\n"
                "- 继续了解其他症状的健康知识\n"
                "- 预约校医务室\n"
                "- 咨询健康保健建议"
            )
            for char in reply:
                yield char

        else:
            # 回复不明确 → 追问
            clarification = (
                "抱歉我没听清楚，请直接告诉我：\n"
                "- 回复「是」→ 我帮您预约医务室\n"
                "- 回复「不是」→ 我为您提供健康知识"
            )
            for char in clarification:
                yield char

    # ======================= 症状追问诊断 =======================

    def _detect_complex_symptom(self, user_input: str) -> str:
        """检测输入是否包含复杂症状，返回症状关键词（长词优先）"""
        for word in sorted(self.COMPLEX_SYMPTOM_KEYS, key=len, reverse=True):
            if word in user_input:
                return word
        return ""

    def _get_probe_state(self) -> Dict[str, Any]:
        """获取诊断探针状态"""
        slots = self._get_slots()
        return slots.get('diagnosis_probe') or {}

    def _save_probe_state(self, probe: Dict[str, Any]):
        """保存诊断探针状态"""
        slots = self._get_slots()
        slots['diagnosis_probe'] = probe
        if probe:
            slots['doctor_sub_state'] = 'collecting_symptoms'
        self._set_slots(slots)

    async def _extract_probe_answer(self, user_reply: str) -> Dict[str, str]:
        """用 LLM 从用户回复中提取症状信息字段"""
        prompt = (
            "你是一个医学信息提取器。从用户的症状描述中提取以下字段：\n"
            "location: 疼痛/症状的位置（如右下腹、前额），没有则为空\n"
            "nature: 症状性质（如绞痛、刺痛、胀痛），没有则为空\n"
            "duration: 持续时间（如两天、一周），没有则为空\n"
            "concomitant: 伴随症状（如发烧、恶心），没有则为空\n\n"
            f"用户描述：{user_reply}\n\n"
            "只输出 JSON，格式：{\"location\": \"\", \"nature\": \"\", \"duration\": \"\", \"concomitant\": \"\"}"
        )
        try:
            response = await self.response_generator.llm.ainvoke([{"role": "user", "content": prompt}])
            content = response.content.strip()
            # 兼容 markdown 包裹
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
            import json as _json
            data = _json.loads(content)
            return {k: (v or '') for k, v in data.items() if k in ('location', 'nature', 'duration', 'concomitant')}
        except Exception as e:
            logger.warning(f"[追问] LLM 提取失败，降级关键词匹配: {e}")
            return self._keyword_probe_extract(user_reply)

    def _keyword_probe_extract(self, text: str) -> Dict[str, str]:
        """关键词兜底提取"""
        import re
        result = {'location': '', 'nature': '', 'duration': '', 'concomitant': ''}
        # 位置
        location_words = ['上腹', '下腹', '肚脐', '右下腹', '左下腹', '右上腹', '左上腹', '前额', '后脑', '太阳穴', '左胸', '右胸', '胸骨', '胃', '腹部']
        for w in location_words:
            if w in text:
                result['location'] = w
                break
        # 性质
        nature_words = ['绞痛', '刺痛', '胀痛', '隐痛', '烧灼', '压榨', '搏动', '紧绷', '闷痛', '疼痛']
        for w in nature_words:
            if w in text:
                result['nature'] = w
                break
        # 持续时间
        duration_match = re.search(r'([一二三四五六七八九十\d]+)天|([一二三四五六七八九十\d]+)周|([一二三四五六七八九十\d]+)月|([一二三四五六七八九十\d]+)小时', text)
        if duration_match:
            result['duration'] = duration_match.group(0)
        # 伴随症状
        concomitant_words = ['发烧', '发热', '恶心', '呕吐', '腹泻', '拉肚子', '心慌', '气短', '出汗', '头晕', '畏光', '反酸', '食欲不振', '流鼻涕', '咽痛']
        found = [w for w in concomitant_words if w in text]
        if found:
            result['concomitant'] = '、'.join(found)
        return result

    async def _generate_probe_message(self, symptom: str, collected: Dict[str, str],
                                      next_question: str) -> str:
        """基于已收集的症状信息，用 LLM 生成诊断可能性分析 + 追问

        让追问不再生硬，像真实医生一样先给出基于已知信息的初步判断，
        再追问下一个细节。
        """
        collected_desc = '、'.join(v for v in collected.values() if v) or '尚未明确'
        prompt = (
            "你是校园医务室的全科医生，正在问诊。\n"
            f"主诉症状：{symptom}\n"
            f"目前已了解的信息：{collected_desc}\n\n"
            "请基于以上信息，用 2-3 句话给出可能的病因方向（用'可能涉及''常见原因包括'等措辞，"
            "不要下确定性诊断，语气温和专业），然后自然地引出下一个问题。\n"
            "注意：不要直接复述用户信息，要把它们转化为医学分析的上下文。\n\n"
            f"需要追问的问题：{next_question}"
        )
        try:
            response = await self.response_generator.llm.ainvoke([{"role": "user", "content": prompt}])
            content = response.content.strip()
            if content:
                return content + "\n"
        except Exception as e:
            logger.warning(f"[追问] LLM 生成分析失败，使用模板: {e}")
        # 兜底模板
        return f"根据您提到的{collected_desc}，这有助于初步判断。为了更准确，请您再回答：\n{next_question}\n"

    async def _probe_symptom_flow(self, user_input: str, session_id: str) -> AsyncGenerator[str, None]:
        """复杂症状追问流程：最多3轮，信息不足就继续问，收集到关键信息就停止"""
        # 用户在追问过程中表达了预约/不预约意图 → 直接流转到确认预约
        confirm = self._is_confirmation_reply(user_input)
        if confirm != 'unclear':
            async for token in self._handle_confirmation_reply(user_input, session_id):
                yield token
            return

        probe = self._get_probe_state()
        # 追问进行中：优先用探针保存的症状，回答里可能不含症状词
        if probe and probe.get('symptom'):
            symptom = probe['symptom']
        else:
            symptom = self._detect_complex_symptom(user_input)

        # 首次进入（无探针或症状变了）：初始化探针，只问第一个问题
        if not probe or probe.get('symptom') != symptom or not probe.get('asked'):
            # 保存症状到待确认槽位，供后续预约流转使用
            slots = self._get_slots()
            slots["pending_symptom_query"] = symptom
            self._set_slots(slots)
            probe = {
                'symptom': symptom,
                'round': 0,
                'asked': [],
                'collected': {},
            }
            self._save_probe_state(probe)
            questions = self.COMPLEX_SYMPTOM_PROBES.get(symptom, [])
            if questions:
                probe['round'] += 1
                next_q = questions[0]
                probe['asked'].append(next_q[0])
                self._save_probe_state(probe)
                # 首轮：用 LLM 生成基于主诉的诊断可能性分析
                message = await self._generate_probe_message(
                    symptom, probe['collected'], next_q[1]
                )
                for char in message:
                    yield char
            return

        # 用户回答了追问 → 提取新信息
        extracted = await self._extract_probe_answer(user_input)
        for k, v in extracted.items():
            if v and not probe['collected'].get(k):
                probe['collected'][k] = v
        # 记录已提取的伴随症状到槽位
        if probe['collected'].get('concomitant'):
            slots = self._get_slots()
            if 'accompanying_symptoms' not in slots or not slots.get('accompanying_symptoms'):
                slots['accompanying_symptoms'] = []
            for s in probe['collected']['concomitant'].split('、'):
                if s and s not in slots['accompanying_symptoms']:
                    slots['accompanying_symptoms'].append(s)
            self._set_slots(slots)

        questions = self.COMPLEX_SYMPTOM_PROBES.get(symptom, [])
        unasked = [q for q in questions if q[0] not in probe['asked'] and not probe['collected'].get(q[0])]

        # 收集到关键信息（位置+性质+持续时间）或达到3轮或问题问完 → 停止追问
        collected_keys = set(probe['collected'].keys())
        key_fields = {'location', 'nature', 'duration'}
        has_key_info = key_fields.issubset(collected_keys)
        if probe['round'] >= 3 or has_key_info or not unasked:
            self._save_probe_state({})  # 清空探针
            self._reset_doctor_substate()
            # 进入正式问诊（用已收集信息增强查询）
            enhanced_query = symptom
            if probe['collected']:
                parts = [v for v in probe['collected'].values() if v]
                if parts:
                    enhanced_query = f"{symptom}，{'，'.join(parts)}"
            async for token in self._do_doctor_consultation(enhanced_query, user_input, session_id):
                yield token
            return

        # 还有未问问题 → 结合已有信息生成诊断分析 + 追问下一个
        probe['round'] += 1
        next_q = unasked[0]
        probe['asked'].append(next_q[0])
        self._save_probe_state(probe)

        message = await self._generate_probe_message(
            symptom, probe['collected'], next_q[1]
        )
        for char in message:
            yield char

    async def _do_doctor_consultation(self, original_query: str, user_reply: str, session_id: str) -> AsyncGenerator[str, None]:
        """医学问诊流程：结合知识库给建议，并建议预约医务室"""
        knowledge_docs = await self.knowledge_retriever.search_knowledge(original_query, top_k=3)

        if self.memory and self.conversation_id:
            await self._extract_and_save_symptoms(original_query)

        intro = (
            "了解到您有身体不适，我来为您提供初步的医学建议。\n\n"
            "⚠️ 温馨提示：我是AI助手，以下建议仅供参考，不能替代专业医生诊断。\n\n"
        )
        for char in intro:
            yield char

        # 用LLM生成医学建议
        prompt = (
            "你是校园医务室的医生助手，用户报告了以下症状，"
            "请基于提供的医学知识给出谨慎的初步建议，"
            "语气要温和、专业，避免给出绝对的诊断结论，倾向于建议就医。\n\n"
            f"用户症状：{original_query}\n\n"
        )
        if knowledge_docs:
            prompt += "相关医学知识：\n"
            for doc in knowledge_docs:
                content = doc.get('answer', '')
                if not content:
                    content = doc.get('content', '')
                if content and not self._is_query_text(content):
                    prompt += f"- {content}\n"
        prompt += (
            "\n请给出：\n"
            "1. 简要的初步分析（不要过度诊断）\n"
            "2. 一般性的自我护理建议\n"
            "3. 如果症状持续或加重，建议及时到校医务室就诊\n"
            "注意：不要询问是否需要预约，这个问题由系统统一处理。"
        )

        try:
            response = await self.response_generator.llm.ainvoke([{"role": "user", "content": prompt}])
            content = response.content
            for char in content:
                yield char
        except Exception as e:
            logger.error(f"LLM问诊生成失败: {e}")
            fallback = (
                "根据您描述的症状，建议您：\n"
                "1. 注意休息，多喝温水\n"
                "2. 观察症状变化\n"
                "3. 如果症状持续或加重，请及时到校医务室就诊\n\n"
            )
            for char in fallback:
                yield char

        # 问诊完成：进入预约确认状态，输出按钮供用户选择
        slots = self._get_slots()
        slots["doctor_sub_state"] = "awaiting_confirmation"
        slots["pending_symptom_query"] = original_query
        self._set_slots(slots)

        confirm_question = (
            "\n\n需不需要我帮您预约校医务室呢？\n"
            "[BUTTONS]需要,不需要\n"
        )
        for char in confirm_question:
            yield char

    async def _do_rag_answer(self, user_input: str, session_id: str,
                             is_knowledge_only: bool = False,
                             is_doctor_consultation: bool = False) -> AsyncGenerator[str, None]:
        """纯RAG健康知识回答"""
        knowledge_docs = await self.knowledge_retriever.search_knowledge(user_input, top_k=3)

        if self.memory and self.conversation_id:
            await self._extract_and_save_symptoms(user_input)

        if is_knowledge_only:
            prefix = "[REPLY][健康知识]\n好的，以下是关于这个问题的健康知识信息：\n\n"
            for char in prefix:
                yield char
        else:
            async for token in self.response_generator.generate_response_stream(user_input, knowledge_docs):
                yield token
            await self._record_consultation_behavior(user_input, knowledge_docs, session_id)
            return

        if knowledge_docs:
            try:
                prompt = (
                    "你是校园医务室的健康知识助手，用户咨询健康知识问题（不是问诊）。\n"
                    "请基于以下知识库信息，用通俗易懂的语言回答用户的问题。\n\n"
                )
                prompt += "相关医学知识：\n"
                for i, doc in enumerate(knowledge_docs, 1):
                    # 优先使用answer字段（问答对格式），其次使用content字段
                    content = doc.get('answer', doc.get('content', ''))
                    if content:
                        prompt += f"{i}. {content}\n"
                prompt += f"\n用户问题：{user_input}\n\n请简洁专业地回答。"
                response = await self.response_generator.llm.ainvoke([{"role": "user", "content": prompt}])
                content = response.content
                for char in content:
                    yield char
            except Exception as e:
                logger.error(f"RAG回答生成失败: {e}")
                for doc in knowledge_docs:
                    yield doc.get('content', '') + "\n\n"
        else:
            fallback = "抱歉，暂时没有找到与该问题相关的健康知识。您可以直接到校园医务室咨询医护人员。"
            for char in fallback:
                yield char

        await self._record_consultation_behavior(user_input, knowledge_docs, session_id)

    async def handle_unrelated_request(self, user_input: str, unrelated_callback, shared_state) -> AsyncGenerator[str, None]:
        """处理非医学类请求 - 转发回主分类器"""
        if unrelated_callback:
            async for token in unrelated_callback(user_input):
                yield token
        else:
            yield "[REPLY][助手]"
            msg = "抱歉，我主要负责医学健康相关的问题。请问您有什么健康方面的问题需要咨询吗？"
            for char in msg:
                yield char

    async def _extract_and_save_symptoms(self, user_input: str):
        """从用户输入提取症状信息并保存到医疗槽位"""
        slots = self._get_slots()
        if not slots:
            return

        if not slots.get('chief_complaint'):
            slots['chief_complaint'] = user_input.strip()

        symptom_keywords = [
            '发烧', '发热', '咳嗽', '头疼', '头痛', '头晕', '肚子疼',
            '腹泻', '拉肚子', '恶心', '呕吐', '流鼻涕', '鼻塞',
            '喉咙痛', '嗓子疼', '过敏', '皮疹', '疼痛', '疲劳',
            '乏力', '失眠', '胸闷', '心慌', '关节痛', '肌肉痛'
        ]

        detected = []
        for kw in symptom_keywords:
            if kw in user_input and kw not in slots.get('accompanying_symptoms', []):
                detected.append(kw)

        if detected:
            if 'accompanying_symptoms' not in slots:
                slots['accompanying_symptoms'] = []
            slots['accompanying_symptoms'].extend(detected)

        if any(w in user_input for w in ['发烧', '发热', '高烧']):
            slots['fever'] = True

        if any(w in user_input for w in ['受伤', '外伤', '撞到', '摔伤', '割伤']):
            slots['trauma'] = True

        self._set_slots(slots)

    async def _record_consultation_behavior(self, user_input: str, knowledge_docs: list, session_id: str):
        """记录咨询行为"""
        if not self.memory or not self.conversation_id:
            return
        behavior = self.memory.get_behavior_memory(self.conversation_id) or {}
        behavior['consultation_count'] = behavior.get('consultation_count', 0) + 1
        behavior['last_consultation'] = user_input
        self.memory.set_behavior_memory(self.conversation_id, behavior)
