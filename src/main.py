"""智能天气助手 - 基于 LangChain Agent"""

import logging
import sys
import os
from typing import List, Tuple

from langchain_openai import ChatOpenAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.tools.sql_database.tool import (
    QuerySQLDataBaseTool,
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
)

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from Config_Manager import ConfigManager
import Weather_Service
from database.sql_database_wrapper import LangChainSQLDatabase

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 常量配置
MAX_HISTORY_TURNS = 5
CACHE_KEY = "getweather-assistant-v2.1"
TEMPERATURE = 0.7
MAX_ITERATIONS = 5

# 系统提示词
SYSTEM_PROMPT = """你是智能天气助手"小天"，专注于提供准确的天气信息和贴心服务。

🎯 工具使用原则：

1. **普通对话** → 直接回答，不调用工具
   示例："你好"、"你是谁"、"谢谢"

2. **天气查询** → 优先复用历史数据，必要时调用 weather_query
   - 历史中已有天气数据 → 直接使用历史回答追问
   - 新地区或无历史数据 → 调用 weather_query 工具

   示例：
   用户："深圳天气怎么样？" → [调用工具] "深圳晴天，25-30℃"
   用户："温度高吗？" → [用历史] "最高30℃，比较温暖"
   用户："北京呢？" → [新地区，调用工具]

3. **数据库查询** → 使用 SQL 工具（省份必须用 LIKE 模糊匹配）
   示例："广东有哪些地级市？"
   SQL: SELECT region FROM weather_regions WHERE province LIKE '%广东%' AND region_type='地级市'

💡 交互原则：
- 自然友好，简洁明了
- 温度使用℃符号
- 理解上下文引用（记住最近5轮对话）
- 不要过度使用工具，优先复用历史数据
- 数据库查询结果用清晰语言总结"""


class DialogueService:
    """基于 LangChain Agent 的智能对话服务"""

    def __init__(self):
        self.config = ConfigManager()
        self.llm = self._init_llm()
        self.sql_db = self._init_database()
        self.agent_executor = self._setup_agent()

    def _init_llm(self) -> ChatOpenAI:
        """初始化 LLM，使用 prompt_cache_key 优化缓存"""
        return ChatOpenAI(
            model=self.config.model,
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            temperature=TEMPERATURE
        )

    def _init_database(self) -> LangChainSQLDatabase:
        """初始化数据库连接"""
        try:
            db = LangChainSQLDatabase()
            logger.info("✅ 数据库初始化成功")
            return db
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise RuntimeError("数据库初始化失败，无法启动服务")

    def _setup_agent(self) -> AgentExecutor:
        """设置 Agent 和工具"""
        logger.info("🚀 初始化智能 Agent")

        tools = []

        # 天气工具
        weather_tool = Weather_Service.create_weather_tool(
            llm=self.llm,
            sql_db=self.sql_db,
            config=self.config
        )
        if weather_tool:
            tools.append(weather_tool)
        else:
            logger.warning("⚠️ WeatherTool 初始化失败")

        # SQL 工具
        db_instance = self.sql_db.get_db_instance()
        tools.extend([
            QuerySQLDataBaseTool(db=db_instance),
            InfoSQLDatabaseTool(db=db_instance),
            ListSQLDatabaseTool(db=db_instance),
        ])

        # 创建提示词模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 创建 Agent
        agent = create_tool_calling_agent(self.llm, tools, prompt)

        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=MAX_ITERATIONS
        )

        logger.info(f"✅ Agent 创建成功，工具数量: {len(tools)}")
        return executor

    def run_conversation(self, user_input: str, chat_history: List[Tuple[str, str]] = None) -> str:
        """运行对话"""
        try:
            history_messages = self._convert_history(chat_history)

            response = self.agent_executor.invoke({
                "input": user_input,
                "chat_history": history_messages,
                "prompt_cache_key": CACHE_KEY
            })

            return response.get("output", "抱歉，我无法处理这个请求。")

        except Exception as e:
            logger.error(f"对话执行失败: {e}", exc_info=True)
            return "对不起，我在处理您的请求时遇到了问题。请稍后再试。"

    @staticmethod
    def _convert_history(chat_history: List[Tuple[str, str]]) -> List:
        """将对话历史转换为 LangChain 消息格式"""
        if not chat_history:
            return []

        messages = []
        for user_msg, ai_msg in chat_history:
            messages.append(HumanMessage(content=user_msg))
            messages.append(AIMessage(content=ai_msg))
        return messages


