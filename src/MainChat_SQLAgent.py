"""
升级版对话服务 - 集成 LangChain SQL Agent

新特性:
1. 使用 create_sql_agent 创建 SQL Agent，支持自然语言直接查询数据库
2. 集成 QuerySQLDataBaseTool 和 WeatherTool，双工具协同
3. Agent 可以自主决定何时查询数据库、何时调用天气工具
4. 更强大的多轮对话能力

对比传统版本：
- 传统版本：只能通过 WeatherTool 间接访问数据库
- SQL Agent 版本：可以直接用自然语言查询数据库 + 调用天气工具
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


class SQLAgentDialogueService:
    """
    基于 LangChain SQL Agent 的高级对话服务

    架构优势：
    1. Agent 可以自主查询数据库表结构
    2. 支持复杂的自然语言数据库查询（如："有多少个直辖市？"）
    3. 与 WeatherTool 协同工作
    """

    def __init__(self, use_sql_agent: bool = True):
        """
        初始化对话服务

        Args:
            use_sql_agent: 是否使用 SQL Agent（True=高级模式，False=传统模式）
        """
        self.config = ConfigManager()
        self.use_sql_agent = use_sql_agent

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
            self.sql_db = None

        # 初始化工具和 Agent
        if self.use_sql_agent and self.sql_db:
            self._setup_sql_agent()
        else:
            self._setup_traditional_agent()

    def _setup_sql_agent(self):
        """
        设置 SQL Agent 模式（高级模式）

        功能：
        - 自然语言查询数据库
        - 查看表结构
        - 列出所有表
        - 调用天气工具
        """
        logger.info("🚀 初始化 SQL Agent 模式")

        # 创建 SQL 相关工具
        sql_tools = [
            QuerySQLDataBaseTool(db=self.sql_db.get_db_instance()),  # SQL 查询工具
            InfoSQLDatabaseTool(db=self.sql_db.get_db_instance()),   # 表结构查询工具
            ListSQLDatabaseTool(db=self.sql_db.get_db_instance()),   # 列出表名工具
        ]

        # 创建天气工具
        weather_tool = Weather_Service.create_weather_tool(use_langchain_sql=True)
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

    def _setup_traditional_agent(self):
        """
        设置传统 Agent 模式（兼容旧版）
        """
        logger.info("📦 初始化传统 Agent 模式")

        # 初始化 WeatherTool
        self.weather_tool = Weather_Service.create_weather_tool(use_langchain_sql=False)
        if not self.weather_tool:
            logger.error("❌ 天气工具初始化失败")
            self.tools = []
        else:
            self.tools = [self.weather_tool]

        # 设置系统提示词
        self.system_prompt = "你是一个可以实时查询天气的AI助手。当用户询问天气时，使用提供的工具获取最新信息，并在气温后面加上℃让回答更美观。"

        # 创建 Prompt Template
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        # 创建传统 Agent
        self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )

        logger.info("✅ 传统 Agent 创建成功")

    def run_conversation(self, user_input: str, chat_history: List[Tuple[str, str]] = None) -> str:
        """
        运行一次对话

        Args:
            user_input: 用户输入
            chat_history: 历史对话（可选）

        Returns:
            AI 回复
        """
        if chat_history is None:
            chat_history = []

        # 将历史对话转换为 LangChain 消息格式
        formatted_chat_history = []
        for human_msg, ai_msg in chat_history:
            formatted_chat_history.append(HumanMessage(content=human_msg))
            formatted_chat_history.append(AIMessage(content=ai_msg))

        try:
            # SQL Agent 模式
            if self.use_sql_agent:
                # SQL Agent 使用 input 参数
                response = self.agent_executor.invoke({"input": user_input})
                return response.get("output", "抱歉，我无法处理这个请求。")

            # 传统模式
            else:
                response = self.agent_executor.invoke(
                    {"input": user_input, "chat_history": formatted_chat_history}
                )
                return response["output"]

        except Exception as e:
            logger.error(f"对话执行失败: {e}", exc_info=True)
            return "对不起，我在处理您的请求时遇到了问题。请稍后再试。"


# 主程序入口
if __name__ == "__main__":
    print("=" * 60)
    print("🌤️  AI 天气助手 - SQL Agent 版本")
    print("=" * 60)
    print("功能特性:")
    print("  1. 自然语言查询数据库（如：有多少个直辖市？）")
    print("  2. 天气查询（如：北京天气怎么样？）")
    print("  3. 复杂组合查询（如：查找所有省会城市并显示天气）")
    print()
    print("命令:")
    print("  'exit' 或 'quit' - 退出程序")
    print("  'clear' - 清除对话历史")
    print("  'mode' - 切换 Agent 模式")
    print("=" * 60)
    print()

    # 用户选择模式
    mode_choice = input("选择模式 (1=SQL Agent 高级模式, 2=传统模式) [默认:1]: ").strip()
    use_sql_agent = mode_choice != "2"

    # 初始化服务
    try:
        dialogue_service = SQLAgentDialogueService(use_sql_agent=use_sql_agent)
        chat_history = []

        mode_name = "SQL Agent 高级模式" if use_sql_agent else "传统模式"
        print(f"\n✅ {mode_name} 已启动\n")

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

                if user_query.lower() == 'mode':
                    print(f"📊 当前模式: {mode_name}")
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
