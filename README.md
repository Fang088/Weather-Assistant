# GetWeather - 智能天气助手 🌤️

基于 **LangChain** 和 **OpenAI** 的智能天气查询助手，支持自然语言对话、实时天气查询和数据库统计查询。

## ✨ 功能特点

- **智能场景识别** - 自动识别普通对话、天气查询、数据库查询三种场景
- **实时天气查询** - 通过外部搜索API获取实时天气信息
- **上下文记忆** - 记住最近5轮对话，支持上下文引用（如"那上海呢？"）
- **自然语言数据库查询** - 用自然语言直接查询数据库（如："有多少个直辖市？"）
- **智能工具选择** - Agent根据问题自动选择合适的工具
- **自动数据保存** - 新查询的地区信息自动保存到数据库
- **⚡ OpenAI 缓存优化** - 自动缓存系统提示词，节省 50% 成本，降低 80% 延迟（v2.1 新增）

## 🎯 三大场景

| 场景 | 示例 | 处理方式 |
|------|------|----------|
| **普通对话** | "你好"、"谢谢"、"你是谁" | LLM直接回答，不调用工具 |
| **天气查询** | "北京天气怎么样"、"上海会下雨吗" | 调用搜索API + LLM解析 |
| **数据库查询** | "有多少个直辖市"、"列出所有省会城市" | 使用SQL工具查询数据库 |

## 项目结构

```
GetWeather/
├── .env.example               # 环境变量配置模板
├── requirements.txt           # Python 依赖
├── README.md                  # 项目说明
├── database/
│   └── sql_database_wrapper.py # LangChain SQLDatabase 封装
└── src/
    ├── Config_Manager.py      # 配置管理模块
    ├── Weather_Service.py     # 天气查询工具（集成搜索API）
    └── main.py                # 主程序入口（Agent + 上下文记忆）
```

## 安装步骤

### 1. 克隆项目

```bash
cd GetWeather
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `langchain` - Agent框架
- `langchain-openai` - OpenAI模型集成
- `langchain-community` - SQL工具集成
- `pymysql` - MySQL数据库驱动
- `requests` - HTTP请求库（调用搜索API）
- `python-dotenv` - 环境变量管理

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# OpenAI API 配置（用于对话和天气信息解析）
API_KEY=your_openai_api_key_here
BASE_URL=https://api.openai.com/v1
MODEL=gpt-4o-mini

# 搜索 API 配置（用于天气查询，必填）
SEARCH_API_KEY=your_search_api_key_here
SEARCH_API_URL=https://api.302.ai/search1api/search

# 数据库配置
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_database_password_here
DB_NAME=fang
DB_CHARSET=utf8mb4
```

### 4. 准备数据库

创建 MySQL 数据库和表：

```sql
CREATE DATABASE fang CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE fang;

CREATE TABLE weather_regions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    region VARCHAR(100) NOT NULL COMMENT '地区名称',
    weather_code VARCHAR(20) NOT NULL COMMENT '天气编码（9位数字）',
    province VARCHAR(50) COMMENT '所属省份',
    region_type ENUM('直辖市','省会城市','地级市','县级市') COMMENT '地区类型',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    INDEX idx_weather_code (weather_code),
    UNIQUE KEY uk_region (region)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='天气地区编码表';
```

**注意：** 表可以为空，系统会在查询天气时自动添加新地区数据。

## 使用方法

### 启动应用

```bash
python src/main.py
```

### 对话示例

