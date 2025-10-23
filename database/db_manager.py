
import pymysql
from typing import List, Dict, Optional, Tuple, Any
import logging
from enum import Enum
import sys
import os

# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..')
project_root = os.path.abspath(project_root)
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RegionType(Enum):
    """地区类型枚举，与数据库中的ENUM类型保持一致"""
    MUNICIPALITY = '直辖市'
    PROVINCIAL_CAPITAL = '省会城市'
    PREFECTURE_CITY = '地级市'
    COUNTY_CITY = '县级市'

class AreaCodeManager:
    """
    地区代码管理器，负责对 MySQL 数据库中的 weather_regions 表进行 CRUD 操作。
    表结构: region, weather_code, province, region_type (ENUM('直辖市','省会城市','地级市','县级市'))
    """

    def __init__(self, host: str = None, user: str = None, password: str = None,
                 database: str = None, charset: str = None):
        """
        初始化数据库连接参数。

        Args:
            host: 数据库主机地址，默认从环境变量读取。
            user: 数据库用户名，默认从环境变量读取。
            password: 数据库密码，默认从环境变量读取。
            database: 数据库名称，默认从环境变量读取。
            charset: 字符集，默认从环境变量读取。
        """
        # 如果未提供参数，尝试从 ConfigManager 读取
        if any(param is None for param in [host, user, password, database, charset]):
            try:
                from src.Config_Manager import ConfigManager
                config = ConfigManager()
                self.host = host or config.db_host
                self.user = user or config.db_user
                self.password = password or config.db_password
                self.database = database or config.db_name
                self.charset = charset or config.db_charset
                logger.info("已从 ConfigManager 加载数据库配置。")
            except Exception as e:
                logger.warning(f"无法从 ConfigManager 加载配置: {e}，使用默认值。")
                self.host = host or 'localhost'
                self.user = user or 'root'
                self.password = password or '123456'
                self.database = database or 'fang'
                self.charset = charset or 'utf8mb4'
        else:
            self.host = host
            self.user = user
            self.password = password
            self.database = database
            self.charset = charset

        self.connection = None
        self.connect()
    
    def connect(self) -> bool:
        """
        尝试连接到 MySQL 数据库。
        
        Returns:
            如果连接成功返回 True，否则返回 False。
        """
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                charset=self.charset,
                cursorclass=pymysql.cursors.DictCursor # 返回字典形式的结果
            )
            logger.info("数据库连接成功。")
            return True
        except pymysql.Error as e:
            logger.error(f"数据库连接失败: {e}")
            self.connection = None
            return False
    
    def disconnect(self):
        """
        断开数据库连接。
        """
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("数据库连接已关闭。")
    
    def reconnect(self) -> bool:
        """
        断开并重新连接数据库。
        
        Returns:
            如果重新连接成功返回 True，否则返回 False。
        """
        self.disconnect()
        return self.connect()
    
    def _ensure_connection(self):
        """
        确保数据库连接是活跃的。如果连接断开，尝试重新连接。
        """
        if not self.connection or not self.connection.open:
            logger.warning("数据库连接已断开或未建立，尝试重新连接...")
            if not self.reconnect():
                raise ConnectionError("无法建立或重新建立数据库连接。")

    def execute_query(self, query: str, params: Optional[Tuple] = None) -> Optional[List[Dict]]:
        """
        执行 SQL 查询语句。
        """
        self._ensure_connection()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                return result
        except pymysql.Error as e:
            logger.error(f"查询执行失败: {e}, SQL: {query}, Params: {params}")
            return None
    
    def execute_update(self, query: str, params: Optional[Tuple] = None) -> bool:
        """
        执行 SQL 更新语句 (INSERT, UPDATE, DELETE)。
        """
        self._ensure_connection()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return True
        except pymysql.Error as e:
            self.connection.rollback()
            logger.error(f"更新执行失败: {e}, SQL: {query}, Params: {params}")
            return False
    
    # --- 核心功能 ---
    
    def get_total_records_count(self) -> int:
        """
        获取 weather_regions 表中的总记录数。
        """
        query = "SELECT COUNT(*) AS count FROM weather_regions"
        result = self.execute_query(query)
        return result[0]['count'] if result else 0

    def insert_region(self, region: str, weather_code: str, province: str, 
                     region_type: str) -> bool:
        """
        插入一条新的地区记录。
        在插入前会检查该 region 是否已存在。
        如果已存在，则不执行插入操作，并返回 False。
        """
        if region_type not in [item.value for item in RegionType]:
            logger.error(f"无效的地区类型: {region_type}。必须是 {', '.join([item.value for item in RegionType])} 之一。")
            return False

        # 检查 region 是否已存在
        check_query = "SELECT COUNT(*) AS count FROM weather_regions WHERE region = %s"
        check_result = self.execute_query(check_query, (region,))
        
        if check_result and check_result[0]['count'] > 0:
            logger.warning(f"地区 '{region}' 已存在，不执行添加操作。")
            return False

        query = """
        INSERT INTO weather_regions (region, weather_code, province, region_type)
        VALUES (%s, %s, %s, %s)
        """
        params = (region, weather_code, province, region_type)
        return self.execute_update(query, params)
    
    def search_regions_by_name(self, region_name: str) -> List[Dict]:
        """
        根据地区名称进行模糊查询。
        
        Args:
            region_name: 要模糊匹配的地区名称。
            
        Returns:
            匹配的地区记录列表。
        """
        query = "SELECT * FROM weather_regions WHERE region LIKE %s ORDER BY province, region"
        params = (f"%{region_name}%",)
        
        result = self.execute_query(query, params)
        return result if result is not None else []

    def update_region(self, weather_code: str, update_data: Dict[str, Any]) -> bool:
        """
        根据 weather_code 更新地区记录。
        """
        if not update_data:
            logger.warning("没有提供更新数据。")
            return False
        
        set_clauses = []
        params = []
        
        for key, value in update_data.items():
            if key == 'region_type':
                if value not in [item.value for item in RegionType]:
                    logger.error(f"无效的地区类型值 '{value}'。必须是 {', '.join([item.value for item in RegionType])} 之一。")
                    return False
            set_clauses.append(f"{key} = %s")
            params.append(value)
        
        query = f"UPDATE weather_regions SET {', '.join(set_clauses)} WHERE weather_code = %s"
        params.append(weather_code)
        
        return self.execute_update(query, tuple(params))
    
    def delete_region(self, weather_code: str) -> bool:
        """
        根据 weather_code 删除地区记录。
        """
        query = "DELETE FROM weather_regions WHERE weather_code = %s"
        params = (weather_code,)
        return self.execute_update(query, params)


