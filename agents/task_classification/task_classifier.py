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
            '胸痛', '左胸痛', '右胸痛', '心梗', '心脏',
            '呼吸困难', '喘不上气', '窒息', '晕倒', '昏迷',
            '大出血', '严重出血', '失血', '休克',
            '脑中风', '中风', '卒中', '瘫痪',
            '割腕', '自杀', '服毒', '中毒', '吞药',
            '尖锐物扎', '刀砍', '枪伤', '烧伤', '触电',
            '意外', '创伤', '外伤', '骨折', '脱臼'
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

        Returns:
            Optional[str]: 'appointment'/'faq'/'doctor' 或 None（匹配不上）
        """
        task_lower = task.lower()

        # 预约类（优先级最高）
        for keyword in self.appointment_keywords:
            if keyword in task_lower:
                return 'appointment'

        # FAQ/健康咨询类
        for keyword in self.faq_keywords:
            if keyword in task_lower:
                return 'faq'

        # 医生问诊类：用户描述症状（包含痛、疼、不舒服、难受等词）
        symptom_indicators = ['疼', '痛', '不舒服', '难受', '痒', '肿', '麻', '酸', '晕', '吐', '泻', '烧', '热', '冷', '酸']
        for indicator in symptom_indicators:
            if indicator in task_lower:
                return 'doctor'

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
