"""Redis 缓存管理模块
智能缓存天气查询结果
"""

import hashlib
import json
import logging
import os
import sys
import re
from typing import Optional, List
from datetime import timedelta

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class RedisCacheManager:
    """Redis 缓存管理器"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = None,
        password: str = None,
        default_ttl: int = 1800  # 默认缓存 30 分钟
    ):
        """
        初始化 Redis 缓存管理器

        Args:
            host: Redis 主机地址
            port: Redis 端口
            db: Redis 数据库编号
            password: Redis 密码
            default_ttl: 默认缓存过期时间（秒）
        """
        if not REDIS_AVAILABLE:
            logger.warning("⚠️ Redis 未安装，缓存功能已禁用")
            self.enabled = False
            self.client = None
            return

        # 从 ConfigManager 或参数获取配置
        if host is None or port is None or db is None:
            try:
                from Config_Manager import ConfigManager
                config = ConfigManager()
                self.host = host or config.redis_host
                self.port = port or config.redis_port
                self.db = db if db is not None else config.redis_db
                self.password = password or (config.redis_password if config.redis_password else None)
            except Exception as e:
                logger.warning(f"⚠️ 无法加载配置，使用默认值: {e}")
                self.host = host or "localhost"
                self.port = port or 6379
                self.db = db if db is not None else 0
                self.password = password
        else:
            self.host = host
            self.port = port
            self.db = db
            self.password = password

        self.default_ttl = default_ttl

        try:
            # 创建 Redis 客户端
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5
            )

            # 测试连接
            self.client.ping()
            self.enabled = True
            logger.info(
                f"✅ Redis 缓存已启用，"
                f"服务器: {self.host}:{self.port}，"
                f"默认 TTL: {self.default_ttl}秒"
            )

        except Exception as e:
            logger.error(f"❌ Redis 连接失败: {e}，缓存功能已禁用")
            self.enabled = False
            self.client = None

    def _normalize_location(self, text: str) -> Optional[str]:
        """
        智能提取并标准化地区名称（增强版）

        支持多种问法:
        - "北京天气怎么样?" → "北京"
        - "那北京的呢?" → "北京"
        - "上海会下雨吗?" → "上海"
        - "深圳今天气温" → "深圳"
        - "广州市" → "广州"

        Args:
            text: 原始文本

        Returns:
            标准化后的地区名称,未找到返回 None
        """
        if not text:
            return None

        # 去除常见修饰词和标点
        cleaned_text = text
        noise_words = [
            "今天", "明天", "后天", "昨天",
            "天气", "气温", "温度", "怎么样", "如何",
            "会", "吗", "呢", "的", "那", "这", "和",
            "下雨", "晴天", "阴天", "多云", "刮风"
        ]
        for word in noise_words:
            cleaned_text = cleaned_text.replace(word, " ")

        # 去除标点符号
        cleaned_text = re.sub(r'[?!。,，、;；:：""''《》【】\s]+', ' ', cleaned_text).strip()

        # 提取地区名称的多种正则模式
        patterns = [
            # 模式 1: 带行政区划 (北京市、广东省、深圳市)
            r'([\u4e00-\u9fff]{2,10}?)(市|省|县|区|镇|自治区|特别行政区)',
            # 模式 2: 纯中文地名 (2-10个汉字)
            r'([\u4e00-\u9fff]{2,10})',
        ]

        for pattern in patterns:
            match = re.search(pattern, cleaned_text)
            if match:
                location = match.group(1)
                # 去除行政区划后缀,统一格式
                location = re.sub(r'(市|省|县|区|镇|自治区|特别行政区)$', '', location)
                location = location.strip()

                # 过滤无效结果
                if len(location) >= 2 and location not in noise_words:
                    return location

        return None

    def _get_location_aliases(self, location: str) -> List[str]:
        """
        获取地区的所有别名（用于多键缓存）

        例如:
        - "北京" → ["北京", "北京市", "首都"]
        - "上海" → ["上海", "上海市", "魔都"]
        - "广州" → ["广州", "广州市", "羊城"]

        Args:
            location: 标准化的地区名称

        Returns:
            别名列表
        """
        # 城市别名映射表 (可以根据需要扩展)
        alias_map = {
            "北京": ["北京", "北京市", "首都"],
            "上海": ["上海", "上海市", "魔都"],
            "广州": ["广州", "广州市", "羊城"],
            "深圳": ["深圳", "深圳市", "鹏城"],
            "杭州": ["杭州", "杭州市"],
            "成都": ["成都", "成都市", "蓉城"],
            "重庆": ["重庆", "重庆市", "山城"],
            "西安": ["西安", "西安市", "长安"],
            "南京": ["南京", "南京市", "金陵"],
            "武汉": ["武汉", "武汉市", "江城"],
        }

        # 查找别名
        for standard_name, aliases in alias_map.items():
            if location in aliases or location == standard_name:
                return aliases

        # 如果没有特殊别名,返回基础变体
        return [
            location,
            f"{location}市",  # 添加"市"后缀
        ]

    def _generate_cache_key(self, user_message: str, prefix: str = "weather") -> Optional[str]:
        """
        生成统一的缓存键（优化版）

        策略:
        1. 提取地区名称并标准化
        2. 使用标准化地区名作为键（不使用哈希）
        3. 统一格式: weather:北京

        Args:
            user_message: 用户输入的消息
            prefix: 缓存键前缀

        Returns:
            缓存键字符串,未找到地区返回 None
        """
        # 提取并标准化地区名称
        location = self._normalize_location(user_message)

        if not location:
            logger.debug(f"⚠️ 无法从消息中提取地区: '{user_message}'")
            return None

        # 使用标准化地区名生成缓存键 (不使用哈希,便于调试和管理)
        cache_key = f"{prefix}:{location}"

        logger.debug(f"🔑 生成缓存键: '{user_message}' → '{location}' → '{cache_key}'")

        return cache_key

    def get(self, user_message: str, prefix: str = "weather") -> Optional[str]:
        """
        从缓存中获取结果（智能匹配）

        支持多种问法命中同一缓存:
        - "北京天气" → weather:北京
        - "北京市天气" → weather:北京
        - "首都天气" → weather:北京
        - "那北京的呢" → weather:北京

        Args:
            user_message: 用户输入的消息
            prefix: 缓存键前缀

        Returns:
            缓存的响应内容,如果未命中则返回 None
        """
        if not self.enabled:
            return None

        try:
            # 提取地区名称
            location = self._normalize_location(user_message)
            if not location:
                return None

            # 获取该地区的所有别名
            aliases = self._get_location_aliases(location)

            # 尝试使用每个别名查找缓存
            for alias in aliases:
                cache_key = f"{prefix}:{alias}"
                cached_value = self.client.get(cache_key)

                if cached_value:
                    logger.info(f"💾 缓存命中: '{user_message}' → {cache_key}")
                    return cached_value

            logger.debug(f"❌ 缓存未命中: '{user_message}' (尝试了 {len(aliases)} 个别名)")
            return None

        except Exception as e:
            logger.error(f"❌ 缓存读取失败: {e}")
            return None

    def set(
        self,
        user_message: str,
        response: str,
        prefix: str = "weather",
        ttl: int = None
    ) -> bool:
        """
        将结果保存到缓存（多键存储）

        会为所有别名都创建缓存键,确保多种问法都能命中:
        - "北京天气" → 同时创建:
          * weather:北京
          * weather:北京市
          * weather:首都

        Args:
            user_message: 用户输入的消息
            response: AI 响应内容
            prefix: 缓存键前缀
            ttl: 缓存过期时间（秒），None 则使用默认值

        Returns:
            是否保存成功
        """
        if not self.enabled:
            return False

        try:
            # 提取地区名称
            location = self._normalize_location(user_message)
            if not location:
                logger.warning(f"⚠️ 无法提取地区,跳过缓存: '{user_message}'")
                return False

            # 获取所有别名
            aliases = self._get_location_aliases(location)
            ttl = ttl or self.default_ttl

            # 为所有别名都创建缓存
            saved_count = 0
            for alias in aliases:
                cache_key = f"{prefix}:{alias}"
                try:
                    self.client.setex(cache_key, ttl, response)
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ 缓存写入失败 ({cache_key}): {e}")

            if saved_count > 0:
                logger.info(f"📝 写入缓存: {saved_count} 个键 ({', '.join(aliases)})，TTL: {ttl}秒")
                return True
            else:
                logger.error(f"❌ 所有缓存键写入失败")
                return False

        except Exception as e:
            logger.error(f"❌ 缓存写入失败: {e}")
            return False

    def delete(self, user_message: str, prefix: str = "weather") -> bool:
        """
        删除缓存（删除所有别名）

        Args:
            user_message: 用户输入的消息
            prefix: 缓存键前缀

        Returns:
            是否删除成功
        """
        if not self.enabled:
            return False

        try:
            # 提取地区名称
            location = self._normalize_location(user_message)
            if not location:
                return False

            # 获取所有别名
            aliases = self._get_location_aliases(location)

            # 删除所有别名的缓存
            deleted_count = 0
            for alias in aliases:
                cache_key = f"{prefix}:{alias}"
                try:
                    result = self.client.delete(cache_key)
                    if result > 0:
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ 缓存删除失败 ({cache_key}): {e}")

            if deleted_count > 0:
                logger.info(f"🗑️ 删除缓存: {deleted_count} 个键 ({', '.join(aliases)})")
                return True
            else:
                logger.debug(f"ℹ️ 无缓存需要删除: '{user_message}'")
                return False

        except Exception as e:
            logger.error(f"❌ 缓存删除失败: {e}")
            return False

    def clear_all(self, prefix: str = "weather") -> int:
        """
        清空指定前缀的所有缓存

        Args:
            prefix: 缓存键前缀

        Returns:
            删除的缓存数量
        """
        if not self.enabled:
            return 0

        try:
            pattern = f"{prefix}:*"
            keys = self.client.keys(pattern)

            if keys:
                count = self.client.delete(*keys)
                logger.info(f"🗑️ 清空缓存: {count} 条（前缀: {prefix}）")
                return count
            else:
                logger.info(f"ℹ️ 无缓存需要清空（前缀: {prefix}）")
                return 0

        except Exception as e:
            logger.error(f"❌ 缓存清空失败: {e}")
            return 0

    def get_stats(self, prefix: str = "weather") -> dict:
        """
        获取缓存统计信息

        Args:
            prefix: 缓存键前缀

        Returns:
            统计信息字典
        """
        if not self.enabled:
            return {
                "enabled": False,
                "total_keys": 0,
                "message": "Redis 未启用"
            }

        try:
            pattern = f"{prefix}:*"
            keys = self.client.keys(pattern)

            # 获取内存使用情况
            info = self.client.info("memory")
            memory_used_mb = info.get("used_memory", 0) / 1024 / 1024

            return {
                "enabled": True,
                "host": self.host,
                "port": self.port,
                "total_keys": len(keys),
                "prefix": prefix,
                "memory_used_mb": round(memory_used_mb, 2),
                "default_ttl": self.default_ttl
            }

        except Exception as e:
            logger.error(f"❌ 获取缓存统计失败: {e}")
            return {
                "enabled": True,
                "error": str(e)
            }

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            Redis 是否正常工作
        """
        if not self.enabled:
            return False

        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.error(f"❌ Redis 健康检查失败: {e}")
            return False


# 全局单例
_cache_manager: Optional[RedisCacheManager] = None


def get_cache_manager(
    host: str = None,
    port: int = None,
    db: int = 0,
    password: str = None,
    default_ttl: int = 1800
) -> RedisCacheManager:
    """
    获取全局缓存管理器实例（单例模式）

    Args:
        host: Redis 主机地址
        port: Redis 端口
        db: Redis 数据库编号
        password: Redis 密码
        default_ttl: 默认缓存过期时间（秒）

    Returns:
        RedisCacheManager: 缓存管理器实例
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = RedisCacheManager(
            host=host,
            port=port,
            db=db,
            password=password,
            default_ttl=default_ttl
        )
    return _cache_manager
