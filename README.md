# GetWeather - AI天气助手

基于 LangChain 和 OpenAI 的智能天气查询助手，支持通过自然语言对话查询中国各地天气信息。

## 功能特点

- 自然语言天气查询
- 基于 LangChain Agent 的工具调用
- MySQL 数据库存储中国地区天气编码
- 支持对话历史管理
- 完善的错误处理和日志记录

## 项目结构

```
GetWeather/
├── .env.example          # 环境变量配置模板
├── requirements.txt      # Python 依赖
├── database/
│   └── db_manager.py     # 数据库管理模块
└── src/
    ├── Config_Manager.py     # 配置管理模块
    ├── Weather_Service.py    # 天气查询工具
    └── MainChat.py           # 主对话服务（入口）
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

### 运行主程序

```bash
python src/MainChat.py
```

### 对话示例

```
==================================================
AI天气助手已启动
输入 'exit' 或 'quit' 退出
输入 'clear' 清除对话历史
==================================================

你: 北京今天天气怎么样？

AI: 北京的天气信息可以在这里查看：http://www.weather.com.cn/weather/101010100.shtml

你: clear
对话历史已清除。

你: exit
再见！
```

## 模块说明

### Config_Manager.py
- 管理环境变量加载
- 提供 API 和数据库配置
- 自动验证必需配置项

### db_manager.py
- MySQL 数据库连接管理
- 地区编码的 CRUD 操作
- 支持模糊查询地区名称
- 自动重连机制

### Weather_Service.py
- 实现 LangChain `BaseTool` 接口
- 根据地区名称生成天气网站 URL
- 集成数据库查询功能

### MainChat.py
- 对话服务主入口
- LangChain Agent 和 Executor 初始化
- 命令行交互界面
- 对话历史管理

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| API_KEY | OpenAI API 密钥 | - | ✅ |
| BASE_URL | API 基础地址 | 无地址 | ❌ |
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

- **LangChain**: Agent 和工具调用框架
- **OpenAI API**: 大语言模型
- **PyMySQL**: MySQL 数据库驱动
- **Pydantic**: 数据验证
- **Python-dotenv**: 环境变量管理

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

## 许可证

本项目仅供学习和研究使用。

## 贡献

欢迎提交 Issue 和 Pull Request！
