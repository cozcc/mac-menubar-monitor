# 天元模型控制台

这是一个用于 Hermes、OpenClaw 和 WorkBuddy 模型路由管理的小型本地控制台，也可以作为 OpenClaw 本地插件直接加载。

当前版本已经整理为一个开箱即用的简洁版本地软件，同时保留 OpenClaw 插件和 WorkBuddy / CodeBuddy 配置器能力。

它提供：

- 脱敏查看 Hermes 的 `model` / `custom_providers` 当前状态。
- 脱敏查看 OpenClaw 智能体和 provider 模型目录。
- 通过命令行或浏览器一键切换 provider、Base URL 和模型。
- 真实写入配置前自动创建带时间戳的备份。
- 从最近本地 JSON/JSONL 记录中尽力汇总 Token 用量。
- 一键注册为 OpenClaw 插件，并可写入 WorkBuddy / CodeBuddy 本地模型配置。

## 独立软件

直接启动：

```bash
/Users/vv/.openclaw/openfei/tianyuan-model-console/standalone/TianyuanModelConsole.command
```

默认会在本机启动中文网页控制台：

```text
http://127.0.0.1:51280
```

安装到用户 Applications：

```bash
/Users/vv/.openclaw/openfei/tianyuan-model-console/standalone/install.command
```

默认安装目录：

```text
~/Applications/Tianyuan Model Console
```

安装器只复制软件并注册 OpenClaw 插件。OpenClaw、WorkBuddy / CodeBuddy 等路径和模型参数由用户在网页里的“软件配置”和“WorkBuddy / CodeBuddy”表单中自行填写。

简洁版网页只保留四块：

- 软件状态：显示本地服务、菜单栏 CPU/MEM、Hermes、OpenClaw 和 Token 总量。
- 模型配置：统一填写目标、provider、Base URL、模型，再预演或应用。
- 路径设置：折叠展示 Hermes、OpenClaw、WorkBuddy / CodeBuddy 的本地路径。
- 结果：显示每次操作返回的 JSON。

“软件状态”里可以勾选 `顶端菜单栏显示 CPU / MEM`。勾选后会启动本软件自带的菜单栏 helper，在 macOS 顶端菜单栏显示 `CPU xx%  MEM yy%`；取消勾选会停止该 helper。

网页端可保存的配置包括：

- Hermes 配置文件、密钥文件和会话目录。
- OpenClaw 配置文件、模型目录、会话目录和日志目录。
- WorkBuddy / CodeBuddy 模型配置文件。
- WorkBuddy CLI 路径。

后续要继续修改界面时，核心页面在 `model_console.py` 的 `INDEX_HTML` 常量中；后端接口集中在 `/api/status`、`/api/settings` 和 `/api/apply`。菜单栏 helper 源码在 `menubar/TianyuanMenuBarMonitor.m`。

可选安装后台自启动：

```bash
~/Applications/Tianyuan\ Model\ Console/standalone/install-launchagent.command
```

移除后台自启动：

```bash
~/Applications/Tianyuan\ Model\ Console/standalone/uninstall-launchagent.command
```

默认可写目标：

- `/Users/vv/.hermes/config.yaml`
- `/Users/vv/.openclaw/openclaw.json`
- `/Users/vv/.workbuddy/models.json`
- `/Users/vv/.codebuddy/models.json`

只读发现目标：

- `/Users/vv/.hermes/profiles/agentinf/auth.json`
- `/Users/vv/.openclaw/models.json`
- 最近的 Hermes/OpenClaw session 与 log JSON/JSONL 文件

工具不会主动打印密钥。key、token、cookie、bearer 等敏感字段会在状态输出里脱敏。

## 命令行

```bash
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py status
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py usage
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py plugin-info
```

也可以使用 Node 包装器：

```bash
/Users/vv/.openclaw/openfei/tianyuan-model-console/bin/tianyuan-model-console.js status
```

