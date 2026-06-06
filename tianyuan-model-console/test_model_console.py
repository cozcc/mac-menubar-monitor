#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import model_console as mc


HERMES_YAML = """model:
  default: old-model
  provider: custom:old
  base_url: https://old.example/v1
  api_mode: chat_completions
custom_providers:
- name: old
  base_url: https://old.example/v1
  api_mode: chat_completions
  model: old-model
- name: oxo
  base_url: https://api.oxoapi.com/v1
  key_env: OXOAPI_API_KEY
  api_mode: chat_completions
  model: qwen3.7-max
"""


OPENCLAW_JSON = {
    "models": {
        "providers": {
            "oxo": {
                "baseUrl": "https://api.oxoapi.com/v1",
                "apiKey": "secret-openclaw",
                "api": "openai-completions",
                "models": [{"id": "old-model", "name": "old-model"}],
            }
        }
    },
    "agents": {
        "defaults": {"model": {"primary": "oxo/old-model"}},
        "list": [{"id": "main", "model": "oxo/old-model", "default": True}],
    },
}


class ModelConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.hermes = root / "config.yaml"
        self.hermes.write_text(HERMES_YAML, encoding="utf-8")
        self.hermes_auth = root / "auth.json"
        self.hermes_auth.write_text('{"providers": {"p": {"api_key": "secret", "base_url": "x"}}}', encoding="utf-8")
        self.openclaw = root / "openclaw.json"
        self.openclaw.write_text(json.dumps(OPENCLAW_JSON), encoding="utf-8")
        self.openclaw_models = root / "models.json"
        self.openclaw_models.write_text('{"providers": {}}', encoding="utf-8")
        self.workbuddy_models = root / ".workbuddy" / "models.json"
        self.codebuddy_models = root / ".codebuddy" / "models.json"
        self.workbuddy_cli = root / "codebuddy"
        self.sessions = root / "sessions"
        self.sessions.mkdir()
        (self.sessions / "one.jsonl").write_text(
            json.dumps({"model": "oxo/new-model", "usage": {"prompt_tokens": 10, "completion_tokens": 4}}) + "\n",
            encoding="utf-8",
        )
        self.paths = mc.Paths(
            hermes_config=self.hermes,
            hermes_auth=self.hermes_auth,
            hermes_sessions=self.sessions,
            openclaw_config=self.openclaw,
            openclaw_models=self.openclaw_models,
            openclaw_sessions=self.sessions,
            openclaw_logs=root / "missing-logs",
            workbuddy_models=self.workbuddy_models,
            codebuddy_models=self.codebuddy_models,
            workbuddy_cli=self.workbuddy_cli,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_hermes_dry_run_does_not_write(self):
        result = mc.apply_hermes(
            self.paths,
            {"provider": "oxo", "model": "new-model", "base_url": "https://new.example/v1"},
            dry_run=True,
        )
        self.assertTrue(result["changed"])
        self.assertEqual(self.hermes.read_text(encoding="utf-8"), HERMES_YAML)

    def test_apply_hermes_updates_known_fields_and_backs_up(self):
        result = mc.apply_hermes(
            self.paths,
            {"provider": "oxo", "model": "new-model", "base_url": "https://new.example/v1"},
            dry_run=False,
        )
        text = self.hermes.read_text(encoding="utf-8")
        self.assertIn("default: new-model", text)
        self.assertIn("provider: custom:oxo", text)
        self.assertIn("base_url: https://new.example/v1", text)
        self.assertTrue(Path(result["backup"]).exists())

    def test_apply_openclaw_updates_agent_provider_and_model(self):
        result = mc.apply_openclaw(
            self.paths,
            {"agent_id": "main", "provider": "oxo", "model": "new-model", "base_url": "https://new.example/v1"},
            dry_run=False,
        )
        data = json.loads(self.openclaw.read_text(encoding="utf-8"))
        self.assertEqual(data["agents"]["list"][0]["model"], "oxo/new-model")
        self.assertEqual(data["agents"]["defaults"]["model"]["primary"], "oxo/new-model")
        self.assertEqual(data["models"]["providers"]["oxo"]["baseUrl"], "https://new.example/v1")
        self.assertEqual(result["model_ref"], "oxo/new-model")

    def test_status_redacts_auth_and_summarizes_usage(self):
        data = mc.status(self.paths)
        self.assertEqual(data["hermes"]["auth"]["providers"]["p"]["has_api_key"], True)
        self.assertEqual(data["usage"]["totals"]["total"], 28)
        self.assertIn("oxo/new-model", data["usage"]["by_model"])

    def test_install_openclaw_plugin_registers_local_path(self):
        result = mc.install_openclaw_plugin(self.paths, dry_run=False)
        data = json.loads(self.openclaw.read_text(encoding="utf-8"))
        self.assertTrue(result["changed"])
        self.assertIn(mc.PLUGIN_ID, data["plugins"]["allow"])
        self.assertIn(str(mc.PLUGIN_ROOT), data["plugins"]["load"]["paths"])
        self.assertTrue(data["plugins"]["entries"][mc.PLUGIN_ID]["enabled"])
        self.assertEqual(data["plugins"]["installs"][mc.PLUGIN_ID]["source"], "path")

    def test_install_workbuddy_writes_both_model_files(self):
        result = mc.install_workbuddy_model(
            self.paths,
            {
                "provider": "oxo",
                "model": "qwen3.7-max",
                "base_url": "https://api.oxoapi.com/v1",
                "api_key": "secret",
            },
            dry_run=False,
        )
        self.assertTrue(all(item["changed"] for item in result["targets"]))
        for path in (self.workbuddy_models, self.codebuddy_models):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["availableModels"], ["qwen3.7-max"])
            self.assertEqual(data["models"][0]["id"], "qwen3.7-max")
            self.assertEqual(data["models"][0]["url"], "https://api.oxoapi.com/v1")
            self.assertFalse(data["models"][0]["supportsToolCall"])

    def test_install_workbuddy_can_use_openclaw_provider_key(self):
        result = mc.install_workbuddy_model(
            self.paths,
            {
                "provider": "oxo",
                "model": "claude-opus-4-7",
                "base_url": "https://api.oxoapi.com/v1",
            },
            dry_run=False,
        )
        self.assertEqual(result["api_key_source"], "openclaw_config:oxo")
        data = json.loads(self.workbuddy_models.read_text(encoding="utf-8"))
        self.assertEqual(data["models"][0]["apiKey"], "secret-openclaw")

    def test_plugin_info_exposes_standalone_entrypoints(self):
        info = mc.plugin_info(self.paths)
        self.assertTrue(info["standalone"]["launcher"].endswith("TianyuanModelConsole.command"))
        self.assertTrue(info["standalone"]["installer"].endswith("install.command"))
        self.assertTrue(info["standalone"]["package_script"].endswith("package_standalone.sh"))

    def test_user_settings_persist_and_override_default_paths(self):
        config_path = Path(self.tmp.name) / "app_config.json"
        custom_openclaw = Path(self.tmp.name) / "custom-openclaw.json"
        result = mc.save_user_settings(
            {
                "openclaw_config": str(custom_openclaw),
                "workbuddy_models": "~/custom-workbuddy-models.json",
                "openclaw_logs": "",
            },
            config_path=config_path,
        )
        saved = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["openclaw_config"], str(custom_openclaw))
        self.assertNotIn("openclaw_logs", saved)
        paths = mc.Paths.from_env(settings=result["settings"])
        self.assertEqual(paths.openclaw_config, custom_openclaw)
        self.assertEqual(paths.workbuddy_models, Path("~/custom-workbuddy-models.json").expanduser())


if __name__ == "__main__":
    unittest.main()
