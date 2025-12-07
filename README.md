# AstrBot 念中心插件

这是一个功能丰富的AstrBot插件，支持灵感记录、待办管理、关键字触发API调用、主动消息任务轮询、本地存储任务、富媒体缓存以及完整的日志管理系统。

## 核心功能

### 1. 灵感记录功能 ✅
- 支持多类型内容记录：文本、图片、视频、音频、文件
- 自动分组管理（通过 `#分组名` 指定）
- 关键字标记（通过 `@关键字` 指定）
- 关键字搜索检索
- 每日自动生成 Markdown 格式汇总报告
- 手动触发汇总功能

**可用命令**：
- `n记录 内容 #分组 @关键字` - 添加灵感记录
- `n搜索 关键字` - 搜索相关记录
- `nt1` - 手动触发今日笔记汇总

### 2. 待办管理功能 ✅
- 创建待办事项并设置预计完成时间
- 支持多媒体跟进记录（文本、图片、视频、音频）
- 智能时间解析（今日/明日/具体日期时间）
- 待办状态管理（进行中/已完成）
- **双层提醒机制**：
  - 定时提醒：每日 8:00 和 14:00 推送进行中任务
  - 到期提醒：预计完成时间到达时单独提醒
- 每日自动生成 Markdown 格式待办总结
- 手动触发汇总功能

**可用命令**：
- `n待办 内容 by时间` - 创建待办（时间格式：今日/明日/今日 21:00/明日 18:00/12-25 15:00）
- `n跟进 序号 内容` - 添加跟进记录
- `n关闭 序号` - 关闭已完成的待办
- `n看待办` - 查看所有进行中的待办
- `nt2` - 手动触发今日待办汇总
- `n当前时间` - 查看服务器时间

### 3. 关键字触发API调用 ✅
- 监听私聊消息中的关键字
- 根据`configs/config.json`中的规则调用外部接口
- 支持多种回复类型：text、image、voice、video、file
- 支持自动媒体下载和缓存
- 支持URL和Base64编码格式

### 4. 主动消息任务轮询 ✅
- 定时轮询云端任务中心API
- 自动同步未同步的主动消息任务
- 按执行时间自动发送消息到指定用户
- 支持多种消息类型
- 自动更新任务状态到云端

### 5. 本地存储任务 ✅
- 定时轮询云端获取本地存储任务
- 自动将任务内容保存到本地文件
- 按类型分别存储（image、voice、video、file等）
- 支持URL和Base64双格式

### 6. 富媒体回复缓存优化 ✅
- API返回图片/语音/视频/文件时自动缓存到本地
- 避免重复下载，提高响应速度
- 自动识别MIME类型，确定文件扩展名
- 使用本地文件方式发送而非URL方式

### 7. 完整的日志管理系统 ✅
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

### 8. 数据查询与展示 ✅
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

### 管理指令

管理员可在聊天中使用以下指令：

```
/niancenter_logs      - 查看最近50条日志
/niancenter_tasks     - 查看本地任务统计
/niancenter_origins   - 查看用户映射统计
```

### 用户指令

**灵感记录相关**：
```
n记录 内容 #分组 @关键字    - 添加灵感记录（分组和关键字可选）
n搜索 关键字                - 搜索相关记录
nt1                        - 手动触发今日笔记汇总
```

**待办管理相关**：
```
n待办 内容 by时间          - 创建待办（支持：今日/明日/今日21:00/12-25 15:00）
n跟进 序号 内容            - 添加跟进记录（支持文本和多媒体）
n关闭 序号                 - 关闭已完成的待办
n看待办                    - 查看所有进行中的待办
nt2                        - 手动触发今日待办汇总
n当前时间                  - 查看服务器当前时间
```

**账户相关**：
```
n登录                      - 创建账户
n修改密码                  - 修改密码
```

## 配置项说明

### 基础配置

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

### 灵感记录配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_note_summary` | bool | true | 是否启用笔记汇总功能 |
| `note_summary_hour` | int | 22 | 笔记汇总执行小时（0-23） |
| `note_summary_minute` | int | 0 | 笔记汇总执行分钟（0-59） |

### 待办管理配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_todo_features` | bool | true | 是否启用待办功能 |
| `enable_todo_reminder` | bool | true | 是否启用待办定时提醒（8:00和14:00） |
| `enable_todo_summary` | bool | true | 是否启用待办汇总功能 |
| `todo_summary_hour` | int | 22 | 待办汇总执行小时（0-23） |
| `todo_summary_minute` | int | 30 | 待办汇总执行分钟（0-59） |

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
├── api/                      # API请求模块
│   ├── __init__.py
│   └── request.py           # HTTP请求工具
│
├── plugin_config/            # 插件配置模块
│   ├── __init__.py
│   └── logger_manager.py    # 日志管理器
│
├── users/                    # 用户管理模块
│   ├── __init__.py
│   └── user_manager.py      # 用户管理器
│
├── notes/                    # 灵感记录模块
│   ├── __init__.py
│   └── note_manager.py      # 笔记管理器
│
├── todos/                    # 待办管理模块
│   ├── __init__.py
│   └── todo_manager.py      # 待办管理器
│
├── session/                  # 会话管理模块
│   ├── __init__.py
│   └── keyword_handlers.py  # 关键字处理器（处理所有用户命令）
│
├── processing/               # 消息加工模块
│   ├── __init__.py
│   ├── components_extractor.py    # 消息组件提取
│   ├── message_chain_builder.py   # 消息链构建
│   └── rule_processor.py          # 规则处理器
│
├── scheduler/                # 定时任务模块
│   ├── __init__.py
│   ├── task_sync_manager.py       # 任务同步管理器
│   ├── task_executor.py           # 任务执行器
│   ├── note_summary_task.py       # 笔记汇总定时任务
│   ├── todo_summary_task.py       # 待办汇总定时任务
│   └── todo_reminder_task.py      # 待办提醒定时任务
│
├── storage/                  # 本地存储模块
│   ├── __init__.py
│   ├── cache_utils.py             # 缓存工具
│   ├── data_viewer.py             # 数据查看器
│   ├── local.py                   # 本地存储
│   └── unified_store.py           # 统一存储
│
├── core/                     # 核心协调模块
│   ├── __init__.py
│   └── task_manager.py            # 任务管理器（协调者）
│
├── handlers/                 # 主动消息模块
│   ├── __init__.py
│   └── message_handler.py         # 消息处理器
│
├── configs/                  # 配置文件目录
│   ├── config.json          # 主配置文件
│   └── keywords.json        # 关键字配置文件
│
└── main.py                   # 插件主入口
```

## 工作流程

### 灵感记录流程

```
用户发送 n记录 命令
    ↓
