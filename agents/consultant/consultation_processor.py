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
        '嗯', '嗯嗯', '是', '有', '对'
    }

    def __init__(self, knowledge_retriever: KnowledgeRetriever,
                 consultation_classifier: ConsultationClassifier,
                 response_generator: ResponseGenerator,
                 memory_service=None,
                 conversation_id=None):
        self.knowledge_retriever = knowledge_retriever
        self.consultation_classifier = consultation_classifier
        self.response_generator = response_generator
        self.memory = memory_service
        self.conversation_id = conversation_id

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

            # 明确知识类问题（如何预防、什么是...）→ 直接 RAG，不走问诊
            knowledge_patterns = ['如何预防', '怎么预防', '什么是', '如何治疗', '怎么治疗',
                                  '注意事项', '能吃吗', '有什么用', '是什么原因',
                                  '怎么回事', '为什么会']
            is_knowledge_question = any(p in user_input for p in knowledge_patterns)
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
                    "请基于以下知识库信息，用1-2句话给出简洁的健康知识科普，语气中立专业。\n\n"
                )
                prompt += "相关医学知识：\n"
                for i, doc in enumerate(knowledge_docs, 1):
                    content = doc.get('answer', doc.get('content', ''))
                    if content:
                        prompt += f"{i}. {content}\n"
                prompt += f"\n用户问题：{user_input}\n\n请简洁回答。"
                response = await self.response_generator.llm.ainvoke([{"role": "user", "content": prompt}])
                content = response.content.strip()
                if content:
                    has_relevant_knowledge = True
                    yield content + "\n\n"
            except Exception:
                pass

        if not has_relevant_knowledge:
            yield f"关于「{mentioned_symptom or user_input}」，这是校园常见症状之一。注意休息，如症状持续建议就医检查。\n\n"

        # 再询问是否自己有症状
        if mentioned_symptom:
            question = (
                f"请问是您自己出现了「{mentioned_symptom}」的症状吗？\n"
                f"- 如果是，我可以帮您预约校医务室\n"
                f"- 如果不是，我为您提供健康知识"
            )
        else:
            question = (
                f"请问是您自己出现了这个症状吗？\n"
                f"- 如果是，我可以帮您预约校医务室\n"
                f"- 如果不是，我为您提供健康知识"
            )
        for char in question:
            yield char

    def _extract_mentioned_symptom(self, user_input: str) -> str:
        """从用户输入中提取提到的症状词"""
        for word in sorted(self.SYMPTOM_WORDS, key=len, reverse=True):
            if word in user_input:
                return word
        return ""

    async def _handle_confirmation_reply(self, user_input: str, session_id: str) -> AsyncGenerator[str, None]:
        """处理用户对症状确认的回复"""
        reply_type = self._is_confirmation_reply(user_input)
        slots = self._get_slots()
        original_query = slots.get("pending_symptom_query", user_input)

        if reply_type == 'confirm':
            # 用户确认有症状 → 建议预约医务室
            logger.info(f"[症状确认] 用户确认有症状，建议预约: {original_query}")
            self._reset_doctor_substate()

            reply = (
                "了解，如果您有这方面的不适，建议及时到校医务室就诊检查。\n\n"
                "需要我帮您预约校医务室吗？回复「预约」即可。"
            )
            for char in reply:
                yield char

        elif reply_type == 'deny':
            # 用户否认 → 礼貌结束
            self._reset_doctor_substate()
            logger.info(f"[症状确认] 用户否认有症状，礼貌结束: {original_query}")

            reply = (
                "好的，了解了。如果您后续有任何健康问题或需要预约医务室，随时找我。\n"
                "祝您身体健康！"
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
                content = doc.get('answer', doc.get('content', ''))
                if content:
                    prompt += f"- {content}\n"
        prompt += (
            "\n请给出：\n"
            "1. 简要的初步分析（不要过度诊断）\n"
            "2. 一般性的自我护理建议\n"
            "3. 如果症状持续或加重，建议及时到校医务室就诊\n"
            "最后主动询问是否需要帮您预约校医务室。"
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
                "需要我帮您预约校医务室吗？"
            )
            for char in fallback:
                yield char

        # 问诊完成，重置子状态
        self._reset_doctor_substate()

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
