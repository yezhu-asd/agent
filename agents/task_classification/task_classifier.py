"""
任务分类器 - 专门负责判断用户医学咨询请求的类型 (校园医务室版本)

职责：
1. 接收用户输入，分析其医学咨询意图
2. 根据预定义的分类规则，将任务归类为：
   - doctor（医生问诊/症状评估）
   - appointment（校园医务室预约）  
   - faq（健康知识问答）
   - emergency（紧急升级 - 红旗症状）
   - chat（闲聊/一般咨询）
3. 提供清晰的分类结果和置信度
4. 识别潜在的医学紧急情况
"""

import logging
from langchain.prompts import PromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class TaskClassifier:
    """医学咨询任务分类器 - 关键词优先，LLM兜底"""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm
        self._initialize_prompt()
        self.chain = self.prompt | self.llm

        # 定义红旗症状关键词（需要紧急升级）
        self.red_flag_keywords = {
            '胸痛', '左胸痛', '右胸痛', '心梗', '心脏', '心绞痛',
            '呼吸困难', '喘不上气', '窒息', '晕倒', '昏迷', '失去知觉', '失去意识',
            '大出血', '严重出血', '失血', '休克', '持续出血', '流血不止',
            '吐血', '咳血', '便血', '尿血', '大便出血',
            '脑中风', '中风', '卒中', '瘫痪',
            '割腕', '自杀', '服毒', '中毒', '吞药', '药物中毒',
            '尖锐物扎', '刀砍', '枪伤', '烧伤', '大面积烧伤', '触电',
            '意外', '创伤', '外伤', '骨折', '脱臼',
            '剧烈头痛', '头炸裂', '头痛欲裂', '胸骨剧痛', '胸骨痛',
            '持续高烧', '烧到40度', '39度以上', '高烧不退', '体温40度', '体温39度',
            '腹部剧痛', '急性腹痛', '严重腹痛',
            '过敏性休克', '严重过敏'
        }

        # 预约关键词
        self.appointment_keywords = {
            '预约', '挂号', '约号', '挂号费', '退号', '取消预约',
            '改约', '改期', '改时间', '换个时间', '换时间', '重新预约', '重新约',
            '修改预约', '调整预约', '换个医生', '改预约', '换预约', '变更预约',
            '哪个医生有时间', '有号吗', '约满', '没号', '加号', '预约成功', '预约失败',
            '就诊', '看病', '看医生', '校医'
        }

        # 健康咨询/FAQ关键词
        self.faq_keywords = {
            '怎么预防', '怎么办', '怎么处理', '需要多久',
            '能吃吗', '注意事项', '正常吗', '严重吗',
            '什么是', '怎么治', '如何治疗', '病因',
            '症状', '感冒', '发烧', '中暑', '过敏',
            '健康', '医学', '知识'
        }
    
    def _initialize_prompt(self):
        """初始化分类提示词模板（医学咨询版本）"""
        self.prompt = PromptTemplate(
            input_variables=["task"],
            template=(
                "你是校园医务室的智能分诊助手。你需要对用户的医学咨询请求进行分类。\n\n"
                "分类规则：\n"
                "1. doctor（医生问诊）- 用户报告症状或身体不适，需要医生评估\n"
                "   例子：\"我胸口疼\"、\"最近一直感冒\"、\"脚扭伤了怎么办\"\n\n"
                "2. appointment（预约挂号）- 用户预约、取消预约、改期、查询预约等挂号相关操作\n"
                "   例子：\"我想预约医生\"、\"今天能挂号吗\"、\"哪个医生有时间\"、\"帮我取消预约\"、\"我要退号\"、\"我要改期\"、\"不想去了\"、\"换个时间\"\n\n"
                "3. faq（健康咨询）- 用户询问健康知识而非个人症状\n"
                "   例子：\"感冒应该怎么预防\"、\"骨折了需要多久恢复\"、\"创可贴怎么用\"\n\n"
                "4. emergency（紧急）- 用户提到危急症状，需要立即上报\n"
                "   例子：\"胸痛\"、\"呼吸困难\"、\"我昏迷了\"、\"大出血\"\n\n"
                "5. chat（闲聊）- 与医学无关或不相关的聊天\n"
                "   例子：\"你好\"、\"今天天气真好\"、\"食堂在哪里\"\n\n"
                "请只回复以下分类之一（全小写）：\n"
                "doctor / appointment / faq / emergency / chat\n\n"
                "用户请求：{task}"
            )
        )
    
    async def classify_task(self, task: str) -> str:
        """
        分类医学咨询任务 - 关键词优先，LLM兜底

        Args:
            task: 用户输入的任务内容

        Returns:
            str: 分类结果 ('doctor', 'appointment', 'faq', 'emergency', 'chat')
        """
        try:
            # 首先检查是否是紧急症状（快速路径）
            if self._is_emergency(task):
                logger.warning(f"[关键词匹配] 检测到紧急症状: {task}")
                return 'emergency'

            # 二级识别 1: 关键词匹配
            keyword_category = self._classify_by_keywords(task)
            if keyword_category:
                logger.info(f"[关键词匹配] {task[:30]}... -> {keyword_category}")
                return keyword_category

            # 二级识别 2: LLM分类（关键词匹配不上时使用）
            logger.debug(f"[关键词匹配] 未命中，调用LLM分类: {task[:30]}...")
            category_msg = await self.chain.ainvoke({"task": task})
            category = category_msg.content.strip().lower()

            # 验证分类结果是否有效
            valid_categories = {'doctor', 'appointment', 'faq', 'emergency', 'chat'}
            if category not in valid_categories:
                logger.debug(f"无效分类结果: {category}，返回 chat")
                return 'chat'  # 默认归类为闲聊

            logger.debug(f"[LLM分类] {task[:30]}... -> {category}")
            return category

        except Exception as e:
            logger.error(f"任务分类失败: {str(e)}")
            raise  # 分类失败时向上传播异常，避免将不确定的分类误判为'chat'

    def _classify_by_keywords(self, task: str) -> Optional[str]:
        """
        基于关键词快速分类

        优先级：appointment > doctor(症状描述) > faq > chat

        Returns:
            Optional[str]: 'appointment'/'doctor'/'faq'/'chat' 或 None（匹配不上走LLM）
        """
        task_lower = task.lower()

        # 预约类（最高优先级）
        for keyword in self.appointment_keywords:
            if keyword in task_lower:
                return 'appointment'

        # 医生问诊类：用户描述自身症状（优先级高于FAQ，
        # 因为"我咳嗽/发烧/疼"是报告个人症状，比"健康知识咨询"更紧急）
        # 第一人称症状（"我"+ 症状词）
        first_person = ['我', '本人']
        has_first_person = any(p in task_lower for p in first_person)
        # 症状指示词（涵盖生理症状 + 情绪/饮食/作息）
        symptom_indicators = [
            '疼', '痛', '不舒服', '难受', '痒', '肿', '麻', '酸', '晕', '吐', '泻', '烧', '热',
            '咳', '痰', '喘', '失眠', '睡不着', '乏力', '没精神', '过敏', '红疹', '出血', '发炎',
            '情绪', '心情', '焦虑', '抑郁', '压力', '紧张',
            '吃', '辣', '凉', '胃', '肚子', '头痛', '头晕', '恶心'
        ]
        # 明确症状程度/时间修饰（说明是已发生的具体症状，而非泛泛健康知识）
        # 注意：不要用"了"（太宽泛，"感冒了"也是泛指），只用强程度/时长词
        severity_markers = ['厉害', '严重', '一直', '反复', '特别', '很疼', '很痛', '两个月', '很久', '好多天', '不断', '整天', '每天晚上', '睡不着觉']
        for indicator in symptom_indicators:
            if indicator in task_lower:
                # 第一人称 + 症状词 → 明确是 doctor
                if has_first_person:
                    return 'doctor'
                # 非疑问句式 → 症状描述 → doctor
                is_query_style = any(q in task_lower for q in [
                    '怎么办', '怎么预防', '怎么治', '能吃吗', '怎么处理', '有什么危害',
                    '要注意什么', '能喝吗', '能恢复吗', '怎么调理', '怎么退烧',
                    '怎么缓解', '怎么回事', '为什么', '是什么原因'
                ])
                if not is_query_style:
                    return 'doctor'
                # 疑问句式 + 强程度/时长修饰 → 已发生的具体症状 → doctor
                # （如"咳嗽两个月了怎么办"，区别于"感冒怎么预防"）
                if is_query_style and any(s in task_lower for s in severity_markers):
                    return 'doctor'
                # 纯疑问句式 + 无强修饰（如"感冒能喝枸杞茶吗"）→ 落到 FAQ
                break

        # FAQ/健康咨询类
        for keyword in self.faq_keywords:
            if keyword in task_lower:
                return 'faq'

        # 关键词匹配不上
        return None
    
    def _is_emergency(self, task: str) -> bool:
        """检查是否包含红旗症状关键词"""
        task_lower = task.lower()
        for keyword in self.red_flag_keywords:
            if keyword in task_lower:
                return True
        return False
    
    def get_category_description(self, category: str) -> str:
        """获取分类类别的描述信息"""
        descriptions = {
            'doctor': '医生问诊 - 用户报告症状需要医生评估',
            'appointment': '预约挂号 - 用户预约看医生',
            'faq': '健康咨询 - 用户询问医学知识',
            'emergency': '紧急处理 - 检测到危急症状，需要立即处理',
            'chat': '闲聊/无关 - 与医学无关的请求'
        }
        return descriptions.get(category, '未知任务类型')
