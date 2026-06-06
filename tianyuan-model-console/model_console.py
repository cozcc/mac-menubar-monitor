#!/usr/bin/env python3
"""Hermes 和 OpenClaw 的本地模型路由控制台。

The tool is intentionally dependency-free. It reads actual local configuration,
redacts secrets, can update the small routing fields needed for model switches,
and keeps timestamped backups before every real write.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_HERMES_CONFIG = Path("/Users/vv/.hermes/config.yaml")
DEFAULT_HERMES_AUTH = Path("/Users/vv/.hermes/profiles/agentinf/auth.json")
DEFAULT_HERMES_SESSIONS = Path("/Users/vv/.hermes/profiles/agentinf/sessions")
DEFAULT_OPENCLAW_CONFIG = Path("/Users/vv/.openclaw/openclaw.json")
DEFAULT_OPENCLAW_MODELS = Path("/Users/vv/.openclaw/models.json")
DEFAULT_OPENCLAW_SESSIONS = Path("/Users/vv/.openclaw/agents/main/sessions")
DEFAULT_OPENCLAW_LOGS = Path("/Users/vv/.openclaw/logs")
DEFAULT_WORKBUDDY_MODELS = Path("/Users/vv/.workbuddy/models.json")
DEFAULT_CODEBUDDY_MODELS = Path("/Users/vv/.codebuddy/models.json")
DEFAULT_WORKBUDDY_CLI = Path("/Applications/WorkBuddy.app/Contents/Resources/app.asar.unpacked/cli/bin/codebuddy")
DEFAULT_APP_CONFIG = Path.home() / ".tianyuan-model-console" / "config.json"

PLUGIN_ID = "tianyuan-model-console"
PLUGIN_NAME = "天元模型控制台"
PLUGIN_PACKAGE_NAME = "@tianyuan/model-console-openclaw"
PLUGIN_VERSION = "2026.6.6"
PLUGIN_ROOT = Path(__file__).resolve().parent

SECRET_KEY_RE = re.compile(r"(key|token|secret|password|cookie|bearer|authorization)", re.I)
SAFE_SECRET_STATUS_KEYS = {
    "key_env",
    "has_api_key",
    "credential_present",
    "api_key_source",
    "api_key_written",
}

SETTING_PATH_KEYS = {
    "hermes_config": ("TMC_HERMES_CONFIG", DEFAULT_HERMES_CONFIG),
    "hermes_auth": ("TMC_HERMES_AUTH", DEFAULT_HERMES_AUTH),
    "hermes_sessions": ("TMC_HERMES_SESSIONS", DEFAULT_HERMES_SESSIONS),
    "openclaw_config": ("TMC_OPENCLAW_CONFIG", DEFAULT_OPENCLAW_CONFIG),
    "openclaw_models": ("TMC_OPENCLAW_MODELS", DEFAULT_OPENCLAW_MODELS),
    "openclaw_sessions": ("TMC_OPENCLAW_SESSIONS", DEFAULT_OPENCLAW_SESSIONS),
    "openclaw_logs": ("TMC_OPENCLAW_LOGS", DEFAULT_OPENCLAW_LOGS),
    "workbuddy_models": ("TMC_WORKBUDDY_MODELS", DEFAULT_WORKBUDDY_MODELS),
    "codebuddy_models": ("TMC_CODEBUDDY_MODELS", DEFAULT_CODEBUDDY_MODELS),
    "workbuddy_cli": ("TMC_WORKBUDDY_CLI", DEFAULT_WORKBUDDY_CLI),
}
TOKEN_KEYS = {
    "prompt": {
        "prompt_tokens",
        "input_tokens",
        "input_token_count",
        "inputTokenCount",
        "promptTokens",
    },
    "completion": {
        "completion_tokens",
        "output_tokens",
        "output_token_count",
        "outputTokenCount",
        "completionTokens",
    },
    "total": {
        "total_tokens",
        "total_token_count",
        "totalTokenCount",
        "totalTokens",
    },
    "cache_read": {
        "cache_read_input_tokens",
        "cached_tokens",
        "cacheRead",
        "cache_read",
    },
    "cache_write": {
        "cache_creation_input_tokens",
        "cacheWrite",
        "cache_write",
    },
}


@dataclass(frozen=True)
class Paths:
    hermes_config: Path = DEFAULT_HERMES_CONFIG
    hermes_auth: Path = DEFAULT_HERMES_AUTH
    hermes_sessions: Path = DEFAULT_HERMES_SESSIONS
    openclaw_config: Path = DEFAULT_OPENCLAW_CONFIG
    openclaw_models: Path = DEFAULT_OPENCLAW_MODELS
    openclaw_sessions: Path = DEFAULT_OPENCLAW_SESSIONS
    openclaw_logs: Path = DEFAULT_OPENCLAW_LOGS
    workbuddy_models: Path = DEFAULT_WORKBUDDY_MODELS
    codebuddy_models: Path = DEFAULT_CODEBUDDY_MODELS
    workbuddy_cli: Path = DEFAULT_WORKBUDDY_CLI

    @classmethod
    def from_env(cls, settings: dict[str, Any] | None = None) -> "Paths":
        settings = load_user_settings() if settings is None else settings

        def configured_path(key: str) -> Path:
            env_name, default = SETTING_PATH_KEYS[key]
            value = os.getenv(env_name) or settings.get(key) or str(default)
            return Path(str(value)).expanduser()

        return cls(
            hermes_config=configured_path("hermes_config"),
            hermes_auth=configured_path("hermes_auth"),
            hermes_sessions=configured_path("hermes_sessions"),
            openclaw_config=configured_path("openclaw_config"),
            openclaw_models=configured_path("openclaw_models"),
            openclaw_sessions=configured_path("openclaw_sessions"),
            openclaw_logs=configured_path("openclaw_logs"),
            workbuddy_models=configured_path("workbuddy_models"),
            codebuddy_models=configured_path("codebuddy_models"),
            workbuddy_cli=configured_path("workbuddy_cli"),
        )


def now_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as fh:
        fh.write(text)
        tmp_name = fh.name
    os.replace(tmp_name, path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def app_config_path() -> Path:
    return Path(os.getenv("TMC_APP_CONFIG", str(DEFAULT_APP_CONFIG))).expanduser()


def load_user_settings(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or app_config_path()
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_user_settings(payload: dict[str, Any], config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or app_config_path()
    settings = load_user_settings(path)
    for key in SETTING_PATH_KEYS:
        if key not in payload:
            continue
        value = str(payload.get(key) or "").strip()
        if value:
            settings[key] = str(Path(value).expanduser())
        else:
            settings.pop(key, None)
    atomic_write_json(path, settings)
    return {
        "config_path": str(path),
        "settings": settings,
        "effective_paths": paths_to_dict(Paths.from_env(settings=settings)),
    }


def paths_to_dict(paths: Paths) -> dict[str, str]:
    return {
        "hermes_config": str(paths.hermes_config),
        "hermes_auth": str(paths.hermes_auth),
        "hermes_sessions": str(paths.hermes_sessions),
        "openclaw_config": str(paths.openclaw_config),
        "openclaw_models": str(paths.openclaw_models),
        "openclaw_sessions": str(paths.openclaw_sessions),
        "openclaw_logs": str(paths.openclaw_logs),
        "workbuddy_models": str(paths.workbuddy_models),
        "codebuddy_models": str(paths.codebuddy_models),
        "workbuddy_cli": str(paths.workbuddy_cli),
    }


def settings_info(paths: Paths) -> dict[str, Any]:
    return {
        "config_path": str(app_config_path()),
        "persisted": load_user_settings(),
        "effective_paths": paths_to_dict(paths),
        "env_overrides": {key: env for key, (env, _) in SETTING_PATH_KEYS.items() if os.getenv(env)},
    }


def backup_file(path: Path) -> Path:
    backup = path.with_name(f"{path.name}.bak.{now_stamp()}_model_console")
    shutil.copy2(path, backup)
    return backup


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if str(key) not in SAFE_SECRET_STATUS_KEYS and SECRET_KEY_RE.search(str(key)):
                out[key] = "<redacted>" if item not in (None, "") else item
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def yaml_scalar(value: str | None) -> str:
    if value is None:
        return ""
    value = str(value)
    if value == "":
        return "''"
    if re.search(r"[\n#\[\]{}]", value) or value.strip() != value:
        return json.dumps(value, ensure_ascii=False)
    return value


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "''", '""'}:
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def parse_hermes_config(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {"model": {}, "custom_providers": []}
    section: str | None = None
    current_provider: dict[str, Any] | None = None

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if not raw.startswith(" ") and stripped.endswith(":") and not stripped.startswith("- "):
            section = stripped[:-1]
            current_provider = None
            continue
        if section == "model" and raw.startswith("  ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            parsed["model"][key.strip()] = parse_scalar(value)
            continue
        if section == "custom_providers":
            if stripped.startswith("- "):
                current_provider = {}
                parsed["custom_providers"].append(current_provider)
                rest = stripped[2:]
                if ":" in rest:
                    key, value = rest.split(":", 1)
                    current_provider[key.strip()] = parse_scalar(value)
                continue
            if current_provider is not None and raw.startswith("  ") and ":" in stripped:
                key, value = stripped.split(":", 1)
                current_provider[key.strip()] = parse_scalar(value)
    return parsed


def find_section(lines: list[str], name: str) -> tuple[int | None, int | None]:
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == f"{name}:" and not line.startswith(" "):
            start = idx
            break
    if start is None:
        return None, None
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        line = lines[idx]
        if not line.strip():
            continue
        if not line.startswith(" ") and not line.startswith("- ") and line.strip().endswith(":"):
            end = idx
            break
    return start, end


def set_mapping_section(text: str, section: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    start, end = find_section(lines, section)
    if start is None or end is None:
        insert = [f"{section}:"] + [f"  {key}: {yaml_scalar(value)}" for key, value in updates.items()]
        return "\n".join(insert + [""] + lines) + "\n"

    found: set[str] = set()
    for idx in range(start + 1, end):
        stripped = lines[idx].strip()
        if not lines[idx].startswith("  ") or ":" not in stripped:
            continue
        key = stripped.split(":", 1)[0].strip()
        if key in updates:
            lines[idx] = f"  {key}: {yaml_scalar(updates[key])}"
            found.add(key)

    insert_at = start + 1
    for idx in range(start + 1, end):
        if lines[idx].startswith("  ") and ":" in lines[idx].strip():
            insert_at = idx + 1
    for key, value in updates.items():
        if key not in found:
            lines.insert(insert_at, f"  {key}: {yaml_scalar(value)}")
            insert_at += 1
    return "\n".join(lines) + "\n"


def provider_blocks(lines: list[str], start: int, end: int) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    idx = start + 1
    while idx < end:
        line = lines[idx]
        match = re.match(r"^-\s+name:\s*(.+?)\s*$", line)
        if not match:
            idx += 1
            continue
        block_start = idx
        name = str(parse_scalar(match.group(1))).strip()
        idx += 1
        while idx < end and not re.match(r"^-\s+name:\s*", lines[idx]):
            idx += 1
        blocks.append((block_start, idx, name))
    return blocks


def set_custom_provider(
    text: str,
    provider: str,
    *,
    base_url: str,
    model: str,
    api_mode: str,
    key_env: str | None = None,
) -> str:
    lines = text.splitlines()
    start, end = find_section(lines, "custom_providers")
    if start is None or end is None:
        tail = [
            "custom_providers:",
            f"- name: {yaml_scalar(provider)}",
            f"  base_url: {yaml_scalar(base_url)}",
            f"  api_mode: {yaml_scalar(api_mode)}",
            f"  model: {yaml_scalar(model)}",
        ]
        if key_env:
            tail.insert(3, f"  key_env: {yaml_scalar(key_env)}")
        return "\n".join(lines + [""] + tail) + "\n"

    updates = {"base_url": base_url, "api_mode": api_mode, "model": model}
    if key_env:
        updates["key_env"] = key_env

    for block_start, block_end, name in provider_blocks(lines, start, end):
        if name != provider:
            continue
        found: set[str] = set()
        for idx in range(block_start + 1, block_end):
            stripped = lines[idx].strip()
            if not lines[idx].startswith("  ") or ":" not in stripped:
                continue
            key = stripped.split(":", 1)[0].strip()
            if key in updates:
                lines[idx] = f"  {key}: {yaml_scalar(updates[key])}"
                found.add(key)
        insert_at = block_end
        for key, value in updates.items():
            if key not in found:
                lines.insert(insert_at, f"  {key}: {yaml_scalar(value)}")
                insert_at += 1
        return "\n".join(lines) + "\n"

    new_block = [
        f"- name: {yaml_scalar(provider)}",
        f"  base_url: {yaml_scalar(base_url)}",
        f"  api_mode: {yaml_scalar(api_mode)}",
        f"  model: {yaml_scalar(model)}",
    ]
    if key_env:
        new_block.insert(2, f"  key_env: {yaml_scalar(key_env)}")
    lines[end:end] = new_block
    return "\n".join(lines) + "\n"


def normalize_provider_name(provider: str) -> str:
    provider = provider.strip()
    if provider.startswith("custom:"):
        return provider.split(":", 1)[1].strip()
    return provider


def update_hermes_config_text(
    text: str,
    *,
    provider: str,
    model: str,
    base_url: str,
    api_mode: str = "chat_completions",
    key_env: str | None = None,
) -> str:
    provider_name = normalize_provider_name(provider)
    text = set_mapping_section(
        text,
        "model",
        {
            "default": model,
            "provider": f"custom:{provider_name}",
            "base_url": base_url,
            "api_mode": api_mode,
        },
    )
    return set_custom_provider(
        text,
        provider_name,
        base_url=base_url,
        model=model,
        api_mode=api_mode,
        key_env=key_env,
    )


def summarize_hermes(paths: Paths) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "config_path": str(paths.hermes_config),
        "auth_path": str(paths.hermes_auth),
        "config_exists": paths.hermes_config.exists(),
        "auth_exists": paths.hermes_auth.exists(),
        "model": {},
        "custom_providers": [],
        "auth": {},
    }
    if paths.hermes_config.exists():
        cfg = parse_hermes_config(read_text(paths.hermes_config))
        summary["model"] = cfg.get("model", {})
        summary["custom_providers"] = redact(cfg.get("custom_providers", []))
    if paths.hermes_auth.exists():
        try:
            auth = read_json(paths.hermes_auth)
            providers = auth.get("providers", {}) if isinstance(auth, dict) else {}
            summary["auth"] = {
                "active_provider": auth.get("active_provider") if isinstance(auth, dict) else None,
                "providers": redact(
                    {
                        name: {
                            "base_url": value.get("base_url"),
                            "model": value.get("model"),
                            "api_mode": value.get("api_mode"),
                            "has_api_key": bool(value.get("api_key")),
                        }
                        for name, value in providers.items()
                        if isinstance(value, dict)
                    }
                ),
            }
        except (OSError, json.JSONDecodeError) as exc:
            summary["auth_error"] = str(exc)
    return summary


def provider_from_model(model_ref: str) -> tuple[str | None, str]:
    if "/" not in model_ref:
        return None, model_ref
    provider, model = model_ref.split("/", 1)
    return provider, model


def summarize_openclaw(paths: Paths) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "config_path": str(paths.openclaw_config),
        "models_path": str(paths.openclaw_models),
        "config_exists": paths.openclaw_config.exists(),
        "models_exists": paths.openclaw_models.exists(),
        "agents": [],
        "providers": {},
        "read_only_models_catalog": {},
    }
    if paths.openclaw_config.exists():
        data = read_json(paths.openclaw_config)
        models = data.get("models", {}) if isinstance(data, dict) else {}
        providers = models.get("providers", {}) if isinstance(models, dict) else {}
        summary["providers"] = {
            name: {
                "baseUrl": value.get("baseUrl"),
                "api": value.get("api"),
                "model_count": len(value.get("models", []) or []),
                "models": [m.get("id") for m in (value.get("models", []) or []) if isinstance(m, dict)],
            }
            for name, value in providers.items()
            if isinstance(value, dict)
        }
        agents = (data.get("agents") or {}).get("list", []) if isinstance(data, dict) else []
        summary["default_model"] = ((data.get("agents") or {}).get("defaults") or {}).get("model", {}).get("primary")
        summary["agents"] = [
            {
                "id": agent.get("id"),
                "name": agent.get("name"),
                "default": bool(agent.get("default")),
                "model": agent.get("model"),
                "provider": provider_from_model(str(agent.get("model") or ""))[0],
                "workspace": agent.get("workspace"),
            }
            for agent in agents
            if isinstance(agent, dict)
        ]
    if paths.openclaw_models.exists():
        try:
            data = read_json(paths.openclaw_models)
            providers = data.get("providers", {}) if isinstance(data, dict) else {}
            summary["read_only_models_catalog"] = {
                name: {
                    "baseUrl": value.get("baseUrl"),
                    "api": value.get("api"),
                    "model_count": len(value.get("models", []) or []),
                }
                for name, value in providers.items()
                if isinstance(value, dict)
            }
        except (OSError, json.JSONDecodeError) as exc:
            summary["models_error"] = str(exc)
    return redact(summary)


def coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def usage_from_dict(obj: dict[str, Any], source: str, model_hint: str | None = None) -> dict[str, Any] | None:
    model = obj.get("model") or obj.get("model_id") or obj.get("modelId") or model_hint or "unknown"
    totals = {"prompt": 0, "completion": 0, "total": 0, "cache_read": 0, "cache_write": 0}
    for bucket, keys in TOKEN_KEYS.items():
        for key in keys:
            totals[bucket] += coerce_int(obj.get(key))
    if not any(totals.values()):
        return None
    if totals["total"] == 0:
        totals["total"] = totals["prompt"] + totals["completion"]
    return {"source": source, "model": str(model), **totals}


def walk_usage(obj: Any, source: str, out: list[dict[str, Any]], model_hint: str | None = None) -> None:
    if isinstance(obj, dict):
        model = obj.get("model") or obj.get("model_id") or obj.get("modelId") or model_hint
        direct = usage_from_dict(obj, source, model)
        if direct:
            out.append(direct)
        usage = obj.get("usage")
        if isinstance(usage, dict):
            record = usage_from_dict(usage, source, model)
            if record:
                out.append(record)
        for key, value in obj.items():
            if key == "usage":
                continue
            walk_usage(value, source, out, model)
    elif isinstance(obj, list):
        for item in obj:
            walk_usage(item, source, out, model_hint)


def recent_files(root: Path, patterns: tuple[str, ...], limit: int, max_bytes: int) -> list[Path]:
    if not root.exists():
        return []
    paths: list[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if not any(fnmatch.fnmatch(filename, pattern) for pattern in patterns):
                continue
            path = Path(dirpath) / filename
            try:
                if path.stat().st_size <= max_bytes:
                    paths.append(path)
            except OSError:
                continue
    paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return paths[:limit]


def scan_json_file(path: Path, source_name: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    try:
        if path.suffix == ".jsonl" or ".jsonl" in path.name:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        walk_usage(json.loads(line), source_name, records)
                    except json.JSONDecodeError:
                        continue
        else:
            walk_usage(read_json(path), source_name, records)
    except OSError:
        pass
    return records


def summarize_usage(paths: Paths, file_limit: int = 80, max_file_mb: int = 8) -> dict[str, Any]:
    max_bytes = max_file_mb * 1024 * 1024
    sources = [
        ("openclaw_sessions", paths.openclaw_sessions, ("*.jsonl", "*.json")),
        ("openclaw_logs", paths.openclaw_logs, ("*.jsonl", "*.json")),
        ("hermes_sessions", paths.hermes_sessions, ("*.json", "*.jsonl")),
    ]
    records: list[dict[str, Any]] = []
    scanned: list[str] = []
    for source_name, root, patterns in sources:
        for path in recent_files(root, patterns, file_limit, max_bytes):
            scanned.append(str(path))
            records.extend(scan_json_file(path, source_name))

    by_model: dict[str, dict[str, int]] = {}
    by_source: dict[str, dict[str, int]] = {}
    total = {"prompt": 0, "completion": 0, "total": 0, "cache_read": 0, "cache_write": 0}
    for record in records:
        model = record["model"]
        source = record["source"]
        by_model.setdefault(model, total.copy())
        by_source.setdefault(source, total.copy())
        for key in total:
            value = coerce_int(record.get(key))
            total[key] += value
            by_model[model][key] += value
            by_source[source][key] += value
    return {
        "record_count": len(records),
        "scanned_file_count": len(scanned),
        "scanned_files_sample": scanned[:12],
        "totals": total,
        "by_model": by_model,
        "by_source": by_source,
        "note": "Token 用量来自最近本地 JSON/JSONL 记录中可识别的 token 字段，属于推断汇总。",
    }


def apply_hermes(paths: Paths, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    required = ["provider", "model", "base_url"]
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    old_text = read_text(paths.hermes_config)
    new_text = update_hermes_config_text(
        old_text,
        provider=str(payload["provider"]).strip(),
        model=str(payload["model"]).strip(),
        base_url=str(payload["base_url"]).strip().rstrip("/"),
        api_mode=str(payload.get("api_mode") or "chat_completions").strip(),
        key_env=str(payload.get("key_env") or "").strip() or None,
    )
    parsed = parse_hermes_config(new_text)
    result = {
        "target": str(paths.hermes_config),
        "dry_run": dry_run,
        "changed": new_text != old_text,
        "backup": None,
        "resulting_model": parsed.get("model", {}),
    }
    if dry_run or new_text == old_text:
        return result
    backup = backup_file(paths.hermes_config)
    atomic_write_text(paths.hermes_config, new_text)
    result["backup"] = str(backup)
    return result


def ensure_openclaw_provider(data: dict[str, Any], provider: str, base_url: str | None) -> dict[str, Any]:
    models = data.setdefault("models", {})
    providers = models.setdefault("providers", {})
    entry = providers.setdefault(provider, {"api": "openai-completions", "models": []})
    if base_url:
        entry["baseUrl"] = base_url.rstrip("/")
    entry.setdefault("api", "openai-completions")
    entry.setdefault("models", [])
    return entry


def ensure_openclaw_model(provider_entry: dict[str, Any], model: str) -> None:
    entries = provider_entry.setdefault("models", [])
    for item in entries:
        if isinstance(item, dict) and item.get("id") == model:
            return
    entries.append(
        {
            "id": model,
            "name": model,
            "reasoning": False,
            "input": ["text"],
            "contextWindow": 131072,
            "maxTokens": 8192,
        }
    )


def apply_openclaw(paths: Paths, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    required = ["provider", "model"]
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    provider = str(payload["provider"]).strip()
    model = str(payload["model"]).strip()
    agent_id = str(payload.get("agent_id") or "main").strip()
    base_url = str(payload.get("base_url") or "").strip() or None
    data = read_json(paths.openclaw_config)
    before = json.dumps(data, sort_keys=True, ensure_ascii=False)
    provider_entry = ensure_openclaw_provider(data, provider, base_url)
    ensure_openclaw_model(provider_entry, model)
    model_ref = f"{provider}/{model}"

    agents = data.setdefault("agents", {})
    defaults = agents.setdefault("defaults", {}).setdefault("model", {})
    if agent_id in {"", "defaults", "default"}:
        defaults["primary"] = model_ref
    else:
        for agent in agents.setdefault("list", []):
            if isinstance(agent, dict) and agent.get("id") == agent_id:
                agent["model"] = model_ref
                if agent.get("default"):
                    defaults["primary"] = model_ref
                break
        else:
            raise ValueError(f"agent_id not found: {agent_id}")

    after = json.dumps(data, sort_keys=True, ensure_ascii=False)
    result = {
        "target": str(paths.openclaw_config),
        "dry_run": dry_run,
        "changed": before != after,
        "backup": None,
        "model_ref": model_ref,
        "agent_id": agent_id,
    }
    if dry_run or before == after:
        return result
    backup = backup_file(paths.openclaw_config)
    atomic_write_json(paths.openclaw_config, data)
    result["backup"] = str(backup)
    return result


def plugin_info(paths: Paths) -> dict[str, Any]:
    installed: dict[str, Any] = {"registered": False}
    if paths.openclaw_config.exists():
        try:
            data = read_json(paths.openclaw_config)
            plugins = data.get("plugins", {}) if isinstance(data, dict) else {}
            entries = plugins.get("entries", {}) if isinstance(plugins, dict) else {}
            installs = plugins.get("installs", {}) if isinstance(plugins, dict) else {}
            installed = {
                "registered": PLUGIN_ID in entries or PLUGIN_ID in installs,
                "enabled": bool((entries.get(PLUGIN_ID) or {}).get("enabled")) if isinstance(entries, dict) else False,
                "install": redact(installs.get(PLUGIN_ID)) if isinstance(installs, dict) else None,
            }
        except (OSError, json.JSONDecodeError) as exc:
            installed = {"registered": False, "error": str(exc)}
    return {
        "id": PLUGIN_ID,
        "name": PLUGIN_NAME,
        "package": PLUGIN_PACKAGE_NAME,
        "version": PLUGIN_VERSION,
        "root": str(PLUGIN_ROOT),
        "python": sys.executable,
        "script": str(PLUGIN_ROOT / "model_console.py"),
        "openclaw": {
            "config": str(paths.openclaw_config),
            **installed,
        },
        "workbuddy": {
            "models": [str(paths.workbuddy_models), str(paths.codebuddy_models)],
            "cli": str(paths.workbuddy_cli),
            "cli_exists": paths.workbuddy_cli.exists(),
        },
        "standalone": {
            "launcher": str(PLUGIN_ROOT / "standalone" / "TianyuanModelConsole.command"),
            "installer": str(PLUGIN_ROOT / "standalone" / "install.command"),
            "launch_agent_template": str(PLUGIN_ROOT / "standalone" / "com.tianyuan.model-console.plist"),
            "manifest": str(PLUGIN_ROOT / "standalone" / "app_manifest.json"),
            "package_script": str(PLUGIN_ROOT / "scripts" / "package_standalone.sh"),
        },
        "commands": {
            "web": f"python3 {PLUGIN_ROOT / 'model_console.py'} serve --host 127.0.0.1 --port 51280",
            "status": f"python3 {PLUGIN_ROOT / 'model_console.py'} status",
            "install_openclaw": f"python3 {PLUGIN_ROOT / 'model_console.py'} install-openclaw-plugin",
            "install_workbuddy": f"python3 {PLUGIN_ROOT / 'model_console.py'} install-workbuddy --provider oxo --model <model> --base-url <url>",
        },
    }


def install_openclaw_plugin(paths: Paths, dry_run: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if paths.openclaw_config.exists():
        data = read_json(paths.openclaw_config)
        if not isinstance(data, dict):
            raise ValueError("OpenClaw 配置必须是 JSON 对象。")
    before = json.dumps(data, sort_keys=True, ensure_ascii=False)
    plugins = data.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise ValueError("OpenClaw plugins 字段必须是 JSON 对象。")

    allow = plugins.setdefault("allow", [])
    if not isinstance(allow, list):
        raise ValueError("OpenClaw plugins.allow 字段必须是数组。")
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)

    load = plugins.setdefault("load", {})
    if not isinstance(load, dict):
        raise ValueError("OpenClaw plugins.load 字段必须是对象。")
    load_paths = load.setdefault("paths", [])
    if not isinstance(load_paths, list):
        raise ValueError("OpenClaw plugins.load.paths 字段必须是数组。")
    plugin_root = str(PLUGIN_ROOT)
    if plugin_root not in load_paths:
        load_paths.append(plugin_root)

    entries = plugins.setdefault("entries", {})
    if not isinstance(entries, dict):
        raise ValueError("OpenClaw plugins.entries 字段必须是对象。")
    entry = entries.setdefault(PLUGIN_ID, {})
    if not isinstance(entry, dict):
        entry = {}
        entries[PLUGIN_ID] = entry
    entry["enabled"] = True
    entry.setdefault(
        "config",
        {
            "host": "127.0.0.1",
            "port": 51280,
            "script": str(PLUGIN_ROOT / "model_console.py"),
            "workbuddyModels": [str(paths.workbuddy_models), str(paths.codebuddy_models)],
        },
    )

    installs = plugins.setdefault("installs", {})
    if not isinstance(installs, dict):
        raise ValueError("OpenClaw plugins.installs 字段必须是对象。")
    installs[PLUGIN_ID] = {
        "source": "path",
        "sourcePath": str(PLUGIN_ROOT),
        "installPath": str(PLUGIN_ROOT),
        "version": PLUGIN_VERSION,
        "resolvedName": PLUGIN_PACKAGE_NAME,
        "resolvedVersion": PLUGIN_VERSION,
        "resolvedSpec": f"{PLUGIN_PACKAGE_NAME}@{PLUGIN_VERSION}",
        "installedAt": dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
    }

    after = json.dumps(data, sort_keys=True, ensure_ascii=False)
    result = {
        "target": str(paths.openclaw_config),
        "dry_run": dry_run,
        "changed": before != after,
        "backup": None,
        "plugin_id": PLUGIN_ID,
        "enabled": True,
        "install_path": str(PLUGIN_ROOT),
        "load_path": str(PLUGIN_ROOT),
    }
    if dry_run or before == after:
        return result
    backup = backup_file(paths.openclaw_config) if paths.openclaw_config.exists() else None
    atomic_write_json(paths.openclaw_config, data)
    result["backup"] = str(backup) if backup else None
    return result


def find_hermes_api_key(paths: Paths, provider: str) -> str | None:
    if not paths.hermes_auth.exists():
        return None
    try:
        auth = read_json(paths.hermes_auth)
    except (OSError, json.JSONDecodeError):
        return None
    providers = auth.get("providers", {}) if isinstance(auth, dict) else {}
    aliases = {provider, normalize_provider_name(provider), f"custom:{normalize_provider_name(provider)}"}
    for name, value in providers.items():
        if name not in aliases or not isinstance(value, dict):
            continue
        api_key = value.get("api_key") or value.get("apiKey") or value.get("token")
        if isinstance(api_key, str) and api_key.strip():
            return api_key.strip()
    return None


def find_openclaw_api_key(paths: Paths, provider: str) -> str | None:
    if not paths.openclaw_config.exists():
        return None
    try:
        data = read_json(paths.openclaw_config)
    except (OSError, json.JSONDecodeError):
        return None
    providers = ((data.get("models") or {}).get("providers") or {}) if isinstance(data, dict) else {}
    entry = providers.get(provider) or providers.get(normalize_provider_name(provider))
    if not isinstance(entry, dict):
        return None
    api_key = entry.get("apiKey") or entry.get("api_key") or entry.get("token")
    if isinstance(api_key, str) and api_key.strip():
        return api_key.strip()
    return None


def resolve_workbuddy_api_key(
    paths: Paths,
    *,
    provider: str,
    api_key: str | None,
    api_key_env: str | None,
    use_hermes_auth: bool,
) -> tuple[str | None, str]:
    if api_key:
        return api_key, "argument"
    if api_key_env:
        env_value = os.getenv(api_key_env)
        if env_value:
            return env_value, f"env:{api_key_env}"
    if use_hermes_auth:
        hermes_key = find_hermes_api_key(paths, provider)
        if hermes_key:
            return hermes_key, f"hermes_auth:{provider}"
    openclaw_key = find_openclaw_api_key(paths, provider)
    if openclaw_key:
        return openclaw_key, f"openclaw_config:{provider}"
    return None, "missing"


def build_workbuddy_model_entry(
    *,
    provider: str,
    model: str,
    base_url: str,
    api_key: str | None,
    supports_tool_call: bool,
    supports_images: bool,
    max_input_tokens: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": model,
        "name": f"{provider}/{model}",
        "vendor": provider,
        "url": base_url.rstrip("/"),
        "credits": "local",
        "maxOutputTokens": max_output_tokens,
        "maxInputTokens": max_input_tokens,
        "maxAllowedSize": max_input_tokens,
        "supportsToolCall": supports_tool_call,
        "supportsImages": supports_images,
        "descriptionZh": "由天元模型控制台写入的本地上游模型。",
        "descriptionEn": "Local upstream model installed by Tianyuan Model Console.",
    }
    if api_key:
        entry["apiKey"] = api_key
    return entry


def read_workbuddy_models(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"models": [], "availableModels": []}
    data = read_json(path)
    if isinstance(data, list):
        return {"models": data, "availableModels": [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]}
    if isinstance(data, dict):
        models = data.get("models")
        available = data.get("availableModels")
        return {
            **data,
            "models": models if isinstance(models, list) else [],
            "availableModels": available if isinstance(available, list) else [],
        }
    raise ValueError(f"WorkBuddy models 配置必须是 JSON 对象或数组：{path}")


def merge_workbuddy_model_config(data: dict[str, Any], entry: dict[str, Any], visible: bool = True) -> dict[str, Any]:
    models = data.setdefault("models", [])
    if not isinstance(models, list):
        models = []
        data["models"] = models
    model_id = entry["id"]
    for idx, item in enumerate(models):
        if isinstance(item, dict) and item.get("id") == model_id:
            models[idx] = entry
            break
    else:
        models.append(entry)
    if visible:
        available = data.setdefault("availableModels", [])
        if not isinstance(available, list):
            available = []
            data["availableModels"] = available
        if model_id not in available:
            available.append(model_id)
    return data


def install_workbuddy_model(paths: Paths, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    required = ["provider", "model", "base_url"]
    missing = [key for key in required if not str(payload.get(key) or "").strip()]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    provider = str(payload["provider"]).strip()
    model = str(payload["model"]).strip()
    base_url = str(payload["base_url"]).strip().rstrip("/")
    api_key, api_key_source = resolve_workbuddy_api_key(
        paths,
        provider=provider,
        api_key=str(payload.get("api_key") or "").strip() or None,
        api_key_env=str(payload.get("api_key_env") or "").strip() or None,
        use_hermes_auth=bool(payload.get("use_hermes_auth", True)),
    )
    entry = build_workbuddy_model_entry(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        supports_tool_call=bool(payload.get("supports_tool_call", False)),
        supports_images=bool(payload.get("supports_images", False)),
        max_input_tokens=int(payload.get("max_input_tokens") or 131072),
        max_output_tokens=int(payload.get("max_output_tokens") or 8192),
    )
    targets = [paths.workbuddy_models, paths.codebuddy_models]
    results: list[dict[str, Any]] = []
    for target in targets:
        before = ""
        data = {"models": [], "availableModels": []}
        if target.exists():
            before = read_text(target)
            data = read_workbuddy_models(target)
        new_data = merge_workbuddy_model_config(data, entry, visible=bool(payload.get("visible", True)))
        after = json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
        item = {
            "target": str(target),
            "dry_run": dry_run,
            "changed": before != after,
            "backup": None,
        }
        if not dry_run and before != after:
            backup = backup_file(target) if target.exists() else None
            atomic_write_text(target, after)
            item["backup"] = str(backup) if backup else None
        results.append(item)
    return {
        "dry_run": dry_run,
        "model": model,
        "provider": provider,
        "base_url": base_url,
        "api_key_source": api_key_source,
        "api_key_written": bool(api_key),
        "targets": results,
        "workbuddy_cli": str(paths.workbuddy_cli),
        "workbuddy_cli_exists": paths.workbuddy_cli.exists(),
        "smoke_command": f"{paths.workbuddy_cli} --print --model {model} --tools \"\" --max-turns 1 --output-format text",
    }


def status(paths: Paths, include_usage: bool = True) -> dict[str, Any]:
    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "settings": settings_info(paths),
        "hermes": summarize_hermes(paths),
        "openclaw": summarize_openclaw(paths),
        "plugin": plugin_info(paths),
    }
    if include_usage:
        out["usage"] = summarize_usage(paths)
    return out


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>天元模型控制台</title>
  <style>
    :root { color-scheme: light; --ink:#17202a; --muted:#667481; --line:#dbe1e8; --bg:#f6f8fb; --panel:#fff; --accent:#1266a8; --soft:#eef5fb; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    header { background:#fff; border-bottom:1px solid var(--line); padding:16px 20px; display:flex; align-items:center; justify-content:space-between; gap:12px; }
    h1 { margin:0; font-size:20px; font-weight:650; letter-spacing:0; }
    main { max-width:980px; margin:0 auto; padding:16px; display:grid; gap:12px; }
    section, details { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:14px; }
    summary { cursor:pointer; font-weight:650; }
    h2 { margin:0 0 12px; font-size:15px; }
    label { display:block; margin:10px 0 4px; color:var(--muted); font-size:12px; }
    input, select { width:100%; min-height:36px; border:1px solid #cbd5df; border-radius:6px; background:#fff; padding:7px 9px; font:inherit; }
    input[type="checkbox"] { width:auto; min-height:0; margin-right:6px; }
    button { border:1px solid var(--accent); border-radius:6px; background:var(--accent); color:#fff; padding:8px 12px; font-weight:650; cursor:pointer; }
    button.secondary { background:#fff; color:var(--accent); }
    button:disabled { opacity:.55; cursor:wait; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { padding:7px 6px; border-bottom:1px solid #edf1f5; text-align:left; vertical-align:top; word-break:break-word; }
    th { color:var(--muted); font-weight:600; }
    pre { margin:0; max-height:240px; overflow:auto; white-space:pre-wrap; word-break:break-word; background:#f2f5f8; border:1px solid #e1e7ee; border-radius:6px; padding:10px; font-size:12px; }
    .grid { display:grid; grid-template-columns:repeat(2, minmax(260px,1fr)); gap:10px 12px; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
    .status { display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:8px; }
    .tile { background:var(--soft); border:1px solid #d7e7f4; border-radius:8px; padding:10px; min-height:74px; }
    .tile b { display:block; font-size:12px; color:var(--muted); margin-bottom:5px; }
    .tile span { display:block; font-size:14px; word-break:break-word; }
    .muted { color:var(--muted); }
    .hidden { display:none !important; }
    @media (max-width:760px) { header { align-items:flex-start; flex-direction:column; } main { padding:12px; } .grid, .status { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <header>
    <h1>天元模型控制台</h1>
    <button class="secondary" onclick="loadStatus()">刷新</button>
  </header>
  <main>
    <section>
      <h2>状态</h2>
      <div class="status">
        <div class="tile"><b>Hermes</b><span id="tileHermes">正在加载</span></div>
        <div class="tile"><b>OpenClaw</b><span id="tileOpenclaw">正在加载</span></div>
        <div class="tile"><b>WorkBuddy</b><span id="tileWorkbuddy">正在加载</span></div>
        <div class="tile"><b>Token</b><span id="tileUsage">正在加载</span></div>
      </div>
    </section>

    <section>
      <h2>模型配置</h2>
      <div class="grid">
        <div>
          <label>目标</label>
          <select id="target" onchange="syncTargetFields()">
            <option value="openclaw">OpenClaw</option>
            <option value="hermes">Hermes</option>
            <option value="workbuddy">WorkBuddy / CodeBuddy</option>
          </select>
        </div>
        <div id="agentField">
          <label>OpenClaw 智能体</label>
          <select id="agent"></select>
        </div>
        <div><label>上游通道</label><input id="provider" placeholder="provider"></div>
        <div><label>模型</label><input id="model" placeholder="model-id"></div>
        <div><label>Base URL</label><input id="baseUrl" placeholder="https://example.com/v1"></div>
        <div id="apiModeField"><label>API 模式</label><input id="apiMode" value="chat_completions"></div>
        <div id="apiKeyField"><label>API Key</label><input id="apiKey" type="password" placeholder="可留空"></div>
        <div id="apiKeyEnvField"><label>API Key 环境变量</label><input id="apiKeyEnv" placeholder="可留空"></div>
        <div id="maxInputField"><label>最大输入 Token</label><input id="maxInput" type="number" value="131072"></div>
        <div id="maxOutputField"><label>最大输出 Token</label><input id="maxOutput" type="number" value="8192"></div>
      </div>
      <div id="capabilityField" class="actions">
        <label><input id="toolCall" type="checkbox">工具调用</label>
        <label><input id="images" type="checkbox">图片输入</label>
      </div>
      <div class="actions">
        <button class="secondary" onclick="applyRoute(true)">预演</button>
        <button onclick="applyRoute(false)">应用</button>
      </div>
    </section>

    <details>
      <summary>路径设置</summary>
      <div class="grid">
        <div><label>Hermes 配置文件</label><input id="cfgHermesConfig"></div>
        <div><label>Hermes 密钥文件</label><input id="cfgHermesAuth"></div>
        <div><label>Hermes 会话目录</label><input id="cfgHermesSessions"></div>
        <div><label>OpenClaw 配置文件</label><input id="cfgOpenclawConfig"></div>
        <div><label>OpenClaw 模型目录</label><input id="cfgOpenclawModels"></div>
        <div><label>OpenClaw 会话目录</label><input id="cfgOpenclawSessions"></div>
        <div><label>OpenClaw 日志目录</label><input id="cfgOpenclawLogs"></div>
        <div><label>WorkBuddy 模型文件</label><input id="cfgWorkbuddyModels"></div>
        <div><label>CodeBuddy 模型文件</label><input id="cfgCodebuddyModels"></div>
        <div><label>WorkBuddy CLI</label><input id="cfgWorkbuddyCli"></div>
      </div>
      <div class="actions">
        <button onclick="saveSettings()">保存路径</button>
      </div>
      <div class="muted">配置文件：<span id="settingsPath"></span></div>
    </details>

    <details>
      <summary>详细状态</summary>
      <h2>上游通道</h2>
      <div id="providers"></div>
      <h2>Token 用量</h2>
      <div id="usage"></div>
    </details>

    <section>
      <h2>结果</h2>
      <pre id="result">就绪。</pre>
    </section>
  </main>
<script>
let statusCache = null;
const pathInputs = [
  ['hermes_config', 'cfgHermesConfig'],
  ['hermes_auth', 'cfgHermesAuth'],
  ['hermes_sessions', 'cfgHermesSessions'],
  ['openclaw_config', 'cfgOpenclawConfig'],
  ['openclaw_models', 'cfgOpenclawModels'],
  ['openclaw_sessions', 'cfgOpenclawSessions'],
  ['openclaw_logs', 'cfgOpenclawLogs'],
  ['workbuddy_models', 'cfgWorkbuddyModels'],
  ['codebuddy_models', 'cfgCodebuddyModels'],
  ['workbuddy_cli', 'cfgWorkbuddyCli']
];
function esc(v) { return String(v ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function byId(id) { return document.getElementById(id); }
function table(rows, headers) {
  if (!rows.length) return '<div class="muted">暂无记录。</div>';
  return '<table><thead><tr>' + headers.map(h => '<th>'+esc(h)+'</th>').join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + headers.map(h => '<td>'+esc(r[h])+'</td>').join('') + '</tr>').join('') + '</tbody></table>';
}
function setBusy(busy) { document.querySelectorAll('button').forEach(button => button.disabled = busy); }
function setText(id, text) { byId(id).textContent = text || '未配置'; }
function splitModelRef(value) {
  const text = String(value || '');
  if (!text.includes('/')) return ['', text];
  const parts = text.split('/');
  return [parts.shift(), parts.join('/')];
}
function syncTargetFields() {
  const target = byId('target').value;
  byId('agentField').classList.toggle('hidden', target !== 'openclaw');
  byId('apiModeField').classList.toggle('hidden', target !== 'hermes');
  for (const id of ['apiKeyField', 'apiKeyEnvField', 'maxInputField', 'maxOutputField', 'capabilityField']) {
    byId(id).classList.toggle('hidden', target !== 'workbuddy');
  }
}
function fillFormFromStatus(target) {
  const h = statusCache?.hermes?.model || {};
  const agents = statusCache?.openclaw?.agents || [];
  const main = agents.find(agent => agent.default) || agents[0] || {};
  const providers = statusCache?.openclaw?.providers || {};
  if (target === 'hermes') {
    byId('provider').value = String(h.provider || '').replace(/^custom:/, '');
    byId('model').value = h.default || '';
    byId('baseUrl').value = h.base_url || '';
    byId('apiMode').value = h.api_mode || 'chat_completions';
  } else if (target === 'openclaw') {
    const [provider, model] = splitModelRef(main.model);
    byId('agent').value = main.id || '';
    byId('provider').value = provider || '';
    byId('model').value = model || '';
    byId('baseUrl').value = providers[provider]?.baseUrl || '';
  }
}
async function loadStatus() {
  const res = await fetch('/api/status');
  statusCache = await res.json();
  const settings = statusCache.settings || {};
  const effective = settings.effective_paths || {};
  for (const [key, id] of pathInputs) byId(id).value = effective[key] || '';
  byId('settingsPath').textContent = settings.config_path || '';

  const hermesModel = statusCache.hermes?.model || {};
  setText('tileHermes', [hermesModel.provider, hermesModel.default].filter(Boolean).join(' / '));
  const agents = statusCache.openclaw?.agents || [];
  const main = agents.find(agent => agent.default) || agents[0] || {};
  setText('tileOpenclaw', main.model || '');
  setText('tileWorkbuddy', effective.workbuddy_models || '');
  setText('tileUsage', String(statusCache.usage?.totals?.total ?? 0));

  const agentSelect = byId('agent');
  agentSelect.innerHTML = agents.map(agent => '<option value="'+esc(agent.id)+'">'+esc(agent.id)+'</option>').join('');
  fillFormFromStatus(byId('target').value);

  const providerRows = [];
  for (const [name, provider] of Object.entries(statusCache.openclaw?.providers || {})) {
    providerRows.push({上游通道:name, BaseURL:provider.baseUrl, API:provider.api, 模型数:provider.model_count});
  }
  byId('providers').innerHTML = table(providerRows, ['上游通道','BaseURL','API','模型数']);
  const usageRows = Object.entries(statusCache.usage?.by_model || {}).map(([model, usage]) => ({
    模型:model,
    输入:usage.prompt,
    输出:usage.completion,
    总计:usage.total,
  }));
  byId('usage').innerHTML = table(usageRows, ['模型','输入','输出','总计']);
  syncTargetFields();
}
async function saveSettings() {
  const payload = {};
  for (const [key, id] of pathInputs) payload[key] = byId(id).value;
  setBusy(true);
  try {
    const res = await fetch('/api/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await res.json();
    byId('result').textContent = JSON.stringify(data, null, 2);
    await loadStatus();
  } finally {
    setBusy(false);
  }
}
async function applyRoute(dryRun) {
  const target = byId('target').value;
  const payload = {
    target,
    dry_run: dryRun,
    provider: byId('provider').value,
    model: byId('model').value,
    base_url: byId('baseUrl').value,
  };
  if (target === 'openclaw') payload.agent_id = byId('agent').value;
  if (target === 'hermes') payload.api_mode = byId('apiMode').value;
  if (target === 'workbuddy') {
    payload.api_key = byId('apiKey').value;
    payload.api_key_env = byId('apiKeyEnv').value;
    payload.supports_tool_call = byId('toolCall').checked;
    payload.supports_images = byId('images').checked;
    payload.max_input_tokens = Number(byId('maxInput').value || 131072);
    payload.max_output_tokens = Number(byId('maxOutput').value || 8192);
  }
  setBusy(true);
  try {
    const res = await fetch('/api/apply', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await res.json();
    byId('result').textContent = JSON.stringify(data, null, 2);
    await loadStatus();
  } finally {
    setBusy(false);
  }
}
byId('target').addEventListener('change', () => {
  syncTargetFields();
  fillFormFromStatus(byId('target').value);
});
loadStatus().catch(err => { byId('result').textContent = String(err); });
</script>
</body>
</html>
"""


