# 天元模型控制台独立软件说明

天元模型控制台现在同时具备三种形态：

- 独立本地软件：双击 `standalone/TianyuanModelConsole.command` 即可启动简洁版中文网页控制台。
- OpenClaw 插件：注册后提供 `model-console-status`、`model-console-serve`、`model-console-install-workbuddy` 等命令。
- WorkBuddy / CodeBuddy 配置器：把同一个上游 Base URL、模型 ID 和本地 API Key 写入桌面端模型目录。

## 产品功能

- 简洁版首页：状态、模型配置、路径设置、结果四块。
- 监控 Hermes 当前 `model.default`、`model.provider`、`model.base_url` 和 `custom_providers`。
- 监控 OpenClaw 智能体、默认模型、provider、Base URL 和本地模型目录。
- 在网页或命令行中预演/应用模型切换，具体到 provider、Base URL、模型 ID 和 API 模式。
- 从 Hermes/OpenClaw 最近 JSON/JSONL 记录中推断 Token 用量，按模型和来源汇总。
- 写入前自动备份真实配置文件，不在输出中泄露 API Key。
- 一键注册 OpenClaw 插件，并一键写入 WorkBuddy / CodeBuddy 模型配置。

## 启动

直接运行：

```bash
/Users/vv/.openclaw/openfei/tianyuan-model-console/standalone/TianyuanModelConsole.command
```

默认地址：

```text
http://127.0.0.1:51280
```

也可以指定端口：

```bash
TMC_PORT=51380 /Users/vv/.openclaw/openfei/tianyuan-model-console/standalone/TianyuanModelConsole.command
```

## 安装到用户 Applications

运行：

```bash
/Users/vv/.openclaw/openfei/tianyuan-model-console/standalone/install.command
```

默认安装目录：

```text
~/Applications/Tianyuan Model Console
```

安装器只复制本软件并注册 OpenClaw 插件。OpenClaw、WorkBuddy / CodeBuddy 等路径和模型参数由用户打开网页后自行填写。

网页端提供：

- “软件配置”：保存 Hermes、OpenClaw、WorkBuddy / CodeBuddy 的配置文件和日志/会话目录。
- “WorkBuddy / CodeBuddy”：填写 provider、Base URL、模型 ID、API Key 来源、工具调用和图片能力，再预演或应用。

后续修改界面主要编辑 `model_console.py` 的 `INDEX_HTML`；后端 API 入口保持在 `/api/status`、`/api/settings` 和 `/api/apply`。

## 打包发布

```bash
cd /Users/vv/.openclaw/openfei/tianyuan-model-console
bash scripts/package_standalone.sh
```

产物会输出到：

```text
dist/tianyuan-model-console-standalone-2026.6.6.tar.gz
```

包内不包含本地备份、缓存、`dist/` 目录或密钥文件。
