
import json
import requests
import re
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
import logging
import sys
import os

# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..')
project_root = os.path.abspath(project_root)
sys.path.insert(0, project_root)

try:
    from database.sql_database_wrapper import LangChainSQLDatabase
    from Config_Manager import ConfigManager
except ImportError as e:
    logging.error(f"无法导入模块: {e}")
    LangChainSQLDatabase = None
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
    sql_db: LangChainSQLDatabase  # LangChain SQL 数据库
    llm: BaseChatModel  # LLM实例用于整理天气信息
    config: ConfigManager  # 配置管理器
    search_api_key: str = None  # 搜索 API Key（可选，优先使用）
    search_api_url: str = "https://api.302.ai/search1api/search"  # 固定搜索 URL

    class Config:
        arbitrary_types_allowed = True  # 允许自定义类型

    def __init__(self, search_api_key: str = None, search_api_url: str = None, **data):
        """
        初始化天气查询工具。

        Args:
            sql_db: LangChainSQLDatabase 实例（必需）
            llm: ChatModel 实例（必需，用于整理天气信息）
            config: ConfigManager 实例（必需）
            search_api_key: 搜索 API Key（可选，优先使用传入的值）
            search_api_url: 搜索 API URL（可选，默认固定为 302.ai）
        """
        super().__init__(**data)

        # 设置搜索 API Key 和 URL
        self.search_api_key = search_api_key
        if search_api_url:
            self.search_api_url = search_api_url

        if self.sql_db is None:
            raise ValueError("必须提供 sql_db 实例。WeatherTool 无法正常工作。")

        if self.llm is None:
            raise ValueError("必须提供 llm 实例。WeatherTool 无法正常工作。")

        if self.config is None:
            raise ValueError("必须提供 config 实例。WeatherTool 无法正常工作。")

        logger.info(f"使用外部搜索API进行天气查询，URL: {self.search_api_url}")

    def _call_search_api(self, area_name: str) -> Optional[dict]:
        """
        调用外部搜索API获取天气信息

        Args:
            area_name: 地区名称

        Returns:
            搜索结果字典，失败返回 None
        """
        try:
            # 使用固定的搜索 URL
            url = self.search_api_url

            # 优先使用传入的 Key，其次使用配置文件的 Key
            api_key = self.search_api_key or self.config.search_api_key

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "query": f"{area_name}天气"
            }

            logger.info(f"🔍 调用搜索API查询 '{area_name}' 的天气...")

            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            logger.info(f"✅ 搜索API返回成功")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 调用搜索API失败: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ 处理搜索结果时出错: {e}", exc_info=True)
            return None

    def _extract_weather_code_from_url(self, url: str) -> Optional[str]:
        """
        从中国天气网URL中提取天气编码

        Args:
            url: 中国天气网的URL，如 https://www.weather.com.cn/weather/101281001.shtml

        Returns:
            9位数字天气编码，未找到返回 None
        """
        import re
        # 匹配 weather.com.cn/weather/数字.shtml 格式
        match = re.search(r'weather\.com\.cn/weather/(\d{9})\.shtml', url)
        if match:
            return match.group(1)
        return None

    def _parse_weather_with_llm(self, area_name: str, search_result: dict) -> Optional[dict]:
        """
        使用LLM解析搜索结果并提取天气信息

        Args:
            area_name: 地区名称
            search_result: 搜索API返回的结果，格式为：
                {
                    "searchParameters": {...},
                    "results": [
                        {
                            "title": "...",
                            "link": "https://www.weather.com.cn/weather/101281001.shtml",
                            "snippet": "天气信息摘要"
                        }
                    ]
                }

        Returns:
            包含天气信息的字典，失败返回 None
        """
        try:
            # 提取搜索结果
            results = search_result.get('results', [])

            if not results:
                logger.error("搜索结果为空")
                return None

            # 首先从搜索结果中提取天气编码
            weather_code = None
            weather_url = None

            for result in results:
                link = result.get('link', '')
                if 'weather.com.cn' in link:
                    weather_code = self._extract_weather_code_from_url(link)
                    if weather_code:
                        weather_url = link
                        logger.info(f"✅ 从搜索结果提取到天气编码: {weather_code}")
                        break

            # 构建用于LLM的搜索结果文本
            search_text = "搜索结果：\n"
            for i, result in enumerate(results, 1):
                search_text += f"\n结果{i}：\n"
                search_text += f"标题: {result.get('title', '')}\n"
                search_text += f"链接: {result.get('link', '')}\n"
                search_text += f"摘要: {result.get('snippet', '')}\n"

            # 构造prompt让LLM提取天气信息
            prompt = f"""请从以下搜索结果中提取"{area_name}"的天气信息，并严格按照以下JSON格式返回：

{{
    "region": "完整地区名称（必须包含市/县，如：北京市、上海市、湛江市、深圳市）",
    "province": "所属省份（直辖市填写自身名称，如：北京市、广东省、海南省）",
    "region_type": "地区类型（只能是以下之一：直辖市、省会城市、地级市、县级市）",
    "temperature": "温度范围（格式：XX℃ ~ XX℃，如：22℃ ~ 27℃）",
    "weather_condition": "天气状况（如：晴、多云、小雨、中雨、大雨、雷阵雨等）",
    "weather_info": "完整天气描述（基于搜索结果的snippet整理出详细的天气信息，包括温度、天气、风力等）",
    "advice": "生活建议（根据天气状况给出2-3条实用建议，包含：穿衣建议、出行建议、健康建议）"
}}

{search_text}

⚠️ 重要要求：
1. 只返回JSON对象，不要包含任何其他文字、解释或markdown标记
2. region 必须是完整的地区名称，包含"市"或"县"
3. province 必须准确判断所属省份
4. region_type 必须准确判断（例如：湛江是广东省的地级市）
5. 从snippet中提取温度信息，格式化为 XX℃ ~ XX℃
6. weather_info 要综合snippet的信息，描述清晰
7. advice 必须根据实际天气情况生成实用建议
8. 不要在任何文字中添加引用标记如[1]、[2]等

立即返回JSON："""

            logger.info(f"🤖 使用LLM解析天气信息...")

            # 调用LLM
            response = self.llm.invoke(prompt)
            response_text = response.content.strip()

            # 提取JSON
            json_text = response_text
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].split("```")[0].strip()

            # 解析JSON
            weather_data = json.loads(json_text.strip())

            # 将天气编码添加到结果中
            if weather_code:
                weather_data['weather_code'] = weather_code
            else:
                weather_data['weather_code'] = "未找到"
                logger.warning("⚠️ 未能从搜索结果中提取到天气编码")

            # 验证必要字段
            required_fields = ['region', 'temperature', 'weather_condition']
            missing_fields = [field for field in required_fields if not weather_data.get(field)]

            if missing_fields:
                logger.warning(f"⚠️ 部分关键字段缺失: {missing_fields}")

            logger.info(f"✅ 成功解析 {weather_data.get('region')} 的天气数据")
            logger.info(f"   省份: {weather_data.get('province')}, 类型: {weather_data.get('region_type')}, 编码: {weather_data.get('weather_code')}")

            return weather_data

        except json.JSONDecodeError as e:
            logger.error(f"❌ 解析LLM返回的JSON失败: {e}")
            logger.error(f"原始响应: {response_text if 'response_text' in locals() else '无'}")
            return None
        except Exception as e:
            logger.error(f"❌ 使用LLM解析天气信息时出错: {e}", exc_info=True)
            return None

    def _save_area_info_to_db(self, weather_data: dict) -> bool:
        """
        将地区信息保存到数据库（使用参数化查询防止 SQL 注入）

        Args:
            weather_data: 包含地区信息的字典

        Returns:
            保存成功返回 True，否则返回 False
        """
        try:
            region = weather_data.get('region', '')
            weather_code = weather_data.get('weather_code', '')
            province = weather_data.get('province', '')
            region_type = weather_data.get('region_type', '地级市')

            # 验证必要字段
            if not region or not weather_code or weather_code == "未找到":
                logger.warning(f"地区信息不完整，跳过保存: region={region}, weather_code={weather_code}")
                return False

            # 先检查是否已存在（使用参数化查询）
            check_query = """
            SELECT COUNT(*) as count
            FROM weather_regions
            WHERE region = :region OR weather_code = :weather_code
            """
            check_result = self.sql_db.run_query_safe(check_query, {
                "region": region,
                "weather_code": weather_code
            })

            # 解析计数结果
            count = check_result[0]['count'] if check_result else 0

            if count > 0:
                logger.info(f"地区 '{region}' 或编码 '{weather_code}' 已存在于数据库中")
                return False

            # 执行插入（使用参数化查询）
            insert_query = """
            INSERT INTO weather_regions (region, weather_code, province, region_type)
            VALUES (:region, :weather_code, :province, :region_type)
            """
            self.sql_db.run_query_safe(insert_query, {
                "region": region,
                "weather_code": weather_code,
                "province": province,
                "region_type": region_type
            })
            logger.info(f"✅ 成功保存地区信息: {region} ({region_type}), 编码: {weather_code}, 省份: {province}")
            return True

        except Exception as e:
            logger.error(f"保存地区信息到数据库时发生错误: {e}", exc_info=True)
            return False

    def _run(self, area_name: str) -> str:
        """
        执行天气查询

        流程：
        1. 调用外部搜索API获取天气相关信息
        2. 使用LLM解析搜索结果，提取结构化天气信息
        3. 保存地区信息到数据库
        4. 返回格式化的天气信息（不包含数据来源）
        """
        try:
            # 调用搜索API
            search_result = self._call_search_api(area_name)

            if not search_result:
                return f"抱歉，无法获取地区 '{area_name}' 的天气信息。请稍后重试。"

            # 使用LLM解析搜索结果
            weather_data = self._parse_weather_with_llm(area_name, search_result)

            if not weather_data:
                return f"抱歉，无法解析地区 '{area_name}' 的天气信息。"

            # 提取信息
            region = weather_data.get('region', area_name)
            weather_info = weather_data.get('weather_info', '')
            temperature = weather_data.get('temperature', '')
            weather_condition = weather_data.get('weather_condition', '')
            advice = weather_data.get('advice', '')

            # 尝试保存地区信息到数据库
            saved = self._save_area_info_to_db(weather_data)
            if saved:
                logger.info(f"💾 已保存 {region} 的信息到数据库")

            # 构建响应消息 - 只包含文字信息，不显示数据来源
            result = f"\n📍 {region} 天气情况\n"
            result += "=" * 50 + "\n"
            result += f"🌡️  温度: {temperature}\n"
            result += f"☁️  天气: {weather_condition}\n"

            if weather_info:
                # 清理天气信息中的引用标记 [数字]
                clean_weather_info = re.sub(r'\[\d+\]', '', weather_info)
                clean_weather_info = re.sub(r'\s+', ' ', clean_weather_info).strip()
                result += f"\n📝 详细信息:\n{clean_weather_info}\n"

            if advice:
                # 清理建议中的引用标记
                clean_advice = re.sub(r'\[\d+\]', '', advice)
                clean_advice = re.sub(r'\s+', ' ', clean_advice).strip()
                result += f"\n💡 生活建议:\n{clean_advice}\n"

            result += "=" * 50

            return result

        except Exception as e:
            logger.error(f"查询天气信息时发生错误: {e}", exc_info=True)
            return f"查询天气信息时发生错误: {str(e)}"

    async def _arun(self, area_name: str) -> str:
        """异步执行天气查询"""
        return self._run(area_name)

