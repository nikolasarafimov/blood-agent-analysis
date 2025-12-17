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


# Helper functions provided in the prompt
def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """
    Convert PDF pages to PIL Images
    """
    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi)
        return images
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}")


def image_to_base64(image: Image) -> str:
    """
    Convert PIL Image to base64 string for LLM input
    """
    buffer = io.BytesIO()
    # Convert to RGB if necessary
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

        # Convert image to base64
        img_base64 = image_to_base64(image)

        # Create message with image
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

        # Send to vision model (this depends on your vision model setup)
        # Note: This is a placeholder for your actual LLM client call
        response = vision_model.chat.completions.create(
            model="gpt-4o", messages=messages, max_tokens=2048  # Example model
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


# ---


def _is_valid_extracted_text(text: str) -> bool:
    """
    Checks if the LLM response appears to be actual extracted text rather than a refusal message.
    Returns True if the text seems valid, False if it looks like a refusal or error.
    """
    if not text or len(text.strip()) < 10:
        return False

    text_lower = text.lower()

    # Common refusal/error patterns
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
        "there doesn't appear",
        "there does not appear",
        "sorry, but",
        "i apologize",
        "as an ai",
    ]

    # Check if the response starts with or contains refusal patterns
    for pattern in refusal_patterns:
        if pattern in text_lower:
            return False

    # Additional check: if response is very short and doesn't contain typical document text
    # (numbers, common medical terms, etc.), it might not be extracted text
    if len(text.strip()) < 50:
        # Check for presence of numbers or common document characters
        has_numbers = any(c.isdigit() for c in text)
        has_common_chars = any(c in text for c in ["-", ":", "/", "."])
        if not (has_numbers or has_common_chars):
            return False

    return True


def _extract_text_from_image_llm(
        image: Image.Image, prompt: str, max_retries: int = 3, model_config=None
) -> str:
    """
    Attempts to extract text from an image using LLM with retry logic.
    Returns the extracted text or empty string if all attempts fail.
    """
    if model_config is None:
        model_config = get_model_config()

    img_array = np.array(image)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    retval, buffer = cv2.imencode(".jpg", img_bgr)
    image_bytes = buffer.tobytes()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # More explicit prompts for retries
    prompts = [
        prompt,  # Original prompt
        (
            "You are an OCR system. Your ONLY task is to transcribe ALL visible text from this image. "
            "Return ONLY the raw text content exactly as it appears, without any explanations, apologies, or commentary. "
            "If you see text, transcribe it. If you see no text, return an empty string. "
            "Do not refuse. Do not explain. Only transcribe."
        ),
        (
            "Extract and return ALL text visible in this image. Return the text content only, nothing else. "
            "No explanations, no apologies, no commentary - just the transcribed text from the image."
        ),
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
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ]

            response = client.chat.completions.create(
                model=model_config.model_name, messages=messages, max_tokens=4096
            )

            extracted_text = response.choices[0].message.content

            if _is_valid_extracted_text(extracted_text):
                print(extracted_text)
                return extracted_text
            else:
                print(
                    f"Retry attempt {attempt + 1}: LLM returned invalid response, retrying..."
                )
                if attempt < max_retries - 1:
                    continue

        except Exception as e:
            print(f"LLM extraction attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                continue

    return ""  # Return empty string if all LLM attempts failed


def _extract_text_from_image_ocr(image: Image.Image, lang: str | None) -> str:
    """
    Fallback: Extract text from image using OCR (pytesseract).
    """
    try:
        return pytesseract.image_to_string(image, lang=lang)
    except Exception as e:
        print(f"OCR extraction failed: {e}")
        return f"[Error: OCR extraction failed: {e}]"


def extract_text_with_llm(inp: ExtractTextInput, model_config=None) -> str:
    """
    Processes a file (image or PDF) and extracts text from it using a Vision LLM.

    This function handles both single images and multi-page PDFs by converting
    them into a list of images, then uses a Vision LLM to extract text from each
    image, and finally concatenates the results.

    If LLM extraction fails or returns invalid results, falls back to OCR.
    """
    if model_config is None:
        model_config = get_model_config()
    
    all_extracted_text = []

    mime, _ = mimetypes.guess_type(inp.filepath)

    if mime and "pdf" in mime:
        images = pdf_to_images(inp.filepath)
    else:
        images = [Image.open(inp.filepath)]

    page_prompt = (
        "Extract all text from the provided medical laboratory report page and return it as a single continuous string. "
        "This is for record-keeping and documentation purposes only. "
        "Preserve original formatting elements such as line breaks, spacing, and indentation as much as possible. "
        "Replace any personally identifiable information (PII) such as names, addresses, and identification numbers with '[REDACTED]'. "
        "Only return the transcribed text content including test names, values, and reference ranges. "
        "Exclude explanations, metadata, or non-textual elements. "
        "Do not interpret results or provide medical advice."
    )

    for i, image in enumerate(images):
        print(f"Processing page/image {i + 1}/{len(images)} with LLM...")

        # Try LLM extraction first with retries
        extracted_text = _extract_text_from_image_llm(image, page_prompt, max_retries=3, model_config=model_config)

        # If LLM extraction failed or returned invalid result, fall back to OCR
        if not extracted_text or not _is_valid_extracted_text(extracted_text):
            print(f"LLM extraction failed for page {i + 1}, falling back to OCR...")
            extracted_text = _extract_text_from_image_ocr(image, inp.language)

        if extracted_text:
            print(f"Successfully extracted text from page {i + 1}")
            all_extracted_text.append(extracted_text)
        else:
            print(f"Failed to extract text from page {i + 1} using both LLM and OCR")
            all_extracted_text.append(
                f"[Error: Could not extract text from page {i + 1}]"
            )

    final_text = "\n".join(all_extracted_text)
    return final_text
