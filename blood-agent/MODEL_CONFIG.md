# Model Configuration Guide

Blood Agent supports OpenAI, Anthropic, and Ollama through `src/model_config.py`. The configuration is shared by the PydanticAI orchestration agent, optional vision OCR, optional LLM anonymization refinement, and structured JSON extraction.

**LOINC enrichment is deterministic and local.** It uses a curated CBC mapping catalog rather than requesting codes from a language model.

This project is intended for development and demonstration. It is not a medical device and must not be used to make clinical decisions.

## 1. Environment setup

Create a `.env` file in the `blood-agent` directory, or provide the same variables through your runtime environment or Docker configuration. Do not commit `.env` or any real credentials.

### OpenAI

```dotenv
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=your_openai_api_key

ENABLE_LLM_OCR=false
ALLOW_UNREDACTED_LLM_OCR=false
ENABLE_LLM_ANONYMIZATION=false
```

The default OpenAI API base URL is `https://api.openai.com/v1`. Set a custom endpoint only when needed:

```dotenv
OPENAI_BASE_URL=https://example.com/v1
```

### Anthropic

```dotenv
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-5
ANTHROPIC_API_KEY=your_anthropic_api_key

ENABLE_LLM_OCR=false
ALLOW_UNREDACTED_LLM_OCR=false
ENABLE_LLM_ANONYMIZATION=false
```

A custom Anthropic endpoint is optional:

```dotenv
ANTHROPIC_BASE_URL=https://example.com
```

The selected model must be available to your API account.

### Ollama

For an Ollama service running on the same machine as the Python process:

```dotenv
MODEL_PROVIDER=ollama
MODEL_NAME=qwen3
OLLAMA_BASE_URL=http://localhost:11434/v1

ENABLE_LLM_OCR=false
ALLOW_UNREDACTED_LLM_OCR=false
ENABLE_LLM_ANONYMIZATION=false
```

For a Docker container connecting to Ollama on a Windows host with Docker Desktop, an endpoint such as the following may be appropriate, provided the Ollama service is reachable from the container:

```dotenv
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
```

`localhost` inside a container refers to that container, not the Windows host. Ollama normally needs no real API key for a local endpoint; `ModelConfig` supplies a placeholder automatically. An authenticated endpoint may use `OLLAMA_API_KEY` or the legacy fallback `LLAMA_API_KEY`.

### Base URL precedence

`ModelConfig` chooses the first nonempty value in this order:

1. Explicit `base_url` passed to `ModelConfig` (including the CLI `--model-base-url` override).
2. `MODEL_BASE_URL`.
3. Provider-specific `OPENAI_BASE_URL`, `ANTHROPIC_BASE_URL`, or `OLLAMA_BASE_URL`.
4. Provider default.

For example:

```dotenv
MODEL_BASE_URL=https://example.com/v1
```

The URL must be an absolute HTTP(S) address without embedded credentials, a query, or a fragment. An empty `OPENAI_BASE_URL` does not override the default endpoint.

## 2. Model selection

If `MODEL_NAME` is not set, the configured defaults are:

| Provider | Default model |
| --- | --- |
| OpenAI | `gpt-4o` |
| Anthropic | `claude-sonnet-4-5` |
| Ollama | `qwen3` |

These are configuration defaults, not guarantees of model availability or feature support. The chosen model must support tool calling for agent orchestration and text generation for JSON extraction. Vision OCR additionally requires image input. Check provider and model capabilities before switching models.

For the existing tested workflow, retain `MODEL_PROVIDER=openai` and `MODEL_NAME=gpt-4o` unless there is a specific reason to change them.

## 3. Optional LLM features

### Vision OCR

Local PDF extraction and Tesseract OCR are used by default:

```dotenv
ENABLE_LLM_OCR=false
ALLOW_UNREDACTED_LLM_OCR=false
```

To permit vision OCR, **both** settings must explicitly be enabled:

