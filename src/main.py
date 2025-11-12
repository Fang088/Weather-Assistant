"""智能天气助手 - 基于 LangChain Agent"""

import logging
import sys
import os
from typing import List, Tuple

from langchain_openai import ChatOpenAI
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.tools.sql_database.tool import (
    QuerySQLDatabaseTool,
    InfoSQLDatabaseTool,
    ListSQLDatabaseTool,
)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from Config_Manager import ConfigManager
import Weather_Service
from database.sql_database_wrapper import LangChainSQLDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 5
CACHE_KEY = "getweather-assistant-v2.1"
TEMPERATURE = 0.7
MAX_ITERATIONS = 8  # 从 5 增加到 8，支持更复杂的查询

SYSTEM_PROMPT = """你是智能天气助手"小天"，专注于提供准确的天气信息和贴心服务。

🎯 **场景识别与工具选择 (重要!)**

📌 场景 1: 普通对话 → 不调用任何工具
识别特征: 问候、感谢、闲聊、询问身份
✅ 正例:
  - "你好" → 直接回答: "你好! 我是小天..."
  - "谢谢" → 直接回答: "不客气!..."
  - "你是谁" → 直接回答: "我是智能天气助手小天..."
❌ 反例:
  - "你好" → ❌ 不要调用任何工具
  - "谢谢" → ❌ 不要查询数据库

📌 场景 2: 天气查询 → 调用 weather_query 工具
识别特征: 包含"天气"、"温度"、"下雨"、"气温"等关键词 + 地名
✅ 正例:
  - "北京天气怎么样?" → 调用 weather_query(area_name="北京")
  - "上海会下雨吗?" → 调用 weather_query(area_name="上海")
  - "深圳今天气温多少?" → 调用 weather_query(area_name="深圳")

🔄 上下文引用处理:
  - "那上海呢?" (前一轮问了北京天气) → 调用 weather_query(area_name="上海")
  - "广州的呢?" (前一轮问了天气) → 调用 weather_query(area_name="广州")

⚡ 优化策略:
  - 如果最近 2 轮内已查询过该地区天气 → 直接引用历史回答
  - 否则 → 调用 weather_query 工具

📌 场景 3: 数据库查询 → 调用 SQL 工具
识别特征: 统计、列出、查询地区数量/类型，不涉及天气
✅ 正例:
  - "有多少个直辖市?" → sql_db_query("SELECT COUNT(*) FROM weather_regions WHERE region_type='直辖市'")
  - "广东省有哪些地级市?" → sql_db_query("SELECT region FROM weather_regions WHERE province LIKE '%广东%' AND region_type='地级市'")
  - "列出所有省会城市" → sql_db_query("SELECT region FROM weather_regions WHERE region_type='省会城市'")

⚠️ SQL 安全规则:
  - 省份/地区名称必须用 LIKE 模糊匹配: province LIKE '%广东%'
  - 只执行 SELECT 查询，禁止 INSERT/UPDATE/DELETE
  - 查询结果用自然语言总结，不要直接输出原始数据

💡 **效率优先原则**
1. 优先复用最近 2 轮内的历史数据
2. 单次对话工具调用不超过 3 次
3. 如果 3 次调用后仍无法回答 → 礼貌告知用户并建议换个问法

💡 **交互规范**
- 自然友好，简洁明了 (避免冗长解释)
- 温度统一使用℃符号
- 理解上下文引用 (记住最近对话)
- 数据库查询结果用清晰语言总结

❌ **禁止行为**
- 不要为普通对话调用工具 (浪费资源)
- 不要重复查询已有的天气数据 (检查历史)
- 不要执行非 SELECT 的 SQL 语句 (安全风险)
- 不要输出原始 SQL 语句给用户 (用户体验差)"""


