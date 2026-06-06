# MiniMonitor

一个最小的 macOS 顶部菜单栏监控程序，显示 CPU 和内存使用率。实现是单文件 Objective-C/AppKit，不依赖 Xcode 工程。

## 运行

```bash
cd /Users/vv/Documents/Playground/mac-menubar-monitor
bash scripts/run.sh
```

运行后会在顶部菜单栏出现：

```text
CPU 12%  MEM 54%
```

点击菜单栏文字可以手动刷新或退出。

`run.sh` 会用 `launchctl submit` 启动一个当前登录会话里的临时任务；这不是开机自启项。退出登录或运行停止脚本后会停止。

也可以用脚本停止：

```bash
bash scripts/stop.sh
```

## 构建

```bash
bash scripts/build.sh
```

生成的程序在：

```text
/Users/vv/Documents/Playground/mac-menubar-monitor/dist/MiniMonitor
```

这是一个普通可执行文件。它启动后不会显示 Dock 图标，只会在顶部菜单栏显示状态。