```
============================================================
🌤️  智能天气助手 - 小天
============================================================

✨ 功能介绍:
  📊 自然语言查询数据库（如：有多少个直辖市？）
  🌡️  智能天气查询（如：北京天气怎么样？）
  💡 提供出行生活建议
  🔄 支持复杂组合查询
  💭 记忆最近5轮对话的上下文

📌 使用提示:
  • 直接输入问题，我会智能理解并回答
  • 输入 'exit' 或 'quit' 退出程序
  • 输入 'clear' 清除对话历史
  • 输入 'help' 查看帮助信息
============================================================

✅ 小天已上线，随时为您服务！
💭 我会记住最近 5 轮对话的上下文

🧑 你: 你好
🤖 小天: 你好！我是小天，智能天气助手。我可以帮您查询天气、统计地区数据等。有什么可以帮您的吗？

🧑 你: 北京天气怎么样？
🤖 小天:
📍 北京市 天气情况
==================================================
🌡️  温度: 15℃ ~ 25℃
☁️  天气: 晴

📝 详细信息:
今天晴，温度15-25℃，风力3-4级，空气质量良好

💡 生活建议:
1. 穿衣建议：早晚温差较大，建议穿长袖外套
2. 出行建议：天气晴朗，适合户外活动
3. 健康建议：紫外线较强，注意防晒
==================================================

🧑 你: 那上海呢？
🤖 小天:
📍 上海市 天气情况
==================================================
🌡️  温度: 18℃ ~ 26℃
☁️  天气: 多云

📝 详细信息:
今天多云，温度18-26℃，风力2-3级

💡 生活建议:
1. 穿衣建议：适合穿轻薄外套
2. 出行建议：天气适宜，出行便利
3. 健康建议：空气湿度适中，注意补水
==================================================

🧑 你: 有多少个直辖市？
🤖 小天: 根据数据库查询，中国共有 4 个直辖市：北京市、上海市、天津市、重庆市。

🧑 你: 广东省有哪些地级市？
🤖 小天: 广东省的地级市有：广州市、深圳市、珠海市、汕头市、佛山市、韶关市、湛江市、肇庆市、江门市、茂名市、惠州市、梅州市、汕尾市、河源市、阳江市、清远市、东莞市、中山市、潮州市、揭阳市、云浮市，共21个地级市。

🧑 你: 刚才查询的城市天气怎么样？
🤖 小天: 您刚才查询的是上海的天气。上海今天多云，温度18-26℃，天气比较适宜出行。

🧑 你: exit
👋 小天：再见！祝您生活愉快！
```

## 核心模块说明

### Config_Manager.py
- 管理环境变量加载
- 提供 API、搜索API 和数据库配置
- 自动验证必需配置项（API_KEY 和 SEARCH_API_KEY）

### sql_database_wrapper.py
- **LangChain SQLDatabase 封装类**
- 自动生成表结构描述供 LLM 理解
- 内置连接池管理（pool_pre_ping, pool_recycle）
- 支持安全的 SQL 执行
- 与 LangChain Agent 无缝集成

### Weather_Service.py
**核心工作流程：**
1. 调用外部搜索API获取天气相关网页信息
2. 从搜索结果中提取中国天气网URL和天气编码
3. 使用LLM解析搜索结果，提取结构化天气信息
4. 自动保存新地区的编码、省份、类型到数据库
5. 返回格式化的天气信息（无引用标记）

**关键特性：**
- 实现 LangChain `BaseTool` 接口
- 集成 302.ai 搜索API
- 正则表达式提取天气编码（9位数字）
- 自动清理引用标记 `[1]` `[2]` 等
- 自动识别地区所属省份和类型

### main.py
**智能Agent对话服务：**
- 使用 Tool Calling Agent（非SQL Agent）
- 三种场景智能识别和处理
- 上下文记忆功能（最近5轮对话）
- 多工具协同（Weather + SQL工具）
- 命令行交互界面

**上下文记忆机制：**
- 自动保存最近5轮对话历史
- 支持上下文引用理解
- 滑动窗口自动淘汰旧对话
- `clear` 命令可随时清空历史

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| API_KEY | OpenAI API 密钥 | - | ✅ |
| BASE_URL | API 基础地址 | https://api.openai.com/v1 | ❌ |
| MODEL | 使用的模型 | gpt-4o-mini | ❌ |
| SEARCH_API_KEY | 搜索API密钥（302.ai）| - | ✅ |
| SEARCH_API_URL | 搜索API地址 | https://api.302.ai/search1api/search | ❌ |
| DB_HOST | 数据库主机 | localhost | ❌ |
| DB_USER | 数据库用户 | root | ❌ |
| DB_PASSWORD | 数据库密码 | 空 | ❌ |
| DB_NAME | 数据库名称 | fang | ❌ |
| DB_CHARSET | 字符集 | utf8mb4 | ❌ |