预演切换：

```bash
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py apply-hermes \
  --provider oxo \
  --model qwen3.7-max \
  --base-url https://api.oxoapi.com/v1 \
  --dry-run

python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py apply-openclaw \
  --agent-id main \
  --provider oxo \
  --model claude-opus-4-7 \
  --base-url https://api.oxoapi.com/v1 \
  --dry-run
```

真实切换时去掉 `--dry-run`。每次真实写入都会在被编辑文件旁边生成备份，例如：

```text
config.yaml.bak.20260606T043807Z_model_console
openclaw.json.bak.20260606T043807Z_model_console
```

## 网页控制台

```bash
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py serve --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

网页端支持预演和真实应用。真实应用同样会先创建备份。

## OpenClaw 插件安装

当前目录已经包含 OpenClaw 插件清单：

- `package.json`
- `openclaw.plugin.json`
- `index.js`
- `bin/tianyuan-model-console.js`

注册到本机 OpenClaw：

```bash
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py install-openclaw-plugin
```

该命令会在 `/Users/vv/.openclaw/openclaw.json` 的 `plugins.allow`、`plugins.entries` 和 `plugins.installs` 中追加 `tianyuan-model-console`，写入前会自动备份。

注册后可用的 OpenClaw CLI 入口：

```bash
openclaw model-console
openclaw model-console-status
openclaw model-console-serve --port 51280
openclaw model-console-install-workbuddy --provider oxo --model qwen3.7-max --base-url https://api.oxoapi.com/v1
```

如果 OpenClaw 当前环境没有暴露这些命令，仍可直接使用本目录的 Python / Node 入口，功能一致。

## WorkBuddy 开箱即用配置

写入 WorkBuddy / CodeBuddy 本地模型配置：

```bash
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py install-workbuddy \
  --provider oxo \
  --model qwen3.7-max \
  --base-url https://api.oxoapi.com/v1
```

网页和命令行都会优先从用户填写的路径读取配置。WorkBuddy / CodeBuddy 写入时，用户可以直接填写 API Key、指定 API Key 环境变量，或允许工具从 Hermes / OpenClaw 的同名 provider 中读取本地密钥；命令输出不会打印密钥。

也可以显式指定环境变量：

```bash
python3 /Users/vv/.openclaw/openfei/tianyuan-model-console/model_console.py install-workbuddy \
  --provider oxo \
  --model qwen3.7-max \
  --base-url https://api.oxoapi.com/v1 \
  --api-key-env OXOAPI_API_KEY
```

安装后可用 WorkBuddy CLI 烟测：

```bash
/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy \
  --print \
  --model qwen3.7-max \
  --tools "" \
  --max-turns 1 \
  --output-format text
```

如果 CLI 返回 `429 当前版本存在已知问题，已在最新版本修复`，说明 WorkBuddy 当前安装包被官方版本门禁拦截；本地 `models.json` 已写好，但需要升级 WorkBuddy 后再运行 CLI。

## 一键启动

```bash
/Users/vv/.openclaw/openfei/tianyuan-model-console/launch.command
```

它会先注册 OpenClaw 插件，再在 `127.0.0.1:51280` 启动网页控制台。

## 打包发布

```bash
cd /Users/vv/.openclaw/openfei/tianyuan-model-console
bash scripts/package_standalone.sh
```

产物会生成在：

```text
dist/tianyuan-model-console-standalone-2026.6.6.tar.gz
dist/tianyuan-model-console-standalone-2026.6.6.tar.gz.sha256
```

打包脚本会排除 `dist/`、`__pycache__`、`.DS_Store`、Python 缓存和本工具生成的配置备份文件。

## 测试

```bash
cd /Users/vv/.openclaw/openfei/tianyuan-model-console
python3 -m unittest -v
```

测试使用临时 fixture 文件，不会修改真实 Hermes/OpenClaw 配置。
