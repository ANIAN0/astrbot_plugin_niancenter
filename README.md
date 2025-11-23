# helloworld

AstrBot 插件模板

A template plugin for AstrBot plugin feature

# 支持

[帮助文档](https://astrbot.app)

## 本插件说明

- 功能：基于本地 `configs/config.json` 中配置的关键字，监听私聊消息并调用对应接口，根据返回结果以不同类型（文本/图片/视频/序列）回复。
- 暴露对外 HTTP 接口：`POST /send_message`，用于向指定用户发送私聊消息（JSON 格式，包含 `user_id`、`type`、`content`）。

## 快速运行

1. 安装依赖：

```powershell
pip install -r requirements.txt
```

2. 将本插件放入 AstrBot 插件目录并按 astrbot 文档加载（或在开发环境中运行）。

3. 插件会在容器内启动一个 HTTP 服务以便外部调用并支持通过 UI 更新配置。注意 Astr 容器已映射端口范围 `6180-6200`，因此插件默认绑定 `6180`。

4. 调用外部发送接口示例：

```powershell
# POST JSON: {"user_id": "123456", "type": "text", "content": "Hello from API"}
curl -X POST http://localhost:6180/send_message -H "Content-Type: application/json" -d '{"user_id":"123456","type":"text","content":"你好"}'
```

## 配置文件

配置位于 `configs/config.json`，样例如下：

```json
{
	"http_port": 8080,
	"rules": [ ... ]
}
```

请根据需要编辑 `configs/config.json` 中的 `rules` 字段，字段说明见代码注释。

## 配置 API

- 获取当前配置：`GET http://localhost:6180/get_config`
- 更新配置（覆盖文件）：`POST http://localhost:6180/update_config`，Body 为完整的 JSON 配置，会写入 `configs/config.json` 并立即生效。
