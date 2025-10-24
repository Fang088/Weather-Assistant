# 快速入门指南 - GetWeather SQL Agent 版本

## 🚀 5分钟快速体验

### Step 1: 安装依赖（1分钟）

```bash
cd GetWeather
pip install -r requirements.txt
```

**新增依赖**:
- `langchain-community>=0.0.20` - SQL Agent 工具集
- `sqlalchemy>=2.0.0` - 数据库 ORM

---

### Step 2: 配置环境变量（1分钟）

确保 `.env` 文件包含以下配置：

```env
# OpenAI API 配置
API_KEY=your_openai_api_key_here
BASE_URL=https://api.openai.com/v1
MODEL=gpt-4o-mini

# 数据库配置
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=fang
DB_CHARSET=utf8mb4
```

---

### Step 3: 测试 SQL 封装（1分钟）

```bash
python database/sql_database_wrapper.py
```

**预期输出**:
```
✅ LangChain SQLDatabase 初始化成功
可用的表: ['weather_regions']

数据库表结构信息:
Table: weather_regions
Columns: region, weather_code, province, region_type
Sample rows:
  ('北京', '101010100', '北京市', '直辖市')
  ...
```

---

### Step 4: 运行 SQL Agent（2分钟）

```bash
python src/MainChat_SQLAgent.py
```

**交互示例**:

```
选择模式 (1=SQL Agent 高级模式, 2=传统模式) [默认:1]: 1

✅ SQL Agent 高级模式 已启动

你: 有多少个直辖市？
🤖 AI: 数据库中共有 4 个直辖市。

你: 北京天气怎么样？
🤖 AI: 北京今天晴，气温 15℃ - 25℃。

你: 列出所有省会城市
🤖 AI: 数据库中的省会城市有：北京、上海、广州...

你: 广东省有哪些地级市？
🤖 AI: 广东省的地级市有：广州、深圳、珠海...
```

---

## 🎯 核心功能演示

### 功能 1: 统计查询

```
你: 有多少个直辖市？
AI: 自动生成 SQL → SELECT COUNT(*) FROM weather_regions WHERE region_type='直辖市'
返回: 4 个直辖市
```

### 功能 2: 天气查询

```
你: 北京天气怎么样？
AI: 调用 WeatherTool → 查询数据库 → 生成天气 URL
返回: http://www.weather.com.cn/weather/101010100.shtml
```

### 功能 3: 列表查询

```
你: 列出所有省会城市
AI: 自动生成 SQL → SELECT region FROM weather_regions WHERE region_type='省会城市'
返回: 北京、上海、广州、成都...
```

### 功能 4: 复杂查询

```
你: 广东省有哪些地级市？
AI: 自动生成 SQL →
    SELECT region FROM weather_regions
    WHERE province='广东省' AND region_type='地级市'
返回: 广州、深圳、珠海、佛山...
```

### 功能 5: 表结构查询

```
你: weather_regions 表有哪些列？
AI: 使用 InfoSQLDatabaseTool 查看表结构
返回: region, weather_code, province, region_type
```

---

## 📊 对比测试

### 传统模式 vs SQL Agent 模式

**测试 1: 统计查询**

| 模式 | 查询 | 结果 |
|-----|-----|-----|
| 传统模式 | "有多少个直辖市？" | ❌ 无法回答（功能不支持） |
| SQL Agent | "有多少个直辖市？" | ✅ "4 个直辖市" |

**测试 2: 天气查询**

| 模式 | 查询 | 响应时间 |
|-----|-----|---------|
| 传统模式 | "北京天气" | ~1s |
| SQL Agent | "北京天气" | ~2s（+1s LLM 推理） |

**测试 3: 列表查询**

| 模式 | 查询 | 结果 |
|-----|-----|-----|
| 传统模式 | "列出所有省会城市" | ❌ 无法回答 |
| SQL Agent | "列出所有省会城市" | ✅ 完整列表 |

---

## 🔧 常见问题

### Q1: 如何切换模式？

**运行时选择**:
```bash
python src/MainChat_SQLAgent.py
# 输入 1 = SQL Agent 模式
# 输入 2 = 传统模式
```

