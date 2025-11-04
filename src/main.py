"""
智能天气助手 - 基于 LangChain Agent

核心特性:
1. 使用智能Agent，根据问题类型选择合适的工具
2. 普通对话和天气查询使用LLM直接回答和联网搜索
3. 只在查询地级市等数据库相关信息时才使用SQL工具
4. 支持复杂的多轮对话和组合查询
"""

import logging
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
    基于 LangChain Agent 的智能对话服务

    架构优势：
    1. 智能识别问题类型，按需选择工具
    2. 普通对话直接由LLM回答，不调用工具
    3. 天气查询使用WeatherTool联网搜索
    4. 数据库查询（如地级市统计）才使用SQL工具
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
            temperature=0.7  # 适中的温度，既保证准确性又有一定灵活性
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
        设置智能 Agent

        功能：
        - 普通对话直接回答，不使用工具
        - 天气查询使用 weather_query 工具
        - 数据库统计查询使用 SQL 工具
        """
        logger.info("🚀 初始化智能 Agent")

        # 创建工具列表
        tools = []

        # 创建天气工具（传入LLM实例、数据库实例和配置实例）
        weather_tool = Weather_Service.create_weather_tool(llm=self.llm, sql_db=self.sql_db, config=self.config)
        if weather_tool:
            tools.append(weather_tool)
        else:
            logger.warning("⚠️ WeatherTool 初始化失败")

        # 创建 SQL 相关工具
        sql_tools = [
            QuerySQLDataBaseTool(db=self.sql_db.get_db_instance()),  # SQL 查询工具
            InfoSQLDatabaseTool(db=self.sql_db.get_db_instance()),   # 表结构查询工具
            ListSQLDatabaseTool(db=self.sql_db.get_db_instance()),   # 列出表名工具
        ]
        tools.extend(sql_tools)

        # 设置系统提示词 - 关键优化点
        prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个智能天气助手，名字叫"小天"，专注于为用户提供准确的天气信息和贴心的服务。

🎯 工具使用原则（非常重要）：

**场景1：普通对话问题 → 直接回答，不使用任何工具**
   示例："你好"、"你是谁"、"今天心情不错"、"谢谢"、"再见"
   处理：直接用你的知识友好回复，不要调用任何工具

**场景2：天气查询问题 → 只使用 weather_query 工具**
   示例："北京天气怎么样"、"上海需要带伞吗"、"深圳今天温度"、"广州下雨吗"
   处理：
   - 直接调用 weather_query 工具获取实时天气
   - 天气查询工具会自动调用搜索API并使用AI整理信息
   - 你只需要将工具返回的结果转述给用户即可

**场景3：数据库统计问题 → 使用 SQL 相关工具（支持模糊查询）**
   示例问题：
   - "有多少个直辖市"
   - "列出所有省会城市"
   - "广东省有哪些地级市" / "广东地级市" / "查询广东的地级市"
   - "浙江省有多少个城市"
   - "数据库里有哪些城市"

   处理策略：
   1. 使用 sql_db_schema 或 sql_db_list_tables 了解表结构
   2. 使用 sql_db_query 执行SQL查询
   3. 数据库表：weather_regions(region, weather_code, province, region_type)

   🔍 模糊查询技巧（重要！）：
   - 查询某个省份的地区时，使用 LIKE 模糊匹配
   - province 字段可能是 "广东" 或 "广东省"，需要用 LIKE '%广东%'
   - 示例SQL：
     * 查询广东省地级市：
       SELECT region, region_type FROM weather_regions
       WHERE province LIKE '%广东%' AND region_type = '地级市'

     * 查询浙江省所有城市：
       SELECT region, region_type FROM weather_regions
       WHERE province LIKE '%浙江%'

     * 统计某省城市数量：
       SELECT COUNT(*) as count FROM weather_regions
       WHERE province LIKE '%广东%'

   ⚠️ 注意事项：
   - 始终使用 LIKE '%省份名%' 进行省份匹配（不要用 province = '广东'）
   - region_type 字段值：直辖市、省会城市、地级市、县级市
   - 查询结果要用友好的语言总结，列出清单

💡 交互原则：
- 回答要自然、友好、简洁明了
- 温度后统一使用℃符号
- 对于数据库查询结果，用清晰的语言总结（如：列表形式、数量统计等）
- 如果用户问题不明确，友好地请求澄清
- 你可以访问最近5轮对话的上下文，理解上下文引用（如"那上海呢？"）

📋 重要提醒：
- 不要过度使用工具！简单问候和闲聊直接回答即可
- 只有明确需要查询实时数据或数据库时才使用相应工具
- 天气查询工具已经集成了搜索和AI整理功能，你不需要额外处理
- 利用对话历史理解用户的上下文引用，提供更智能的回复
- 数据库查询必须使用 LIKE 模糊匹配省份名称，确保查询成功
"""),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 创建 Agent
        agent = create_tool_calling_agent(self.llm, tools, prompt)

        # 创建 AgentExecutor
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5  # 限制最大迭代次数，避免过度调用工具
        )

        logger.info(f"✅ Agent 创建成功，工具数量: {len(tools)}")

    def run_conversation(self, user_input: str, chat_history: List[Tuple[str, str]] = None) -> str:
        """
        运行一次对话

        Args:
            user_input: 用户输入
            chat_history: 历史对话列表，格式为 [(user_msg, ai_msg), ...]

        Returns:
            AI 回复
        """
        try:
            # 将历史对话转换为 LangChain 消息格式
            history_messages = []
            if chat_history:
                for user_msg, ai_msg in chat_history:
                    history_messages.append(HumanMessage(content=user_msg))
                    history_messages.append(AIMessage(content=ai_msg))

            # 执行对话
            response = self.agent_executor.invoke({
                "input": user_input,
                "chat_history": history_messages
            })
            return response.get("output", "抱歉，我无法处理这个请求。")

        except Exception as e:
            logger.error(f"对话执行失败: {e}", exc_info=True)
            return "对不起，我在处理您的请求时遇到了问题。请稍后再试。"


