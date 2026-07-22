"""Ollama client for chat_json and generate_raw modes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT = 120.0


class OllamaError(RuntimeError):
    pass


class RunStatus(str, Enum):
    """Outcome of one inference call, decided at the call boundary.

    The distinction that matters: COMPLETED with output "" means the model
    answered with nothing, and legitimately scores zero. Every other status
    means no answer was observed, and there is nothing to score. Collapsing
    the two is what let a fully timed-out Qwen3.5 run report a headline.
    """

    COMPLETED = "completed"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class InferenceResult:
    status: RunStatus
    output: str | None
    error: str | None
    elapsed_seconds: float
    timeout_seconds: float

    @property
    def observed(self) -> bool:
        """True only when the model's answer was actually seen."""
        return self.status is RunStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            # null, never "": empty string means an observed zero-length answer
            "output": self.output,
            "error": self.error,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "timeout_seconds": self.timeout_seconds,
            "valid_measurement": self.observed,
        }


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

    def run(self, model_input: dict[str, Any]) -> InferenceResult:
        """Execute one inference and classify the outcome. Never raises.

        Prefer this over generate() anywhere the result will be scored.
        generate() signals every operational failure as one exception type,
        which forces the caller to flatten timeout / transport / bad-response
        into a single ambiguous state.
        """
        mode = model_input.get("mode", "chat_json")
        started = time.monotonic()

        def done(status: RunStatus, output: str | None, error: str | None) -> InferenceResult:
            return InferenceResult(
                status=status,
                output=output,
                error=error,
                elapsed_seconds=time.monotonic() - started,
                timeout_seconds=float(self.timeout),
            )

        try:
            response = self.generate(model_input)
        except httpx.TimeoutException as e:
            return done(
                RunStatus.TIMEOUT, None, f"Ollama request timed out after {self.timeout}s: {e}"
            )
        except OllamaError as e:
            # generate() wraps the underlying cause; recover timeouts it swallowed
            if "timeout" in str(e).lower() or "timed out" in str(e).lower():
                return done(RunStatus.TIMEOUT, None, str(e))
            return done(RunStatus.TRANSPORT_ERROR, None, str(e))
        except Exception as e:  # noqa: BLE001
            return done(RunStatus.TRANSPORT_ERROR, None, f"{type(e).__name__}: {e}")

        try:
            text = OllamaClient.extract_text(response, mode)
        except Exception as e:  # noqa: BLE001
            return done(RunStatus.INVALID_RESPONSE, None, f"{type(e).__name__}: {e}")
        if text is None:
            return done(RunStatus.INVALID_RESPONSE, None, "no text field in response")
        # "" is a legitimate observed answer and is preserved as such
        return done(RunStatus.COMPLETED, str(text), None)

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
