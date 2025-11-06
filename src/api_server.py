"""智能天气助手 FastAPI 服务器"""

import logging
import sys
import os
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from main import DialogueService
from auth import verify_api_key, APIKeyConfig
from concurrency_limiter import get_limiter, ConcurrencyLimiter
from cache_manager import get_cache_manager, RedisCacheManager
from session_manager import SessionManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

dialogue_service: Optional[DialogueService] = None
limiter: Optional[ConcurrencyLimiter] = None
cache_manager: Optional[RedisCacheManager] = None
session_manager: Optional[SessionManager] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID（可选，不传则自动生成新会话）")
    chat_history: Optional[List[List[str]]] = Field(None, description="手动传递的历史记录（可选，优先使用服务端会话管理）")


class ChatResponse(BaseModel):
    response: str = Field(..., description="AI 回复")
    session_id: str = Field(..., description="会话 ID")
    status: str = Field(default="success", description="响应状态")
    history_turns: int = Field(default=0, description="当前会话历史轮数")


class HealthResponse(BaseModel):
    status: str
    service_name: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dialogue_service, limiter, cache_manager, session_manager

    logger.info("🚀 启动服务...")
    try:
        dialogue_service = DialogueService()
        limiter = get_limiter(max_concurrency=5)
        cache_manager = get_cache_manager(default_ttl=1800)
        session_manager = SessionManager(cache_manager=cache_manager, max_history_turns=5, session_ttl=3600)
        logger.info("✅ 服务启动完成")
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        raise

    yield
    logger.info("👋 服务关闭...")


app = FastAPI(
    title="智能天气助手 API",
    description="基于 LangChain Agent 的智能天气查询服务",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "服务器内部错误"}
    )


@app.get("/")
async def root():
    return {
        "service": "智能天气助手 API",
        "version": "2.0.0",
        "endpoints": {
            "health": "/Fang-GetWeather/health",
            "chat": "/Fang-GetWeather/chat",
            "status": "/Fang-GetWeather/status",
            "session_info": "/Fang-GetWeather/session/{session_id}",
            "clear_session": "/Fang-GetWeather/session/{session_id} (DELETE)",
            "list_sessions": "/Fang-GetWeather/sessions",
            "docs": "/docs"
        }
    }


@app.get("/Fang-GetWeather/health", response_model=HealthResponse)
async def health_check():
    if dialogue_service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="服务未就绪")
    return HealthResponse(status="healthy", service_name="智能天气助手", version="2.0.0")


@app.get("/Fang-GetWeather/status")
async def get_status():
    status_info = {
        "service": "智能天气助手",
        "version": "2.0.0",
        "status": "healthy"
    }

    if limiter:
        status_info["concurrency"] = await limiter.get_status()

    if cache_manager:
        status_info["cache"] = cache_manager.get_stats()

    if session_manager:
        status_info["session"] = session_manager.get_stats()

    return status_info