# 主程序入口
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🌤️  智能天气助手 - 小天")
    print("=" * 60)
    print("\n✨ 功能介绍:")
    print("  📊 自然语言查询数据库（如：有多少个直辖市？）")
    print("  🌡️  智能天气查询（如：北京天气怎么样？）")
    print("  💡 提供出行生活建议")
    print("  🔄 支持复杂组合查询")
    print("\n📌 使用提示:")
    print("  • 直接输入问题，我会智能理解并回答")
    print("  • 输入 'exit' 或 'quit' 退出程序")
    print("  • 输入 'clear' 清除对话历史")
    print("  • 输入 'help' 查看帮助信息")
    print("=" * 60 + "\n")

    # 初始化服务
    try:
        dialogue_service = DialogueService()
        chat_history = []  # 对话历史，格式: [(user_msg, ai_msg), ...]
        max_history_turns = 5  # 最多保留5轮对话
        print("✅ 小天已上线，随时为您服务！")

        while True:
            try:
                user_query = input("🧑 你: ").strip()

                if not user_query:
                    continue

                if user_query.lower() in ['exit', 'quit', '退出']:
                    print("\n👋 小天：再见！祝您生活愉快！")
                    break

                if user_query.lower() in ['clear', '清除']:
                    chat_history = []
                    print("✅ 对话历史已清除\n")
                    continue

                if user_query.lower() in ['help', '帮助']:
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
                    print("\n🔹 命令:")
                    print("  • exit/quit/退出 - 退出程序")
                    print("  • clear/清除 - 清除对话历史")
                    print("  • help/帮助 - 显示此帮助信息")
                    print(f"\n💭 提示：我会记住最近 {max_history_turns} 轮对话的上下文")
                    print("=" * 60 + "\n")
                    continue

                # 执行对话
                print("\n🤖 小天: ", end="", flush=True)
                ai_response = dialogue_service.run_conversation(user_query, chat_history)
                print(ai_response + "\n")

                # 更新历史，保留最近5轮对话
                chat_history.append((user_query, ai_response))
                if len(chat_history) > max_history_turns:
                    chat_history = chat_history[-max_history_turns:]  # 只保留最后5轮
                    logger.debug(f"历史记录已裁剪，当前保留 {len(chat_history)} 轮对话")

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


