# Model Configuration Guide

The blood agent pipeline supports multiple LLM providers. You can configure the model in one place and it will be used
throughout the entire pipeline (agent, text extraction, anonymization, JSON conversion, and LOINC validation).

## Configuration Methods

### 1. Environment Variables (Recommended)

Set these in your `.env` file:

```bash
# Model Provider (openai, anthropic, ollama)
MODEL_PROVIDER=openai

# Model Name (varies by provider)
MODEL_NAME=gpt-4o

# Base URL (required for Ollama, optional for others)
MODEL_BASE_URL=https://llama3.finki.ukim.mk/v1

# API Keys (provider-specific)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
LLAMA_API_KEY=your_llama_key  # or OLLAMA_API_KEY
```

### 2. Command Line Arguments

You can override env vars using command-line arguments in `batch_process.py`:

```bash
# Use Claude
python batch_process.py /path/to/files \
    --model-provider anthropic \
    --model-name claude-3-5-sonnet-20241022

# Use Llama via Ollama
python batch_process.py /path/to/files \
    --model-provider ollama \
    --model-name llama3.3:70b \
    --model-base-url https://llama3.finki.ukim.mk/v1
```

### 3. Programmatic Configuration

In your Python code:

```python
from src.model_config import ModelConfig, set_model_config
from src.agent import create_blood_agent

# Configure model
model_config = ModelConfig(
    provider="openai",
    model_name="gpt-4o"
)

# Set as global config
set_model_config(model_config)

# Create agent with this config
blood_agent = create_blood_agent(model_config)
```

## Supported Providers

### OpenAI

```bash
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o  # or gpt-3.5-turbo, gpt-4-turbo, etc.
OPENAI_API_KEY=sk-...
```

### Anthropic (Claude)

```bash
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-3-5-sonnet-20241022  # or claude-3-opus-20240229, etc.
ANTHROPIC_API_KEY=sk-ant-...
```

### Ollama / Llama

```bash
MODEL_PROVIDER=ollama
MODEL_NAME=llama3.3:70b  # or llama2, mistral, etc.
MODEL_BASE_URL=https://llama3.finki.ukim.mk/v1  # or http://localhost:11434/v1
LLAMA_API_KEY=your_key  # or OLLAMA_API_KEY
```

## Model Compatibility

**Vision Models (for text extraction):**

- OpenAI: `gpt-4o`, `gpt-4-turbo` (vision capable)
- Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229` (vision capable)
- Ollama: Check your specific model supports vision

**Structured Output:**

- OpenAI: `gpt-4o` (supports `.beta.chat.completions.parse`)
- Anthropic: Most Claude models support structured outputs
- Ollama: May require manual JSON parsing

**Note:** Some features like structured JSON parsing may not be available for all models. The code will attempt to use
the best available method for each provider.

## Examples

### Using OpenAI GPT-4o (Default)

```bash
export MODEL_PROVIDER=openai
export MODEL_NAME=gpt-4o
export OPENAI_API_KEY=sk-...

python batch_process.py /path/to/blood_tests
```

### Using Claude

```bash
export MODEL_PROVIDER=anthropic
export MODEL_NAME=claude-3-5-sonnet-20241022
export ANTHROPIC_API_KEY=sk-ant-...

python batch_process.py /path/to/blood_tests
```

### Using Llama via Ollama

```bash
export MODEL_PROVIDER=ollama
export MODEL_NAME=llama3.3:70b
export MODEL_BASE_URL=https://llama3.finki.ukim.mk/v1
export LLAMA_API_KEY=your_key

python batch_process.py /path/to/blood_tests
```

## Where the Model is Used

The configured model is automatically used in:

1. **Agent** (`src/agent.py`) - Main orchestration agent
2. **Text Extraction** (`src/tools/extract_text.py`) - Vision LLM for OCR
3. **Anonymization** (`src/tools/anonymize.py`) - PII removal
4. **JSON Conversion** (`src/tools/txt_to_json.py`) - Structured output
5. **LOINC Validation** (`src/tools/loinc_validation.py`) - Medical coding

All these components use the same model configuration, ensuring consistency across the pipeline.

