
import requests
import re
import json
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import logging
import sys
import os

# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..')
project_root = os.path.abspath(project_root)
sys.path.insert(0, project_root)

try:
    from database.db_manager import AreaCodeManager
except ImportError as e:
    logging.error(f"无法导入 AreaCodeManager: {e}。请确保 'GetWeather/database/db_manager.py' 文件存在且路径正确。")
    AreaCodeManager = None

try:
    from src.Config_Manager import ConfigManager
except ImportError as e:
    logging.error(f"无法导入 ConfigManager: {e}")
    ConfigManager = None

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WeatherQueryInput(BaseModel):
    """天气查询的输入参数"""
    area_name: str = Field(description="需要查询天气的地区名称,如:北京、上海等")

class WeatherTool(BaseTool):
    name: str = "weather_query"
    description: str = "查询指定地区的天气信息。输入应为地区名称,例如 '北京'。"
    args_schema: Type[BaseModel] = WeatherQueryInput
    db_manager: Optional[AreaCodeManager] = None
    base_url: str = ""
    api_key: Optional[str] = None
    unifuncs_search_url: str = "https://api.302.ai/unifuncs/api/web-search/search"

    def __init__(self, **data):
        """
        初始化天气查询工具。
        Args:
            db_manager: AreaCodeManager 实例,用于查询地区编码。
            api_key: API密钥,用于Unifuncs搜索。
        """
        super().__init__(**data) # Pydantic 的 __init__ 会处理 db_manager 字段的设置

        # 即使是可选的,如果实际使用时需要,仍然需要检查
        if self.db_manager is None:
            raise ValueError("AreaCodeManager 实例未提供或导入失败。WeatherTool 无法正常工作。")
        self.base_url = "http://www.weather.com.cn/weather/{}.shtml" # 7天天气预报

    def _get_area_code(self, area_name: str) -> Optional[str]:
        """
        根据地区名称从数据库获取天气编码。
        使用模糊查询,并返回第一个匹配项的 weather_code。
        """
        if not self.db_manager:
            logger.error("AreaCodeManager 未初始化,无法查询地区编码。")
            return None

        # 调用 AreaCodeManager 的模糊查询方法
        matching_regions = self.db_manager.search_regions_by_name(area_name)

        if matching_regions:
            # 假设我们取第一个匹配项的 weather_code
            # 在实际应用中,可能需要更复杂的逻辑来处理多个匹配项
            logger.info(f"找到地区 '{area_name}' 的匹配项: {matching_regions[0]['region']},编码: {matching_regions[0]['weather_code']}")
            return matching_regions[0]['weather_code']
        else:
            logger.warning(f"未在数据库中找到地区 '{area_name}' 对应的编码。")
            return None

    def _search_weather_via_unifuncs(self, area_name: str) -> Optional[dict]:
        """
        通过 Unifuncs API 搜索天气信息。

        Args:
            area_name: 地区名称

        Returns:
            包含 'snippet'(天气描述) 和 'weather_code'(编码) 的字典，失败返回 None
        """
        if not self.api_key:
            logger.error("API密钥未配置，无法调用 Unifuncs 搜索。")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "query": f"{area_name}天气",
                "page": 1,
                "count": 1
            }

            logger.info(f"通过 Unifuncs API 搜索 '{area_name}' 的天气信息...")
            response = requests.post(
                self.unifuncs_search_url,
                headers=headers,
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"Unifuncs API 请求失败，状态码: {response.status_code}, 响应: {response.text}")
                return None

            data = response.json()

            # 解析响应数据（按照新的格式）
            if data.get('code') != 0:
                logger.error(f"Unifuncs API 返回错误代码: {data.get('code')}, 消息: {data.get('message')}")
                return None

            # 检查 data.webPages 是否存在且有数据
            web_pages = data.get('data', {}).get('webPages', [])
            if not web_pages or len(web_pages) == 0:
                logger.warning(f"Unifuncs API 未返回 '{area_name}' 的搜索结果。")
                return None

            # 获取第一个搜索结果
            result = web_pages[0]
            snippet = result.get('snippet', '')
            display_url = result.get('displayUrl', '')

            # 从 displayUrl 中提取天气编码
            # URL 格式: https://www.weather.com.cn/weather/{编码}.shtml
            weather_code = None
            match = re.search(r'weather\.com\.cn/weather/(\d+)\.shtml', display_url)
            if match:
                weather_code = match.group(1)
                logger.info(f"从 Unifuncs 搜索结果中提取到天气编码: {weather_code}")
            else:
                logger.warning(f"无法从 URL '{display_url}' 中提取天气编码，但仍返回snippet供模型解析。")

            # 无论是否提取到编码，都返回 snippet 数据
            return {
                'snippet': snippet,
                'weather_code': weather_code,  # 可能为 None
                'display_url': display_url
            }

        except requests.exceptions.Timeout:
            logger.error("Unifuncs API 请求超时。")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Unifuncs API 请求异常: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"解析 Unifuncs API 响应失败: {e}")
            return None
        except Exception as e:
            logger.error(f"调用 Unifuncs API 时发生未知错误: {e}", exc_info=True)
            return None

    def _save_area_code_to_db(self, area_name: str, weather_code: str) -> bool:
        """
        将新发现的地区编码保存到数据库。

        Args:
            area_name: 地区名称
            weather_code: 天气编码

        Returns:
            保存成功返回 True，否则返回 False
        """
        if not self.db_manager:
            logger.error("AreaCodeManager 未初始化，无法保存地区编码。")
            return False

        try:
            # 尝试插入新记录（province 和 region_type 留空或设置默认值）
            success = self.db_manager.insert_region(
                region=area_name,
                weather_code=weather_code,
                province="",  # 暂时留空
                region_type="地级市"  # 默认设置为地级市
            )

            if success:
                logger.info(f"成功将地区 '{area_name}' 的编码 '{weather_code}' 保存到数据库。")
            else:
                logger.warning(f"地区 '{area_name}' 可能已存在于数据库中，未重复添加。")

            return success

        except Exception as e:
            logger.error(f"保存地区编码到数据库时发生错误: {e}", exc_info=True)
            return False

    def _run(self, area_name: str) -> str:
        """
        执行天气查询，返回天气信息或URL。

        流程：
        1. 先从数据库查询编码
        2. 如果数据库没有，通过 Unifuncs API 搜索
        3. 将新编码保存到数据库
        4. 返回天气信息给模型
        """
        try:
            # 第一步：尝试从数据库获取编码
            area_code = self._get_area_code(area_name)

            if area_code:
                # 数据库中找到编码，直接构建URL
                url = self.base_url.format(area_code)
                logger.info(f"从数据库为地区 '{area_name}' 生成天气URL: {url}")
                return url

            # 第二步：数据库未找到，尝试通过 Unifuncs API 搜索
            logger.info(f"数据库中未找到 '{area_name}' 的编码，尝试通过 Unifuncs API 搜索...")
            search_result = self._search_weather_via_unifuncs(area_name)

            if not search_result:
                return f"抱歉，无法找到地区 '{area_name}' 的天气信息。请确认地区名称是否正确。"

            # 第三步：提取信息
            weather_code = search_result.get('weather_code')
            snippet = search_result.get('snippet', '')
            display_url = search_result.get('display_url', '')

            # 如果提取到了天气编码，保存到数据库（供下次查询使用）
            if weather_code:
                self._save_area_code_to_db(area_name, weather_code)
                url = self.base_url.format(weather_code)
                response = f"{snippet}\n\n详细天气信息请访问：{url}"
                logger.info(f"通过 Unifuncs API 为地区 '{area_name}' 获取到天气信息和编码。")
            else:
                # 即使没有编码，也返回 snippet 让模型进行解析
                response = snippet if snippet else f"搜索到 '{area_name}' 的部分信息，但无法提取详细数据。"
                logger.info(f"通过 Unifuncs API 为地区 '{area_name}' 获取到天气描述，但未提取到编码。")

            return response

        except Exception as e:
            logger.error(f"查询天气信息时发生未知错误: {e}", exc_info=True)
            return f"查询天气信息时发生错误: {str(e)}"

    async def _arun(self, area_name: str) -> str:
        """异步执行天气查询,返回天气网站URL"""
        # 对于简单的URL生成,直接调用同步方法即可
        return self._run(area_name)