@app.post("/Fang-GetWeather/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    api_config: APIKeyConfig = Depends(verify_api_key)
):
    """对话接口 - 支持认证、限流、缓存、会话管理"""
    if dialogue_service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="服务未初始化")

    # 1. 会话 ID 处理
    session_id = request.session_id
    if not session_id:
        if session_manager and session_manager.enabled:
            session_id = session_manager.generate_session_id()
            logger.info(f"🆔 生成新会话: {session_id}")
        else:
            session_id = "default"  # 会话管理器未启用时的兜底

    # 2. 加载会话历史（优先使用服务端管理的历史）
    chat_history = None
    if session_manager and session_manager.enabled:
        chat_history = session_manager.get_history(session_id)
        logger.info(f"📖 加载会话历史: {session_id} ({len(chat_history)} 轮)")
    elif request.chat_history:
        # 兜底：使用客户端传递的历史
        chat_history = [tuple(pair) for pair in request.chat_history]
        logger.debug(f"📝 使用客户端历史: {len(chat_history)} 轮")

    # 3. 尝试从天气缓存获取
    if cache_manager and cache_manager.enabled:
        cached_response = cache_manager.get(request.message)
        if cached_response:
            logger.info(f"💾 缓存命中: {request.message[:30]}...")
            # 即使缓存命中，也要保存这轮对话到会话历史
            if session_manager and session_manager.enabled:
                session_manager.append_turn(session_id, request.message, cached_response)
            return ChatResponse(
                response=cached_response,
                session_id=session_id,
                status="success_cached",
                history_turns=len(chat_history) + 1 if chat_history else 1
            )

    # 4. 并发限流
    if limiter is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="限流器未初始化")

    try:
        async with limiter.acquire(timeout=30.0):
            logger.info(f"🔑 请求 (Key: {api_config.api_key[:10]}..., Session: {session_id[:8]}...): {request.message}")

            # 5. 创建对话服务并运行
            user_dialogue_service = DialogueService(api_key=api_config.api_key)
            ai_response = user_dialogue_service.run_conversation(
                user_input=request.message,
                chat_history=chat_history
            )

            logger.info(f"✅ 回复: {ai_response[:50]}...")

            # 6. 保存到天气缓存（如果是天气查询）
            if cache_manager and cache_manager.enabled:
                weather_keywords = ["天气", "气温", "温度", "下雨", "晴", "阴", "雪"]
                if any(kw in request.message for kw in weather_keywords):
                    cache_manager.set(request.message, ai_response)

            # 7. 保存到会话历史
            if session_manager and session_manager.enabled:
                session_manager.append_turn(session_id, request.message, ai_response)

            # 8. 返回响应
            current_history_turns = len(chat_history) + 1 if chat_history else 1
            return ChatResponse(
                response=ai_response,
                session_id=session_id,
                status="success",
                history_turns=current_history_turns
            )

    except asyncio.TimeoutError as e:
        logger.error(f"⏱️ 请求超时: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "service_busy", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"❌ 处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理失败: {str(e)}"
        )


@app.get("/Fang-GetWeather/session/{session_id}")
async def get_session_info(session_id: str):
    """获取会话信息"""
    if session_manager is None or not session_manager.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话管理器未启用"
        )

    try:
        session_info = session_manager.get_session_info(session_id)
        return session_info
    except Exception as e:
        logger.error(f"❌ 获取会话信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取会话信息失败: {str(e)}"
        )


@app.delete("/Fang-GetWeather/session/{session_id}")
async def clear_session(session_id: str):
    """清除会话历史"""
    if session_manager is None or not session_manager.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话管理器未启用"
        )

    try:
        success = session_manager.clear_history(session_id)
        if success:
            return {"status": "success", "message": f"会话 {session_id} 已清除"}
        else:
            return {"status": "not_found", "message": f"会话 {session_id} 不存在"}
    except Exception as e:
        logger.error(f"❌ 清除会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清除会话失败: {str(e)}"
        )


@app.get("/Fang-GetWeather/sessions")
async def list_sessions(limit: int = 100):
    """列出活跃会话"""
    if session_manager is None or not session_manager.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="会话管理器未启用"
        )

    try:
        session_ids = session_manager.list_active_sessions(limit=limit)
        return {
            "status": "success",
            "total": len(session_ids),
            "sessions": session_ids[:limit]
        }
    except Exception as e:
        logger.error(f"❌ 列出会话失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出会话失败: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    port = 6666
    print(f"\n{'='*70}")
    print("🌤️  智能天气助手 FastAPI 服务器")
    print(f"{'='*70}")
    print(f"\n📡 服务地址: http://localhost:{port}")
    print(f"📚 API 文档: http://localhost:{port}/docs\n")
    print(f"{'='*70}\n")

    try:
        uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False, log_level="info")
    except OSError as e:
        if "address already in use" in str(e).lower():
            recommended_port = 8000
            logger.warning(f"⚠️ 端口 {port} 已占用，切换到 {recommended_port}")
            uvicorn.run("api_server:app", host="0.0.0.0", port=recommended_port, reload=False, log_level="info")
        else:
            raise
