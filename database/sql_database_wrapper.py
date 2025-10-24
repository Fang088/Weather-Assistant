"""
LangChain SQLDatabase 封装类
使用 LangChain 原生 SQL 能力替代手动 pymysql 操作
"""

import logging
from typing import Optional
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
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
    3. 支持自然语言查询
    4. 与 LangChain Agent 无缝集成
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
                sample_rows_in_table_info=3          # 在表描述中包含3行示例数据
            )
            logger.info("LangChain SQLDatabase 初始化成功")
            logger.info(f"可用的表: {self.db.get_usable_table_names()}")
        except Exception as e:
            logger.error(f"初始化 LangChain SQLDatabase 失败: {e}")
            raise

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

    def get_db_instance(self) -> SQLDatabase:
        """
        获取 LangChain SQLDatabase 实例
        供 SQLDatabaseChain 或 SQL Agent 使用

        Returns:
            SQLDatabase 实例
        """
        return self.db

    def search_region_by_name(self, area_name: str) -> str:
        """
        根据地区名称查询天气编码（兼容旧接口）

        Args:
            area_name: 地区名称

        Returns:
            查询结果（包含 region, weather_code, province 等字段）
        """
        query = f"""
        SELECT region, weather_code, province, region_type
        FROM weather_regions
        WHERE region LIKE '%{area_name}%'
        ORDER BY province, region
        LIMIT 5
        """
        return self.run_query(query)

    def close(self):
        """关闭数据库连接"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            logger.info("数据库连接已关闭")


# 使用示例
if __name__ == "__main__":

    try:
        # 创建数据库实例
        db_wrapper = LangChainSQLDatabase()

        # 1. 查看表结构信息
        print("=" * 60)
        print("数据库表结构信息（供 LLM 理解）:")
        print("=" * 60)
        print(db_wrapper.get_table_info())

        # 2. 执行查询
        print("\n" + "=" * 60)
        print("查询测试 - 搜索'北京':")
        print("=" * 60)
        result = db_wrapper.search_region_by_name("北京")
        print(result)

        # 3. 直接执行 SQL
        print("\n" + "=" * 60)
        print("直接 SQL 查询 - 统计记录数:")
        print("=" * 60)
        count_result = db_wrapper.run_query("SELECT COUNT(*) as total FROM weather_regions")
        print(f"总记录数: {count_result}")

    except Exception as e:
        logger.critical(f"测试失败: {e}", exc_info=True)
    finally:
        db_wrapper.close()