class DialogueService:
    """基于 LangChain Agent 的智能对话服务"""

    def __init__(self, api_key: str = None):
        self.config = ConfigManager()
        self.api_key = api_key or self.config.api_key
        self.llm = self._init_llm()
        self.sql_db = self._init_database()
        self.agent_executor = self._setup_agent()

    def _init_llm(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.config.model,
            base_url=self.config.base_url,
            api_key=self.api_key,
            temperature=TEMPERATURE
        )

    def _init_database(self) -> LangChainSQLDatabase:
        try:
            db = LangChainSQLDatabase()
            logger.info("✅ 数据库初始化成功")
            return db
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")
            raise

    def _setup_agent(self) -> AgentExecutor:
        logger.info("🚀 初始化 Agent")

        tools = []

        # 天气工具
        weather_tool = Weather_Service.create_weather_tool(
            llm=self.llm,
            sql_db=self.sql_db,
            config=self.config,
            search_api_key=self.api_key,
            search_api_url=self.config.search_api_url
        )
        if weather_tool:
            tools.append(weather_tool)

        # SQL 工具
        db_instance = self.sql_db.get_db_instance()
        tools.extend([
            QuerySQLDatabaseTool(db=db_instance),
            InfoSQLDatabaseTool(db=db_instance),
            ListSQLDatabaseTool(db=db_instance),
        ])

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self.llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=MAX_ITERATIONS
        )

        logger.info(f"✅ Agent 创建成功，工具数: {len(tools)}")
        return executor

    def run_conversation(self, user_input: str, chat_history: List[Tuple[str, str]] = None) -> str:
        try:
            # 智能压缩历史记录，减少 Token 消耗
            compressed_history = self._compress_history(chat_history)
            history_messages = self._convert_history(compressed_history)

            response = self.agent_executor.invoke({
                "input": user_input,
                "chat_history": history_messages,
                "prompt_cache_key": CACHE_KEY
            })
            return response.get("output", "抱歉，我无法处理这个请求。")
        except Exception as e:
            logger.error(f"对话失败: {e}", exc_info=True)
            return "对不起，我在处理您的请求时遇到了问题。请稍后再试。"

    @staticmethod
    def _compress_history(chat_history: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        智能压缩历史记录，优先保留重要上下文

        策略:
        1. 保留最近 2 轮完整对话 (用于上下文引用)
        2. 之前的对话进行摘要压缩 (只保留关键信息)
        3. 过滤掉无关对话 (问候、感谢等)

        Returns:
            压缩后的历史记录
        """
        if not chat_history or len(chat_history) <= 2:
            return chat_history  # 少于 2 轮，直接返回

        # 无关对话关键词 (用于过滤)
        trivial_keywords = ["你好", "谢谢", "再见", "不客气", "没事", "好的", "嗯", "哦"]

        # 分离最近 2 轮和历史对话
        recent_history = chat_history[-2:]  # 最近 2 轮完整保留
        old_history = chat_history[:-2]     # 之前的对话

        # 压缩旧对话 (只保留重要的)
        compressed_old = []
        for user_msg, ai_msg in old_history:
            # 过滤无关对话
            if any(keyword in user_msg for keyword in trivial_keywords):
                continue  # 跳过问候、感谢等

            # 压缩冗长的回答 (保留前 100 字符)
            if len(ai_msg) > 150:
                ai_msg_compressed = ai_msg[:100] + "..."
            else:
                ai_msg_compressed = ai_msg

            compressed_old.append((user_msg, ai_msg_compressed))

        # 最多保留 2 轮压缩后的旧对话 + 2 轮完整的最近对话
        max_old_turns = 2
        if len(compressed_old) > max_old_turns:
            compressed_old = compressed_old[-max_old_turns:]

        # 合并: 压缩的旧对话 + 完整的最近对话
        result = compressed_old + recent_history

        logger.debug(f"📊 历史压缩: {len(chat_history)} 轮 → {len(result)} 轮 (节省 {len(chat_history) - len(result)} 轮)")
        return result

    @staticmethod
    def _convert_history(chat_history: List[Tuple[str, str]]) -> List:
        if not chat_history:
            return []
        messages = []
        for user_msg, ai_msg in chat_history:
            messages.append(HumanMessage(content=user_msg))
            messages.append(AIMessage(content=ai_msg))
        return messages


def print_welcome():
    print("\n" + "="*60)
    print("🌤️  智能天气助手 - 小天")
    print("="*60)
    print("\n✨ 功能：")
    print("  📊 自然语言查询数据库")
    print("  🌡️  智能天气查询")
    print("\n📌 命令：")
    print("  exit/quit - 退出程序")
    print("  clear - 清除对话历史")
    print("  help - 查看帮助")
    print("="*60 + "\n")


def print_help():
    print("\n" + "="*60)
    print("📖 帮助信息")
    print("="*60)
    print("\n🔹 天气查询示例：")
    print("  • 北京天气怎么样？")
    print("  • 上海需要带伞吗？")
    print("\n🔹 数据查询示例：")
    print("  • 有多少个直辖市？")
    print("  • 广东省有哪些地级市？")
    print(f"\n💭 提示：记住最近 {MAX_HISTORY_TURNS} 轮对话")
    print("="*60 + "\n")


def handle_user_command(command: str, chat_history: List) -> Tuple[bool, List]:
    cmd = command.lower()

    if cmd in ['exit', 'quit', '退出']:
        print("\n👋 再见！")
        return True, chat_history

    if cmd in ['clear', '清除']:
        print("✅ 对话历史已清除\n")
        return False, []

    if cmd in ['help', '帮助']:
        print_help()
        return False, chat_history

    return False, chat_history


def main():
    print_welcome()

    try:
        dialogue_service = DialogueService()
        chat_history = []
        print("✅ 小天已上线！\n")

        while True:
            try:
                user_query = input("🧑 你: ").strip()
                if not user_query:
                    continue

                should_exit, chat_history = handle_user_command(user_query, chat_history)
                if should_exit:
                    break

                if user_query.lower() in ['help', '帮助', 'clear', '清除']:
                    continue

                print("\n🤖 小天: ", end="", flush=True)
                ai_response = dialogue_service.run_conversation(user_query, chat_history)
                print(ai_response + "\n")

                chat_history.append((user_query, ai_response))
                if len(chat_history) > MAX_HISTORY_TURNS:
                    chat_history = chat_history[-MAX_HISTORY_TURNS:]

            except KeyboardInterrupt:
                print("\n\n👋 Ctrl+C 退出...")
                break
            except Exception as e:
                logger.error(f"对话出错: {e}", exc_info=True)
                print(f"\n❌ 处理出错：{str(e)}\n")

    except Exception as e:
        logger.critical(f"启动失败: {e}", exc_info=True)
        print(f"\n❌ 启动失败: {e}")


if __name__ == "__main__":
    main()
