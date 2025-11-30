# AstrBot 念中心插件 - 新功能指南

本文档说明了最新版本中新增的功能及其配置方法。

## 新增功能总览

### 1. 主动消息任务管理 (Active Message Tasks)
- **功能**：支持定时轮询远程任务队列，获取未同步的主动消息任务，并按时间触发发送消息
- **应用场景**：需要在指定时间向特定用户/群组发送消息

### 2. 本地存储任务管理 (Local Storage Tasks)  
- **功能**：支持定时轮询远程任务队列，获取未同步的本地存储任务，并将任务内容保存到本地
- **应用场景**：需要将数据缓存到本地文件系统

### 3. 富媒体回复结果缓存优化
- **功能**：API返回image、voice、video、file等富媒体内容时，自动缓存到本地后再发送
- **应用场景**：避免重复下载，提高响应速度，支持URL和Base64两种格式

## 配置说明

### 基础配置 (config.json)

```json
{
  "task_center_url": "https://hunian003-message.hf.space/plugins/astr_task_center/api/tasks",
  "authorization": "your_api_token_here",
  "task_poll_interval": 60,
  "rules": [...]
}
```

**配置项说明：**

| 配置项 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `task_center_url` | string | 否 | 见上 | 任务中心API地址 |
| `authorization` | string | 否 | 空字符串 | API认证token，留空则禁用任务轮询 |
| `task_poll_interval` | int | 否 | 60 | 轮询间隔，单位秒 |

### 启用任务轮询

1. **获取API Token**
   - 联系任务中心管理员获取authorization token

2. **配置token**
   ```json
   {
     "authorization": "your_token_here"
   }
   ```

3. **设置轮询间隔**（可选）
   ```json
   {
     "task_poll_interval": 30  // 改为30秒轮询一次
   }
   ```

## 任务格式

### 主动消息任务格式

```json
{
  "id": "task_uuid",
  "type": "active_message",
  "scheduled_time": "2025-12-01T10:00:00Z",
  "unified_msg_origin": "bot_id:MessageType:user_id",
  "message_type": "text|image|voice|video|file",
  "context": "消息内容或资源URL/Base64",
  "status": "pending|running|success|failed"
}
```

**字段说明：**
- `type`: 固定值 `active_message`
- `scheduled_time`: 执行时间（ISO 8601格式）
- `unified_msg_origin`: AstrBot统一消息源标识
- `message_type`: 消息类型，支持text/image/voice/video/file
- `context`: 
  - 文本类型：直接文本内容
  - 其他类型：可以是URL或Base64编码数据

### 本地存储任务格式

```json
{
  "id": "task_uuid",
  "type": "local_storage",
  "scheduled_time": "2025-12-01T10:00:00Z",
  "message_type": "text|image|voice|video|file",
  "context": "内容或资源URL/Base64",
  "status": "pending|running|success|failed"
}
```

## 工作流程

### 主动消息任务执行流程

```
1. 后台轮询线程 (每60秒)
   ↓
2. 向任务中心查询未同步的active_message任务
   ↓
3. 保存到本地 (configs/tasks.json)
   ↓
4. 标记为已同步
   ↓
5. 定时检查本地任务列表
   ↓
6. 找到执行时间在过去5分钟内的待执行任务
   ↓
7. 下载/缓存媒体文件（如果是URL/Base64）
   ↓
8. 通过AstrBot API发送消息到unified_msg_origin
   ↓
9. 更新任务状态为success/failed
   ↓
10. 同步状态回任务中心
```

### 本地存储任务执行流程

```
1. 后台轮询线程 (每60秒)
   ↓
2. 向任务中心查询未同步的local_storage任务
   ↓
3. 保存到本地 (configs/tasks.json)
   ↓
4. 标记为已同步
   ↓
5. 定时检查本地任务列表
   ↓
6. 找到执行时间在过去5分钟内的待执行任务
   ↓
7. 根据类型保存内容：
   - 文本：保存为 .txt
   - 图片：保存为 .png/.jpg 等
   - 语音：保存为 .wav/.mp3 等
   - 视频：保存为 .mp4 等
   - 文件：保存原格式
   ↓
8. 文件保存到 cache/{type}/ 目录
   ↓
9. 更新任务状态为success/failed
   ↓
10. 同步状态回任务中心
```

### 富媒体回复缓存流程

```
关键词触发规则
   ↓
调用外部API
   ↓
API返回结果
   ↓
检查reply_type
   ↓
├─ text: 直接发送
│
├─ image: 检查是否需要缓存
│  ├─ URL: 下载到本地 cache/image/ 后发送
│  └─ Base64: 解码到本地 cache/image/ 后发送
│
├─ voice: 同image处理
├─ video: 同image处理  
└─ file: 同image处理
   ↓
发送消息给用户
```

## 缓存目录结构

插件启动时会自动创建以下目录结构：

```
plugin_dir/
├── cache/
│   ├── image/      # 图片缓存
│   ├── voice/      # 语音缓存
│   ├── video/      # 视频缓存
│   └── file/       # 文件缓存
└── configs/
    └── tasks.json  # 任务列表
```

## 错误处理

### 轮询线程错误恢复机制

- **连续错误次数统计**：记录轮询中连续出现的错误
- **指数退避重试**：每次错误后，等待时间呈指数增加（最多8倍）
- **自动停止保护**：连续错误5次后自动停止轮询，防止频繁错误
- **日志记录**：所有错误都会记录到日志供排查

### 任务执行错误处理

- **任务级异常隔离**：单个任务失败不会影响其他任务
- **自动状态更新**：失败的任务会记录错误信息到本地和远程
- **错误信息包含**：`{"error": "具体错误信息"}`

## 日志记录

插件使用AstrBot的logger接口记录日志，关键日志信息：

```
INFO: 启动任务轮询线程
INFO: 添加新任务: xxx (类型: active_message)
INFO: 主动消息任务执行成功: xxx
INFO: 本地存储任务执行成功: xxx -> /path/to/file
DEBUG: 任务同步完成
WARNING: 未配置authorization，跳过任务同步
ERROR: 轮询循环连续失败5次，停止轮询
```

## 常见问题

### Q: 如何禁用任务轮询？
**A**: 删除或注释掉config.json中的`authorization`字段，设置为空字符串，或不填写该字段。

### Q: 任务没有被执行？
**A**: 检查以下几点：
1. 确认已配置authorization
2. 检查插件日志是否有错误信息
3. 确认任务的scheduled_time在过去5分钟内
4. 验证unified_msg_origin格式是否正确
5. 检查network连接是否正常

### Q: 如何查看缓存的文件？
**A**: 缓存文件保存在插件目录的`cache/{type}/`下，如：
- 图片: `plugin_dir/cache/image/1701234567890.png`
- 视频: `plugin_dir/cache/video/1701234567890.mp4`

### Q: Base64数据支持哪些格式？
**A**: 支持标准Base64编码以及带有MIME类型前缀的格式：
- 标准: `aGVsbG8gd29ybGQ=`
- 带前缀: `data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...`

### Q: 能否修改轮询间隔？
**A**: 可以，修改config.json中的`task_poll_interval`值（单位秒）。建议不低于30秒以避免过度请求。

## 升级说明

如果从旧版本升级：

1. **自动创建目录**：首次启动时会自动创建cache目录结构
2. **配置文件兼容**：旧的config.json不需要修改，新增字段有默认值
3. **任务文件**：首次启动会创建tasks.json

## 联系与反馈

如有问题或建议，请联系插件开发者。

---
*文档更新时间：2025年11月30日*
*插件版本：1.0.0 (with task management and media caching)*
