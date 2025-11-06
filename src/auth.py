"""API Key 认证模块 - 标准 Bearer Token 格式"""

import sys
import os
import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from pydantic import BaseModel, Field

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from Config_Manager import ConfigManager

logger = logging.getLogger(__name__)


class APIKeyConfig(BaseModel):
    api_key: str = Field(..., description="API Key")


def get_env_api_key() -> Optional[str]:
    """从配置管理器获取 API Key"""
    try:
        config = ConfigManager()
        api_key = config.api_key
        return api_key if api_key and api_key != "your_openai_api_key_here" else None
    except Exception as e:
        logger.warning(f"⚠️ 无法加载配置: {e}")
        return None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """从 Authorization 头中提取 Bearer Token"""
    if not authorization:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


async def verify_api_key(
    authorization: Optional[str] = Header(default=None)
) -> APIKeyConfig:
    """
    验证 API Key（优先用户 Key > 配置文件 Key）

    Raises:
        HTTPException: 401 验证失败
    """
    # 优先使用用户提供的 Key
    user_api_key = extract_bearer_token(authorization)

    if user_api_key:
        if len(user_api_key) < 10:
            logger.warning(f"❌ 无效的 API Key: {user_api_key[:5]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_api_key", "message": "API Key 格式错误"},
                headers={"WWW-Authenticate": "Bearer"}
            )
        logger.info(f"✅ 使用用户 Key: {user_api_key[:10]}...")
        return APIKeyConfig(api_key=user_api_key)

    # 使用环境变量 Key
    env_api_key = get_env_api_key()

    if env_api_key:
        logger.debug("✅ 使用配置 Key")
        return APIKeyConfig(api_key=env_api_key)

    # 两者都没有
    logger.warning("❌ API Key 缺失")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": "missing_api_key",
            "message": "API Key 未配置",
            "hint": "请提供 Authorization 头或配置 .env 文件"
        },
        headers={"WWW-Authenticate": "Bearer"}
    )
