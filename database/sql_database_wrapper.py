"""
LangChain SQLDatabase 封装类
使用 LangChain 原生 SQL 能力替代手动 pymysql 操作

优化特性：
1. 增强的表结构描述（供 Agent 更好理解）
2. 自定义 table_info 支持模糊查询提示
3. 安全的参数化查询
4. 智能模糊匹配
"""

import logging
from typing import Optional, List, Dict, Any
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text
import sys
import os

# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..')
project_root = os.path.abspath(project_root)
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LangChainSQLDatabase:
    """
    基于 LangChain 的 SQL 数据库封装类

    优势：
    1. 自动生成表结构描述供 LLM 理解
    2. 内置安全的 SQL 执行机制
    3. 支持自然语言模糊查询
    4. 与 LangChain Agent 无缝集成
    5. 防止 SQL 注入攻击
    """

    def __init__(self, host: str = None, user: str = None, password: str = None,
                 database: str = None, charset: str = None):
        """
        初始化 LangChain SQL 数据库连接

        Args:
            host: 数据库主机地址
            user: 数据库用户名
            password: 数据库密码
            database: 数据库名称
            charset: 字符集
        """
        # 从 ConfigManager 加载配置
        if any(param is None for param in [host, user, password, database, charset]):
            try:
                from src.Config_Manager import ConfigManager
                config = ConfigManager()
                self.host = host or config.db_host
                self.user = user or config.db_user
                self.password = password or config.db_password
                self.database = database or config.db_name
                self.charset = charset or config.db_charset
                logger.info("已从 ConfigManager 加载数据库配置")
            except Exception as e:
                logger.warning(f"无法从 ConfigManager 加载配置: {e}，使用默认值")
                self.host = host or 'localhost'
                self.user = user or 'root'
                self.password = password or ''
                self.database = database or 'fang'
                self.charset = charset or 'utf8mb4'
        else:
            self.host = host
            self.user = user
            self.password = password
            self.database = database
            self.charset = charset

        # 构建 SQLAlchemy 连接 URL
        # 格式: mysql+pymysql://user:password@host/database?charset=utf8mb4
        self.connection_url = (
            f"mysql+pymysql://{self.user}:{self.password}@{self.host}/"
            f"{self.database}?charset={self.charset}"
        )

        # 创建 SQLAlchemy engine
        try:
            self.engine = create_engine(
                self.connection_url,
                pool_pre_ping=True,  # 自动检测连接是否有效
                pool_recycle=3600,   # 连接回收时间（秒）
                echo=False           # 设为 True 可查看 SQL 日志
            )
            logger.info("SQLAlchemy engine 创建成功")
        except Exception as e:
            logger.error(f"创建 SQLAlchemy engine 失败: {e}")
            raise

        # 创建 LangChain SQLDatabase 实例
        try:
            self.db = SQLDatabase(
                engine=self.engine,
                include_tables=['weather_regions'],  # 指定要使用的表
                sample_rows_in_table_info=5,         # 增加到5行示例数据
                custom_table_info=self._get_custom_table_info()  # 自定义表信息
            )
            logger.info("LangChain SQLDatabase 初始化成功")
            logger.info(f"可用的表: {self.db.get_usable_table_names()}")
        except Exception as e:
            logger.error(f"初始化 LangChain SQLDatabase 失败: {e}")
            raise

    def _get_custom_table_info(self) -> Dict[str, str]:
        """
        生成自定义表结构描述，帮助 Agent 更好理解如何查询

        Returns:
            表名到描述的映射
        """
        return {
            "weather_regions": """
表名: weather_regions
描述: 存储中国各地区的天气编码和行政信息
用途: 支持通过地区名称或省份查询天气编码

字段说明:
- id: 主键（自增）
- region: 地区名称（如：北京市、广州市、深圳市、湛江市）
- weather_code: 9位天气编码（如：101010100）
- province: 所属省份（如：北京市、广东省、海南省）
- region_type: 地区类型（枚举值：直辖市、省会城市、地级市、县级市）
- created_at: 记录创建时间

索引:
- idx_region: 地区名称索引（支持快速查询）
- idx_weather_code: 天气编码索引
- uk_region: 地区名称唯一约束

🔍 模糊查询提示（非常重要）:
1. 查询某个省份的所有地级市：
   SELECT region, region_type FROM weather_regions
   WHERE province LIKE '%广东%' AND region_type = '地级市'

2. 查询某个地区（支持模糊匹配）：
   SELECT * FROM weather_regions
   WHERE region LIKE '%北京%' OR province LIKE '%北京%'

3. 统计某个省份的城市数量：
   SELECT region_type, COUNT(*) as count FROM weather_regions
   WHERE province LIKE '%广东%' GROUP BY region_type

4. 列出所有直辖市：
   SELECT region FROM weather_regions WHERE region_type = '直辖市'

⚠️ 注意事项:
- province 字段可能是 "广东" 或 "广东省"，使用 LIKE '%广东%' 进行模糊匹配
- region 字段包含 "市" 或 "县"，如 "深圳市"、"湛江市"
- 查询时优先使用 province 字段筛选省份
- region_type 可用于精确筛选地区类型

📊 示例数据：
| region | weather_code | province | region_type |
|--------|--------------|----------|-------------|
| 北京市 | 101010100    | 北京市   | 直辖市      |
| 广州市 | 101280101    | 广东省   | 省会城市    |
| 深圳市 | 101280601    | 广东省   | 地级市      |
| 湛江市 | 101281001    | 广东省   | 地级市      |
"""
        }

    def get_table_info(self) -> str:
        """
        获取数据库表结构信息（供 LLM 理解）

        Returns:
            包含表结构、列类型、示例数据的描述文本
        """
        return self.db.table_info

    def run_query(self, query: str) -> str:
        """
        执行 SQL 查询并返回结果

        Args:
            query: SQL 查询语句

        Returns:
            查询结果（字符串格式）
        """
        try:
            result = self.db.run(query)
            logger.info(f"SQL 查询成功: {query[:100]}...")
            return result
        except Exception as e:
            logger.error(f"SQL 查询失败: {e}, 查询语句: {query}")
            return f"查询失败: {str(e)}"

    def run_query_safe(self, query: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        执行参数化查询（防止 SQL 注入）

        Args:
            query: SQL 查询语句，使用 :param_name 占位符
            params: 参数字典

        Returns:
            查询结果列表（字典格式）

        Example:
            query = "SELECT * FROM weather_regions WHERE province LIKE :province"
            params = {"province": "%广东%"}
            result = db.run_query_safe(query, params)
        """
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(query), params or {})
                columns = result.keys()
                rows = result.fetchall()

                # 转换为字典列表
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"参数化查询失败: {e}, 查询语句: {query}, 参数: {params}")
            return []

    def search_regions_by_province(self, province_name: str,
                                   region_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        根据省份名称查询地区（支持模糊匹配）

        Args:
            province_name: 省份名称（如：广东、广东省）
            region_type: 地区类型筛选（可选：直辖市、省会城市、地级市、县级市）

        Returns:
            地区信息列表

        Example:
            # 查询广东省所有地级市
            result = db.search_regions_by_province("广东", "地级市")
        """
        query = """
        SELECT region, weather_code, province, region_type
        FROM weather_regions
        WHERE province LIKE :province
        """

        params = {"province": f"%{province_name}%"}

        if region_type:
            query += " AND region_type = :region_type"
            params["region_type"] = region_type

        query += " ORDER BY region"

        logger.info(f"🔍 查询省份: {province_name}, 类型: {region_type or '全部'}")
        return self.run_query_safe(query, params)

    def search_regions_by_name(self, area_name: str) -> List[Dict[str, Any]]:
        """
        根据地区名称模糊查询（支持模糊匹配）

        Args:
            area_name: 地区名称关键词

        Returns:
            地区信息列表
        """
        query = """
        SELECT region, weather_code, province, region_type
        FROM weather_regions
        WHERE region LIKE :area_name OR province LIKE :area_name
        ORDER BY
            CASE
                WHEN region = :exact_name THEN 1
                WHEN region LIKE :exact_name_city THEN 2
                ELSE 3
            END,
            province, region
        LIMIT 10
        """

        params = {
            "area_name": f"%{area_name}%",
            "exact_name": area_name,
            "exact_name_city": f"{area_name}市"
        }

        logger.info(f"🔍 模糊查询地区: {area_name}")
        return self.run_query_safe(query, params)

    def get_statistics_by_region_type(self, province_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        统计地区类型分布

        Args:
            province_name: 省份名称（可选，不提供则统计全国）

        Returns:
            统计结果列表
        """
        query = """
        SELECT region_type, COUNT(*) as count
        FROM weather_regions
        """

        params = {}

        if province_name:
            query += " WHERE province LIKE :province"
            params["province"] = f"%{province_name}%"

        query += " GROUP BY region_type ORDER BY count DESC"

        logger.info(f"📊 统计地区类型: {province_name or '全国'}")
        return self.run_query_safe(query, params)

    def get_db_instance(self) -> SQLDatabase:
        """
        获取 LangChain SQLDatabase 实例
        供 SQLDatabaseChain 或 SQL Agent 使用

        Returns:
            SQLDatabase 实例
        """
        return self.db

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            logger.info("数据库连接已关闭")

