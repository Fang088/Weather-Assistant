# GetWeather - 智能天气助手 🌤️

基于 **LangChain** 和 **OpenAI** 的智能天气查询助手，支持自然语言对话、实时天气查询、数据库统计查询和会话记忆。

---

## ✨ 核心特性

- 🧠 **会话管理** - 基于 Redis 的上下文记忆，支持多轮对话
- 💾 **智能缓存** - 天气查询缓存 30 分钟，多种问法命中同一缓存
- 🌡️ **实时天气查询** - 通过外部搜索 API 获取实时天气信息
- 📊 **自然语言数据库查询** - 用自然语言直接查询数据库
- ⚡ **并发限流** - 最多 5 个并发请求，自动排队
- 🔑 **API Key 认证** - 支持多用户，优先使用用户提供的 Key

---

## 🎯 使用模式

### 1. CLI 模式（命令行交互）
```bash
python src/main.py
```

### 2. API 模式（HTTP 服务）
```bash
python src/api_server.py
```

服务地址：`http://localhost:6666`

---

## 📦 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `langchain` - Agent 框架
- `langchain-openai` - OpenAI 模型集成
- `langchain-community` - SQL 工具集成
- `fastapi` - API 服务框架
- `redis` - 缓存和会话管理
- `pymysql` - MySQL 数据库驱动

### 2. 配置环境变量

编辑 `.env` 文件：

```env
# API Key（可选，用户未提供时使用）
API_KEY=sk-your-302ai-key

# API 路径
BASE_URL=https://api.302.ai/v1
SEARCH_API_URL=https://api.302.ai/search1api/search

# 数据库（必填）
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=fang

# Redis 缓存与会话管理（推荐）
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 3. 准备数据库

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

**注意：** 表可以为空，系统会自动添加新地区数据。

---

## 📡 API 快速调用

### Windows (CMD)
```cmd
curl -X POST http://localhost:6666/Fang-GetWeather/chat ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer sk-your-api-key" ^
  -d "{\"message\":\"北京天气\"}"
```

### Linux / macOS
```bash
curl -X POST http://localhost:6666/Fang-GetWeather/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{"message":"北京天气"}'
```

### 会话记忆（带 session_id）

#### Windows (CMD)
```cmd
REM 第一轮
curl -X POST http://localhost:6666/Fang-GetWeather/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"北京天气\"}"

REM 第二轮（带上 session_id）
curl -X POST http://localhost:6666/Fang-GetWeather/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"那上海的呢?\",\"session_id\":\"abc123...\"}"
```

#### Linux / macOS
```bash
# 第一轮
curl -X POST http://localhost:6666/Fang-GetWeather/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"北京天气"}'

# 第二轮（带上 session_id）
curl -X POST http://localhost:6666/Fang-GetWeather/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"那上海的呢?","session_id":"abc123..."}'
```

---

## 📁 项目结构

```
GetWeather/
├── .env                       # 环境变量配置（需自行创建）
├── requirements.txt           # Python 依赖
├── README.md                  # 项目说明
├── API使用文档.md             # API 详细文档
├── database/
│   └── sql_database_wrapper.py # LangChain SQLDatabase 封装
├── src/
│   ├── Config_Manager.py      # 配置管理模块
│   ├── Weather_Service.py     # 天气查询工具
│   ├── cache_manager.py       # Redis 缓存管理
│   ├── session_manager.py     # 会话管理
│   ├── concurrency_limiter.py # 并发限流
│   ├── auth.py                # API Key 认证
│   ├── main.py                # CLI 主程序
│   └── api_server.py          # API 服务器
```

---

## 🎯 功能特点

### 1. 智能场景识别

| 场景 | 示例 | 处理方式 |
|------|------|----------|
| **普通对话** | "你好"、"谢谢" | LLM 直接回答，不调用工具 |
| **天气查询** | "北京天气怎么样"、"上海会下雨吗" | 调用搜索 API + LLM 解析 |
| **数据库查询** | "有多少个直辖市"、"列出所有省会城市" | 使用 SQL 工具查询数据库 |

### 2. 智能缓存机制

- **自动提取地区**：从查询中提取城市名（如"北京"、"上海"）
- **别名映射**：支持多种名称命中同一缓存
  - 北京/北京市/首都 → 同一缓存
  - 上海/上海市/魔都 → 同一缓存
  - 广州/广州市/羊城 → 同一缓存
- **缓存时间**：30 分钟
- **性能提升**：缓存命中响应时间 <50ms（提升 60-100 倍）

### 3. 会话管理

- **基于 Redis**：会话历史存储在 Redis 中
- **自动记忆**：保留最近 5 轮对话
- **上下文理解**：理解"那上海的呢"等上下文引用
- **自动过期**：会话 1 小时不活跃自动清除
- **多用户隔离**：每个会话独立的 session_id

---

## 🔧 高级配置

### 修改会话参数

编辑 `src/api_server.py` 第 61 行：
```python
session_manager = SessionManager(
    cache_manager=cache_manager,
    max_history_turns=10,   # 最大历史轮数（默认 5）
    session_ttl=7200        # 会话过期时间（默认 3600 秒）
)
```

### 修改并发数

编辑 `src/api_server.py` 第 59 行：
```python
limiter = get_limiter(max_concurrency=10)  # 默认 5
```

### 修改缓存时间

编辑 `src/api_server.py` 第 60 行：
```python
cache_manager = get_cache_manager(default_ttl=3600)  # 默认 1800 秒
```

---


## 🎓 常见问题

### Q1: 必须安装 Redis 吗？
**F**: 推荐安装。不安装会禁用缓存和会话管理，但基础对话功能正常。

### Q2: CLI 和 API 模式有什么区别？
**F**:
- **CLI 模式**：单用户命令行交互，本地对话历史管理
- **API 模式**：多用户 HTTP 服务，基于 Redis 的会话管理，支持远程调用

### Q3: 如何清空所有会话？
**F**: 使用 Redis CLI：
```bash
redis-cli
> KEYS session:*
> DEL session:*
```

### Q4: 支持哪些模型？
**F**: 支持所有 OpenAI 兼容模型，通过 `.env` 的 `MODEL` 配置。

---

## 📚 技术栈

### 核心框架
- **LangChain**: Agent 和工具调用框架
- **FastAPI**: 现代化 Web 框架
- **Redis**: 缓存和会话管理
- **SQLAlchemy**: 数据库 ORM
- **PyMySQL**: MySQL 驱动

### 数据处理
- **Pydantic**: 数据验证
- **Python-dotenv**: 环境变量管理

---

## 📄 许可证

本项目仅供学习和研究使用。

---

**Made with ❤️ using LangChain & FastAPI** 🌤️✨
