# 快速开始指南

## 安装与基本设置

### 1. 配置config.json

编辑 `configs/config.json`，添加任务中心API配置：

```json
{
  "http_port": 6180,
  "task_center_url": "https://hunian003-message.hf.space/plugins/astr_task_center/api/tasks",
  "authorization": "your_api_token_here",
  "task_poll_interval": 60,
  "rules": [...]
}
```

**关键步骤：**
- ✅ 将 `your_api_token_here` 替换为实际的API token
- ✅ 设置合理的轮询间隔（推荐60-120秒）

### 2. 启动插件

启动AstrBot后，插件会自动：
- 加载配置文件
- 创建cache目录结构
- 启动后台任务轮询线程
- 开始监听私聊消息

### 3. 查看日志

查看插件日志，应该看到类似信息：

```
INFO: 任务管理器已启动
INFO: 启动任务轮询线程
DEBUG: 任务同步完成
```

## 测试主动消息任务

### 步骤1：准备测试任务

通过任务中心API创建一个主动消息任务：

```json
POST /plugins/astr_task_center/api/tasks

{
  "type": "active_message",
  "scheduled_time": "2025-12-01T10:00:00Z",
  "unified_msg_origin": "bot_id:FriendMessage:123456",
  "message_type": "text",
  "context": "你好，这是一条自动消息！"
}
```

### 步骤2：等待轮询同步

插件每隔60秒会轮询一次，新任务会被：
- 同步到本地 (`configs/tasks.json`)
- 标记为已同步到任务中心

### 步骤3：任务执行

当任务的 `scheduled_time` 时间到达时：
- 消息会自动发送给指定用户
- 任务状态更新为 `success` 或 `failed`
- 状态同步回任务中心

## 测试本地存储任务

### 步骤1：创建本地存储任务

```json
POST /plugins/astr_task_center/api/tasks

{
  "type": "local_storage",
  "scheduled_time": "2025-12-01T11:00:00Z",
  "message_type": "text",
  "context": "这是需要保存到本地的内容"
}
```

### 步骤2：检查结果

任务执行后，内容会保存到：
```
plugin_dir/cache/text/1701234567890.txt
```

## 测试富媒体缓存

### 场景1：API返回URL图片

修改rule的reply_type为image：

```json
{
  "name": "获取图片",
  "keywords": ["获取图片"],
  "url": "https://api.example.com/get_image",
  "method": "GET",
  "reply_type": "image"
}
```

用户发送 "获取图片" → API返回URL → 自动缓存到 `cache/image/` → 发送给用户

### 场景2：API返回Base64图片

```json
{
  "name": "生成图片",
  "keywords": ["生成图片"],
  "url": "https://api.example.com/generate_image",
  "method": "POST",
  "reply_type": "image"
}
```

API返回: `{"image": "data:image/png;base64,iVBORw0KGgo..."}`
→ 自动解码保存到 `cache/image/` → 发送给用户

## 文件位置参考

```
astrbot_plugin_niancenter/
├── main.py                 # 插件入口
├── handlers/
│   └── message_handler.py  # 消息处理 + 富媒体缓存
├── core/
│   ├── task_manager.py     # 任务管理（新增）
│   ├── request.py          # HTTP请求工具
│   └── unified_store.py    # 用户映射存储
├── configs/
│   ├── config.json         # 配置文件
│   └── tasks.json          # 任务列表（自动生成）
├── cache/                  # 缓存目录（自动生成）
│   ├── image/
│   ├── voice/
│   ├── video/
│   └── file/
└── FEATURE_GUIDE.md        # 完整功能指南
```

## 常用操作

### 查看当前任务列表
```bash
cat configs/tasks.json
```

### 清空任务列表
```bash
echo "[]" > configs/tasks.json
```

### 手动触发轮询
修改code后重启插件，轮询会立即启动

### 禁用任务轮询
```json
{
  "authorization": ""
}
```

## 故障排除

### 问题1：任务没有同步

**检查项**：
```bash
# 1. 查看logs，看是否有同步错误信息
# 2. 验证token是否正确
# 3. 检查network连接
# 4. 确认任务中心API是否可访问
```

### 问题2：任务已同步但未执行

**检查项**：
```bash
# 1. 查看 configs/tasks.json 中任务的 status 字段
# 2. 检查任务的 scheduled_time 是否已过期（5分钟窗口）
# 3. 查看日志中的执行错误信息
```

### 问题3：缓存文件未生成

**检查项**：
```bash
# 1. 检查 cache/ 目录是否存在
# 2. 查看日志中的下载/解码错误
# 3. 对于URL，确认网络连接
# 4. 对于Base64，确认格式是否正确
```

## 下一步

- 📖 查看 [FEATURE_GUIDE.md](./FEATURE_GUIDE.md) 了解完整功能
- 🔧 根据需求修改 `configs/config.json`
- 📝 为API规则添加更多reply_type支持
- 🐛 如有问题，查看日志排查

---
**版本**: 1.0.0 with Task Management & Media Caching  
**最后更新**: 2025年11月30日