### 搜索API说明

**302.ai 搜索API格式：**

**请求：**
```bash
POST https://api.302.ai/search1api/search
Headers:
  Authorization: Bearer YOUR_API_KEY
  Content-Type: application/json

Body:
{
  "query": "湛江天气"
}
```

**响应：**
```json
{
  "searchParameters": {
    "query": "湛江天气",
    "search_service": "google",
    "max_results": 5
  },
  "results": [
    {
      "title": "湛江天气预报,湛江7天天气预报...",
      "link": "https://www.weather.com.cn/weather/101281001.shtml",
      "snippet": "29日（今天）. 小雨. 27/22℃. 3-4级..."
    }
  ]
}
```

系统会自动：
1. 从 `link` 中提取天气编码（如 `101281001`）
2. 从 `snippet` 中提取温度、天气状况
3. 使用LLM整理成结构化信息

### 数据库表结构

`weather_regions` 表字段：
- `region`: 地区名称（如：北京市、湛江市）
- `weather_code`: 天气编码（9位数字，如：101281001）
- `province`: 所属省份（如：北京市、广东省）
- `region_type`: 地区类型（直辖市/省会城市/地级市/县级市）

## 技术栈

### 核心框架
- **LangChain**: Agent 和工具调用框架
  - `langchain-core`: 核心抽象和接口
  - `langchain-openai`: OpenAI 模型集成
  - `langchain-community`: SQL 工具集成
- **OpenAI API**: 大语言模型（对话和信息解析）
- **SQLAlchemy**: 数据库 ORM 和连接池管理
- **PyMySQL**: MySQL 数据库驱动
- **Requests**: HTTP客户端（调用搜索API）

### 数据处理
- **Pydantic**: 数据验证和模型定义
- **Python-dotenv**: 环境变量管理
- **正则表达式**: 天气编码提取

## 🚀 核心技术实现

### 1. 智能Agent架构
```python
from langchain.agents import create_tool_calling_agent, AgentExecutor

# 创建Agent，集成多个工具
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=5
)
```

### 2. 搜索API集成
```python
def _call_search_api(self, area_name: str):
    response = requests.post(
        url="https://api.302.ai/search1api/search",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"query": f"{area_name}天气"}
    )
    return response.json()
```

### 3. 天气编码提取
```python
def _extract_weather_code_from_url(self, url: str):
    # 从 https://www.weather.com.cn/weather/101281001.shtml
    # 提取 101281001
    match = re.search(r'weather\.com\.cn/weather/(\d{9})\.shtml', url)
    if match:
        return match.group(1)
```

### 4. 上下文记忆
```python
# 保存最近5轮对话
chat_history = []  # [(user_msg, ai_msg), ...]
max_history_turns = 5

# 更新历史
chat_history.append((user_query, ai_response))
if len(chat_history) > max_history_turns:
    chat_history = chat_history[-max_history_turns:]
```

### 5. 多工具协同
- **WeatherTool**: 调用搜索API获取天气（自定义工具）
- **QuerySQLDataBaseTool**: 执行 SQL 查询
- **InfoSQLDatabaseTool**: 查看表结构
- **ListSQLDatabaseTool**: 列出所有表

Agent 自动根据问题选择合适的工具！

## 工作流程图