**代码切换**:
```python
# src/MainChat_SQLAgent.py
dialogue_service = SQLAgentDialogueService(use_sql_agent=True)  # SQL Agent
dialogue_service = SQLAgentDialogueService(use_sql_agent=False) # 传统
```

---

### Q2: SQL Agent 不工作怎么办？

**排查步骤**:

1. 检查依赖是否安装：
   ```bash
   pip list | grep langchain-community
   pip list | grep sqlalchemy
   ```

2. 查看详细日志：
   ```python
   # 在 MainChat_SQLAgent.py 顶部添加
   logging.basicConfig(level=logging.DEBUG)
   ```

3. 测试数据库连接：
   ```bash
   python database/sql_database_wrapper.py
   ```

---

### Q3: 如何添加新查询类型？

**传统模式**: 需要修改代码添加新函数

**SQL Agent 模式**: 零代码！直接问即可
```
你: 有多少个县级市？
AI: 自动处理并返回结果
```

---

## 📚 深入学习

### 学习路径

1. **入门**: 运行 `COMPARISON_EXAMPLES.py` 了解差异
2. **进阶**: 阅读 `UPGRADE_GUIDE.md` 理解架构
3. **实践**: 修改 `MainChat_SQLAgent.py` 添加新工具
4. **掌握**: 查看 LangChain 官方文档学习 SQL Agent

### 核心代码阅读顺序

```
1️⃣ database/sql_database_wrapper.py
   └─ 理解 LangChain SQLDatabase 封装

2️⃣ src/Weather_Service.py (Line 77-133)
   └─ 理解双模式工具实现

3️⃣ src/MainChat_SQLAgent.py (Line 50-115)
   └─ 理解 SQL Agent 创建和使用

4️⃣ UPGRADE_GUIDE.md
   └─ 理解整体优化思路
```

---

## 🎓 实战练习

### 练习 1: 添加新工具

创建一个"人口查询工具"，查询城市人口数据。

**提示**: 参考 `Weather_Service.py` 的 `WeatherTool` 实现。

---

### 练习 2: 自定义 SQL Agent

修改 `MainChat_SQLAgent.py`，添加对多个数据库表的支持。

**提示**: 修改 `include_tables` 参数。

---

### 练习 3: 优化 Prompt

修改 SQL Agent 的系统提示词，提高查询准确率。

**提示**: 在 `MainChat_SQLAgent.py:65` 修改 `system_prefix`。

---

## 🌟 最佳实践

### 1. 性能优化

```python
# 使用连接池避免频繁连接
engine = create_engine(
    connection_url,
    pool_pre_ping=True,      # 自动检测连接有效性
    pool_recycle=3600,       # 1小时回收连接
    pool_size=10,            # 连接池大小
    max_overflow=20          # 最大溢出连接数
)
```

---

### 2. 安全性增强

```python
# 限制可访问的表
db = SQLDatabase(
    engine=engine,
    include_tables=['weather_regions'],  # 白名单
    sample_rows_in_table_info=3          # 限制示例数据
)

# 使用只读数据库用户
DB_USER=readonly_user
```

---

### 3. 错误处理

```python
# 启用详细日志
agent_executor = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,              # 显示执行过程
    handle_parsing_errors=True # 自动处理解析错误
)
```

---

## 📈 下一步

完成快速入门后，你可以：

1. ✅ **阅读升级指南**: `UPGRADE_GUIDE.md`
2. ✅ **查看对比示例**: `python COMPARISON_EXAMPLES.py`
3. ✅ **学习 LangChain 文档**: [SQL Agent](https://python.langchain.com/docs/use_cases/sql/agents)
4. ✅ **实践项目扩展**: 添加新工具、新数据源
5. ✅ **分享你的经验**: 提交 Issue 或 PR

---

## 💡 提示

- SQL Agent 适合**快速原型**和**复杂查询**场景
- 传统模式适合**简单、稳定**的生产环境
- 两种模式可以**并存**，根据需求选择

**开始你的 LangChain SQL Agent 之旅吧！** 🚀
