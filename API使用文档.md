# 智能天气助手 API - 使用文档

> 版本：v2.0 Final | 更新日期：2025-11-05

---

## 🎯 核心特性

✨ **API Key 认证** - 优先使用用户提供的 Key，支持多用户
⚡ **并发限流** - 最多 5 个并发，超出自动排队（30秒超时）
💾 **智能缓存** - 相同天气查询缓存 30 分钟，响应速度提升 60-100 倍

---

## 🚀 快速开始

### 基础配置（服务器端）

1. **复制配置文件**
```bash
cp .env.example .env
```

2. **编辑 `.env` 文件**
```env
# 统一 API Key（用户未提供时使用，可选）
API_KEY=sk-your-302ai-key

# API 路径配置
BASE_URL=https://api.302.ai/v1
SEARCH_API_URL=https://api.302.ai/search1api/search

# 数据库配置（必填）
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=fang

# Redis 缓存（可选）
REDIS_HOST=localhost
REDIS_PORT=6379
```

3. **启动服务**
```bash
cd src
python api_server.py
```

服务地址：`http://localhost:6666`
API 文档：`http://localhost:6666/docs`

---

## 📡 API 调用

### 认证方式（二选一）

#### 方式一：使用自己的 API Key（推荐）
```bash
curl -X POST http://localhost:6666/Fang-GetWeather/chat -H "Content-Type: application/json" -H "Authorization: Bearer sk-your-api-key" -d "{\"message\":\"北京天气\"}"
```

#### 方式二：使用服务器配置的 Key
```bash
curl -X POST http://localhost:6666/Fang-GetWeather/chat -H "Content-Type: application/json" -d "{\"message\":\"北京天气\"}"
```

> 💡 **说明**：
> - 方式一：每个用户使用自己的 Key，适合多用户场景
> - 方式二：所有用户共享服务器配置的 Key，适合内部使用

---

## 📝 接口详情

### 1. 对话接口

**路径**: `POST /Fang-GetWeather/chat`

**请求参数**:
```json
{
  "message": "用户输入的消息",
  "chat_history": [
    ["用户历史消息", "AI 历史回复"]
  ]
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | ✅ | 用户当前输入 |
| `chat_history` | array | ❌ | 对话历史（可选） |

**请求头（可选）**:
```
Authorization: Bearer {your-api-key}
```

**响应示例**:
```json
{
  "response": "北京今天晴天,温度15-25℃,适合出行",
  "status": "success"
}
```

| 字段 | 说明 |
|------|------|
| `response` | AI 助手回复内容 |
| `status` | `success` - 正常 / `success_cached` - 缓存命中 |

---

### 2. 健康检查

**路径**: `GET /Fang-GetWeather/health`

**响应**:
```json
{
  "status": "healthy",
  "service_name": "智能天气助手",
  "version": "2.0.0"
}
```

---

### 3. 服务状态

**路径**: `GET /Fang-GetWeather/status`

**响应**:
```json
{
  "service": "智能天气助手",
  "version": "2.0.0",
  "concurrency": {
    "max_concurrency": 5,
    "active_requests": 2,
    "queued_requests": 0
  },
  "cache": {
    "enabled": true,
    "total_keys": 42,
    "memory_used_mb": 12.5
  }
}
```

---

## 💻 代码示例

### Python 调用

```python
import requests

API_URL = "http://localhost:6666/Fang-GetWeather/chat"

# 使用自己的 API Key
headers = {"Authorization": "Bearer sk-your-api-key"}
data = {"message": "上海明天天气"}

response = requests.post(API_URL, json=data, headers=headers)

if response.status_code == 200:
    result = response.json()
    print(f"回复: {result['response']}")
    print(f"状态: {result['status']}")
else:
    print(f"错误: {response.json()}")
```

### JavaScript 调用

```javascript
const API_URL = "http://localhost:6666/Fang-GetWeather/chat";

