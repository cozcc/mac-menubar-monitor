# 独立软件入口

本目录提供天元模型控制台的 macOS 独立软件包装：

- `TianyuanModelConsole.command`：双击启动中文网页控制台。
- `install.command`：复制到 `~/Applications/Tianyuan Model Console` 并注册 OpenClaw 插件。
- `install-launchagent.command`：可选安装后台自启动服务。
- `uninstall-launchagent.command`：移除后台自启动服务。
- `com.tianyuan.model-console.plist`：LaunchAgent 模板。
- `app_manifest.json`：产品功能和入口清单。

默认网页地址是 `http://127.0.0.1:51280`。
