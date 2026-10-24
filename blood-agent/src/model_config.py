from __future__ import annotations

import base64
import binascii
import math
import os
import re
import threading
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlsplit

from dotenv import load_dotenv


class ModelProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


_DEFAULT_MODELS = {
    ModelProvider.OPENAI: "gpt-4o",
    ModelProvider.ANTHROPIC: "claude-sonnet-4-5",
    ModelProvider.OLLAMA: "qwen3",
}

_DEFAULT_BASE_URLS = {
    ModelProvider.OPENAI: "https://api.openai.com/v1",
    ModelProvider.ANTHROPIC: "https://api.anthropic.com",
    ModelProvider.OLLAMA: "http://localhost:11434/v1",
}

_BASE_URL_VARIABLES = {
    ModelProvider.OPENAI: "OPENAI_BASE_URL",
    ModelProvider.ANTHROPIC: "ANTHROPIC_BASE_URL",
    ModelProvider.OLLAMA: "OLLAMA_BASE_URL",
}

_REASONING_MODEL_PATTERN = re.compile(
    r"^(?:o[134](?:-|$)|gpt-(?:5|6)(?:[.-]|$))",
    re.IGNORECASE,
)


class ModelConfig:
    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        load_dotenv(override=False)

        provider_value = (
            provider or os.getenv("MODEL_PROVIDER") or "openai"
        ).strip().lower()

        try:
            self.provider_enum = ModelProvider(provider_value)
        except ValueError as exc:
            supported = ", ".join(item.value for item in ModelProvider)
            raise ValueError(
                f"Unsupported model provider. Supported providers: {supported}"
            ) from exc

        self.provider = self.provider_enum.value
        self.model_name = (
            model_name or os.getenv("MODEL_NAME") or _DEFAULT_MODELS[self.provider_enum]
        ).strip()

        if not self.model_name:
            raise ValueError("Model name cannot be empty")

        self.base_url = self._resolve_base_url(base_url)
        self.api_key = (
            api_key.strip() if api_key is not None else self._get_api_key_default()
        ) or None
        self._validate_configuration()

    @staticmethod
    def _validate_base_url(value: str) -> str:
        try:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Invalid model API base URL")
            _ = parsed.port
        except ValueError as exc:
            raise ValueError(
                "Model API base URL must be an absolute HTTP(S) URL without credentials, query, or fragment"
            ) from exc
        return value.rstrip("/")

    def _resolve_base_url(self, explicit_base_url: Optional[str]) -> str:
        candidates = (
            explicit_base_url,
            os.getenv("MODEL_BASE_URL"),
            os.getenv(_BASE_URL_VARIABLES[self.provider_enum]),
            _DEFAULT_BASE_URLS[self.provider_enum],
        )
        for candidate in candidates:
            if candidate is not None and candidate.strip():
                return self._validate_base_url(candidate.strip())
        raise ValueError("Model API base URL is missing")

    def _get_api_key_default(self) -> Optional[str]:
        if self.provider_enum == ModelProvider.OPENAI:
            return (os.getenv("OPENAI_API_KEY") or "").strip() or None
        if self.provider_enum == ModelProvider.ANTHROPIC:
            return (os.getenv("ANTHROPIC_API_KEY") or "").strip() or None
        return (
            (os.getenv("OLLAMA_API_KEY") or os.getenv("LLAMA_API_KEY") or "").strip()
            or "ollama"
        )

    def _validate_configuration(self) -> None:
        if self.provider_enum == ModelProvider.OPENAI and not self.api_key:
            raise ValueError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
        if self.provider_enum == ModelProvider.ANTHROPIC and not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when MODEL_PROVIDER=anthropic")

    def _is_openai_reasoning_model(self) -> bool:
        return bool(_REASONING_MODEL_PATTERN.match(self.model_name))

    def get_pydantic_ai_model_string(self) -> str:
        return f"{self.provider}:{self.model_name}"

    def get_pydantic_ai_model(self) -> Any:
        if self.provider_enum == ModelProvider.OPENAI:
            from pydantic_ai.providers.openai import OpenAIProvider

            if self._is_openai_reasoning_model():
                try:
                    from pydantic_ai.models.openai import OpenAIResponsesModel
                except ImportError as exc:
                    raise RuntimeError(
                        "This OpenAI reasoning model requires a PydanticAI version with OpenAIResponsesModel"
                    ) from exc
                model_class = OpenAIResponsesModel
            else:
                try:
                    from pydantic_ai.models.openai import OpenAIChatModel
                except ImportError:
                    from pydantic_ai.models.openai import OpenAIModel as OpenAIChatModel
                model_class = OpenAIChatModel

            return model_class(
                model_name=self.model_name,
                provider=OpenAIProvider(api_key=self.api_key, base_url=self.base_url),
            )

        if self.provider_enum == ModelProvider.ANTHROPIC:
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider

            if self.base_url == _DEFAULT_BASE_URLS[ModelProvider.ANTHROPIC]:
                provider = AnthropicProvider(api_key=self.api_key)
            else:
                from anthropic import AsyncAnthropic

                provider = AnthropicProvider(
                    anthropic_client=AsyncAnthropic(
                        api_key=self.api_key,
                        base_url=self.base_url,
                    )
                )
            return AnthropicModel(model_name=self.model_name, provider=provider)

        if self.provider_enum == ModelProvider.OLLAMA:
            from pydantic_ai.providers.ollama import OllamaProvider

            try:
                from pydantic_ai.models.ollama import OllamaModel
            except ImportError:
                try:
                    from pydantic_ai.models.openai import OpenAIChatModel as OllamaModel
                except ImportError:
                    from pydantic_ai.models.openai import OpenAIModel as OllamaModel

            return OllamaModel(
                model_name=self.model_name,
                provider=OllamaProvider(
                    base_url=self.base_url,
                    api_key=self.api_key or "ollama",
                ),
            )

        raise ValueError("Unsupported model provider")

    def get_openai_client(self) -> Any:
        from openai import OpenAI

        if self.provider_enum not in {ModelProvider.OPENAI, ModelProvider.OLLAMA}:
            raise ValueError("get_openai_client() requires OpenAI or Ollama")

        return OpenAI(
            api_key=self.api_key or "ollama",
            base_url=self.base_url,
        )

    def _get_anthropic_client(self) -> Any:
        if self.provider_enum != ModelProvider.ANTHROPIC:
            raise ValueError("Anthropic client requires MODEL_PROVIDER=anthropic")
        from anthropic import Anthropic

        return Anthropic(api_key=self.api_key, base_url=self.base_url)

    @staticmethod
    def _anthropic_text(message: Any) -> str:
        return "\n".join(
            block.text
            for block in (getattr(message, "content", None) or [])
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ).strip()

    @staticmethod
    def _openai_text(response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise RuntimeError("Model returned no completion choices")
        content = getattr(choices[0].message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Model returned empty text")
        return content.strip()

    @staticmethod
    def _validate_base64_image(image_base64_jpeg: str) -> None:
        if not isinstance(image_base64_jpeg, str) or not image_base64_jpeg.strip():
            raise ValueError("image_base64_jpeg must be a non-empty string")

        if len(image_base64_jpeg) > 12_000_000:
            raise ValueError("Image payload is too large")

        try:
            content = base64.b64decode(image_base64_jpeg, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("image_base64_jpeg is not valid base64") from exc

        if not content.startswith(b"\xff\xd8\xff") or not content.endswith(b"\xff\xd9"):
            raise ValueError("Image payload is not a valid JPEG signature")

    @staticmethod
    def _validate_chat_parameters(prompt: str, max_tokens: int, temperature: float) -> None:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if not isinstance(temperature, (int, float)) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")

    def _openai_completion_options(self, max_tokens: int, temperature: float) -> dict[str, Any]:
        if self.provider_enum == ModelProvider.OPENAI and self._is_openai_reasoning_model():
            return {"max_completion_tokens": max_tokens}
        return {"max_tokens": max_tokens, "temperature": temperature}

    def chat_text(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> str:
        self._validate_chat_parameters(user, max_tokens, temperature)

        if self.provider_enum in {ModelProvider.OPENAI, ModelProvider.OLLAMA}:
            with self.get_openai_client() as client:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    **self._openai_completion_options(max_tokens, temperature),
                )
            return self._openai_text(response)

        if self.provider_enum == ModelProvider.ANTHROPIC:
            with self._get_anthropic_client() as client:
                message = client.messages.create(
                    model=self.model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
            result = self._anthropic_text(message)
            if not result:
                raise RuntimeError("Model returned empty text")
            return result

        raise ValueError("Unsupported model provider")

    def chat_vision_text(
        self,
        *,
        user_prompt: str,
        image_base64_jpeg: str,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> str:
        self._validate_chat_parameters(user_prompt, max_tokens, temperature)
        self._validate_base64_image(image_base64_jpeg)

        if self.provider_enum in {ModelProvider.OPENAI, ModelProvider.OLLAMA}:
            with self.get_openai_client() as client:
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": user_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64_jpeg}"
                                    },
                                },
                            ],
                        }
                    ],
                    **self._openai_completion_options(max_tokens, temperature),
                )
            return self._openai_text(response)

        if self.provider_enum == ModelProvider.ANTHROPIC:
            with self._get_anthropic_client() as client:
                message = client.messages.create(
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
            result = self._anthropic_text(message)
            if not result:
                raise RuntimeError("Model returned empty text")
            return result

        raise ValueError("Unsupported model provider")

    def __repr__(self) -> str:
        return (
            f"ModelConfig(provider={self.provider!r}, "
            f"model={self.model_name!r}, base_url={self.base_url!r})"
        )


_model_config: Optional[ModelConfig] = None
_model_config_lock = threading.Lock()


def get_model_config() -> ModelConfig:
    global _model_config
    if _model_config is None:
        with _model_config_lock:
            if _model_config is None:
                _model_config = ModelConfig()
    return _model_config


def set_model_config(config: ModelConfig) -> None:
    if not isinstance(config, ModelConfig):
        raise TypeError("config must be a ModelConfig instance")
    global _model_config
    with _model_config_lock:
        _model_config = config


def reset_model_config() -> None:
    global _model_config
    with _model_config_lock:
        _model_config = None