```
用户输入
    ↓
Agent分析
    ↓
    ├─→ 普通对话？ → LLM直接回答
    ├─→ 天气查询？ → 调用WeatherTool
    │                    ↓
    │              搜索API获取数据
    │                    ↓
    │              LLM解析结构化
    │                    ↓
    │              提取天气编码
    │                    ↓
    │              保存到数据库
    │                    ↓
    │              返回格式化结果
    └─→ 数据库查询？ → 调用SQL工具
                         ↓
                    执行SQL查询
                         ↓
                    返回查询结果
```

## 日志

项目使用 Python 内置 `logging` 模块，日志级别为 `INFO`。日志包括：
- 配置加载状态
- 数据库连接状态
- LLM 初始化状态
- 搜索API调用过程
- 天气编码提取结果
- 工具调用过程
- 数据库保存状态
- 错误和异常信息

## 错误处理

- 配置缺失时提供清晰错误提示
- 数据库连接失败自动重连
- 搜索API调用失败友好提示
- LLM 解析失败降级处理
- Ctrl+C 优雅退出

## 注意事项

1. ⚠️ 确保 MySQL 服务已启动
2. ⚠️ 确保 `.env` 文件中的 `API_KEY` 和 `SEARCH_API_KEY` 有效
3. ✅ 数据库表可以为空，系统会自动添加数据
4. ✅ 建议使用 Python 3.8 及以上版本
5. ✅ 天气编码会自动从搜索结果中提取
6. ✅ 上下文记忆自动管理，无需手动清理

## 常见问题

### Q1: 搜索API调用失败？
**A:** 检查 `SEARCH_API_KEY` 是否正确，确保API额度充足。

### Q2: 天气编码提取失败？
**A:** 系统会自动从中国天气网URL中提取，如果失败会保存为"未找到"，不影响天气信息显示。

### Q3: 数据库连接失败？
**A:** 检查MySQL服务是否启动，数据库配置是否正确。

### Q4: 上下文记忆不工作？
**A:** 确保对话历史未被清除（`clear` 命令），系统会自动保留最近5轮对话。

### Q5: Agent选择了错误的工具？
**A:** 调整System Prompt中的场景说明，或增加示例来引导Agent。

## 📚 学习资源

### LangChain 官方文档
- [Tool Calling Agent](https://python.langchain.com/docs/modules/agents/agent_types/tool_calling)
- [Custom Tools](https://python.langchain.com/docs/modules/agents/tools/custom_tools)
- [SQL Database](https://python.langchain.com/docs/integrations/tools/sql_database)
- [Memory](https://python.langchain.com/docs/modules/memory/)

### 关键代码位置
- Agent配置: `src/main.py:77-156`
- 天气工具: `src/Weather_Service.py:33-297`
- 搜索API调用: `src/Weather_Service.py:67-102`
- 上下文记忆: `src/main.py:159-187, 255-259`

## 🎯 项目特色

### 核心优势
✅ **三场景智能识别** - 自动区分对话、天气、数据库三种场景
✅ **上下文记忆** - 记住最近5轮对话，理解上下文引用
✅ **实时天气数据** - 通过搜索API获取最新天气信息
✅ **自动数据保存** - 新地区信息自动入库
✅ **无引用标记** - 自动清理 `[1]` `[2]` 等引用标记
✅ **智能工具选择** - Agent根据问题自动选择合适工具

### 技术亮点
- 🔥 LangChain Tool Calling Agent
- 🔥 外部搜索API集成
- 🔥 正则表达式提取天气编码
- 🔥 上下文滑动窗口记忆
- 🔥 多工具智能协同
- 🔥 结构化信息提取

## 版本历史

### v2.0 (2025-01-29)
- ✨ 重构为Tool Calling Agent架构
- ✨ 集成302.ai搜索API
- ✨ 添加上下文记忆功能（5轮）
- ✨ 自动提取天气编码
- ✨ 自动清理引用标记
- ✨ 三场景智能识别

### v1.0
- 初始版本
- SQL Agent架构
- 依赖模型联网能力

## 许可证

本项目仅供学习和研究使用。

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题或建议，欢迎提交 Issue。

---

**Made with ❤️ using LangChain**
