# 天元模型控制台独立软件说明

天元模型控制台现在同时具备三种形态：

- 独立本地软件：双击 `standalone/TianyuanModelConsole.command` 即可启动中文网页控制台。
- OpenClaw 插件：注册后提供 `model-console-status`、`model-console-serve`、`model-console-install-workbuddy` 等命令。
- WorkBuddy / CodeBuddy 配置器：把同一个上游 Base URL、模型 ID 和本地 API Key 写入桌面端模型目录。

## 产品功能

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

安装器会复制本软件、注册 OpenClaw 插件，并尝试写入默认 WorkBuddy / CodeBuddy 模型：

- provider：`oxo`
- Base URL：`https://api.oxoapi.com/v1`
- model：`qwen3.7-max`

如需跳过 WorkBuddy 写入：

```bash
TMC_SKIP_WORKBUDDY=1 /Users/vv/.openclaw/openfei/tianyuan-model-console/standalone/install.command
```

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
