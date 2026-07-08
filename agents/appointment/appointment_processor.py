"""
预约处理器
负责把"预约这件事"从信息收集、医生匹配、推荐确认，到最终落库和回复，整条流程串起来
负责协调整个预约流程
"""
"""
# 作用：处理预约相关的核心业务逻辑，包括从用户输入中提取预约信息，查找合适的医生，处理用户对推荐医生的确认或拒绝，
 以及在预约成功后结合北京天气生成个性化的温馨提示；同时还处理与预约无关的请求，并提供相应的回复和引导。
对于追加信息，会判断是与预约任务有关还是无关，无关请求会调用无关处理器处理,重置状态为分类状态，
appointment_history 里的已收集信息不会立刻清空，下一条相关预约请求再进来时，有机会继续接着处理, 它不是一个真正的"任务挂起队列"，而是状态回切 + 保留上下文；
 对于预约相关的信息，会更新预约历史，并检查信息是否完整，如果完整则进入预约成功流程，如果不完整则询问用户补充信息；
 在预约成功流程中，会检查是否需要推荐医生，如果需要则生成推荐消息并等待用户确认，如果不需要则直接处理预约成功；
 在处理预约成功时，还会调用天气工具获取北京天气信息，并结合天气情况生成个性化的成功提示。

 我前面的请求如何等到后面的请求到来一起执行呢？或者说不用等待？那如果用户提供的信息不全但是后续这个请求就刚好提供了怎么办？
当前解决方案：用户信息不全直接回去问，不会等下一个请求，同时把当前会话信息保存下来，后续请求来了直接补全，信息齐了后续这个请求就会直接预约；
这个方案呢有个缺点就是容易出现用户补充两次相同的信息；
"""
import os
import json
import asyncio
import aiohttp
import re
import logging
from datetime import datetime
from typing import Dict, Any, AsyncGenerator
from .input_parser import InputParser
from .doctor_finder import DoctorFinder
from .message_builder import MessageBuilder
from .appointment_database import AppointmentDatabase
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate


