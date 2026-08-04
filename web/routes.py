"""
Web界面路由

处理前端页面渲染和聊天功能
"""
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from api.chat_handler import ProcessUserInput_stream
from services.auth_service import auth_service
import logging
from typing import Optional

# 创建logger实例
logger = logging.getLogger(__name__)
# 模板配置
templates = Jinja2Templates(directory="web/templates")

# Web路由器
router = APIRouter(tags=["Web界面"])

class ChatRequest(BaseModel):
    message: str
    state: str | None = None
    risk: str | None = None  # 高风险信号：'high' 或 'none'

@router.get("/login", response_class=HTMLResponse, summary="登录页面")
async def login_page(request: Request):
    """渲染登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/", response_class=HTMLResponse, summary="主页")
async def read_root(request: Request):
    """渲染主页聊天界面"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/chat/stream", summary="流式聊天")
async def chat_stream_endpoint(chat: ChatRequest, authorization: Optional[str] = Header(default=None)):
    """处理流式聊天请求"""
    # 验证并提取 token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或 Token 格式错误")

    token = authorization[7:]  # 移除 "Bearer " 前缀
    session = auth_service.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或 Token 已失效")

    async def token_generator():
        try:
            async for token_chunk in ProcessUserInput_stream(
                chat.message,
                token=token,
                state=chat.state,
                user_id=session.get('phone'),  # 用手机号作为 user_id
                conversation_id=session.get('conversation_id'),
                user_info={
                    'phone': session.get('phone'),
                    'user_name': session.get('user_name'),
                    'role': session.get('role'),
                    'created_at': session.get('created_at')
                },
                context={'risk': chat.risk} if chat.risk else None
            ):
                yield token_chunk
        except Exception as exc:
            logger.exception("流式聊天处理失败")
            yield f"[ERROR] {str(exc)}"
    return StreamingResponse(token_generator(), media_type="text/plain")

@router.post("/chat", summary="兼容性聊天接口")
async def chat_endpoint(chat: ChatRequest, authorization: Optional[str] = Header(default=None)):
    """兼容性聊天接口，建议使用/chat/stream"""
    # 验证并提取 token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或 Token 格式错误")

    token = authorization[7:]  # 移除 "Bearer " 前缀
    session = auth_service.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="未登录或 Token 已失效")

    async def token_generator():
        try:
            async for token_chunk in ProcessUserInput_stream(
                chat.message,
                token=token,
                state=chat.state,
                user_id=session.get('phone'),
                conversation_id=session.get('conversation_id'),
                user_info={
                    'phone': session.get('phone'),
                    'user_name': session.get('user_name'),
                    'role': session.get('role'),
                    'created_at': session.get('created_at')
                }
            ):
                yield token_chunk
        except Exception as exc:
            logger.exception("兼容聊天接口流式处理失败")
            yield f"[ERROR] {str(exc)}"
    return StreamingResponse(token_generator(), media_type="text/plain")

@router.get("/knowledge", response_class=HTMLResponse, summary="知识库管理页面")
async def knowledge_page(request: Request):
    """知识库管理页面"""
    # 通过API层获取知识库数据
    try:
        from api.knowledge import get_all_knowledge
        
        # 调用API层函数获取数据
        knowledge_data = await get_all_knowledge()
        documents = knowledge_data.get("documents", [])
        categories = knowledge_data.get("categories", [])
        
        return templates.TemplateResponse("knowledge_management.html", {
            "request": request,
            "documents": documents,
            "categories": categories
        })
    except Exception as e:
        return templates.TemplateResponse("knowledge_management.html", {
            "request": request,
            "documents": [],
            "categories": [],
            "error": str(e)
        })

@router.get("/technician", response_class=HTMLResponse, summary="医生状态页面")
async def technician_page(request: Request):
    """医生状态页面"""
    # 通过API层获取医生数据
    try:
        from api.technician import get_all_technicians
        
        # 调用API层函数获取数据
        technicians = await get_all_technicians()
        
        return templates.TemplateResponse("technician.html", {
            "request": request,
            "doctors": technicians
        })
    except Exception as e:
        return templates.TemplateResponse("technician.html", {
            "request": request,
            "doctors": [],
            "error": str(e)
        })

@router.get("/technician_schedule", response_class=HTMLResponse, summary="医生值班页面")
async def technician_schedule_page(request: Request):
    """医生值班页面"""
    try:
        from api.technician import get_all_technicians_schedule_today
        from config.time_config import time_config
        
        # 获取当前日期
        current_date = time_config.current_date_str()
        
        # 通过API层获取所有医生的值班数据
        schedules_data = await get_all_technicians_schedule_today()
        
        # 构建排班数据格式 - 直接使用API返回的数据
        schedule = []
        for schedule_item in schedules_data:
            schedule.append({
                "id": schedule_item.get("doctor_id", schedule_item.get("technician_id")),
                "name": schedule_item.get("doctor_name", schedule_item.get("technician_name")),
                "busy_periods": schedule_item.get("busy_periods", [])
            })
        
        return templates.TemplateResponse("technician_schedule.html", {
            "request": request,
            "schedule": schedule,
            "current_date": current_date
        })
    except Exception as e:
        logger.error(f"加载医生排班数据失败: {str(e)}")
        return templates.TemplateResponse("technician_schedule.html", {
            "request": request,
            "schedule": [],
            "error": str(e)
        })

@router.get("/admin", response_class=HTMLResponse, summary="系统管理页面")
async def admin_dashboard(request: Request):
    """系统管理仪表板"""
    try:
        # 通过API层获取系统状态信息
        from api.knowledge import get_all_knowledge
        from api.technician import get_all_technicians
        
        # 获取知识库数据
        knowledge_data = await get_all_knowledge()
        knowledge_count = knowledge_data.get("total_count", 0)
        categories = knowledge_data.get("categories", [])
        
        # 获取医生数据
        doctors = await get_all_technicians()

        # 数据库信息
        db_info = {
            "knowledge_count": knowledge_count,
            "categories_count": len(categories),
            "doctors_count": len(doctors),
            "categories": categories
        }

        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "db_info": db_info,
            "doctors": doctors[:5]  # 只显示前5个医生
        })
    except Exception as e:
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "db_info": {},
            "doctors": [],
            "error": str(e)
        })

@router.get("/admin/database", response_class=HTMLResponse, summary="数据库管理页面")
async def database_admin_page(request: Request):
    """数据库管理页面"""
    try:
        # 通过API层获取数据库统计信息
        from api.knowledge import get_all_knowledge
        from api.technician import get_all_technicians
        
        # 获取知识库数据
        knowledge_data = await get_all_knowledge()
        
        # 获取医生数据
        doctors_data = await get_all_technicians()

        stats = {
            "knowledge_documents": knowledge_data.get("total_count", 0),
            "categories": len(knowledge_data.get("categories", [])),
            "doctors": len(doctors_data),
            "appointments": 0  # TODO: 通过API获取预约数量
        }
        
        return templates.TemplateResponse("database_admin.html", {
            "request": request,
            "stats": stats
        })
    except Exception as e:
        return templates.TemplateResponse("database_admin.html", {
            "request": request,
            "stats": {},
            "error": str(e)
        })
