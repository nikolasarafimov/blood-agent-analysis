import base64
import io
import mimetypes
import os
import subprocess
import tempfile
from typing import List, Optional

import cv2
import numpy as np
import pdfplumber
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from pydantic import BaseModel

from ..model_config import get_model_config
from ..models import RawText


class ExtractTextInput(BaseModel):
    filepath: str
    language: str | None = None  # 'en' or 'mkd' for Tesseract


def _pdf_text_fast(path: str) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join([page.extract_text() or "" for page in pdf.pages]).strip()


def _pdf_to_ocr_text(path: str, lang: str | None) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as out_pdf:
        # Add text layer using OCRmyPDF (wraps Tesseract)
        subprocess.run(
            [
                "ocrmypdf",
                "--skip-text",
                *(["-l", lang] if lang else []),
                path,
                out_pdf.name,
            ],
            check=True,
        )
        return _pdf_text_fast(out_pdf.name)


def _image_to_text(path: str, lang: str | None) -> str:
    img = Image.open(path)
    return pytesseract.image_to_string(img, lang=lang)


def extract_text(inp: ExtractTextInput) -> RawText:
    mime, _ = mimetypes.guess_type(inp.filepath)
    lang = inp.language
    if mime and "pdf" in mime:
        text = _pdf_text_fast(inp.filepath)
        if not text or len(text.strip()) < 10:
            text = _pdf_to_ocr_text(inp.filepath, lang)
    else:
        text = _image_to_text(inp.filepath, lang)
    return RawText(text=text, source_name=os.path.basename(inp.filepath), language=lang)


def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    poppler_bin = os.getenv("POPPLER_PATH", None)

    try:
        images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_bin)
        return images
    except Exception as e:
        error_msg = str(e)
        if "PDFInfoNotInstalledError" in error_msg:
            raise Exception(
                "Error: Poppler not found!"
            )
        raise Exception(f"Error converting PDF to images: {error_msg}")


def image_to_base64(image: Image) -> str:
    """
    Convert PIL Image to base64 string for LLM input
    """
    buffer = io.BytesIO()
    if image.mode != "RGB":
        image = image.convert("RGB")
    image.save(buffer, format="JPEG", quality=95)
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8")


def image_to_text_with_llm(image: Image, vision_model, prompt: str = None) -> RawText:
    """
    Extract text from image using Vision LLM
    """
    try:
        if prompt is None:
            prompt = """Please extract all the text you can see in this image.
            Maintain the original formatting as much as possible, including:
            - Line breaks and paragraphs
            - Lists and bullet points
            - Tables (format as plain text tables)
            - Any headers or titles

            Only return the extracted text, no additional commentary."""

        img_base64 = image_to_base64(image)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                    },
                ],
            }
        ]

        response = vision_model.chat.completions.create(
            model="gpt-4o", messages=messages, max_tokens=2048
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        raise Exception(f"Error extracting text with LLM: {str(e)}")


def create_medical_extraction_prompt(language: Optional[str] = None) -> str:
    """
    Create a specialized prompt for extracting text from medical/blood test documents
    """
    lang_instruction = f" in {language}" if language else ""

    prompt = f"""You are analyzing a medical document, likely a blood test or lab report. Please extract ALL visible text from this image with high accuracy.

IMPORTANT INSTRUCTIONS:
1. Extract every piece of text you can see, including:
   - Patient information (names, IDs, dates)
   - Test names and categories
   - Numerical values and units
   - Reference ranges
   - Doctor/lab information
   - Headers, footers, and labels

2. Maintain the original structure and formatting:
   - Preserve line breaks and spacing
   - Keep tables in tabular format
   - Maintain the relationship between test names and values
   - Include any special symbols or formatting

3. Be extremely precise with:
   - Numbers and decimal points
   - Medical terminology
   - Units of measurement
   - Dates and times

4. If any text is unclear or partially obscured, indicate this with [UNCLEAR: partial_text]

5. Do NOT:
   - Add interpretations or explanations
   - Modify or "correct" any information
   - Skip any visible text, even if it seems unimportant

Extract the text{lang_instruction} maintaining maximum fidelity to the original document:"""


    return prompt


def _is_valid_extracted_text(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False

    text_lower = text.lower()
    refusal_patterns = [
        "i can't assist", "i cannot assist", "i'm unable to", "i am unable to",
        "there is no text", "no text to extract", "cannot extract", "unable to extract",
        "i don't see", "i do not see", "sorry, but", "as an ai",
    ]

    for pattern in refusal_patterns:
        if pattern in text_lower:
            return False

    if len(text.strip()) < 50:
        has_numbers = any(c.isdigit() for c in text)
        has_common_chars = any(c in text for c in ["-", ":", "/", "."])
        if not (has_numbers or has_common_chars):
            return False

    return True


def _extract_text_from_image_llm(
        image: Image.Image, prompt: str, max_retries: int = 3, model_config=None
) -> str:
    if model_config is None:
        model_config = get_model_config()

    img_array = np.array(image)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    retval, buffer = cv2.imencode(".jpg", img_bgr)
    image_bytes = buffer.tobytes()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompts = [
        prompt,
        "You are an OCR system. Return ONLY the raw text exactly as it appears.",
        "Extract and return ALL text visible in this image. No commentary."
    ]

    client = model_config.get_openai_client()

    for attempt in range(min(max_retries, len(prompts))):
        try:
            current_prompt = prompts[attempt]
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": current_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ]

            response = client.chat.completions.create(
                model=model_config.model_name, messages=messages, max_tokens=4096
            )

            extracted_text = response.choices[0].message.content

            if _is_valid_extracted_text(extracted_text):
                return extracted_text

        except Exception as e:
            print(f"LLM extraction attempt {attempt + 1} failed: {e}")

    return ""


def _extract_text_from_image_ocr(image: Image.Image, lang: str | None) -> str:
    try:
        return pytesseract.image_to_string(image, lang=lang)
    except Exception as e:
        return f"[Error: OCR extraction failed: {e}]"


def extract_text_with_llm(inp: ExtractTextInput, model_config=None) -> str:
    if model_config is None:
        model_config = get_model_config()

    all_extracted_text = []
    mime, _ = mimetypes.guess_type(inp.filepath)

    if mime and "pdf" in mime:
        images = pdf_to_images(inp.filepath)
    else:
        images = [Image.open(inp.filepath)]

    page_prompt = (
        "Extract all text from the provided medical laboratory report page. "
        "Redact PII with '[REDACTED]'. "
        "Return only the text content."
    )

    for i, image in enumerate(images):
        extracted_text = _extract_text_from_image_llm(image, page_prompt, max_retries=3, model_config=model_config)

        if not extracted_text or not _is_valid_extracted_text(extracted_text):
            extracted_text = _extract_text_from_image_ocr(image, inp.language)

        if extracted_text:
            all_extracted_text.append(extracted_text)
        else:
            all_extracted_text.append(f"[Error: Could not extract text from page {i + 1}]")

    return "\n".join(all_extracted_text)