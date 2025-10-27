"""
智能天气助手 - 基于 LangChain SQL Agent

核心特性:
1. 使用 create_sql_agent 创建 SQL Agent，支持自然语言直接查询数据库
2. 集成 QuerySQLDataBaseTool、InfoSQLDatabaseTool、ListSQLDatabaseTool 和 WeatherTool
3. Agent 可以自主决定何时查询数据库、何时调用天气工具
4. 支持复杂的多轮对话和组合查询
"""

import logging
from typing import List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_openai import ChatOpenAI

# LangChain SQL Agent 相关导入
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.tools.sql_database.tool import (
    QuerySQLDataBaseTool,
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
)

import sys
import os

# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..')
project_root = os.path.abspath(project_root)
sys.path.insert(0, project_root)

# 导入配置管理器和工具
from Config_Manager import ConfigManager
import Weather_Service
from database.sql_database_wrapper import LangChainSQLDatabase

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DialogueService:
    """
    基于 LangChain SQL Agent 的智能对话服务

    架构优势：
    1. Agent 可以自主查询数据库表结构
    2. 支持复杂的自然语言数据库查询（如："有多少个直辖市？"）
    3. 与 WeatherTool 协同工作，提供天气查询能力
    """

    def __init__(self):
        """
        初始化对话服务
        """
        self.config = ConfigManager()

        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=self.config.model,
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            temperature=0  # SQL Agent 建议使用低温度以提高准确性
        )

        # 初始化数据库
        try:
            self.sql_db = LangChainSQLDatabase()
            logger.info("✅ LangChain SQLDatabase 初始化成功")
        except Exception as e:
            logger.error(f"❌ SQLDatabase 初始化失败: {e}")
            raise RuntimeError("数据库初始化失败，无法启动服务")

        # 初始化 SQL Agent
        self._setup_agent()

    def _setup_agent(self):
        """
        设置 SQL Agent

        功能：
        - 自然语言查询数据库
        - 查看表结构
        - 列出所有表
        - 调用天气工具
        """
        logger.info("🚀 初始化 SQL Agent")

        # 创建 SQL 相关工具
        sql_tools = [
            QuerySQLDataBaseTool(db=self.sql_db.get_db_instance()),  # SQL 查询工具
            InfoSQLDatabaseTool(db=self.sql_db.get_db_instance()),   # 表结构查询工具
            ListSQLDatabaseTool(db=self.sql_db.get_db_instance()),   # 列出表名工具
        ]

        # 创建天气工具
        weather_tool = Weather_Service.create_weather_tool()
        if weather_tool:
            all_tools = sql_tools + [weather_tool]
        else:
            logger.warning("⚠️ WeatherTool 初始化失败，仅使用 SQL 工具")
            all_tools = sql_tools

        # 设置系统提示词
        system_prefix = """你是一个智能天气助手，具有以下能力：

1. **数据库查询**: 你可以直接查询 weather_regions 表来获取地区天气编码信息
   - 表结构: region(地区名), weather_code(编码), province(省份), region_type(类型)

2. **天气查询**: 使用 weather_query 工具获取具体天气信息

3. **智能决策**:
   - 当用户问"有多少个XX"时，使用 SQL 查询
   - 当用户问"XX天气"时，使用 weather_query 工具
   - 可以组合使用多个工具完成复杂任务

回答时要自然、友好，气温后加℃符号。
"""

        # 创建 SQL Agent
        self.agent_executor = create_sql_agent(
            llm=self.llm,
            db=self.sql_db.get_db_instance(),
            agent_type="tool-calling",  # 使用支持工具调用的 Agent
            verbose=True,
            extra_tools=[weather_tool] if weather_tool else [],
            prefix=system_prefix,
            handle_parsing_errors=True
        )

        logger.info(f"✅ SQL Agent 创建成功，工具数量: {len(all_tools)}")

    def run_conversation(self, user_input: str, chat_history: List[Tuple[str, str]] = None) -> str:
        """
        运行一次对话

        Args:
            user_input: 用户输入
            chat_history: 历史对话（可选，暂不使用但保留接口）

        Returns:
            AI 回复
        """
        try:
            # 使用 SQL Agent 执行对话
            response = self.agent_executor.invoke({"input": user_input})
            return response.get("output", "抱歉，我无法处理这个请求。")

        except Exception as e:
            logger.error(f"对话执行失败: {e}", exc_info=True)
            return "对不起，我在处理您的请求时遇到了问题。请稍后再试。"


# 主程序入口
if __name__ == "__main__":
    print("=" * 60)
    print("🌤️  智能天气助手")
    print("=" * 60)
    print("功能特性:")
    print("  1. 自然语言查询数据库（如：有多少个直辖市？）")
    print("  2. 天气查询（如：北京天气怎么样？）")
    print("  3. 复杂组合查询（如：查找所有省会城市并显示天气）")
    print()
    print("命令:")
    print("  'exit' 或 'quit' - 退出程序")
    print("  'clear' - 清除对话历史")
    print("=" * 60)
    print()

    # 初始化服务
    try:
        dialogue_service = DialogueService()
        chat_history = []
        print("\n✅ 服务已启动\n")

        while True:
            try:
                user_query = input("\n你: ")

                if not user_query.strip():
                    continue

                if user_query.lower() in ['exit', 'quit']:
                    print("\n👋 再见！")
                    break

                if user_query.lower() == 'clear':
                    chat_history = []
                    print("🗑️  对话历史已清除")
                    continue

                # 执行对话
                ai_response = dialogue_service.run_conversation(user_query, chat_history)
                print(f"\n🤖 AI: {ai_response}")

                # 更新历史
                chat_history.append((user_query, ai_response))

            except KeyboardInterrupt:
                print("\n\n👋 检测到 Ctrl+C，正在退出...")
                break

    except Exception as e:
        logger.critical(f"程序启动失败: {e}", exc_info=True)
        print(f"\n❌ 启动失败: {e}")

