"""会话管理模块 - 基于 Redis 的会话历史管理"""

import json
import logging
import uuid
from typing import Optional, List, Tuple
from datetime import datetime

from cache_manager import RedisCacheManager

logger = logging.getLogger(__name__)


class SessionManager:
    """会话管理器 - 负责管理用户对话历史"""

    def __init__(
        self,
        cache_manager: RedisCacheManager,
        max_history_turns: int = 5,
        session_ttl: int = 3600  # 默认 1 小时过期
    ):
        """
        初始化会话管理器

        Args:
            cache_manager: Redis 缓存管理器
            max_history_turns: 最大保留历史轮数
            session_ttl: 会话过期时间（秒）
        """
        self.cache_manager = cache_manager
        self.max_history_turns = max_history_turns
        self.session_ttl = session_ttl
        self.enabled = cache_manager.enabled

        if self.enabled:
            logger.info(f"✅ 会话管理器已启用，最大历史轮数: {max_history_turns}，TTL: {session_ttl}秒")
        else:
            logger.warning("⚠️ 会话管理器未启用（Redis 未连接）")

    def generate_session_id(self) -> str:
        """
        生成新的会话 ID

        Returns:
            UUID 格式的会话 ID
        """
        session_id = str(uuid.uuid4())
        logger.debug(f"🆔 生成新会话 ID: {session_id}")
        return session_id

    def get_history(self, session_id: str) -> List[Tuple[str, str]]:
        """
        获取会话历史

        Args:
            session_id: 会话 ID

        Returns:
            历史对话列表 [(user_msg, ai_msg), ...]
        """
        if not self.enabled:
            return []

        try:
            history_key = f"session:{session_id}:history"
            cached_data = self.cache_manager.client.get(history_key)

            if cached_data:
                history = json.loads(cached_data)
                logger.debug(f"📖 加载会话历史: {session_id} ({len(history)} 轮)")
                return [tuple(pair) for pair in history]
            else:
                logger.debug(f"📭 会话历史为空: {session_id}")
                return []

        except Exception as e:
            logger.error(f"❌ 获取会话历史失败: {e}")
            return []

    def save_history(
        self,
        session_id: str,
        chat_history: List[Tuple[str, str]],
        ttl: int = None
    ) -> bool:
        """
        保存会话历史

        Args:
            session_id: 会话 ID
            chat_history: 历史对话列表
            ttl: 过期时间（秒），None 则使用默认值

        Returns:
            是否保存成功
        """
        if not self.enabled:
            return False

        try:
            history_key = f"session:{session_id}:history"
            ttl = ttl or self.session_ttl

            # 限制历史长度
            if len(chat_history) > self.max_history_turns:
                chat_history = chat_history[-self.max_history_turns:]

            # 转换为 JSON 并保存
            history_json = json.dumps(chat_history, ensure_ascii=False)
            self.cache_manager.client.setex(history_key, ttl, history_json)

            logger.debug(f"💾 保存会话历史: {session_id} ({len(chat_history)} 轮，TTL: {ttl}秒)")
            return True

        except Exception as e:
            logger.error(f"❌ 保存会话历史失败: {e}")
            return False

    def append_turn(
        self,
        session_id: str,
        user_message: str,
        ai_response: str
    ) -> bool:
        """
        追加一轮对话到会话历史

        Args:
            session_id: 会话 ID
            user_message: 用户消息
            ai_response: AI 回复

        Returns:
            是否追加成功
        """
        if not self.enabled:
            return False

        try:
            # 获取现有历史
            chat_history = self.get_history(session_id)

            # 追加新对话
            chat_history.append((user_message, ai_response))

            # 保存更新后的历史
            return self.save_history(session_id, chat_history)

        except Exception as e:
            logger.error(f"❌ 追加对话失败: {e}")
            return False

    def clear_history(self, session_id: str) -> bool:
        """
        清除会话历史

        Args:
            session_id: 会话 ID

        Returns:
            是否清除成功
        """
        if not self.enabled:
            return False

        try:
            history_key = f"session:{session_id}:history"
            result = self.cache_manager.client.delete(history_key)

            if result > 0:
                logger.info(f"🗑️ 清除会话历史: {session_id}")
                return True
            else:
                logger.debug(f"ℹ️ 会话历史不存在: {session_id}")
                return False

        except Exception as e:
            logger.error(f"❌ 清除会话历史失败: {e}")
            return False

    def get_session_info(self, session_id: str) -> dict:
        """
        获取会话信息

        Args:
            session_id: 会话 ID

        Returns:
            会话信息字典
        """
        if not self.enabled:
            return {
                "session_id": session_id,
                "enabled": False,
                "message": "会话管理器未启用"
            }

        try:
            history = self.get_history(session_id)
            history_key = f"session:{session_id}:history"

            # 获取 TTL
            ttl = self.cache_manager.client.ttl(history_key)

            return {
                "session_id": session_id,
                "enabled": True,
                "history_turns": len(history),
                "max_history_turns": self.max_history_turns,
                "ttl_seconds": ttl if ttl > 0 else None,
                "exists": len(history) > 0
            }

        except Exception as e:
            logger.error(f"❌ 获取会话信息失败: {e}")
            return {
                "session_id": session_id,
                "enabled": True,
                "error": str(e)
            }

    def list_active_sessions(self, limit: int = 100) -> List[str]:
        """
        列出活跃的会话 ID

        Args:
            limit: 最大返回数量

        Returns:
            会话 ID 列表
        """
        if not self.enabled:
            return []

        try:
            pattern = "session:*:history"
            keys = self.cache_manager.client.keys(pattern)

            # 提取 session_id
            session_ids = []
            for key in keys[:limit]:
                # key 格式: session:<uuid>:history
                parts = key.split(":")
                if len(parts) == 3:
                    session_ids.append(parts[1])

            logger.debug(f"📋 活跃会话数: {len(session_ids)}")
            return session_ids

        except Exception as e:
            logger.error(f"❌ 列出活跃会话失败: {e}")
            return []

    def get_stats(self) -> dict:
        """
        获取会话管理统计信息

        Returns:
            统计信息字典
        """
        if not self.enabled:
            return {
                "enabled": False,
                "message": "会话管理器未启用"
            }

        try:
            active_sessions = self.list_active_sessions(limit=1000)

            return {
                "enabled": True,
                "active_sessions": len(active_sessions),
                "max_history_turns": self.max_history_turns,
                "session_ttl_seconds": self.session_ttl
            }

        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {
                "enabled": True,
                "error": str(e)
            }