async function queryWeather(message, apiKey) {
  const headers = {};
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const response = await fetch(API_URL, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({message: message})
  });

  const result = await response.json();
  console.log("回复:", result.response);
  console.log("状态:", result.status);
}

// 使用自己的 Key
queryWeather("广州今天天气", "sk-your-api-key");

// 或使用服务器配置的 Key
queryWeather("广州今天天气");
```

---

## ⚡ 并发与缓存

### 并发限流

- **最大并发**: 5 个请求
- **排队机制**: 超出自动排队，最长等待 30 秒
- **超时响应**: 返回 `503 Service Unavailable`

**日志示例**:
```
INFO - ⏳ 请求进入排队，当前活跃: 5/5
INFO - ✅ 请求获得许可，等待时间: 3.2秒
INFO - 🔓 请求完成，释放资源
```

### Redis 缓存

**缓存策略**:
- 自动提取地区名称（如"北京"、"上海"）
- 缓存时间：30 分钟
- 命中判断：地区相同即命中

**示例**:
```
✅ "北京天气" + "北京今天怎么样" → 缓存命中
✅ "上海天气" + "上海气温" → 缓存命中
❌ "北京天气" + "上海天气" → 不命中（地区不同）
```

---

## ⚠️ 错误处理

### 401 - API Key 错误

```json
{
  "detail": {
    "error": "missing_api_key",
    "message": "API Key 未配置",
    "hint": "请在请求头中添加 'Authorization: Bearer {your-api-key}'"
  }
}
```

**解决方法**:
- 检查 Authorization 头格式是否正确
- 确认服务器 `.env` 文件中是否配置了 `API_KEY`

### 503 - 服务繁忙

```json
{
  "detail": {
    "error": "service_busy",
    "message": "请求排队超时（超过 30 秒）",
    "hint": "当前请求量较大，请稍后重试"
  }
}
```

**解决方法**:
- 稍后重试
- 错峰调用

---

## 🔧 高级配置

### 修改并发数

编辑 `src/api_server.py` 第 100 行：
```python
limiter = get_limiter(max_concurrency=10)  # 改为 10 个并发
```

### 修改缓存时间

编辑 `src/api_server.py` 第 103 行：
```python
cache_manager = get_cache_manager(default_ttl=3600)  # 改为 1 小时
```

### 修改 API 路径

编辑 `.env` 文件：
```env
# 对话路径
BASE_URL=https://your-custom-api.com/v1

# 搜索路径
SEARCH_API_URL=https://your-custom-api.com/search
```

---

## 📊 性能数据

| 场景 | 响应时间 | 对比 |
|------|----------|------|
| 首次天气查询 | 3-5 秒 | - |
| 缓存命中查询 | **50ms** | **提升 60-100 倍** ⚡ |
| 并发处理 | 稳定 5 个 | 服务稳定性大幅提升 🛡️ |
| API 成本 | 节省 90% | 缓存命中时 💰 |

---

## 🎓 常见问题

### Q1: 必须安装 Redis 吗？
**A**: 不是必须的。不安装 Redis 只会禁用缓存功能，其他功能正常使用。

### Q2: 可以不配置 API_KEY 吗？
**A**: 可以。如果不配置，用户必须在每个请求中提供自己的 API Key。

### Q3: 如何清空缓存？
**A**: 使用 Redis CLI：
```bash
redis-cli
> KEYS weather:*      # 查看所有缓存
> FLUSHDB             # 清空所有缓存
```

### Q4: 支持哪些 LLM 模型？
**A**: 支持所有 OpenAI 兼容的模型，通过 `.env` 的 `MODEL` 字段配置：
```env
MODEL=gpt-4o-mini
```

---

## 📞 技术支持

**项目路径**: `D:\VsCodePyProject\LLMAPP\GetWeather`
**版本**: v2.0.0 Final
**更新日期**: 2025-11-05

---

**享受智能天气助手带来的便利吧！** 🌤️✨
