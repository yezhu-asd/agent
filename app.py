"""
校园医务室 AI Agent 应用程序 - FastAPI 主入口

系统架构：
1. 认证层：Token 登录、会话管理
2. API 层：医学分类、预约、咨询等 REST 端点
3. Agent 层：3 个主要 Agent（分类、预约、咨询）
4. 服务层：认证、预约、知识检索等服务
5. 数据层：MySQL/SQLite + Redis 状态管理

本应用提供：
- 医学任务分类与智能路由
- 医务室预约与医生排班
- 健康知识咨询（RAG）
- 多用户会话隔离
- Token 认证与权限管理
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging
import asyncio

# 导入路由
from api import api_routers, list_api_routes
from api.core.exceptions import api_exception_handler, general_exception_handler, BusinessException
from web import router as web_router

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 可选服务（失败不影响启动）
try:
    from services.knowledge_service import KnowledgeService
except Exception as exc:
    KnowledgeService = None
    logger.warning("❌ 知识库服务不可用: %s", exc)

try:
    from services.recommendation_service import RecommendationService
except Exception as exc:
    RecommendationService = None
    logger.warning("❌ 推荐服务不可用: %s", exc)


async def initialize_medical_system():
    """
    校园医务室系统启动初始化
    
    初始化流程：
    1. 验证 Token & 认证系统
    2. 加载医学分类模型
    3. 初始化医务室数据（医生、预约）
    4. 启动推荐和提醒调度
    """
    
    try:
        logger.info("\n" + "="*60)
        logger.info("🏥 校园医务室 AI Agent 系统启动")
        logger.info("="*60 + "\n")
        
        # 【步骤 1】验证认证系统
        logger.info("🔐 [步骤 1/4] 初始化认证系统...")
        try:
            from services.auth_service import auth_service
            logger.info("✅ 认证系统就绪")
        except Exception as e:
            logger.error(f"❌ 认证系统初始化失败: {e}")
            raise
        
        # 【步骤 2】加载医学分类模型
        logger.info("🏷️ [步骤 2/4] 加载医学分类模型...")
        try:
            from config.model_provider import create_chat_model
            llm = create_chat_model()
            logger.info("✅ 医学分类模型加载成功")
        except Exception as e:
            logger.warning(f"⚠️ 医学分类模型加载失败（可能需要配置 LLM）: {e}")
        
        # 【步骤 3】初始化医务室数据
        logger.info("📋 [步骤 3/4] 初始化医务室数据...")
        try:
            # 验证医生数据
            from api.appointment import MOCK_DOCTORS
            logger.info(f"✅ 已加载 {len(MOCK_DOCTORS)} 名医生信息")
            
            # 验证状态存储
            from config.constants import get_state_storage
            state_storage = get_state_storage()
            logger.info(f"✅ 状态存储就绪 ({type(state_storage).__name__})")
        except Exception as e:
            logger.warning(f"⚠️ 医务室数据初始化失败: {e}")
        
        # 【步骤 4】启动推荐和提醒服务
        logger.info("🎯 [步骤 4/4] 启动推荐和提醒服务...")
        if RecommendationService is not None:
            try:
                recommendation_service = RecommendationService()
                if recommendation_service.start_scheduler():
                    logger.info("✅ 推荐调度服务已启动")
                else:
                    logger.warning("⚠️ 推荐调度服务启动失败")
            except Exception as e:
                logger.warning(f"⚠️ 推荐服务初始化失败: {e}")
        else:
            logger.info("⏭️ 推荐服务跳过初始化")
        
        # 【启动完成】打印 API 路由信息
        logger.info("📚 [API 路由] 已注册的端点:")
        list_api_routes()
        
        logger.info("✅ 系统启动完成！所有医学 API 已就绪。\n")
        logger.info("📖 访问 API 文档: http://127.0.0.1:8001/docs")
        logger.info("📖 访问 ReDoc: http://127.0.0.1:8001/redoc\n")
        
    except Exception as e:
        logger.error(f"\n❌ 系统启动失败: {e}\n", exc_info=True)
        raise


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例
    
    配置：
    1. 应用元数据（标题、描述、版本）
    2. 中间件（CORS、异常处理）
    3. 路由注册（API、Web、静态文件）
    4. 启动/关闭事件
    """
    
    # 【应用元数据】
    app = FastAPI(
        title="🏥 校园医务室 AI Agent",
        description=(
            "智能医学咨询与预约系统\n\n"
            "核心功能：\n"
            "• 医学任务自动分类与智能路由\n"
            "• 智能医务室预约与排班管理\n"
            "• RAG 健康知识咨询\n"
            "• 问诊记录与健康追踪\n"
            "• 多用户会话隔离（Token 认证）\n"
            "• 紧急症状识别与升级"
        ),
        version="2.0.0-medical",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=[
            {
                "name": "医学分类",
                "description": "医学任务分类 - 5 类分类（医生/预约/咨询/紧急/闲聊）"
            },
            {
                "name": "医务室预约",
                "description": "预约管理 - 预约创建、医生选择、时间管理"
            },
            {
                "name": "健康知识",
                "description": "健康咨询 - RAG 知识问答、预防养生"
            },
            {
                "name": "医生值班",
                "description": "医生管理 - 值班表、医生信息、可用性"
            },
        ]
    )

    # 【CORS 中间件】- 支持跨域请求
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应改为具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 【异常处理】
    app.add_exception_handler(BusinessException, api_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # 【注册 API 路由】- 所有医学 API
    for router in api_routers:
        app.include_router(router)

    # 【注册 Web 路由】- 前端页面
    app.include_router(web_router)

    # 【静态文件】- JS、CSS、图片等
    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    # 【启动事件】
    @app.on_event("startup")
    async def startup_event():
        """应用启动时运行的初始化"""
        await initialize_medical_system()

    # 【健康检查端点】
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        """系统健康检查"""
        return {
            "status": "healthy",
            "service": "Campus Medical AI Agent",
            "version": "2.0.0-medical"
        }

    return app


# 创建全局应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    # 启动服务器
    logger.info("🚀 启动校园医务室 AI Agent 服务器...\n")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        log_level="info"
    )
