# AstrBot 念中心插件

这是一个功能丰富的AstrBot插件，支持关键字触发API调用、主动消息任务轮询、本地存储任务、富媒体缓存以及完整的日志管理系统。

## 核心功能

### 1. 关键字触发API调用 ✅
- 监听私聊消息中的关键字
- 根据`configs/config.json`中的规则调用外部接口
- 支持多种回复类型：text、image、voice、video、file
- 支持自动媒体下载和缓存
- 支持URL和Base64编码格式

### 2. 主动消息任务轮询 ✅
- 定时轮询云端任务中心API
- 自动同步未同步的主动消息任务
- 按执行时间自动发送消息到指定用户
- 支持多种消息类型
- 自动更新任务状态到云端

### 3. 本地存储任务 ✅
- 定时轮询云端获取本地存储任务
- 自动将任务内容保存到本地文件
- 按类型分别存储（image、voice、video、file等）
- 支持URL和Base64双格式

### 4. 富媒体回复缓存优化 ✅
- API返回图片/语音/视频/文件时自动缓存到本地
- 避免重复下载，提高响应速度
- 自动识别MIME类型，确定文件扩展名
- 使用本地文件方式发送而非URL方式

### 5. 完整的日志管理系统 ✅
- 日志自动保存到`logs/niancenter.log`
- 支持按大小自动轮转日志
- **两种日志模式**：
  - **详细模式**（log_level=INFO/DEBUG）：记录完整日志，包括：
    - API请求URL和参数
    - API响应结果
    - 文件下载详情
    - 所有执行步骤
  - **异常模式**（log_level=WARNING/ERROR）：仅记录异常和警告信息
- 可配置日志级别、文件大小限制、备份数量

### 6. 数据查询与展示 ✅
- 查看本地任务列表（总数、状态分布、类型分布）
- 查看用户unified_msg_origin映射
- 查看最近日志内容
- 支持JSON格式导出

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

#### 方式一：通过AstrBot管理面板配置（推荐）
1. 启动AstrBot
2. 进入管理面板 → 插件管理
3. 找到"念中心插件"，点击配置
4. 按需修改配置项

#### 方式二：直接编辑config.json

编辑`configs/config.json`：

```json
{
  "enable_task_polling": true,
  "authorization": "your_token_here",
  "task_poll_interval": 60,
  "enable_logging": true,
  "log_level": "INFO",
  "rules": []
}
```

### 可用指令

用户可在聊天中使用以下指令：

```
/niancenter_logs      - 查看最近50条日志
/niancenter_tasks     - 查看本地任务统计
/niancenter_origins   - 查看用户映射统计
```

## 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_task_polling` | bool | false | 是否启用任务轮询 |
| `task_center_url` | string | 官方地址 | 任务中心API地址 |
| `authorization` | string | 空 | API认证token |
| `task_poll_interval` | int | 60 | 轮询间隔（秒） |
| `enable_logging` | bool | true | 是否启用日志 |
| `log_level` | string | INFO | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `max_log_size_mb` | int | 10 | 日志文件最大大小（MB） |
| `log_backup_count` | int | 5 | 保留的日志备份数量 |

## 日志模式说明

### 详细模式（当log_level=INFO或DEBUG时）

详细日志会记录以下信息：

```
[2025-12-02 10:30:45] [DEBUG] [niancenter_plugin]: 同步active_message任务 - 请求URL: https://...
[2025-12-02 10:30:45] [DEBUG] [niancenter_plugin]: 同步active_message任务 - 请求参数: {...}
[2025-12-02 10:30:45] [DEBUG] [niancenter_plugin]: 同步active_message任务 - 响应结果: [...]
[2025-12-02 10:30:45] [INFO] [niancenter_plugin]: 添加新任务: task_123 (类型: active_message)
```

### 异常模式（当log_level=WARNING或ERROR时）

仅记录异常和重要警告：

```
[2025-12-02 10:30:45] [ERROR] [niancenter_plugin]: 任务同步失败: connection timeout
[2025-12-02 10:30:45] [WARNING] [niancenter_plugin]: 任务轮询已经在运行中
```

## 目录结构

```
astrbot_plugin_niancenter/
├── configs/
│   ├── config.json          # 规则配置
│   ├── tasks.json           # 同步的任务列表（自动生成）
│   └── unified_store.json   # 用户映射（自动生成）
├── core/
│   ├── task_manager.py      # 任务管理核心
│   ├── logger_manager.py    # 日志管理
│   ├── data_viewer.py       # 数据查询
│   ├── request.py           # HTTP请求
│   └── unified_store.py     # 用户映射存储
├── handlers/
│   └── message_handler.py   # 消息处理
├── logs/                    # 日志文件（自动生成）
├── cache/                   # 缓存文件（自动生成）
│   ├── image/
│   ├── voice/
│   ├── video/
│   └── file/
├── main.py                  # 插件入口
├── _conf_schema.json        # 配置Schema定义
└── requirements.txt
```

## 工作流程

### 消息触发流程

```
用户发送私聊消息
    ↓
检查关键字匹配
    ↓
调用外部接口（记录请求参数和响应结果）
    ↓
下载/缓存富媒体内容（如果需要）
    ↓
发送回复消息
```

### 任务轮询流程

```
后台轮询线程（每60秒）
    ↓
查询云端未同步的任务
    ↓
保存到本地 tasks.json
    ↓
标记为已同步
    ↓
检查执行时间是否到期（5分钟窗口）
    ↓
执行任务（发送消息或保存文件）
    ↓
更新任务状态到云端
```

## 常见问题

### Q: 如何查看完整的API请求/响应日志？
A: 在管理面板中设置 `log_level` 为 `INFO` 或 `DEBUG`，即可记录所有详细信息。

### Q: 如何只记录异常日志？
A: 在管理面板中设置 `log_level` 为 `WARNING` 或 `ERROR`。

### Q: 任务没有被执行？
A: 检查以下几点：
1. 确认 `enable_task_polling` 已启用
2. 确认 `authorization` 已配置
3. 查看日志确认是否有错误
4. 确认任务的 `scheduled_time` 在过去5分钟内

### Q: 缓存文件放在哪里？
A: 缓存文件保存在插件目录的 `cache/{type}/` 下，如：
- 图片: `cache/image/1701234567890.png`
- 视频: `cache/video/1701234567890.mp4`

## 技术栈

- Python 3.8+
- aiohttp >= 3.8.0
- AstrBot 官方API

## 支持

[AstrBot 帮助文档](https://astrbot.app)

## 许可证

见 LICENSE 文件
