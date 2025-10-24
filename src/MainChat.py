import logging
from typing import List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_openai import ChatOpenAI

import sys
import os

# 添加项目根目录到路径
project_root = os.path.join(os.path.dirname(__file__), '..')
project_root = os.path.abspath(project_root)
sys.path.insert(0, project_root)

# 导入配置管理器和天气工具
from Config_Manager import ConfigManager
import Weather_Service

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DialogueService:
    """
    大模型应用的对话服务层，负责初始化LLM、工具和Agent，并处理用户对话。
    """
    def __init__(self):
        self.config = ConfigManager()

        self.llm = ChatOpenAI(
            model=self.config.model,
            base_url=self.config.base_url,
            api_key=self.config.api_key
        )

        # 初始化 WeatherTool
        self.weather_tool = Weather_Service.create_weather_tool()
        if not self.weather_tool:
            logger.error("天气工具初始化失败，对话服务将无法提供天气查询功能。")
            raise RuntimeError("WeatherTool 初始化失败，无法启动服务")
        else:
            self.tools = [self.weather_tool]
            logger.info("WeatherTool 初始化成功")

        # 设置系统提示词
        self.system_prompt = "你是一个可以实时查询天气的AI助手。当用户询问天气时，使用提供的工具获取最新信息，并在气温后面加上℃让回答更美观。"

        # 创建 Prompt Template
        # MessagesPlaceholder 用于动态插入聊天历史和Agent的思考过程
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history"), # 历史对话
                ("human", "{input}"), # 当前用户输入
                MessagesPlaceholder(variable_name="agent_scratchpad"), # Agent的思考过程和工具调用
            ]
        )

        # 创建 LangChain Agent
        # create_tool_calling_agent 适用于模型能够理解并调用工具的场景
        # 这里的关键是，我们假设LLM在接收到WeatherTool返回的URL后，能够自行解析该链接
        self.agent = create_tool_calling_agent(self.llm, self.tools, self.prompt)

        # 创建 Agent Executor
        # AgentExecutor 负责运行Agent，管理工具调用和响应生成
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True, # 设置为True可以看到Agent的思考过程和工具调用
            handle_parsing_errors=True # 更好地处理Agent输出的解析错误
        )

    def run_conversation(self, user_input: str, chat_history: List[Tuple[str, str]]) -> str:
        """
        运行一次对话。
        Args:
            user_input: 用户输入的消息。
            chat_history: 历史对话记录，格式为 [(human_message, ai_message), ...]。
        Returns:
            AI的回复。
        """
        # 将 chat_history 转换为 LangChain 消息格式
        formatted_chat_history = []
        for human_msg, ai_msg in chat_history:
            formatted_chat_history.append(HumanMessage(content=human_msg))
            formatted_chat_history.append(AIMessage(content=ai_msg))

        try:
            # 调用 Agent Executor 处理用户输入
            response = self.agent_executor.invoke(
                {"input": user_input, "chat_history": formatted_chat_history}
            )
            return response["output"]
        except Exception as e:
            logger.error(f"对话执行失败: {e}", exc_info=True)
            return "对不起，我在处理您的请求时遇到了问题。请稍后再试。"

# 示例用法
if __name__ == "__main__":
    print("=" * 50)
    print("AI天气助手已启动")
    print("输入 'exit' 或 'quit' 退出")
    print("输入 'clear' 清除对话历史")
    print("=" * 50)
    print()

    try:
        dialogue_service = DialogueService()
    except RuntimeError as e:
        logger.error(f"服务启动失败: {e}")
        print(f"\n❌ 启动失败: {e}")
        print("请检查:")
        print("1. 数据库是否正常连接")
        print("2. .env 配置是否正确")
        print("3. 依赖是否完整安装")
        exit(1)

    # 模拟对话历史
    chat_history = []

    while True:
        try:
            user_query = input("\n你: ")

            if not user_query.strip():
                continue

            if user_query.lower() in ['exit', 'quit']:
                print("\n再见！")
                break

            if user_query.lower() == 'clear':
                chat_history = []
                print("对话历史已清除。")
                continue

            ai_response = dialogue_service.run_conversation(user_query, chat_history)
            print(f"\nAI: {ai_response}")

            # 更新对话历史
            chat_history.append((user_query, ai_response))

        except KeyboardInterrupt:
            print("\n\n检测到 Ctrl+C，正在退出...")
            break
        except Exception as e:
            logger.error(f"对话过程出错: {e}", exc_info=True)
            print(f"\n❌ 发生错误: {e}")

