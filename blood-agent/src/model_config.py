from __future__ import annotations

import base64
import os
from enum import Enum
from typing import Any, Optional

from dotenv import load_dotenv


class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class ModelConfig:
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider: str = (provider or os.getenv("MODEL_PROVIDER", "openai")).strip().lower()
        self.model_name: str = (model_name or os.getenv("MODEL_NAME", "gpt-4o")).strip()
        self.base_url: Optional[str] = (base_url or os.getenv("MODEL_BASE_URL") or None)

        try:
            self.provider_enum = ModelProvider(self.provider)
        except ValueError as e:
            raise ValueError(
                f"Unsupported provider: {self.provider}. Supported: {[p.value for p in ModelProvider]}"
            ) from e

        self.api_key: Optional[str] = api_key if api_key is not None else self._get_api_key_default()

        if self.provider_enum == ModelProvider.OPENAI and not self.api_key:
            raise ValueError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")

        if self.provider_enum == ModelProvider.ANTHROPIC and not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic")

        if self.provider_enum == ModelProvider.OLLAMA and not self.base_url:
            self.base_url = "http://localhost:11434/v1"

    def _get_api_key_default(self) -> Optional[str]:
        if self.provider_enum == ModelProvider.OPENAI:
            return os.getenv("OPENAI_API_KEY")
        if self.provider_enum == ModelProvider.ANTHROPIC:
            return os.getenv("ANTHROPIC_API_KEY")
        if self.provider_enum == ModelProvider.OLLAMA:
            return os.getenv("OLLAMA_API_KEY") or os.getenv("LLAMA_API_KEY") or "ollama"
        return None

    def get_pydantic_ai_model_string(self) -> str:
        return f"{self.provider}:{self.model_name}"

    def get_pydantic_ai_model(self):
        if self.provider_enum == ModelProvider.OPENAI:
            from pydantic_ai.models.openai import OpenAIModel

            return OpenAIModel(model_name=self.model_name)

        if self.provider_enum == ModelProvider.ANTHROPIC:
            from pydantic_ai.models.anthropic import AnthropicModel

            return AnthropicModel(model_name=self.model_name)

        if self.provider_enum == ModelProvider.OLLAMA:
            from pydantic_ai.models.openai import OpenAIModel
            from pydantic_ai.providers.ollama import OllamaProvider

            return OpenAIModel(
                model_name=self.model_name,
                provider=OllamaProvider(base_url=self.base_url, api_key=self.api_key or "ollama"),
            )

        raise ValueError(f"Unknown provider: {self.provider}")

    def get_openai_client(self):
        """
        Only valid for OpenAI/Ollama (OpenAI-compatible).
        """
        from openai import OpenAI

        if self.provider_enum == ModelProvider.OPENAI:
            return OpenAI(api_key=self.api_key)

        if self.provider_enum == ModelProvider.OLLAMA:
            return OpenAI(api_key=self.api_key or "ollama", base_url=self.base_url)

        raise ValueError("get_openai_client() is only valid for OpenAI/Ollama providers.")

    def chat_text(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> str:
        """
        Provider-safe text chat. Returns assistant text.
        """
        if self.provider_enum in (ModelProvider.OPENAI, ModelProvider.OLLAMA):
            client = self.get_openai_client()
            resp = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()

        if self.provider_enum == ModelProvider.ANTHROPIC:
            import anthropic

            c = anthropic.Anthropic(api_key=self.api_key)
            msg = c.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": user}]},
                ],
            )
            # anthropic returns content blocks
            parts = []
            for block in msg.content or []:
                if getattr(block, "type", None) == "text":
                    parts.append(block.text)
            return ("\n".join(parts)).strip()

        raise ValueError(f"Unsupported provider: {self.provider_enum}")

    def chat_vision_text(
        self,
        *,
        user_prompt: str,
        image_base64_jpeg: str,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> str:
        """
        Provider-safe vision OCR-like call. Returns assistant text.
        image_base64_jpeg should be raw base64 without data: prefix.
        """
        if self.provider_enum in (ModelProvider.OPENAI, ModelProvider.OLLAMA):
            client = self.get_openai_client()
            resp = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_base64_jpeg}"},
                            },
                        ],
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()

        if self.provider_enum == ModelProvider.ANTHROPIC:
            import anthropic

            # Validate base64
            try:
                base64.b64decode(image_base64_jpeg.encode("utf-8"), validate=True)
            except Exception:
                # still try, but don't crash
                pass

            c = anthropic.Anthropic(api_key=self.api_key)
            msg = c.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64_jpeg,
                                },
                            },
                        ],
                    }
                ],
            )
            parts = []
            for block in msg.content or []:
                if getattr(block, "type", None) == "text":
                    parts.append(block.text)
            return ("\n".join(parts)).strip()

        raise ValueError(f"Unsupported provider: {self.provider_enum}")

    def __repr__(self) -> str:
        return f"ModelConfig(provider={self.provider}, model={self.model_name})"


_model_config: Optional[ModelConfig] = None


def get_model_config() -> ModelConfig:
    global _model_config
    if _model_config is None:
        load_dotenv()
        _model_config = ModelConfig()
    return _model_config


def set_model_config(config: ModelConfig) -> None:
    global _model_config
    _model_config = config


def reset_model_config() -> None:
    global _model_config
    _model_config = None