def print_welcome():
    """打印欢迎信息"""
    print("\n" + "=" * 60)
    print("🌤️  智能天气助手 - 小天")
    print("=" * 60)
    print("\n✨ 功能介绍:")
    print("  📊 自然语言查询数据库")
    print("  🌡️  智能天气查询")
    print("  💡 提供出行建议")
    print("\n📌 使用提示:")
    print("  • 直接输入问题，智能理解并回答")
    print("  • exit/quit - 退出程序")
    print("  • clear - 清除对话历史")
    print("  • help - 查看帮助信息")
    print("=" * 60 + "\n")


def print_help():
    """打印帮助信息"""
    print("\n" + "=" * 60)
    print("📖 帮助信息")
    print("=" * 60)
    print("\n🔹 天气查询示例:")
    print("  • 北京天气怎么样？")
    print("  • 上海今天的天气")
    print("  • 广州需要带伞吗？")
    print("\n🔹 数据查询示例:")
    print("  • 有多少个直辖市？")
    print("  • 列出所有省会城市")
    print("  • 广东省有哪些地级市？")
    print("\n🔹 上下文对话示例:")
    print("  • 你：北京天气怎么样？")
    print("  • 我：[回复天气信息]")
    print("  • 你：那上海呢？（我会记住你在问天气）")
    print(f"\n💭 提示：我会记住最近 {MAX_HISTORY_TURNS} 轮对话的上下文")
    print("=" * 60 + "\n")


def handle_user_command(command: str, chat_history: List) -> Tuple[bool, List]:
    """
    处理用户命令

    Returns:
        (should_exit, updated_history)
    """
    cmd = command.lower()

    if cmd in ['exit', 'quit', '退出']:
        print("\n👋 小天：再见！祝您生活愉快！")
        return True, chat_history

    if cmd in ['clear', '清除']:
        print("✅ 对话历史已清除\n")
        return False, []

    if cmd in ['help', '帮助']:
        print_help()
        return False, chat_history

    return False, chat_history


def main():
    """主程序入口"""
    print_welcome()

    try:
        dialogue_service = DialogueService()
        chat_history = []
        print("✅ 小天已上线，随时为您服务！\n")

        while True:
            try:
                user_query = input("🧑 你: ").strip()

                if not user_query:
                    continue

                # 处理命令
                should_exit, chat_history = handle_user_command(user_query, chat_history)
                if should_exit:
                    break

                # 如果是命令，已经处理完毕，继续下一轮
                if user_query.lower() in ['help', '帮助', 'clear', '清除']:
                    continue

                # 执行对话
                print("\n🤖 小天: ", end="", flush=True)
                ai_response = dialogue_service.run_conversation(user_query, chat_history)
                print(ai_response + "\n")

                # 更新历史
                chat_history.append((user_query, ai_response))
                if len(chat_history) > MAX_HISTORY_TURNS:
                    chat_history = chat_history[-MAX_HISTORY_TURNS:]

            except KeyboardInterrupt:
                print("\n\n👋 检测到 Ctrl+C，小天正在退出...")
                break
            except Exception as e:
                logger.error(f"对话过程出错: {e}", exc_info=True)
                print(f"\n❌ 抱歉，处理您的请求时出现了问题：{str(e)}\n")

    except Exception as e:
        logger.critical(f"程序启动失败: {e}", exc_info=True)
        print(f"\n❌ 启动失败: {e}")
        print("\n💡 请检查:")
        print("  1. 数据库连接是否正常")
        print("  2. .env 配置文件是否正确")
        print("  3. API_KEY 是否有效")


if __name__ == "__main__":
    main()
