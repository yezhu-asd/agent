from dotenv import load_dotenv
import uuid
import logging
from langchain_core.chat_history import InMemoryChatMessageHistory
from config.model_provider import create_chat_model
from services.conversation_memory_service import conversation_memory
from .appointment import (
    InputParser,
    DoctorFinder,
    AppointmentProcessor,
    MessageBuilder,
    AppointmentDatabase
)

load_dotenv()


class AppointmentAgent:
    """
    医生预约机器人主控制器 (校园医务室版本)
    
    职责：
    1. 初始化各个组件
    2. 管理会话状态
    3. 协调整个医生预约流程
    
    预约流程：收集症状 → 评估紧急度 → 选择医生 → 选择时间 → 确认预约
    """
    
    def __init__(self, session_id=None, unrelated_callback=None, user_id=None, conversation_id=None):
        # 基础设置
        self.session_id = session_id or str(uuid.uuid4())
        self.unrelated_callback = unrelated_callback

        # Token 登录信息
        self.user_id = user_id
        self.conversation_id = conversation_id

        self.state = None

        # 初始化LLM
        self.llm = self._initialize_llm()

        # 初始化组件
        self.input_parser = InputParser(self.llm)
        self.technician_finder = DoctorFinder()
        self.message_builder = MessageBuilder()
        self.appointment_database = AppointmentDatabase()
        self.appointment_processor = AppointmentProcessor(
            self.input_parser,
            self.technician_finder,
            self.message_builder,
            self.appointment_database,
            self.llm,
            conversation_memory,
            self.conversation_id,
            self.user_id
        )

        # 会话管理
        self.chats_by_session_id = {}
        self.chat_history = self._get_chat_history(self.session_id)

        # 如果有conversation_id，确保预约槽位存在
        if self.conversation_id:
            # 调用get_appointment_slots自动初始化不存在的槽位，不会覆盖已有数据
            conversation_memory.get_appointment_slots(self.conversation_id)

        # 医生预约状态（校园医务室版本）
        self.reset()
        # 如果已有持久化的预约历史，恢复它
        self._restore_history_from_slots()

    def _initialize_llm(self):
        """初始化通用聊天模型"""
        return create_chat_model(temperature=0)

    def _get_chat_history(self, session_id: str) -> InMemoryChatMessageHistory:
        """获取或创建会话历史记录"""
        chat_history = self.chats_by_session_id.get(session_id)
        if chat_history is None:
            chat_history = InMemoryChatMessageHistory()
            self.chats_by_session_id[session_id] = chat_history
        return chat_history
    
    def reset(self):
        """重置预约历史和状态 (医疗预约版本)"""
        self.appointment_history = {
            # 医疗相关信息
            "symptoms": None,  # 症状描述
            "urgency_level": "routine",  # 紧急度：routine/urgent/emergency
            "preferred_doctor": None,  # 选择的医生
            "preferred_date": None,  # 选择的日期
            "appointment_reason": None,  # 预约原因
            "medical_history": None,  # 相关病史

            # 向后兼容字段（暂时保留）
            "gender": None,
            "start_time": None,
            "duration": None,
            "project": None,
            "preference": None,
            "doctor": None,
            "doctor_name": None,

            # 流程控制字段
            "awaiting_confirmation": False,  # 是否正在等待用户确认推荐
            "awaiting_continue_confirmation": False,  # 是否正在等待用户确认是否继续预约（无关请求后）
            "appointment_in_progress": False,  # 是否正在填写预约信息（用于无关请求时判断）
            "recommended_doctor": None,  # 推荐的医生信息
            "recommended_time": None,  # 推荐的时间
            "original_doctor": None,  # 原始选择的医生（如果有）
            "confirmed_doctor": None,  # 用户确认的医生
            "recommendation_declined": False,  # 用户是否拒绝了推荐
        }
        self.finished = False
        self.chat_history.clear()

    def _reset_to_classify_state(self):
        """将状态重置为 CLASSIFY（同步 SharedState 和持久化存储）"""
        if self.state:
            from config.constants import StateEnum
            self.state.value = StateEnum.CLASSIFY
        if self.user_id and self.conversation_id:
            from config.constants import get_state_storage, StateEnum
            get_state_storage().set_state(self.user_id, self.conversation_id, StateEnum.CLASSIFY)

    def set_shared_state(self, shared_state):
        """设置共享状态"""
        self.state = shared_state

    def set_user_context(self, user_id: str, conversation_id: str):
        """设置用户登录后的上下文信息"""
        self.user_id = user_id
        self.conversation_id = conversation_id
        # 初始化预约槽位
        if conversation_id and conversation_memory:
            conversation_memory.init_appointment_slots(conversation_id)
        # 更新processor中的conversation_id和user_id
        if hasattr(self.appointment_processor, 'conversation_id'):
            self.appointment_processor.conversation_id = conversation_id
        if hasattr(self.appointment_processor, 'user_id'):
            self.appointment_processor.user_id = user_id
        # 重新从槽位恢复历史
        self._restore_history_from_slots()

    def _restore_history_from_slots(self):
        """从持久化存储恢复预约历史（跨请求恢复）"""
        if not self.conversation_id:
            return
        try:
            key = f"conversation:{self.conversation_id}:appointment_history"
            raw = conversation_memory._get_json(key)
            if raw:
                # 恢复所有字段，包括推荐确认相关的关键字段
                for k, v in raw.items():
                    self.appointment_history[k] = v
                logger = logging.getLogger(__name__)
                logger.debug(f"恢复预约历史: {raw}")
                logger.debug(f" awaiting_confirmation: {self.appointment_history.get('awaiting_confirmation')}")
                logger.debug(f" recommended_doctor: {self.appointment_history.get('recommended_doctor')}")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"恢复预约历史失败: {e}")

    @staticmethod
    def _fast_parse_confirmation(user_input: str) -> dict | None:
        """等待确认推荐时，用关键词快速判断用户意图，不依赖LLM。
        返回data dict表示已识别，返回None表示无法判断需走LLM。"""
        text = user_input.strip().lower()
        positive = ['是', '好', '可以', '同意', '确定', '行', '约', '帮我约', 'yes', 'ok', '确认', '接受']
        negative = ['不', '不要', '不行', '不同意', '换', 'no', '拒绝', '算了', '取消', '换个', '换时间', '换医生']

        is_pos = any(p in text for p in positive)
        is_neg = any(n in text for n in negative)

        # 明显否定优先
        if is_neg and not is_pos:
            return {"confirmation": "不", "unrelated": False, "cancel_intent": False}
        if is_pos:
            return {"confirmation": "是", "unrelated": False, "cancel_intent": False}
        return None

    async def run_stream(self, user_input=None):
        """
        流式处理用户医生预约请求的主函数

        这是整个预约流程的入口点，协调各个组件完成预约
        """
        if user_input is None:
            user_input = input("用户：")

        # 保存用户消息到对话历史
        if self.conversation_id and conversation_memory:
            conversation_memory.append_message(self.conversation_id, "user", user_input)

        full_response = ""
        logger = logging.getLogger(__name__)

        # 0. 检查是否正在等待取消预约确认
        cancel_pending = False
        if self.conversation_id and conversation_memory:
            pending_key = f"conversation:{self.conversation_id}:cancel_pending"
            cancel_pending = conversation_memory._get_json(pending_key) is not None

        if cancel_pending:
            # 正在等用户确认取消，直接处理回复，不走LLM解析
            cancelled = False
            try:
                async for token in self.appointment_processor.handle_cancel_confirmation(
                    user_input, self.user_id
                ):
                    if token == "[SIGNAL]cancelled":
                        cancelled = True
                        continue
                    full_response += token
                    yield token
                if self.conversation_id and conversation_memory:
                    conversation_memory.append_message(self.conversation_id, "assistant", full_response)
                if cancelled:
                    # 取消成功（或本就无预约），重置预约历史和全局状态
                    self.reset()
                    self._reset_to_classify_state()
                    self._sync_to_memory_slots()
                return
            except Exception as e:
                logger.error(f"处理取消确认异常: {str(e)}", exc_info=True)
                error_msg = "[REPLY][预约机器人]\n机器人：处理取消请求时遇到问题，请稍后重试。\n"
                yield error_msg
                return

        # 0.3 检查是否正在等待用户确认是否继续预约（无关请求后的恢复）
        if self.appointment_history.get('awaiting_continue_confirmation'):
            # 判断用户是否想继续预约——优先匹配多字词组，避免单字误判
            # 例如 "取消预约" 同时含"取消"(负)和"约"(正)，应判为否定
            negative_phrases = ['取消', '不要', '算了', '不用', '不约了', '不继续', '换个', '重新来', '不约', '不想约']
            positive_phrases = ['继续预约', '继续约', '接着约', '接着继续', '好的继续', '继续填写']
            negative_single = ['不', 'no']
            positive_single = ['是', '好', '要', 'yes', 'ok', '确认', '行', '可以的', '嗯', '对']

            text = user_input.strip().lower()

            # 先匹配多字词组（更精准）
            has_neg_phrase = any(p in text for p in negative_phrases)
            has_pos_phrase = any(p in text for p in positive_phrases)

            if has_neg_phrase and not has_pos_phrase:
                is_neg = True
                is_pos = False
            elif has_pos_phrase and not has_neg_phrase:
                is_neg = False
                is_pos = True
            else:
                # 都没命中或都命中，退到单字兜底
                is_pos = any(p in text for p in positive_single)
                is_neg = any(p in text for p in negative_single)
                # 同时为 True 时优先判定为否定（取消预约场景下用户意图更明确）
                if is_pos and is_neg:
                    is_neg = True
                    is_pos = False

            # 清除标记（无论哪种回复都清除，避免卡死）
            self.appointment_history['awaiting_continue_confirmation'] = False

            if is_neg:
                # 用户选择取消预约填写
                self.reset()
                self._reset_to_classify_state()
                self._sync_to_memory_slots()
                cancel_msg = "[REPLY][预约机器人]\n机器人：好的，已为您取消当前预约填写。请告诉我您需要什么帮助？\n"
                yield cancel_msg
                if self.conversation_id and conversation_memory:
                    conversation_memory.append_message(self.conversation_id, "assistant", cancel_msg)
                return

            # 用户选择继续（或无法判断，默认继续）→ 重新追问缺失信息
            async for token in self.appointment_processor.handle_incomplete_info({}, self.appointment_history):
                full_response += token
                yield token

            if self.conversation_id and conversation_memory:
                self._sync_to_memory_slots()
                conversation_memory.append_message(self.conversation_id, "assistant", full_response)
            return

        # 0.5 检查改期/修改预约意图
        is_modify = InputParser.detect_reschedule_intent_fast(user_input)
        if is_modify:
            # 用户要修改预约，优先从DB获取权威数据，Redis仅用于展示提示
            apt_info = None
            has_apt = False

            # 有user_id时，始终从DB查询权威预约数据
            if self.user_id:
                apt = self.appointment_database.get_user_active_appointment(self.user_id)
                if apt and not apt.get('is_expired', False):
                    apt_info = apt
                    has_apt = True

            # 没登录或DB查不到时，尝试从Redis获取（仅当前会话内的预约）
            if not has_apt and self.conversation_id and conversation_memory:
                completed_key = f"conversation:{self.conversation_id}:appointment_completed"
                redis_apt = conversation_memory._get_json(completed_key)
                if redis_apt and redis_apt.get('appointment_id'):
                    apt_info = redis_apt
                    has_apt = True

            if has_apt:
                # 有旧预约，先告知用户查到了预约，再取消并引导重新预约
                try:
                    # 格式化预约信息用于展示
                    doctor_name = apt_info.get('doctor_name') or apt_info.get('doctor', '未知医生')
                    apt_time = apt_info.get('start_time') or apt_info.get('time', '')
                    if apt_time:
                        try:
                            from datetime import datetime
                            if isinstance(apt_time, datetime):
                                apt_time = apt_time.strftime('%m月%d日 %H:%M')
                                weekday = ['周一','周二','周三','周四','周五','周六','周日'][apt_time.weekday()] if hasattr(apt_time, 'weekday') else ''
                            elif isinstance(apt_time, str):
                                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"]:
                                    try:
                                        dt = datetime.strptime(apt_time[:19] if 'T' in apt_time else apt_time[:16], fmt)
                                        apt_time = dt.strftime('%m月%d日 %H:%M')
                                        break
                                    except ValueError:
                                        continue
                        except Exception:
                            pass

                    # 先回复用户查询到了预约
                    yield f"[THOUGHT][预约机器人]用户要改期，查询到已有预约：{doctor_name} {apt_time}，准备取消旧预约并引导重新预约"
                    yield f"[REPLY][预约机器人]\n机器人：好的，已查询到您的预约：{doctor_name}医生 {apt_time}。我先为您取消这次预约，请告诉我您新的预约时间和需求～\n"

                    # 执行取消（有user_id时用DB数据，权威）
                    cancel_success = False
                    if self.user_id and apt_info:
                        appointment_id = apt_info.get('id') or apt_info.get('appointment_id')
                        schedule_id = apt_info.get('schedule_id')
                        doctor_id = str(apt_info.get('doctor_id', ''))
                        start_time = apt_info.get('start_time')
                        end_time = apt_info.get('end_time')
                        if appointment_id and schedule_id:
                            cancel_success = self.appointment_database.cancel_appointment(
                                appointment_id, schedule_id, doctor_id, start_time, end_time
                            )
                    elif apt_info and apt_info.get('appointment_id') and apt_info.get('schedule_id'):
                        # 未登录用户，仅清理内存中的记录
                        cancel_success = True
                        pass

                    # 清空旧的状态
                    self.reset()
                    # 清理Redis里的预约相关key
                    if self.conversation_id and conversation_memory:
                        try:
                            conversation_memory._delete(f"conversation:{self.conversation_id}:appointment_completed")
                            conversation_memory._delete(f"conversation:{self.conversation_id}:appointment_slots")
                            conversation_memory._delete(f"conversation:{self.conversation_id}:appointment_history")
                            conversation_memory._delete(f"conversation:{self.conversation_id}:cancel_pending")
                            conversation_memory._delete(f"conversation:{self.conversation_id}:has_existing_appointment")
                        except Exception:
                            pass
                    self._sync_to_memory_slots()
                    if self.conversation_id and conversation_memory:
                        conversation_memory.append_message(self.conversation_id, "assistant", f"[REPLY][预约机器人]\n机器人：好的，已查询到您的预约：{doctor_name}医生 {apt_time}。我先为您取消这次预约，请告诉我您新的预约时间和需求～\n")
                    return
                except Exception as e:
                    logger.error(f"修改预约取消旧预约异常: {str(e)}", exc_info=True)
                    yield "[REPLY][预约机器人]\n机器人：取消旧预约时遇到问题，请稍后重试，或直接告诉我新的预约需求。\n"
                    return
            else:
                yield "[REPLY][预约机器人]\n机器人：您当前没有可修改的预约，直接告诉我您的预约需求吧。\n"
                self.reset()
                self._sync_to_memory_slots()
                if self.conversation_id and conversation_memory:
                    conversation_memory.append_message(self.conversation_id, "assistant", full_response)
                return

        # 1. 快速关键词检测取消意图（不依赖LLM，避免无关请求被转交走）
        # 只有在用户已有预约（DB中存在）或会话标记了appointment_completed时才触发取消流程
        is_cancel = InputParser.detect_cancel_intent_fast(user_input)

        if is_cancel:
            try:
                # 先检查是否真的有预约，避免用户在预约填写过程中说"取消"误触发
                has_appointment = False
                if self.conversation_id and conversation_memory:
                    completed_key = f"conversation:{self.conversation_id}:appointment_completed"
                    has_appointment = conversation_memory._get_json(completed_key) is not None
                if not has_appointment and self.user_id:
                    apt = self.appointment_database.get_user_active_appointment(self.user_id)
                    has_appointment = apt is not None and not apt.get('is_expired', False)

                if has_appointment:
                    async for token in self.appointment_processor.handle_cancel_request(self.user_id):
                        full_response += token
                        yield token
                else:
                    # 用户在预约填写过程中说取消，清空当前填写
                    self.reset()
                    self._sync_to_memory_slots()
                    yield "[REPLY][预约机器人]\n机器人：好的，已为您取消当前预约填写。需要重新预约或者有其他需求请告诉我。\n"
                    self._reset_to_classify_state()

                if self.conversation_id and conversation_memory:
                    conversation_memory.append_message(self.conversation_id, "assistant", full_response)
                return
            except Exception as e:
                logger.error(f"处理取消请求异常: {str(e)}", exc_info=True)
                error_msg = "[REPLY][预约机器人]\n机器人：处理取消请求时遇到问题，请稍后重试。\n"
                yield error_msg
                return

        # 2. 解析用户输入：等待确认时优先用关键词快速判断，否则走LLM
        if self.appointment_history.get('awaiting_confirmation'):
            confirm_data = self._fast_parse_confirmation(user_input)
            if confirm_data is not None:
                data = confirm_data
            else:
                ai_content = ""
                for token in self.input_parser.parse_stream(user_input, self.chat_history):
                    ai_content += token
                data = self.input_parser.parse_data(ai_content)
        else:
            ai_content = ""
            for token in self.input_parser.parse_stream(user_input, self.chat_history):
                ai_content += token
            data = self.input_parser.parse_data(ai_content)

        try:
            # 保存原始用户输入，供 processor 做 gender 规则补提
            self.appointment_processor._last_user_input = user_input
            self.finished = self.appointment_processor.update_history_from_data(self.appointment_history, data)

            # 将解析出的预约信息同步到记忆槽位
            if self.conversation_id and conversation_memory:
                self._sync_to_memory_slots()

            # 3. 处理与预约无关的请求
            # 如果正在等待用户确认推荐，不要转交给分类机器人
            if data.get("unrelated", False) and not self.appointment_history.get('awaiting_confirmation'):
                # 如果正在填写预约信息，不直接转交，而是询问用户是否继续预约
                if self.appointment_history.get('appointment_in_progress'):
                    # 标记为等待继续确认
                    self.appointment_history['awaiting_continue_confirmation'] = True

                    # 持久化状态，确保下一轮能恢复
                    if self.conversation_id and conversation_memory:
                        self._sync_to_memory_slots()

                    continue_msg = (
                        "[REPLY][预约机器人]\n机器人：您当前有一个未完成"
                        "的预约填写（已填写部分信息）。"
                        "请问是否继续预约？\n"
                        "[BUTTONS]继续预约,取消预约\n"
                    )
                    yield continue_msg

                    if self.conversation_id and conversation_memory:
                        conversation_memory.append_message(
                            self.conversation_id, "assistant", continue_msg
                        )
                    return

                # 未在预约填写中，正常转交分类机器人
                self._reset_to_classify_state()

                async for token in self.appointment_processor.handle_unrelated_request(
                    user_input, self.unrelated_callback, self.state
                ):
                    full_response += token
                    yield token

                if self.conversation_id and conversation_memory:
                    conversation_memory.append_message(self.conversation_id, "assistant", full_response)
                return

            # 4. 处理预约完成的情况
            if self.finished:
                recommendation_pending = False
                async for token in self.appointment_processor.handle_complete_appointment(
                    self.appointment_history, self.session_id
                ):
                    # 检查是否有推荐等待确认
                    if token == "[SIGNAL]recommendation_pending":
                        recommendation_pending = True
                        # 将 finished 设为 False，让预约流程继续
                        self.finished = False
                        continue
                    full_response += token
                    yield token

                # 只有在真正完成预约时才重置状态
                if not recommendation_pending and not self.appointment_history.get('awaiting_confirmation'):
                    self._reset_state_after_appointment()
                elif recommendation_pending or self.appointment_history.get('awaiting_confirmation'):
                    # 重要：如果有推荐等待确认，必须立即持久化状态！
                    if self.conversation_id and conversation_memory:
                        self._sync_to_memory_slots()

                # 重新检查信息是否完整（可能因为时间不在营业时间或无医生而被清空了 start_time）
                required_fields = ["start_time", "project"]
                doctor_name_val = self.appointment_history.get("doctor_name")
                if not doctor_name_val or doctor_name_val == "未知":
                    required_fields.append("gender")

                has_all_required = all(
                    self.appointment_history.get(field) and self.appointment_history.get(field) != "未知"
                    for field in required_fields
                )

                if not has_all_required:
                    self.finished = False
                    # 持久化更新后的状态（start_time 被清空）
                    if self.conversation_id and conversation_memory:
                        self._sync_to_memory_slots()

                # 保存AI回复到对话历史
                if self.conversation_id and conversation_memory:
                    conversation_memory.append_message(self.conversation_id, "assistant", full_response)
                return

            # 5. 处理信息不完整的情况
            async for token in self.appointment_processor.handle_incomplete_info(data, self.appointment_history):
                full_response += token
                yield token

            # 信息不完整时也要持久化，供下一轮继续补充
            if self.conversation_id and conversation_memory:
                self._sync_to_memory_slots()

            # 保存AI回复到对话历史
            if self.conversation_id and conversation_memory:
                conversation_memory.append_message(self.conversation_id, "assistant", full_response)

        except Exception as e:
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"预约处理异常: {str(e)}", exc_info=True)
            error_msg = f"[REPLY][预约机器人]\n机器人：预约处理遇到问题，请稍后重试。\n"
            full_response += error_msg
            yield error_msg
            # 保存错误回复到对话历史
            if self.conversation_id and conversation_memory:
                conversation_memory.append_message(self.conversation_id, "assistant", full_response)

    def _sync_to_memory_slots(self):
        """将当前预约信息同步到记忆槽位和预约历史持久化"""
        if not self.conversation_id or not conversation_memory:
            return

        # 获取当前槽位
        slots = conversation_memory.get_appointment_slots(self.conversation_id)

        # 同步预约信息到槽位
        if self.appointment_history.get('preferred_date'):
            slots['preferred_date'] = self.appointment_history['preferred_date']
        if self.appointment_history.get('preferred_time_period'):
            slots['preferred_time_period'] = self.appointment_history['preferred_time_period']
        if self.appointment_history.get('urgency_level'):
            slots['urgency'] = self.appointment_history['urgency_level']
        if self.appointment_history.get('symptoms'):
            slots['appointment_reason'] = self.appointment_history['symptoms']
        if self.appointment_history.get('preferred_doctor'):
            slots['location'] = self.appointment_history.get('doctor_name', '校园医务室')

        # 同时也将 start_time/project/gender 等字段同步到槽位
        if self.appointment_history.get("start_time"):
            slots["preferred_date"] = self.appointment_history["start_time"]
        if self.appointment_history.get("project"):
            slots["appointment_reason"] = self.appointment_history["project"]

        # 保存更新后的槽位
        conversation_memory.set_appointment_slots(self.conversation_id, slots)

        # 同时保存完整的 appointment_history 用于跨请求恢复
        # 重要：必须包含推荐确认相关的所有关键字段！
        key = f"conversation:{self.conversation_id}:appointment_history"
        # 创建一个安全的深拷贝，确保所有字段都可序列化
        history_to_save = {}
        for k, v in self.appointment_history.items():
            # 特殊处理：datetime 转字符串
            if hasattr(v, 'isoformat'):
                history_to_save[k] = v.isoformat()
            else:
                history_to_save[k] = v
        conversation_memory._set_json(key, history_to_save)

    def _reset_state_after_appointment(self):
        """预约完成后重置状态"""
        self.reset()
        self._reset_to_classify_state()
