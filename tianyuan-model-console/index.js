"use strict";

const { spawn, spawnSync } = require("node:child_process");
const path = require("node:path");

let emptyPluginConfigSchema = () => ({
  type: "object",
  additionalProperties: true,
  properties: {},
});

try {
  ({ emptyPluginConfigSchema } = require("openclaw/plugin-sdk"));
} catch {
  // The local CLI wrapper works without the OpenClaw SDK. OpenClaw provides it
  // when loading this file as a runtime plugin.
}

const PLUGIN_ID = "tianyuan-model-console";
const PLUGIN_NAME = "天元模型控制台";
const ROOT = __dirname;
const SCRIPT = path.join(ROOT, "model_console.py");

function pythonBin(config) {
  return config?.python || process.env.TMC_PYTHON || "python3";
}

function runPython(args, options = {}) {
  const result = spawnSync(pythonBin(options.config), [SCRIPT, ...args], {
    cwd: ROOT,
    encoding: "utf8",
    env: { ...process.env, ...(options.env || {}) },
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    const message = result.stderr || result.stdout || `退出码 ${result.status}`;
    throw new Error(message.trim());
  }
  return result.stdout.trim();
}

function startServer(config = {}) {
  const host = config.host || "127.0.0.1";
  const port = String(config.port || 51280);
  const child = spawn(pythonBin(config), [SCRIPT, "serve", "--host", host, "--port", port], {
    cwd: ROOT,
    detached: true,
    stdio: "ignore",
    env: { ...process.env },
  });
  child.unref();
  return `http://${host}:${port}`;
}

function registerCli(api) {
  if (!api?.registerCli) {
    return;
  }
  api.registerCli((ctx) => {
    ctx.program
      .command("model-console")
      .description("天元模型控制台：查看/切换 Hermes、OpenClaw、WorkBuddy 模型路由")
      .option("--json", "输出 JSON")
      .action(() => {
        const output = runPython(["plugin-info"], { config: ctx.config });
        console.log(output);
      });

    ctx.program
      .command("model-console-status")
      .description("输出脱敏后的 Hermes / OpenClaw 模型路由状态")
      .option("--no-usage", "跳过 Token 用量扫描")
      .action((opts) => {
        const args = ["status"];
        if (opts.noUsage) args.push("--no-usage");
        console.log(runPython(args, { config: ctx.config }));
      });

    ctx.program
      .command("model-console-serve")
      .description("启动天元模型控制台网页")
      .option("--host <host>", "监听地址", "127.0.0.1")
      .option("--port <port>", "监听端口", "51280")
      .action((opts) => {
        const url = startServer({ ...ctx.config, host: opts.host, port: Number(opts.port) });
        console.log(`天元模型控制台已启动：${url}`);
      });

    ctx.program
      .command("model-console-install-workbuddy")
      .description("把一个上游模型写入 WorkBuddy / CodeBuddy 本地模型配置")
      .requiredOption("--provider <provider>", "上游通道名，例如 oxo")
      .requiredOption("--model <model>", "实际调用的模型 ID")
      .requiredOption("--base-url <url>", "OpenAI 兼容 Base URL")
      .option("--api-key-env <env>", "从指定环境变量读取 API Key")
      .option("--supports-tool-call", "声明该模型支持工具调用")
      .option("--dry-run", "只预演，不写入配置")
      .action((opts) => {
        const args = [
          "install-workbuddy",
          "--provider",
          opts.provider,
          "--model",
          opts.model,
          "--base-url",
          opts.baseUrl,
        ];
        if (opts.apiKeyEnv) args.push("--api-key-env", opts.apiKeyEnv);
        if (opts.supportsToolCall) args.push("--supports-tool-call");
        if (opts.dryRun) args.push("--dry-run");
        console.log(runPython(args, { config: ctx.config }));
      });
  }, {
    commands: [
      "model-console",
      "model-console-status",
      "model-console-serve",
      "model-console-install-workbuddy",
    ],
  });
}

function registerTools(api) {
  if (!api?.registerTool) {
    return;
  }
  api.registerTool({
    name: "tianyuan_model_console_status",
    description: "查看本机 Hermes / OpenClaw 模型路由和 Token 用量，返回脱敏 JSON。",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        no_usage: {
          type: "boolean",
          description: "是否跳过 Token 用量扫描。",
        },
      },
    },
    async execute(input) {
      const args = ["status"];
      if (input?.no_usage) args.push("--no-usage");
      return JSON.parse(runPython(args, { config: api.config }));
    },
  });

  api.registerTool({
    name: "tianyuan_model_console_open",
    description: "启动本地网页控制台并返回 URL。",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        host: { type: "string" },
        port: { type: "number" },
      },
    },
    async execute(input) {
      const url = startServer({ ...api.config, host: input?.host, port: input?.port });
      return { url };
    },
  });
}

const plugin = {
  id: PLUGIN_ID,
  name: PLUGIN_NAME,
  description: "本地监控并切换 Hermes、OpenClaw、WorkBuddy 的上游 Base URL、模型和 Token 用量。",
  configSchema: emptyPluginConfigSchema(),
  register(api) {
    registerCli(api);
    registerTools(api);
  },
};

module.exports = plugin;
module.exports.default = plugin;
