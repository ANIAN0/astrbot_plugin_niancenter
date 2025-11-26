# helloworld

AstrBot 插件模板

A template plugin for AstrBot plugin feature

# 支持

[帮助文档](https://astrbot.app)

## 本插件说明

- 功能：基于本地 `configs/config.json` 中配置的关键字，监听私聊消息并调用对应接口，根据返回结果以不同类型（文本/图片/视频/序列）回复。
- 插件不再暴露对外 HTTP 接口，所有主动消息机制由内部逻辑或云端轮询/调度实现（如需外部触发，请改用云端下发任务并由插件拉取执行）。

## 快速运行

1. 安装依赖：

```powershell
pip install -r requirements.txt
```

2. 将本插件放入 AstrBot 插件目录并按 astrbot 文档加载（或在开发环境中运行）。


3. 插件不对外开放 HTTP 服务；所有消息响应与主动发送请使用本地配置或云端任务/轮询方式实现。

## 配置文件

配置位于 `configs/config.json`，样例如下：

```json
{
	"http_port": 8080,
	"rules": [ ... ]
}
```

请根据需要编辑 `configs/config.json` 中的 `rules` 字段，字段说明见代码注释。

## 配置说明

配置通过编辑 `configs/config.json` 实现。插件会在启动时读取该文件，若希望动态修改配置，请在 AstrBot 管理面板中编辑插件配置或直接修改该文件并重启插件。
