"""Offline API regression tests; no microphone, desktop or API key required."""

from io import BytesIO
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("pyautogui", MagicMock())
import app as server


class AsrTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.key = patch.object(server, "get_api_key", return_value="test-key")
        self.proxy = patch.object(server, "load_proxy_api",
                                  return_value={"enabled": False, "apis": {}})
        self.openai = patch.object(server, "OpenAI")
        self.key.start()
        self.proxy.start()
        self.sdk = self.openai.start()
        self.addCleanup(patch.stopall)
        self.transcribe = self.sdk.return_value.__enter__.return_value.audio.transcriptions.create
        self.transcribe.return_value = SimpleNamespace(text="transcribed words")

    def upload(self, payload=b"test-audio", **fields):
        return self.client.post("/api/asr", data={
            "audio": (BytesIO(payload), "recording.webm"),
            "language": "zh-CN",
            **fields,
        })

    def test_missing_file(self):
        self.assertEqual(self.client.post("/api/asr").status_code, 400)
        self.sdk.assert_not_called()

    def test_missing_key(self):
        with patch.object(server, "get_api_key", return_value=""):
            self.assertEqual(self.upload().status_code, 400)
        self.sdk.assert_not_called()

    def test_empty_file(self):
        self.assertEqual(self.upload(b"").status_code, 400)
        self.sdk.assert_not_called()

    def test_transcription(self):
        response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"text": "transcribed words"})
        kwargs = self.transcribe.call_args.kwargs
        self.assertEqual(kwargs["model"], "whisper-1")
        self.assertEqual(kwargs["language"], "zh")
        self.assertEqual(kwargs["file"][1], b"test-audio")
        self.assertEqual(self.sdk.call_args.kwargs["max_retries"], 0)
        self.sdk.return_value.__exit__.assert_called_once()

    def test_timeout(self):
        import httpx
        self.transcribe.side_effect = server.APITimeoutError(
            request=httpx.Request("POST", "https://example.invalid")
        )
        self.assertEqual(self.upload().status_code, 504)

    def test_upstream_failure(self):
        self.transcribe.side_effect = RuntimeError("ASR unavailable")
        response = self.upload()
        self.assertEqual(response.status_code, 500)
        self.assertIn("ASR unavailable", response.json["error"])

    def test_proxy_does_not_change_process_environment(self):
        before = dict(os.environ)
        with patch.object(server, "DefaultHttpxClient"):
            self.assertEqual(self.upload(proxyEnabled="1", proxyHost="127.0.0.1",
                                         proxyPort="7890").status_code, 200)
        self.assertEqual(dict(os.environ), before)

    def test_invalid_proxy(self):
        self.assertEqual(self.upload(proxyEnabled="1", proxyPort="invalid").status_code, 400)

    def test_private_config_not_served(self):
        for path in ("api_keys.json", "api_base_urls.json", "../app.py"):
            self.assertEqual(self.client.get("/config/" + path).status_code, 404)
        with self.client.get("/config/models.json") as response:
            self.assertEqual(response.status_code, 200)

    def test_home_has_single_asr_panel(self):
        with patch.object(server, "check_for_updates", return_value={"has_update": False}):
            html = self.client.get("/").get_data(as_text=True)
        self.assertEqual(html.count('id="asrPanel"'), 1)
        self.assertLess(html.index('id="asrPanel"'), html.index('id="emptyState"'))


if __name__ == "__main__":
    unittest.main()