```dotenv
ENABLE_LLM_OCR=true
ALLOW_UNREDACTED_LLM_OCR=true
```

**Privacy warning:** Vision OCR sends an image of the original document to the configured model provider *before local anonymization*. This image may contain names, dates of birth, identifiers, addresses, and other sensitive information. Enable this only when the data, provider, agreements, and applicable rules explicitly permit such transmission. If the model does not support images, disable LLM OCR.

With vision OCR disabled, the extraction layer uses embedded PDF text where possible, Tesseract for scanned pages, and optionally OCRmyPDF when installed. Local OCR requires appropriate Tesseract language data (for example `eng` and `mkd`) and Poppler for PDF rendering.

### LLM anonymization refinement

```dotenv
ENABLE_LLM_ANONYMIZATION=false
```

To enable the optional second pass:

```dotenv
ENABLE_LLM_ANONYMIZATION=true
```

The local Presidio-based anonymization step runs first. Only the locally redacted text is intentionally provided to the LLM refinement stage. However, local PII detection is imperfect; residual identifiers may still be present. Anonymization cannot be assumed to be complete without appropriate verification.

If the LLM refinement fails validation, the pipeline retains the locally redacted version rather than accepting an invalid response.

### Structured JSON extraction

JSON extraction uses the configured model through `ModelConfig.chat_text()`; it is **not** controlled by `ENABLE_LLM_OCR` or `ENABLE_LLM_ANONYMIZATION`.

The input is the stored anonymized text, not the original extracted text. The result is checked against the `LaboratoryResults` Pydantic schema. The extraction stage leaves `loinc_code` and `loinc_display` set to `null` for subsequent enrichment.

A valid JSON schema does not guarantee that every test name, number, or unit was extracted correctly. Manually verify extracted results against suitable test documents before relying on them.

### LOINC enrichment

The LOINC step in `src/tools/loinc_validation.py` uses a **local curated CBC catalog**, not an LLM. Codes are assigned only when the parameter name, expected unit, and CBC context satisfy its matching rules. Ambiguous or unmatched tests keep `loinc_code` and `loinc_display` as `null`.

For backward compatibility, some functions retain names ending in `_with_llm`, but these functions do not call the model. LOINC enrichment does not independently send data to an external provider and does not change laboratory measurements. The catalog is limited and is not a substitute for a full terminology service or clinical validation.

## 4. Command-line usage

Run these commands from the `blood-agent` directory.

### Process a folder

```bash
python batch_process.py /path/to/files --language mkd+eng
```

Override the configured provider or model:

```bash
python batch_process.py /path/to/files --model-provider openai --model-name gpt-4o
```

```bash
python batch_process.py /path/to/files --model-provider anthropic --model-name claude-sonnet-4-5
```

```bash
python batch_process.py /path/to/files --model-provider ollama --model-name qwen3 --model-base-url http://localhost:11434/v1
```

Preview supported files without invoking the agent:

```bash
python batch_process.py /path/to/files --dry-run
```

### Process one document

```bash
python demo.py /path/to/sample.pdf
```

```bash
python demo.py /path/to/sample.pdf --model-provider openai --model-name gpt-4o
```

On Windows PowerShell, replace `/path/to/sample.pdf` with an actual path. Quote paths containing spaces. The default `--language` value in both CLI scripts is `mkd+eng`, so the corresponding Tesseract language packs must be installed for OCR to work.

## 5. Python usage

```python
from src.agent import create_blood_agent
from src.model_config import ModelConfig

model_config = ModelConfig(provider="openai", model_name="gpt-4o")
blood_agent = create_blood_agent(model_config=model_config)
```

For Ollama:

```python
from src.agent import create_blood_agent
from src.model_config import ModelConfig

model_config = ModelConfig(
    provider="ollama",
    model_name="qwen3",
    base_url="http://localhost:11434/v1",
)
blood_agent = create_blood_agent(model_config=model_config)
```