class WeatherMCPTool(BaseTool):
    """Weather API 工具"""
    name: str = "get_current_weather"
    description: str = "获取指定城市的当前天气信息"

    def __init__(self):
        super().__init__()
        self._api_key = os.getenv("OPENWEATHER_API_KEY")
        self._base_url = "https://api.openweathermap.org/data/2.5/weather"

    async def _get_weather_data(self, city: str = "Beijing") -> str:
        """异步获取天气数据"""
        if not self._api_key:
            return "今天天气不错，适合就诊。"

        try:
            params = {
                "q": city,
                "appid": self._api_key,
                "units": "metric",
                "lang": "zh_cn"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(self._base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        temp = data["main"]["temp"]
                        feels_like = data["main"]["feels_like"]
                        description = data["weather"][0]["description"]
                        humidity = data["main"]["humidity"]
                        wind_speed = data.get("wind", {}).get("speed", 0)

                        return f"北京当前天气：{description}，气温{temp}°C（体感{feels_like}°C），湿度{humidity}%，风速{wind_speed}m/s"
                    else:
                        return "今天天气不错，适合就诊。"
        except Exception as e:
            return "天气宜人，温度适中，适合就诊。"

    def _run(self, city: str = "Beijing") -> str:
        """同步版本 - 不推荐使用"""
        return asyncio.run(self._get_weather_data(city))

    async def _arun(self, city: str = "Beijing") -> str:
        """异步版本"""
        return await self._get_weather_data(city)


class AppointmentProcessor:
    """预约处理器"""

    def __init__(self, input_parser: InputParser, doctor_finder: DoctorFinder,
                 message_builder: MessageBuilder, appointment_database: AppointmentDatabase,
                 llm=None, memory_service=None, conversation_id=None, user_id=None):
        self.input_parser = input_parser
        self.doctor_finder = doctor_finder
        self.message_builder = message_builder
        self.appointment_database = appointment_database
        self.llm = llm
        self.memory = memory_service
        self.conversation_id = conversation_id
        self.user_id = user_id
        self._last_user_input = ""  # 保存最近一次用户输入，用于 gender 规则补提

        if self.llm:
            self.weather_tool = WeatherMCPTool()
            self.tools = [self.weather_tool]

            self.agent_prompt = ChatPromptTemplate.from_messages([
                ("system", "你是一个校园医务室智能助手，可以为患者生成温馨的预约成功提示。"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])

            self.weather_agent = create_openai_tools_agent(self.llm, self.tools, self.agent_prompt)
            self.agent_executor = AgentExecutor(agent=self.weather_agent, tools=self.tools, verbose=True)

    def _extract_gender_fallback(self, data: Dict[str, Any], appointment_history: Dict[str, Any]) -> str:
        """LLM 没提取到 gender 时，用规则从原始输入中补提"""
        raw_input = self._last_user_input or ""
        if re.search(r'女医生', raw_input):
            return '女'
        if re.search(r'男医生', raw_input):
            return '男'
        # 只包含"女"或"男"字（在预约语境中）
        if re.search(r'[女女]\s*$', raw_input):
            return '女'
        if re.search(r'[男男]\s*$', raw_input):
            return '男'
        return ''

    def update_history_from_data(self, appointment_history: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """从解析数据更新预约历史"""
        if appointment_history.get('awaiting_confirmation'):
            return self._handle_recommendation_response(appointment_history, data)

        for key in ["duration", "gender", "start_time", "project", "doctor_name"]:
            if data.get(key) and data[key] != "未知":
                appointment_history[key] = data[key]

        # LLM输出字段名是 technician_name，映射到 doctor_name
        tech_name = data.get("technician_name")
        if tech_name and tech_name != "未知":
            appointment_history["doctor_name"] = tech_name

        # gender 规则兜底（LLM 可能没提取到"女医生"中的性别）
        if not appointment_history.get("gender") or appointment_history["gender"] == "未知":
            fallback = self._extract_gender_fallback(data, appointment_history)
            if fallback:
                appointment_history["gender"] = fallback

        if not appointment_history.get("duration") or appointment_history["duration"] == "未知":
            appointment_history["duration"] = "30分钟"

        if data.get("preference") and data["preference"] != "未知":
            appointment_history["preference"] = data["preference"]

        required_fields = ["start_time", "project"]
        doctor_name_val = appointment_history.get("doctor_name")

        if not doctor_name_val or doctor_name_val == "未知":
            required_fields.append("gender")

        has_all_required = all(
            appointment_history.get(field) and appointment_history[field] != "未知"
            for field in required_fields
        )

        if has_all_required and doctor_name_val and doctor_name_val != "未知":
            pass

        return has_all_required

    def _handle_recommendation_response(self, appointment_history: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """处理用户对推荐医生的回应"""
        user_response = data.get('confirmation', '').lower()

        positive_responses = ['是', '好', '可以', '同意', '确定', 'yes', 'ok', '行']
        negative_responses = ['不', '不要', '不行', '不同意', '换', 'no']

        is_positive = any(pos in user_response for pos in positive_responses)
        is_negative = any(neg in user_response for neg in negative_responses)

        if is_positive and not is_negative:
            recommended_doc = appointment_history.get('recommended_doctor')
            if recommended_doc:
                appointment_history['confirmed_doctor'] = recommended_doc
                appointment_history['awaiting_confirmation'] = False
                # 如果是时间推荐，更新预约时间为推荐时间
                recommended_time = appointment_history.get('recommended_time')
                if recommended_time:
                    from config.time_config import time_config
                    try:
                        if isinstance(recommended_time, str):
                            dt = time_config.parse_datetime(recommended_time) or datetime.fromisoformat(recommended_time)
                        else:
                            dt = recommended_time
                        appointment_history['start_time'] = time_config.format_datetime(dt)
                    except Exception:
                        pass
                return True
        elif is_negative:
            appointment_history['recommendation_declined'] = True
            appointment_history['awaiting_confirmation'] = False
            return True

        return False

    async def handle_unrelated_request(self, user_input: str, unrelated_callback, state) -> AsyncGenerator[str, None]:
        """处理与预约无关的请求"""
        if unrelated_callback:
            try:
                yield "[REPLY][预约机器人]和预约信息无关，已交给归类机器人处理\n"
                result = unrelated_callback(user_input)
                if hasattr(result, '__aiter__'):
                    async for token in result:
                        yield token
                else:
                    yield await result
            except Exception as e:
                yield f"[ERROR]处理请求时发生错误: {str(e)}\n"
                yield self.message_builder.create_unrelated_message()
        else:
            yield self.message_builder.create_unrelated_message()

    async def handle_complete_appointment(self, appointment_history: Dict[str, Any],
                                        session_id: str) -> AsyncGenerator[str, None]:
        """处理预约信息完整的情况"""
        if appointment_history.get('recommendation_declined'):
            reply = self.message_builder.create_recommendation_declined_message(self.llm)
            yield f"[REPLY][预约机器人]{reply}"
            appointment_history.pop('recommendation_declined', None)
            appointment_history.pop('recommended_doctor', None)
            appointment_history.pop('original_doctor', None)
            appointment_history.pop('recommended_time', None)
            return

        if appointment_history.get('confirmed_doctor'):
            doc = appointment_history['confirmed_doctor']
            doc['is_recommendation'] = True
            doc['original_doctor'] = appointment_history.get('original_doctor')
            reply = await self._process_successful_appointment(doc, appointment_history, session_id)
            yield f"[REPLY][预约机器人]{reply}"
            appointment_history.pop('confirmed_doctor', None)
            appointment_history.pop('recommended_doctor', None)
            appointment_history.pop('original_doctor', None)
            appointment_history.pop('recommended_time', None)
            return

        if appointment_history.get('awaiting_confirmation'):
            yield f"[REPLY][预约机器人]\n机器人：请您明确回复\"是\"或\"不\"，我好为您安排预约。\n"
            return

        # 检查该用户是否已有未完成的预约
        if self.conversation_id or self.user_id:
            from services.conversation_memory_service import conversation_memory as cm

            existing_apt = None
            # 优先从DB查询权威预约数据
            if self.user_id:
                existing_apt = self.appointment_database.get_user_active_appointment(self.user_id)
                if existing_apt and existing_apt.get('is_expired'):
                    existing_apt = None

            # DB没查到时再看Redis（仅当前会话内的预约）
            if not existing_apt and self.conversation_id:
                key = f"conversation:{self.conversation_id}:appointment_completed"
                existing_apt = cm._get_json(key)

            if existing_apt is not None:
                # 检查用户是否正在填写新的预约信息（有必填字段了），先取消旧的继续新的
                has_new_info = (
                    (appointment_history.get('start_time') and appointment_history.get('start_time') != '未知')
                    or (appointment_history.get('project') and appointment_history.get('project') != '未知')
                )
                if has_new_info:
                    # 用户直接说了新的预约需求，先告知用户，取消旧的再继续新的
                    doctor_name = existing_apt.get('doctor_name') or existing_apt.get('doctor', '未知医生')
                    apt_time = existing_apt.get('start_time') or existing_apt.get('time', '')
                    time_display = str(apt_time)
                    if apt_time:
                        try:
                            from datetime import datetime as dt
                            if isinstance(apt_time, dt):
                                time_display = apt_time.strftime('%m月%d日 %H:%M')
                            elif isinstance(apt_time, str):
                                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
                                    try:
                                        parsed = dt.strptime(apt_time[:19] if 'T' in apt_time else apt_time[:16], fmt)
                                        time_display = parsed.strftime('%m月%d日 %H:%M')
                                        break
                                    except ValueError:
                                        continue
                        except Exception:
                            pass

                    yield f"[THOUGHT][预约机器人]检测到已有预约（{doctor_name} {time_display}），用户提供了新预约信息，先取消旧预约再继续"
                    yield f"[REPLY][预约机器人]\n机器人：已查询到您当前的预约：{doctor_name}医生 {time_display}。正在为您取消并重新安排新的预约～\n"

                    # 执行取消
                    cancel_ok = False
                    if self.user_id and 'id' in existing_apt:
                        cancel_ok = self.appointment_database.cancel_appointment(
                            existing_apt['id'],
                            existing_apt.get('schedule_id'),
                            str(existing_apt.get('doctor_id', '')),
                            existing_apt.get('start_time'),
                            existing_apt.get('end_time')
                        )
                    elif existing_apt.get('appointment_id') and existing_apt.get('schedule_id'):
                        # Redis数据，尝试用缓存的ID取消
                        cancel_ok = self.appointment_database.cancel_appointment(
                            existing_apt['appointment_id'],
                            existing_apt.get('schedule_id'),
                            str(existing_apt.get('doctor_id', '')),
                            existing_apt.get('start_time'),
                            existing_apt.get('end_time')
                        )

                    self._clear_appointment_memory()
                    if cancel_ok:
                        yield "[THOUGHT][预约机器人]旧预约已取消，继续处理新预约"
                    # 继续走下面的新预约流程
                else:
                    # 没有新信息，告知已有预约并询问需求
                    doctor_name = existing_apt.get('doctor_name') or existing_apt.get('doctor', '未知医生')
                    apt_time = existing_apt.get('start_time') or existing_apt.get('time', '')
                    time_display = str(apt_time)
                    if apt_time:
                        try:
                            from datetime import datetime as dt
                            if isinstance(apt_time, dt):
                                time_display = apt_time.strftime('%m月%d日 %H:%M')
                            elif isinstance(apt_time, str):
                                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"]:
                                    try:
                                        parsed = dt.strptime(apt_time[:19] if 'T' in apt_time else apt_time[:16], fmt)
                                        time_display = parsed.strftime('%m月%d日 %H:%M')
                                        break
                                    except ValueError:
                                        continue
                        except Exception:
                            pass

                    yield "[THOUGHT][预约机器人]检测到该会话已有预约记录，告知用户并询问需求"
                    yield f"[REPLY][预约机器人]\n机器人：查询到您当前有一条预约：{doctor_name}医生 {time_display}。\n请问您需要改期、更换医生，还是取消预约呢？也可以直接告诉我新的预约需求，我会为您处理～\n"
                    if self.conversation_id:
                        cm._set_json(f"conversation:{self.conversation_id}:has_existing_appointment", {'triggered': True})
                    return

        # 检查预约时间是否在营业时间内
        from config.time_config import time_config
        start_time_str = appointment_history.get("start_time", "")
        if start_time_str and start_time_str != "未知":
            dt = time_config.parse_datetime(start_time_str)
            if dt:
                is_valid, msg = time_config.check_time_valid(dt)
                if not is_valid:
                    # 不在营业时间内：清空 start_time 并继续询问，而不是终止流程
                    appointment_history["start_time"] = None
                    yield f"[REPLY][预约机器人]\n机器人：{msg}"
                    return

        thought_msgs = []
        def collect_thoughts(msg):
            thought_msgs.append(msg)

        doc = self.doctor_finder.find_doctor_with_thought(appointment_history, collect_thoughts)

        for msg in thought_msgs:
            yield msg

        doctor_name_val = appointment_history.get("doctor_name")

        if doc:
            if doc.get('requires_confirmation'):
                if doc.get('is_time_recommendation'):
                    # 时间推荐：同科室最近可预约时间
                    recommended_doc = doc['recommended_doctor']
                    recommended_time = doc['recommended_time']
                    original_time = doc['original_time']
                    recommendation_msg = self.message_builder.create_time_recommendation_message(
                        recommended_doc, recommended_time, original_time, self.llm
                    )
                    appointment_history['recommended_time'] = recommended_time.isoformat() if hasattr(recommended_time, 'isoformat') else str(recommended_time)
                else:
                    # 医生推荐：同科室换医生
                    original_doc = doc.get('original_doctor')
                    recommended_doc = doc.get('recommended_doctor')
                    recommendation_msg = self.message_builder.create_doctor_recommendation_message(
                        original_doc, recommended_doc, appointment_history, self.llm
                    )

                yield f"[REPLY][预约机器人]{recommendation_msg}"

                appointment_history['recommended_doctor'] = recommended_doc
                if doc.get('original_doctor'):
                    appointment_history['original_doctor'] = doc['original_doctor']
                appointment_history['awaiting_confirmation'] = True

                yield "[SIGNAL]recommendation_pending"
                return
            else:
                reply = await self._process_successful_appointment(doc, appointment_history, session_id)
                yield f"[REPLY][预约机器人]{reply}"
        else:
            # 找不到医生时：清空 start_time，让用户重新选择时间，而不是终止流程
            appointment_history["start_time"] = None
            reply = self.message_builder.create_appointment_failure_message(doctor_name_val)
            # 修改回复消息，使其更友好并引导用户继续
            if "请选择其他时间或调整偏好。" in reply:
                reply = reply.replace("请选择其他时间或调整偏好。", "请选择其他营业时间（周一至周五 8:00-18:00，周六日 9:00-17:00）或调整科室/性别偏好，告诉我您新的选择。")
            yield f"[REPLY][预约机器人]{reply}"

    async def _process_successful_appointment(self, doc: Dict[str, Any],
                                           appointment_history: Dict[str, Any], session_id: str) -> str:
        """处理预约成功的情况"""
        start_time, end_time, duration_min = self.doctor_finder.parse_time_and_duration(
            appointment_history["start_time"],
            appointment_history["duration"]
        )
        result = self.appointment_database.save_appointment(
            doc["id"], start_time, end_time, appointment_history, session_id,
            user_id=self.user_id, conversation_id=self.conversation_id
        )
        if result:
            appointment_id = result['appointment_id']
            schedule_id = result['schedule_id']
            self.appointment_database.update_memory_schedule(doc["id"], start_time, end_time)
            # 标记该会话已完成预约
            if self.conversation_id:
                from services.conversation_memory_service import conversation_memory as cm
                cm._set_json(f"conversation:{self.conversation_id}:appointment_completed", {
                    "appointment_id": appointment_id,
                    "schedule_id": schedule_id,
                    "doctor": doc["name"],
                    "doctor_id": doc["id"],
                    "start_time": str(start_time),
                    "end_time": str(end_time),
                    "time": str(start_time)
                })
            if self.llm and hasattr(self, 'agent_executor'):
                prompt = f"请为用户生成一段温馨的预约成功提示。医生姓名：{doc['name']}，性别：{doc['gender']}。"
                try:
                    result = await self.agent_executor.ainvoke({"input": prompt})
                    agent_output = result.get("output", "")
                    return f"\n机器人：已为您预约医生：{doc['name']}，性别：{doc['gender']}。预约成功！\n{agent_output}\n"
                except Exception as e:
                    print(f"Agent调用失败: {e}")
                    return self.message_builder.create_appointment_success_message(doc)
            else:
                return self.message_builder.create_appointment_success_message(doc)
        else:
            return self.message_builder.create_save_failure_message()

    async def handle_incomplete_info(self, data: Dict[str, Any], appointment_history: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """处理信息不完整的情况"""
        missing = []
        doctor_name_val = appointment_history.get("doctor_name")

        if not appointment_history.get("start_time") or appointment_history.get("start_time") == "未知":
            missing.append("start_time")
        if not appointment_history.get("project") or appointment_history.get("project") == "未知":
            missing.append("project")

        if not doctor_name_val or doctor_name_val == "未知":
            if not appointment_history.get("gender") or appointment_history.get("gender") == "未知":
                missing.append("gender")

        # 标记预约填写进行中（用于无关请求时判断是否需要询问是否继续）
        appointment_history['appointment_in_progress'] = True

        reply = self.message_builder.create_missing_info_questions(missing)
        yield f"[THOUGHT][预约机器人]用户的预约信息不完整，缺少：{', '.join(missing)}，我需要询问用户补充这些信息"
        yield f"[REPLY][预约机器人]{reply}"

    # ===========================
    # 取消预约流程
    # ===========================

    async def handle_cancel_request(self, user_id: str) -> AsyncGenerator[str, None]:
        """处理用户的取消预约请求（第一步：查询预约并询问确认）"""
        if not user_id:
            yield "[REPLY][预约机器人]\n机器人：抱歉，您尚未登录，无法取消预约。\n"
            return

        appointment = self.appointment_database.get_user_active_appointment(user_id)

        if not appointment:
            yield "[REPLY][预约机器人]\n机器人：您当前没有可取消的预约哦，需要我帮您预约吗？\n"
            return

        if appointment.get('is_expired'):
            yield "[REPLY][预约机器人]\n机器人：该预约时间已过，无法取消。需要帮您预约新的时间吗？\n"
            return

        # 进入待确认状态
        if self.conversation_id:
            from services.conversation_memory_service import conversation_memory as cm
            cm._set_json(f"conversation:{self.conversation_id}:cancel_pending", appointment)

        doctor_name = appointment['doctor_name']
        start_time = appointment['start_time']
        # 格式化时间显示
        if isinstance(start_time, datetime):
            time_str = start_time.strftime('%m月%d日 %H:%M')
            weekday = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][start_time.weekday()]
            time_display = f"{time_str}（{weekday}）"
        else:
            time_display = str(start_time)

        yield f'[REPLY][预约机器人]\n机器人：您当前有一条预约：{doctor_name}医生 {time_display}，' \
              f'确定要取消吗？（请回复"确认取消"或"算了"）\n'

    async def handle_cancel_confirmation(self, user_response: str, user_id: str) -> AsyncGenerator[str, None]:
        """处理用户对取消预约的确认回复"""
        from services.conversation_memory_service import conversation_memory as cm

        positive_keywords = ['确认取消', '确定取消', '取消', '是', '好', '可以', '确认', '确定', '退', 'yes', 'ok']
        negative_keywords = ['算了', '不取消', '不', '不要', '取消吧不对', 'no', '不用']

        is_positive = any(kw in user_response for kw in positive_keywords)
        is_negative = any(kw in user_response for kw in negative_keywords)

        # 清除待确认标记（无论确认还是取消操作都清除）
        pending_key = f"conversation:{self.conversation_id}:cancel_pending" if self.conversation_id else None
        pending_appt = cm._get_json(pending_key) if pending_key else None
        if pending_key:
            try:
                cm._delete(pending_key)
            except Exception:
                pass

        if is_negative and not is_positive:
            yield "[REPLY][预约机器人]\n机器人：好的，预约已为您保留，有其他需要请告诉我。\n"
            return

        if not is_positive:
            # 无法识别，重新设回cancel_pending等待下次回复
            if self.conversation_id and pending_appt:
                from services.conversation_memory_service import conversation_memory as cm
                cm._set_json(f"conversation:{self.conversation_id}:cancel_pending", pending_appt)
            yield '[REPLY][预约机器人]\n机器人：没听清您的意思，如需取消请回复"确认取消"，否则回复"算了"。\n'
            return

        if not user_id:
            yield "[REPLY][预约机器人]\n机器人：抱歉，系统异常，请重新登录后再试。\n"
            return

        # 如果内存里没有待取消预约，从DB重新查
        if not pending_appt:
            pending_appt = self.appointment_database.get_user_active_appointment(user_id)

        if not pending_appt:
            yield "[REPLY][预约机器人]\n机器人：您当前没有可取消的预约。\n"
            yield "[SIGNAL]cancelled"
            return

        if pending_appt.get('is_expired'):
            yield "[REPLY][预约机器人]\n机器人：该预约时间已过，无法取消。\n"
            yield "[SIGNAL]cancelled"
            return

        # 执行取消
        success = self.appointment_database.cancel_appointment(
            appointment_id=pending_appt['id'],
            schedule_id=pending_appt.get('schedule_id'),
            doctor_id=str(pending_appt['doctor_id']),
            start_time=pending_appt['start_time'],
            end_time=pending_appt['end_time']
        )

        if success:
            self._clear_appointment_memory()
            doctor_name = pending_appt['doctor_name']
            start_time = pending_appt['start_time']
            if isinstance(start_time, datetime):
                time_display = start_time.strftime('%m月%d日 %H:%M')
            else:
                time_display = str(start_time)
            yield f'[REPLY][预约机器人]\n机器人：已成功为您取消{doctor_name}医生 {time_display}的预约。' \
                  f'需要我帮您重新预约吗？\n'
            yield "[SIGNAL]cancelled"
        else:
            yield "[REPLY][预约机器人]\n机器人：取消预约时遇到问题，请稍后重试。\n"

    def _clear_appointment_memory(self):
        """取消预约成功后，清理Redis/内存中的预约相关状态"""
        if not self.conversation_id:
            return
        try:
            from services.conversation_memory_service import conversation_memory as cm
            cm._delete(f"conversation:{self.conversation_id}:appointment_completed")
            cm._delete(f"conversation:{self.conversation_id}:appointment_slots")
            cm._delete(f"conversation:{self.conversation_id}:appointment_history")
            cm._delete(f"conversation:{self.conversation_id}:cancel_pending")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"清理预约记忆失败: {e}")
