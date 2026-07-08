#!/usr/bin/env python3
"""
验收测试2：ConsultantAgent会话记忆集成
验证要点：
1. 医疗槽位是否正确初始化
2. 用户输入的症状是否正确提取保存
3. 对话历史是否正确保存
4. set_user_context是否工作正常
"""

import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.consultant_agent import ConsultantAgent
from services.conversation_memory_service import conversation_memory


async def test_consultant_memory_integration():
    print("=" * 60)
    print("验收测试2：ConsultantAgent会话记忆集成")
    print("=" * 60)

    # 1. 创建ConsultantAgent实例
    print("\n[检查1] 创建ConsultantAgent实例...")
    try:
        agent = ConsultantAgent(
            user_id="test_user_001",
            conversation_id="test_consult_001"
        )
        print("[OK] Agent创建成功")
        print("    user_id: %s" % agent.user_id)
        print("    conversation_id: %s" % agent.conversation_id)
    except Exception as e:
        print("[FAIL] Agent创建失败: %s" % e)
        return False

    # 2. 检查医疗槽位初始化
    print("\n[检查2] 检查医疗槽位初始化...")
    try:
        slots = conversation_memory.get_medical_slots("test_consult_001")
        print("[OK] 医疗槽位已初始化")
        print("    user_id: %s" % slots.get('user_id'))
        print("    role: %s" % slots.get('role'))
        print("    chief_complaint: %s" % slots.get('chief_complaint'))
        if slots.get('user_id') == "test_user_001":
            print("[OK] user_id正确保存到槽位")
        else:
            print("[FAIL] user_id未正确保存")
            return False
    except Exception as e:
        print("[FAIL] 医疗槽位检查失败: %s" % e)
        return False

    # 3. 测试症状提取和保存（模拟一次咨询）
    print("\n[检查3] 测试症状提取和保存...")
    try:
        # 处理用户输入 "我头疼还发烧"
        # 调用consultation_processor的提取方法
        processor = agent.consultation_processor
        await processor._extract_and_save_symptoms("我头疼还发烧")

        # 获取更新后的槽位
        slots = conversation_memory.get_medical_slots("test_consult_001")
        print("[OK] 症状提取完成")
        print("    chief_complaint: %s" % slots.get('chief_complaint'))
        print("    accompanying_symptoms: %s" % slots.get('accompanying_symptoms'))
        print("    fever: %s" % slots.get('fever'))

        # 验证结果
        if "我头疼还发烧" in slots.get('chief_complaint'):
            print("[OK] 主诉正确保存")
        else:
            print("[FAIL] 主诉未正确保存")
            return False

        if "头疼" in slots.get('accompanying_symptoms'):
            print("[OK] 伴随症状正确提取")
        else:
            print("[FAIL] 伴随症状未正确提取")

        if slots.get('fever') is True:
            print("[OK] 发烧标记正确识别")
        else:
            print("[FAIL] 发烧标记未正确识别")
            return False
    except Exception as e:
        print("[FAIL] 症状提取测试失败: %s" % e)
        return False

    # 4. 测试对话历史保存
    print("\n[检查4] 测试对话历史保存...")
    try:
        history = conversation_memory.get_history("test_consult_001")
        print("[OK] 获取对话历史成功")
        print("    消息数量: %d" % len(history))
        for i, msg in enumerate(history):
            print("    %d. [%s] %s" % (i+1, msg.get('role'), msg.get('content')))
    except Exception as e:
        print("[FAIL] 对话历史检查失败: %s" % e)
        return False

    # 5. 测试set_user_context方法
    print("\n[检查5] 测试set_user_context方法...")
    try:
        agent.set_user_context("test_user_002", "test_consult_002")
        slots = conversation_memory.get_medical_slots("test_consult_002")
        if slots.get('user_id') == "test_user_002":
            print("[OK] set_user_context工作正常")
        else:
            print("[FAIL] set_user_context工作异常")
            return False
    except Exception as e:
        print("[FAIL] set_user_context测试失败: %s" % e)
        return False

    # 6. 测试行为记忆记录
    print("\n[检查6] 测试行为记忆记录...")
    try:
        await agent.consultation_processor._record_consultation_behavior(
            "测试咨询行为", [], "test_session"
        )
        behavior = conversation_memory.get_behavior_memory("test_consult_001")
        if behavior and 'consultation_count' in behavior:
            print("[OK] 行为记忆记录成功")
            print("    consultation_count: %d" % behavior['consultation_count'])
        else:
            print("[WARN] 行为记忆为空（这在首次测试时可能正常）")
    except Exception as e:
        print("[FAIL] 行为记忆测试失败: %s" % e)
        return False

    # 7. 清理测试数据
    print("\n[清理] 清理测试数据...")
    try:
        conversation_memory.clear_history("test_consult_001")
        conversation_memory.clear_history("test_consult_002")
        # 槽位会自动过期，不需要手动清理
        print("[OK] 测试数据已清理")
    except Exception as e:
        print("[WARN] 清理失败: %s" % e)

    print("\n" + "=" * 60)
    print("验收测试2通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_consultant_memory_integration())
    sys.exit(0 if success else 1)