# --- 示例用法和测试 ---
if __name__ == "__main__":

    manager = None
    try:
        manager = AreaCodeManager()

        print(f"当前数据库中的总记录数: {manager.get_total_records_count()}")

        # # --- 插入测试 ---
        # print("\n--- 插入测试 ---")
        # if manager.insert_region("测试城市A", "TESTA", "测试省", RegionType.PREFECTURE_CITY.value):
        #     print("插入 '测试城市A' 成功。")
        # else:
        #     print("插入 '测试城市A' 失败或已存在。")
        

        # --- 查询测试 ---
        print("\n--- 查询测试 (通过地区名称模糊查询) ---")
        ma_an_regions = manager.search_regions_by_name('齐齐')
        if ma_an_regions:
            for r in ma_an_regions:
                print(f"  找到: {r['region']} ({r['weather_code']}) - {r['province']}")
        else:
            print("  未找到。")

    #     # --- 更新测试 ---
    #     print("\n--- 更新测试 ---")
    #     if manager.update_region("TESTA", {'region': '更新城市A', 'province': '更新省'}):
    #         print("更新 'TESTA' 成功。")
    #         updated_region = manager.select_regions({'weather_code': 'TESTA'})
    #         print(f"  更新后: {updated_region[0]['region']} - {updated_region[0]['province']}")
    #     else:
    #         print("更新 'TESTA' 失败。")

        # # --- 删除测试 ---
        # print("\n--- 删除测试 ---")
        # if manager.delete_region("TESTA"):
        #     print("删除 'TESTA' 成功。")
        # else:
        #     print("删除 'TESTA' 失败。")
            

    except ConnectionError as e:
        logger.critical(f"数据库连接错误: {e}")
    except Exception as e:
        logger.critical(f"发生未预期错误: {e}", exc_info=True)
    finally:
        if manager:
            manager.disconnect()
