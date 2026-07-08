"""
校园医务室 API 模块 - 医学化版本

包含所有医学相关的 API 路由：
- 身份认证
- 医学分类
- 医务室预约
- 健康知识咨询
- 医生值班表
- 问诊记录与健康追踪
"""

# 【第一层】导入所有业务模块的路由
from .auth import router as auth_router

# 医学相关 API
from .task import router as task_router  # 医学分类
from .appointment import router as appointment_router  # 医务室预约
from .consultation import router as consultation_router  # 健康知识咨询
from .technician import router as technician_router  # 医生值班表

# 保留向后兼容的旧路由（如果还有其他模块使用）
try:
    from .knowledge import router as knowledge_router
except ImportError:
    knowledge_router = None

# 【第二层】创建医学化后的 API 路由列表
medical_api_routers = [
    # 基础认证
    auth_router,
    
    # 医学分类与路由
    task_router,  # /api/medical/classify
    
    # 医务室预约
    appointment_router,  # /api/medical/appointments
    
    # 健康知识
    consultation_router,  # /api/medical/health-inquiries
    
    # 医生值班
    technician_router,  # /api/medical/doctor-schedules
    
]

# 【第三层】完整的 API 路由列表（包括向后兼容）
api_routers = medical_api_routers

# 如果还有 knowledge 路由，添加它
if knowledge_router:
    api_routers.append(knowledge_router)

# 【调试】API 路由摘要
def list_api_routes():
    """打印所有已注册的 API 路由（用于调试）"""
    print("\n" + "="*60)
    print("校园医务室 API 路由摘要")
    print("="*60)
    print("\n✅ 已注册的医学 API 路由:")
    print("  • POST  /api/medical/classify          - 医学任务分类")
    print("  • POST  /api/medical/appointments      - 创建医务室预约")
    print("  • GET   /api/medical/doctors           - 列表所有医生")
    print("  • GET   /api/medical/doctor-schedules  - 医生值班表")
    print("  • POST  /api/medical/health-inquiries  - 健康知识咨询")
    print("  • GET   /api/medical/health-reminders  - 个性化健康提醒")
    print("\n✅ 已注册的认证 API 路由:")
    print("  • POST  /api/auth/login                - 用户登录")
    print("  • POST  /api/auth/logout               - 退出登录")
    print("  • POST  /api/auth/verify-code          - 验证码验证")
    print("\n" + "="*60 + "\n")


__all__ = [
    "api_routers",
    "medical_api_routers",
    "list_api_routes",
    # 各路由
    "auth_router",
    "task_router",
    "appointment_router",
    "consultation_router",
    "technician_router",
]