解析内容、分组、关键字
    ↓
保存到 notes.json（元数据）
    ↓
文本内容追加到分组文件
    ↓
多媒体文件独立存储并重命名
    ↓
返回成功提示

定时汇总任务（每天22:00）
    ↓
遍历所有用户
    ↓
获取今日笔记
    ↓
生成 Markdown 格式汇总文件
    ↓
以文件形式发送给用户
```

### 待办管理流程

```
用户创建待办（n待办）
    ↓
解析内容和预计完成时间
    ↓
保存到 todos.json
    ↓
分配序号（display_id）
    ↓
返回成功提示

用户添加跟进（n跟进）
    ↓
提取文本和多媒体内容
    ↓
多媒体文件保存到 todo_attachments/
    ↓
添加到待办的 follow_ups 列表
    ↓
返回成功提示

定时提醒任务（每天8:00和14:00）
    ↓
遍历所有用户
    ↓
获取进行中的待办
    ↓
按到期时间分类（已到期/即将到期/今日到期/正常）
    ↓
发送提醒消息

到期提醒任务（每分钟检查）
    ↓
遍历所有用户
    ↓
检查是否有待办在0-5分钟内到期
    ↓
发送到期提醒（仅提醒一次）

汇总任务（每天22:30）
    ↓
遍历所有用户
    ↓
生成今日待办总结（Markdown格式）
    ↓
以文件形式发送给用户
```

### 消息触发流程

```
用户发送私聊消息
    ↓
检查关键字匹配（最长匹配优先）
    ↓
调用对应处理器（记录/待办/API调用）
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

### 灵感记录相关

**Q: 如何指定分组和关键字？**
A: 使用格式：`n记录 内容 #分组名 @关键字1 @关键字2`，分组和关键字都是可选的。

**Q: 记录的文件保存在哪里？**
A: 用户数据保存在 `data/users/{user_id}/` 目录下：
- 文本笔记：`notes/{分组名}.txt`
- 多媒体附件：`attachments/`
- 元数据：`notes.json`

**Q: 如何修改汇总时间？**
A: 在配置文件中修改 `note_summary_hour` 和 `note_summary_minute`。

### 待办管理相关

**Q: 支持哪些时间格式？**
A: 支持以下格式：
- `今日` - 今天18:00
- `明日` - 明天18:00
- `今日 21:00` - 今天21:00
- `明日 18:00` - 明天18:00
- `12-25 15:00` - 具体日期时间

**Q: 待办提醒在什么时候发送？**
A: 有两种提醒：
1. 定时提醒：每天 8:00 和 14:00
2. 到期提醒：预计完成时间到达后的 0-5 分钟内

**Q: 如何添加图片或文件到跟进？**
A: 直接在消息中发送图片/文件，格式：`n跟进 序号 文字描述`（文字可选），插件会自动提取多媒体内容。

**Q: 待办数据保存在哪里？**
A: 保存在 `data/users/{user_id}/` 目录下：
- 待办数据：`todos.json`
- 跟进附件：`todo_attachments/`

### 系统相关

**Q: 如何查看完整的API请求/响应日志？**
A: 在管理面板中设置 `log_level` 为 `INFO` 或 `DEBUG`，即可记录所有详细信息。

**Q: 如何只记录异常日志？**
A: 在管理面板中设置 `log_level` 为 `WARNING` 或 `ERROR`。

**Q: 任务没有被执行？**
A: 检查以下几点：
1. 确认 `enable_task_polling` 已启用
2. 确认 `authorization` 已配置
3. 查看日志确认是否有错误
4. 确认任务的 `scheduled_time` 在过去5分钟内

**Q: 缓存文件放在哪里？**
A: 缓存文件保存在插件目录的 `cache/{type}/` 下，如：
- 图片: `cache/image/1701234567890.png`
- 视频: `cache/video/1701234567890.mp4`

**Q: 如何自定义关键字？**
A: 编辑 `configs/keywords.json` 文件，可以修改或添加新的关键字映射。

## 技术栈

- Python 3.8+
- aiohttp >= 3.8.0
- AstrBot 官方API

## 支持

[AstrBot 帮助文档](https://astrbot.app)

## 许可证

见 LICENSE 文件
