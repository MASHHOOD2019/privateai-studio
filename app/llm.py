"""Local LLM chat via Ollama, with token streaming."""
import json
import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "llama3.1")


def chat_stream(messages, model=None):
    """Yield text deltas from Ollama. Raises RuntimeError if unreachable."""
    model = model or CHAT_MODEL
    try:
        with httpx.stream(
            "POST",
            OLLAMA_URL + "/api/chat",
            json={"model": model, "messages": messages, "stream": True},
            timeout=300,
            trust_env=False,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                delta = data.get("message", {}).get("content", "")
                if delta:
                    yield delta
    except Exception as exc:
        raise RuntimeError(
            "Ollama is not reachable. Start Ollama, then run: "
            f"ollama pull {model}"
        ) from exc
