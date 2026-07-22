"""Ollama client for chat_json and generate_raw modes."""

from __future__ import annotations

from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT = 120.0


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def heartbeat(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self.base_url}/api/tags")
                r.raise_for_status()
                return r.json()
        except Exception as e:  # noqa: BLE001 — surface as OllamaError
            raise OllamaError(f"Ollama unreachable at {self.base_url}: {e}") from e

    def list_models(self) -> list[str]:
        data = self.heartbeat()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def generate(self, model_input: dict[str, Any]) -> dict[str, Any]:
        mode = model_input.get("mode", "chat_json")
        payload = model_input["payload"]
        if mode == "chat_json":
            path = "/api/chat"
        elif mode == "generate_raw":
            path = "/api/generate"
        else:
            raise OllamaError(f"Unknown mode: {mode}")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(f"{self.base_url}{path}", json=payload)
                if r.status_code >= 400:
                    raise OllamaError(f"Ollama {path} HTTP {r.status_code}: {r.text[:500]}")
                return r.json()
        except OllamaError:
            raise
        except Exception as e:  # noqa: BLE001
            raise OllamaError(f"Ollama request failed: {e}") from e

    @staticmethod
    def extract_text(response: dict[str, Any], mode: str) -> str:
        if mode == "chat_json":
            msg = response.get("message") or {}
            return (msg.get("content") or "").strip()
        # generate
        return (response.get("response") or "").strip()

    @staticmethod
    def extract_telemetry(response: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
            "model",
            "done",
        )
        return {k: response[k] for k in keys if k in response}
