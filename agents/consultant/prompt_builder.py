"""
提示词构建器

负责构建各种类型的提示词
"""

from typing import List, Dict, Any
#单独用分类 prompt，是为了先把“是不是咨询”这件事判断清楚，再交给回答模型去生成内容，避免两个任务混在一起。
#只输出 YES 或 NO，这样结果更稳定，不容易跑偏。
class PromptBuilder:
    """提示词构建器"""
    
    def __init__(self):
        self.system_prompt = self._create_system_prompt()
        self.classification_prompt_template = self._create_classification_prompt_template()
    
    def _create_system_prompt(self) -> str:
        """创建系统提示词"""
        return (
            "你是校园医务室的医疗咨询助手，负责为学生解答关于健康、医学知识等相关问题。"
            "我会为你提供相关的知识库信息，请基于这些信息来回答用户的问题。"
            "如果知识库中没有相关信息，请提供合理的兜底回答，比如："
            "- 对于专业医学问题：建议您到医务室进行专业咨询和检查。"
            "- 对于其他缺失信息：请您直接到医务室咨询医护人员。"
            "请用专业、礼貌、简洁的语言回复用户。"
            "回答时要自然流畅，不要明显地表现出是在查阅资料。"
        )
    
    def _create_classification_prompt_template(self) -> str:
        """创建分类提示词模板"""
        return (
            "你是一个分类器，判断用户输入是否是关于患者本人的医学症状描述或问诊相关的内容。\n"
            "问诊类问题包括：\n"
            "  - 描述自己的症状（如：我肚子疼、我发烧了、我头晕）\n"
            "  - 询问自己症状的处理方法（如：我这个症状怎么办、应该吃什么药）\n"
            "  - 症状补充或追问（如：医生怎样才能缓解）\n"
            "  - 基于自身症状的医学咨询\n"
            "非问诊类问题包括：\n"
            "  - 健康知识问答（如：怎样预防感冒、维生素有什么作用）\n"
            "  - 一般医学教育（如：什么是糖尿病、感冒的症状有哪些）\n"
            "  - 预约服务（我要预约、帮我安排等）\n"
            "  - 闲聊或完全无关话题（如：天气、股票、新闻）\n"
            "\n如果是问诊类问题（患者描述自己的症状），回答'YES'。\n"
            "如果是非问诊类（健康知识、一般咨询等），回答'NO'。\n"
            "只回答YES或NO。\n\n"
            "用户输入：{user_input}"
        )
    
    def build_consultation_prompt(self, user_input: str, knowledge_docs: List[Dict[str, Any]]) -> str:
        """构建咨询提示词"""
        context = self._build_knowledge_context(knowledge_docs)
        return f"{self.system_prompt}\n\n{context}\n用户问题：{user_input}\n\n请回答用户的问题。"
    
    def build_classification_prompt(self, user_input: str) -> str:
        """构建分类提示词"""
        return self.classification_prompt_template.format(user_input=user_input)
    
    def _build_knowledge_context(self, knowledge_docs: List[Dict[str, Any]]) -> str:
        """构建知识库上下文"""
        if not knowledge_docs:
            return "没有找到直接相关的知识库信息，请基于你对推拿服务的专业知识回答。"
        
        context = "\n以下是相关的知识库信息：\n"
        for i, doc in enumerate(knowledge_docs, 1):
            context += f"{i}. {doc['content']}\n"
        context += "\n请基于以上信息回答用户问题。如果知识库信息不足以回答问题，请基于你对推拿服务的一般了解来补充回答。\n"
        
        return context
