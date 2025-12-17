"""
Centralized model configuration for the blood agent pipeline.
Supports OpenAI, Anthropic Claude, and Ollama/Llama models.
"""
import os
from enum import Enum
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class ModelProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class ModelConfig:
    """
    Centralized model configuration.
    Set via environment variables or direct initialization.
    """

    def __init__(
            self,
            provider: Optional[str] = None,
            model_name: Optional[str] = None,
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
    ):
        # Get from environment or use provided values
        self.provider = provider or os.getenv("MODEL_PROVIDER", "openai").lower()
        self.model_name = model_name or os.getenv("MODEL_NAME", "gpt-4o")
        self.api_key = api_key or self._get_api_key()
        self.base_url = base_url or os.getenv("MODEL_BASE_URL")

        # Validate provider
        try:
            self.provider_enum = ModelProvider(self.provider)
        except ValueError:
            raise ValueError(f"Unsupported provider: {self.provider}. Supported: {[p.value for p in ModelProvider]}")

    def _get_api_key(self) -> Optional[str]:
        """Get API key based on provider."""
        if self.provider == ModelProvider.OPENAI.value:
            return os.getenv("OPENAI_API_KEY")
        elif self.provider == ModelProvider.ANTHROPIC.value:
            return os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == ModelProvider.OLLAMA.value:
            return os.getenv("LLAMA_API_KEY") or os.getenv("OLLAMA_API_KEY")
        return None

    def get_pydantic_ai_model_string(self) -> str:
        """
        Get model string for pydantic_ai Agent.
        Examples: 'openai:gpt-4o', 'anthropic:claude-3-5-sonnet-20241022', 'ollama:llama3.3:70b'
        """
        if self.provider == ModelProvider.OPENAI.value:
            return f"openai:{self.model_name}"
        elif self.provider == ModelProvider.ANTHROPIC.value:
            return f"anthropic:{self.model_name}"
        elif self.provider == ModelProvider.OLLAMA.value:
            # For Ollama, model_name might include version like "llama3.3:70b"
            return f"ollama:{self.model_name}"
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def get_pydantic_ai_model(self):
        """
        Get pydantic_ai Model object with proper configuration.
        Use this for Agent initialization when custom provider setup is needed.
        """
        from pydantic_ai.models.openai import OpenAIModel
        from pydantic_ai.providers.ollama import OllamaProvider

        if self.provider == ModelProvider.OPENAI.value:
            return OpenAIModel(model_name=self.model_name)
        elif self.provider == ModelProvider.ANTHROPIC.value:
            from pydantic_ai.models.anthropic import AnthropicModel
            return AnthropicModel(model_name=self.model_name)
        elif self.provider == ModelProvider.OLLAMA.value:
            if not self.base_url:
                raise ValueError("OLLAMA provider requires base_url to be set")
            return OpenAIModel(
                model_name=self.model_name,
                provider=OllamaProvider(base_url=self.base_url, api_key=self.api_key)
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def get_openai_client(self):
        """
        Get OpenAI-compatible client for direct API calls.
        For Anthropic/Ollama, we'll need to adapt this or use provider-specific clients.
        """
        from openai import OpenAI

        if self.provider == ModelProvider.OPENAI.value:
            return OpenAI(api_key=self.api_key)
        elif self.provider == ModelProvider.ANTHROPIC.value:
            # Anthropic uses a different SDK, but we can use OpenAI-compatible base_url
            # For now, return OpenAI client with Anthropic base URL if configured
            # Note: This might require anthropic SDK for full support
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url or "https://api.anthropic.com/v1"
            )
        elif self.provider == ModelProvider.OLLAMA.value:
            # Ollama is OpenAI-compatible
            return OpenAI(
                api_key=self.api_key,
                base_url=self.base_url or "http://localhost:11434/v1"
            )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def __repr__(self):
        return f"ModelConfig(provider={self.provider}, model={self.model_name})"


# Global model config instance
_model_config: Optional[ModelConfig] = None


def get_model_config() -> ModelConfig:
    """
    Get the global model configuration.
    Creates a new instance if none exists.
    """
    global _model_config
    if _model_config is None:
        _model_config = ModelConfig()
    return _model_config


def set_model_config(config: ModelConfig):
    """Set the global model configuration."""
    global _model_config
    _model_config = config


def reset_model_config():
    """Reset the global model configuration (useful for testing)."""
    global _model_config
    _model_config = None