class ConsoleHandler(BaseHTTPRequestHandler):
    paths = Paths.from_env()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("model-console: " + (fmt % args) + "\n")

    def send_json(self, payload: Any, status_code: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            body = INDEX_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/status":
            self.send_json(status(self.paths))
            return
        if self.path == "/api/settings":
            self.send_json(settings_info(self.paths))
            return
        self.send_json({"error": "未找到"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path == "/api/settings":
            try:
                length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                result = save_user_settings(payload)
                type(self).paths = Paths.from_env(settings=result["settings"])
                self.send_json({"ok": True, "result": result})
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if self.path != "/api/apply":
            self.send_json({"error": "未找到"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            dry_run = bool(payload.get("dry_run"))
            target = payload.get("target")
            if target == "hermes":
                result = apply_hermes(self.paths, payload, dry_run=dry_run)
            elif target == "openclaw":
                result = apply_openclaw(self.paths, payload, dry_run=dry_run)
            elif target == "workbuddy":
                result = install_workbuddy_model(self.paths, payload, dry_run=dry_run)
            else:
                raise ValueError("target 必须是 hermes、openclaw 或 workbuddy")
            self.send_json({"ok": True, "result": result})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)


def print_json(data: Any) -> None:
    print(json.dumps(redact(data), ensure_ascii=False, indent=2))


class ChineseArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help="显示帮助并退出。")
        self._positionals.title = "位置参数"
        self._optionals.title = "可选参数"


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="Hermes / OpenClaw 本地模型路由控制台。")
    sub = parser.add_subparsers(dest="command", required=True, title="命令", parser_class=ChineseArgumentParser)

    status_parser = sub.add_parser("status", help="输出脱敏后的模型路由状态。")
    status_parser.add_argument("--no-usage", action="store_true", help="跳过 Token 用量扫描。")

    sub.add_parser("usage", help="输出可推断的 Token 用量汇总。")
    sub.add_parser("plugin-info", help="输出插件安装信息和可用入口。")

    install_openclaw = sub.add_parser("install-openclaw-plugin", help="把本目录注册为 OpenClaw 本地插件。")
    install_openclaw.add_argument("--dry-run", action="store_true", help="只预演，不写入 OpenClaw 配置。")

    workbuddy = sub.add_parser("install-workbuddy", help="把一个上游模型写入 WorkBuddy / CodeBuddy 本地模型配置。")
    workbuddy.add_argument("--provider", required=True, help="上游通道名，例如 oxo。")
    workbuddy.add_argument("--model", required=True, help="实际调用的模型 ID。")
    workbuddy.add_argument("--base-url", required=True, help="OpenAI 兼容 Base URL。")
    workbuddy.add_argument("--api-key", default="", help="直接写入 WorkBuddy 的 API Key；默认不要求。")
    workbuddy.add_argument("--api-key-env", default="", help="从指定环境变量读取 API Key 后写入。")
    workbuddy.add_argument("--no-hermes-auth", action="store_true", help="不要从 Hermes auth.json 复制本地密钥。")
    workbuddy.add_argument("--supports-tool-call", action="store_true", help="声明该模型支持工具调用。默认关闭。")
    workbuddy.add_argument("--supports-images", action="store_true", help="声明该模型支持图片输入。默认关闭。")
    workbuddy.add_argument("--max-input-tokens", type=int, default=131072)
    workbuddy.add_argument("--max-output-tokens", type=int, default=8192)
    workbuddy.add_argument("--dry-run", action="store_true", help="只预演，不写入 WorkBuddy 配置。")

    serve = sub.add_parser("serve", help="启动本地网页控制台。")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    hermes = sub.add_parser("apply-hermes", help="更新 Hermes 模型路由。")
    hermes.add_argument("--provider", required=True)
    hermes.add_argument("--model", required=True)
    hermes.add_argument("--base-url", required=True)
    hermes.add_argument("--api-mode", default="chat_completions")
    hermes.add_argument("--key-env", default="")
    hermes.add_argument("--dry-run", action="store_true")

    openclaw = sub.add_parser("apply-openclaw", help="更新 OpenClaw 智能体模型路由。")
    openclaw.add_argument("--agent-id", default="main")
    openclaw.add_argument("--provider", required=True)
    openclaw.add_argument("--model", required=True)
    openclaw.add_argument("--base-url", default="")
    openclaw.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = Paths.from_env()
    if args.command == "status":
        print_json(status(paths, include_usage=not args.no_usage))
        return 0
    if args.command == "usage":
        print_json(summarize_usage(paths))
        return 0
    if args.command == "plugin-info":
        print_json(plugin_info(paths))
        return 0
    if args.command == "install-openclaw-plugin":
        print_json(install_openclaw_plugin(paths, dry_run=args.dry_run))
        return 0
    if args.command == "install-workbuddy":
        print_json(
            install_workbuddy_model(
                paths,
                {
                    "provider": args.provider,
                    "model": args.model,
                    "base_url": args.base_url,
                    "api_key": args.api_key,
                    "api_key_env": args.api_key_env,
                    "use_hermes_auth": not args.no_hermes_auth,
                    "supports_tool_call": args.supports_tool_call,
                    "supports_images": args.supports_images,
                    "max_input_tokens": args.max_input_tokens,
                    "max_output_tokens": args.max_output_tokens,
                },
                dry_run=args.dry_run,
            )
        )
        return 0
    if args.command == "apply-hermes":
        print_json(
            apply_hermes(
                paths,
                {
                    "provider": args.provider,
                    "model": args.model,
                    "base_url": args.base_url,
                    "api_mode": args.api_mode,
                    "key_env": args.key_env,
                },
                dry_run=args.dry_run,
            )
        )
        return 0
    if args.command == "apply-openclaw":
        print_json(
            apply_openclaw(
                paths,
                {
                    "agent_id": args.agent_id,
                    "provider": args.provider,
                    "model": args.model,
                    "base_url": args.base_url,
                },
                dry_run=args.dry_run,
            )
        )
        return 0
    if args.command == "serve":
        ConsoleHandler.paths = paths
        server = ThreadingHTTPServer((args.host, args.port), ConsoleHandler)
        print(f"天元模型控制台已启动：http://{args.host}:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 130
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
