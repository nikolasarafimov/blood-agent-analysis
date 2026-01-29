from __future__ import annotations

import base64
import io
import mimetypes
import os
import subprocess
from typing import List, Optional

import pdfplumber
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pydantic import BaseModel

from ..model_config import get_model_config, ModelConfig
from ..models import RawText


class ExtractTextInput(BaseModel):
    filepath: str
    language: Optional[str] = None


def _pdf_text_fast(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        parts: List[str] = []
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()


def _pdf_to_images(path: str, dpi: int = 200) -> List[Image.Image]:
    poppler_bin = os.getenv("POPPLER_PATH") or None
    return convert_from_path(path, dpi=dpi, poppler_path=poppler_bin)


def _image_to_text_ocr(image: Image.Image, lang: Optional[str]) -> str:
    try:
        return pytesseract.image_to_string(image, lang=lang)
    except Exception:
        return pytesseract.image_to_string(image)


def _pdf_to_ocr_text_via_images(path: str, lang: Optional[str]) -> str:
    images = _pdf_to_images(path, dpi=250)
    out: List[str] = []
    for i, img in enumerate(images):
        txt = _image_to_text_ocr(img, lang)
        txt = (txt or "").strip()
        out.append(txt if txt else f"[Error: Could not OCR page {i + 1}]")
    return "\n\n".join(out).strip()


def _pdf_to_ocr_text_via_ocrmypdf(path: str, lang: Optional[str]) -> Optional[str]:
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out_pdf:
            cmd = ["ocrmypdf", "--skip-text"]
            if lang:
                cmd += ["-l", lang]
            cmd += [path, out_pdf.name]
            subprocess.run(cmd, check=True)
            return _pdf_text_fast(out_pdf.name)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def extract_text(inp: ExtractTextInput) -> RawText:
    mime, _ = mimetypes.guess_type(inp.filepath)
    lang = inp.language

    if mime and "pdf" in mime:
        text = _pdf_text_fast(inp.filepath)
        if not text or len(text.strip()) < 10:
            ocr_layer_text = _pdf_to_ocr_text_via_ocrmypdf(inp.filepath, lang)
            if ocr_layer_text and len(ocr_layer_text.strip()) >= 10:
                text = ocr_layer_text
            else:
                text = _pdf_to_ocr_text_via_images(inp.filepath, lang)
    else:
        img = Image.open(inp.filepath)
        text = _image_to_text_ocr(img, lang)

    return RawText(text=text or "", source_name=os.path.basename(inp.filepath), language=lang)


def _pil_to_base64_jpeg(image: Image.Image) -> str:
    buf = io.BytesIO()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(buf, format="JPEG", quality=95)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def create_medical_extraction_prompt(language: Optional[str] = None) -> str:
    lang_instruction = f" in {language}" if language else ""
    return f"""You are analyzing a medical document (blood test / lab report). Extract ALL visible text with high accuracy.

Rules:
- Extract every piece of text, including tables, headers, footers, labels.
- Preserve formatting and table structure as plain text.
- Be precise with numbers, decimal points, units, and ranges.
- If something is unclear, mark it as [UNCLEAR: ...]
- Return ONLY the extracted text. No explanations.

Extract the text{lang_instruction}:"""


def _is_valid_extracted_text(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False

    tl = text.lower()
    refusal_patterns = [
        "i can't assist",
        "i cannot assist",
        "i'm unable to",
        "i am unable to",
        "there is no text",
        "no text to extract",
        "cannot extract",
        "unable to extract",
        "i don't see",
        "i do not see",
        "sorry, but",
        "as an ai",
    ]
    if any(p in tl for p in refusal_patterns):
        return False

    if len(text.strip()) < 50:
        has_numbers = any(c.isdigit() for c in text)
        has_common_chars = any(c in text for c in ["-", ":", "/", "."])
        if not (has_numbers or has_common_chars):
            return False

    return True


def extract_text_with_llm(inp: ExtractTextInput, model_config: Optional[ModelConfig] = None) -> RawText:
    if model_config is None:
        model_config = get_model_config()

    mime, _ = mimetypes.guess_type(inp.filepath)
    lang = inp.language

    if mime and "pdf" in mime:
        images = _pdf_to_images(inp.filepath, dpi=250)
    else:
        images = [Image.open(inp.filepath)]

    prompt = create_medical_extraction_prompt(language=lang)

    prompts = [
        prompt,
        "You are an OCR system. Return ONLY the raw text exactly as it appears. No commentary.",
        "Extract and return ALL text visible in this image. No commentary.",
    ]

    parts: List[str] = []
    for i, img in enumerate(images):
        base64_image = _pil_to_base64_jpeg(img)

        extracted = ""
        for attempt in range(min(3, len(prompts))):
            try:
                extracted = model_config.chat_vision_text(
                    user_prompt=prompts[attempt],
                    image_base64_jpeg=base64_image,
                    temperature=0,
                    max_tokens=4096,
                )
                if _is_valid_extracted_text(extracted):
                    break
            except Exception:
                continue

        if not extracted:
            extracted = _image_to_text_ocr(img, lang)

        extracted = (extracted or "").strip()
        if not extracted:
            extracted = f"[Error: Could not extract text from page {i + 1}]"

        parts.append(extracted)

    full_text = "\n\n".join(parts).strip()
    return RawText(text=full_text, source_name=os.path.basename(inp.filepath), language=lang)