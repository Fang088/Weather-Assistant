# GetWeather - 智能天气助手 🌤️

基于 **LangChain** 和 **OpenAI** 的智能天气查询助手，充分利用 LangChain 的 **SQL Agent** 能力，支持自然语言查询数据库和天气信息。

## ✨ 功能特点

- **自然语言数据库查询** - 用自然语言直接查询数据库（如："有多少个直辖市？"）
- **智能天气查询** - 结合数据库和API查询天气信息
- **SQL Agent 自主决策** - Agent自动决定使用哪个工具完成任务
- **多工具协同** - QuerySQL、InfoSQL、ListSQL、Weather工具智能配合
- **零代码扩展** - 添加新查询类型无需修改代码
- **自动表结构理解** - 自动生成表结构描述和示例数据

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
    ├── Weather_Service.py     # 天气查询工具
    └── main.py                # 主程序入口
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

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# OpenAI API 配置
API_KEY=your_openai_api_key_here
BASE_URL=https://api.openai.com/v1
MODEL=gpt-4o-mini

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
    weather_code VARCHAR(20) NOT NULL COMMENT '天气编码',
    province VARCHAR(50) COMMENT '所属省份',
    region_type ENUM('直辖市','省会城市','地级市','县级市') COMMENT '地区类型',
    INDEX idx_region (region),
    INDEX idx_weather_code (weather_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='天气地区编码表';
```

导入地区数据（需要预先准备中国地区天气编码数据）。

## 使用方法

### 启动应用

```bash
python src/main.py
```

### 对话示例

```
============================================================
🌤️  智能天气助手
============================================================
功能特性:
  1. 自然语言查询数据库（如：有多少个直辖市？）
  2. 天气查询（如：北京天气怎么样？）
  3. 复杂组合查询（如：查找所有省会城市并显示天气）

命令:
  'exit' 或 'quit' - 退出程序
  'clear' - 清除对话历史
============================================================

✅ 服务已启动

你: 有多少个直辖市？
🤖 AI: 数据库中共有 4 个直辖市。

你: 北京天气怎么样？
🤖 AI: 北京今天晴，气温 15℃ - 25℃。

你: 列出所有省会城市
🤖 AI: 数据库中的省会城市有：北京、上海、广州、成都...

你: 广东省有哪些地级市？
🤖 AI: 广东省的地级市有：广州、深圳、珠海、佛山...

你: exit
👋 再见！
```

## 核心模块说明

### Config_Manager.py
- 管理环境变量加载
- 提供 API 和数据库配置
- 自动验证必需配置项

### sql_database_wrapper.py
- **LangChain SQLDatabase 封装类**
- 自动生成表结构描述供 LLM 理解
- 内置连接池管理（pool_pre_ping, pool_recycle）
- 支持安全的 SQL 执行
- 与 LangChain Agent 无缝集成

### Weather_Service.py
- 实现 LangChain `BaseTool` 接口
- 根据地区名称生成天气网站 URL
- 集成 Unifuncs API 搜索
- 自动保存新发现的地区编码到数据库

### main.py
- **SQL Agent 对话服务**
- 支持自然语言直接查询数据库
- 多工具协同（QuerySQLTool + InfoSQLTool + WeatherTool）
- Agent 自主决策使用哪个工具
- 命令行交互界面

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| API_KEY | OpenAI API 密钥 | - | ✅ |
| BASE_URL | API 基础地址 | https://api.openai.com/v1 | ❌ |
| MODEL | 使用的模型 | gpt-4o-mini | ❌ |
| DB_HOST | 数据库主机 | localhost | ❌ |
| DB_USER | 数据库用户 | root | ❌ |
| DB_PASSWORD | 数据库密码 | 空 | ❌ |
| DB_NAME | 数据库名称 | fang | ❌ |
| DB_CHARSET | 字符集 | utf8mb4 | ❌ |

### 数据库表结构

`weather_regions` 表字段：
- `region`: 地区名称（如：北京、上海）
- `weather_code`: 天气网站编码
- `province`: 所属省份
- `region_type`: 地区类型（直辖市/省会城市/地级市/县级市）

## 技术栈

### 核心框架
- **LangChain**: Agent 和工具调用框架
  - `langchain-core`: 核心抽象和接口
  - `langchain-openai`: OpenAI 模型集成
  - `langchain-community`: SQL Agent 和 SQLDatabase
- **OpenAI API**: 大语言模型
- **SQLAlchemy**: 数据库 ORM 和连接池管理
- **PyMySQL**: MySQL 数据库驱动

### 数据处理
- **Pydantic**: 数据验证和模型定义
- **Python-dotenv**: 环境变量管理

## 🚀 LangChain 特性应用

### 1. SQLDatabase 自动化
```python
from langchain_community.utilities import SQLDatabase

# 自动管理连接池和表结构描述
db = SQLDatabase(engine=engine, include_tables=['weather_regions'])
table_info = db.table_info  # 自动生成表结构描述
```

### 2. SQL Agent 智能决策
```python
from langchain_community.agent_toolkits import create_sql_agent

# Agent 自动决定使用 SQL 查询还是调用天气工具
agent = create_sql_agent(
    llm=llm,
    db=db,
    extra_tools=[weather_tool],
    verbose=True
)
```

### 3. 多工具协同
- **QuerySQLDataBaseTool**: 执行 SQL 查询
- **InfoSQLDatabaseTool**: 查看表结构
- **ListSQLDatabaseTool**: 列出所有表
- **WeatherTool**: 查询天气信息

Agent 自动选择合适的工具完成任务！

## 日志

项目使用 Python 内置 `logging` 模块，日志级别为 `INFO`。日志包括：
- 配置加载状态
- 数据库连接状态
- LLM 初始化状态
- 工具调用过程
- 错误和异常信息

## 错误处理

- 配置缺失时提供清晰错误提示
- 数据库连接失败自动重连
- LLM 调用失败友好提示
- Ctrl+C 优雅退出

## 注意事项

1. 确保 MySQL 服务已启动
2. 确保 `.env` 文件中的 `API_KEY` 有效
3. 需要预先导入中国地区天气编码数据
4. 建议使用 Python 3.8 及以上版本

## 📚 学习资源

### LangChain 官方文档
- [SQL Database](https://python.langchain.com/docs/integrations/tools/sql_database)
- [SQL Agent](https://python.langchain.com/docs/use_cases/sql/agents)
- [Tools Documentation](https://python.langchain.com/docs/modules/agents/tools/)

### 关键代码位置
- SQL 封装: `database/sql_database_wrapper.py`
- 天气工具: `src/Weather_Service.py`
- SQL Agent: `src/main.py:45-134`

## 🎯 项目特色

### 核心优势
✅ **自然语言查询** - 用自然语言直接查询数据库，无需编写 SQL
✅ **智能决策** - Agent 自动选择合适的工具完成任务
✅ **零代码扩展** - 添加新查询类型无需修改代码
✅ **LangChain 最佳实践** - 充分发挥 SQL Agent 和多工具协同能力

### 技术亮点
- 🔥 LangChain SQL Agent 集成
- 🔥 多工具协同工作
- 🔥 自动连接池管理
- 🔥 表结构自动描述

## 许可证

本项目仅供学习和研究使用。

## 贡献

欢迎提交 Issue 和 Pull Request！
