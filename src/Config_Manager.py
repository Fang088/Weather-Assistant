
import os
import logging
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理类，负责加载和验证环境变量。"""
    
    def __init__(self):
        self.load_environment_variables()
    
    def load_environment_variables(self) -> None:
        """
        从指定路径的.env文件加载环境变量，并检查必需变量。
        根据当前脚本文件位置，向上两级找到项目根目录，然后加载其中的.env文件。
        """
        # 获取当前脚本文件 (Config_Manager.py) 的绝对路径
        current_file_path = os.path.abspath(__file__)
        # 获取当前脚本文件所在的目录 (src)
        current_dir = os.path.dirname(current_file_path)
        # 获取 src 目录的父目录 (GetWeather，即项目根目录)
        project_root = os.path.dirname(current_dir)

        # 构造 .env 文件的完整路径
        dotenv_path = os.path.join(project_root, '.env')

        if not os.path.exists(dotenv_path):
            raise FileNotFoundError(
                f"未找到 .env 文件于指定路径: {dotenv_path}。"
                f"请确保它在项目根目录中，或参考 .env.example 创建配置文件。"
            )

        load_dotenv(dotenv_path=dotenv_path)

        # 验证必需的环境变量
        required_vars = ["API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(f"缺少必需的环境变量: {', '.join(missing_vars)}")

        logger.info(f"环境变量加载成功，配置文件: {dotenv_path}")
    
    @property
    def api_key(self) -> str:
        """获取API密钥。"""
        return os.getenv("API_KEY", "")
    
    @property
    def base_url(self) -> str:
        """获取对话 API 基础地址。"""
        return os.getenv("BASE_URL", "https://api.302.ai/v1")

    @property
    def model(self) -> str:
        """获取模型名称。"""
        return os.getenv("MODEL", "gpt-4o-mini")

    # --- 数据库配置 ---

    @property
    def db_host(self) -> str:
        """获取数据库主机地址。"""
        return os.getenv("DB_HOST", "localhost")

    @property
    def db_user(self) -> str:
        """获取数据库用户名。"""
        return os.getenv("DB_USER", "root")

    @property
    def db_password(self) -> str:
        """获取数据库密码。"""
        return os.getenv("DB_PASSWORD", "")

    @property
    def db_name(self) -> str:
        """获取数据库名称。"""
        return os.getenv("DB_NAME", "fang")

    @property
    def db_charset(self) -> str:
        """获取数据库字符集。"""
        return os.getenv("DB_CHARSET", "utf8mb4")

    # --- 搜索API配置 ---

    @property
    def search_api_url(self) -> str:
        """获取搜索 API 地址。"""
        return os.getenv("SEARCH_API_URL", "https://api.302.ai/search1api/search")

    # --- Redis缓存配置 ---

    @property
    def redis_host(self) -> str:
        """获取 Redis 主机地址。"""
        return os.getenv("REDIS_HOST", "localhost")

    @property
    def redis_port(self) -> int:
        """获取 Redis 端口。"""
        return int(os.getenv("REDIS_PORT", "6379"))

    @property
    def redis_db(self) -> int:
        """获取 Redis 数据库编号。"""
        return int(os.getenv("REDIS_DB", "0"))

    @property
    def redis_password(self) -> str:
        """获取 Redis 密码（可选）。"""
        return os.getenv("REDIS_PASSWORD", "")