Creating an agent does not process a file by itself. Use `AgentDependencies` and `agent.run_sync(..., deps=...)`, as demonstrated in `demo.py`, or call `run_demo()` / `batch_process()` directly.

## 6. Pipeline architecture

```text
Document upload
    |
    v
MinIO Bronze: original file
    |
    v
Local PDF extraction / OCR (vision LLM optional, explicit opt-in)
    |
    v
MinIO Bronze: extracted text
    |
    v
Local Presidio anonymization (LLM refinement optional)
    |
    v
MinIO Silver: anonymized text
    |
    v
LLM structured extraction + Pydantic validation
    |
    v
MinIO Silver: laboratory JSON
    |
    v
Local deterministic LOINC enrichment
    |
    v
MinIO Silver: enriched laboratory JSON
```

| Component | File | Main responsibility |
| --- | --- | --- |
| Agent orchestration | `src/agent.py` | Enforces the processing sequence and checks completion |
| Model and SDK configuration | `src/model_config.py` | Provider setup, text and vision APIs |
| Input and extraction | `src/tools/ingest.py`, `src/tools/extract_text.py` | Storage, PDF text extraction and OCR |
| Anonymization | `src/tools/anonymize.py` | Local redaction and optional LLM refinement |
| JSON transformation | `src/tools/txt_to_json.py` | LLM extraction and schema validation |
| LOINC enrichment | `src/tools/loinc_validation.py` | Curated deterministic mappings |
| Storage | `storage/minio_storage.py` | Bronze/Silver MinIO objects |
| Persistence | `db/sqlite_db.py` | Document metadata and status tracking |

The agent receives tool results and document IDs; the full extracted report is not intentionally returned through the anonymization tool. JSON extraction still transmits locally anonymized laboratory text to the selected external provider unless a genuinely local model endpoint is used.

## 7. Optional processing limits

These environment variables are read by the relevant processing and storage modules:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAX_UPLOAD_MB` | `20` | Maximum input file size in MB |
| `MAX_DOCUMENT_PAGES` | `30` | Maximum PDF or multipage raster pages |
| `MAX_OCR_IMAGE_PIXELS` | `40000000` | Image pixel limit |
| `PDF_RENDER_TIMEOUT_SECONDS` | `60` | Poppler rendering timeout |
| `OCR_TIMEOUT_SECONDS` | `60` | Tesseract timeout per invocation |
| `OCRMYPDF_TIMEOUT_SECONDS` | `300` | OCRmyPDF process timeout |
| `MAX_PREVIEW_DIMENSION` | `2000` | Maximum preview dimension |
| `MAX_STORAGE_READ_MB` | `32` | Storage read/payload limit in MB |

All these values are optional. The implementation uses positive integer values and falls back to the listed defaults for invalid or nonpositive settings.

## 8. Deployment and privacy notes

- Never commit `.env` files, API credentials, real patient records, MinIO data, or SQLite databases. Also inspect Git history if any sensitive file was previously tracked.
- Bronze storage contains **unredacted** originals and extracted text. Preview images can also contain identifying information. Restrict access to all document endpoints and storage resources.
- Disabling LLM OCR and LLM anonymization does **not** make the whole pipeline offline; structured JSON extraction still invokes the configured model.
- Local Presidio redaction does not guarantee complete de-identification, particularly for unsupported languages, unusual document layouts, and unstructured identifiers.
- Presidio's default English analyzer requires an installed spaCy language model. Python requirements alone do not guarantee the model or system OCR tools are installed; check the Docker image.
- Ollama can keep model calls local only when the configured endpoint actually points to a locally controlled service. Provider-specific functionality and quality still require validation.
- This repository's current local-demo design is not sufficient on its own for a public deployment processing sensitive records. Authentication, authorization, storage controls, retention, auditability, and applicable data-protection requirements must be addressed first.

Use synthetic or otherwise explicitly authorized test documents for demonstrations. The project is for educational and engineering purposes, not clinical interpretation, diagnosis, or treatment.