# 工具实例化函数
def create_weather_tool() -> Optional[WeatherTool]:
    """
    创建天气查询工具实例。

    Returns:
        WeatherTool实例,如果 AreaCodeManager 导入失败则返回 None。
    """
    if AreaCodeManager is None:
        logger.error("AreaCodeManager 未成功导入,无法创建 WeatherTool 实例。")
        return None

    if ConfigManager is None:
        logger.error("ConfigManager 未成功导入,无法创建 WeatherTool 实例。")
        return None

    try:
        # 加载配置获取 API key
        config = ConfigManager()
        db_manager = AreaCodeManager()

        return WeatherTool(
            db_manager=db_manager,
            api_key=config.api_key
        )
    except Exception as e:
        logger.critical(f"初始化 WeatherTool 失败: {e}", exc_info=True)
        return None

# 使用示例
if __name__ == "__main__":

    weather_tool = None
    try:
        # 创建工具实例
        weather_tool = create_weather_tool()

        if weather_tool:
            print("--- 测试查询 '北京' 的天气URL ---")
            result_beijing = weather_tool.run("北京")
            print(result_beijing)
        else:
            print("天气工具初始化失败,无法进行测试。")

    except Exception as e:
        logger.critical(f"主程序发生未预期错误: {e}", exc_info=True)
    finally:
        if weather_tool and weather_tool.db_manager:
            weather_tool.db_manager.disconnect()
            print("\n数据库连接已关闭。")