# 工具实例化函数
def create_weather_tool(
    llm: BaseChatModel,
    sql_db: LangChainSQLDatabase = None,
    config: ConfigManager = None,
    search_api_key: str = None,
    search_api_url: str = None
):
    """
    创建天气查询工具实例。

    Args:
        llm: ChatModel 实例（必需，用于解析天气信息）
        sql_db: LangChainSQLDatabase 实例（可选，如果不提供则自动创建）
        config: ConfigManager 实例（可选，如果不提供则自动创建）
        search_api_key: 搜索 API Key（可选，优先使用）
        search_api_url: 搜索 API URL（可选，默认 https://api.302.ai/search1api/search）

    Returns:
        WeatherTool实例,如果初始化失败则返回 None。
    """
    if llm is None:
        logger.error("必须提供 LLM 实例，无法创建 WeatherTool。")
        return None

    if LangChainSQLDatabase is None or ConfigManager is None:
        logger.error("必要模块未成功导入,无法创建 WeatherTool 实例。")
        return None

    try:
        # 如果没有提供 sql_db，则创建一个新的
        if sql_db is None:
            sql_db = LangChainSQLDatabase()
            logger.info("创建新的 LangChainSQLDatabase 实例")

        # 如果没有提供 config，则创建一个新的
        if config is None:
            config = ConfigManager()
            logger.info("创建新的 ConfigManager 实例")

        logger.info("✅ 使用外部搜索API和LLM创建 WeatherTool")

        return WeatherTool(
            sql_db=sql_db,
            llm=llm,
            config=config,
            search_api_key=search_api_key,  # 传递搜索 API Key
            search_api_url=search_api_url   # 传递搜索 URL
        )

    except Exception as e:
        logger.critical(f"初始化 WeatherTool 失败: {e}", exc_info=True)
        return None
