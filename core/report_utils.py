"""Utilities for extracting text/images from medical reports and analyzing them via OpenRouter."""
import base64
import io
import logging
import os
import requests
from django.conf import settings
from PIL import Image
from pypdf import PdfReader

from accounts.models import SPECIALIZATION_CHOICES

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_PDF_EXTS = {'.pdf'}
MAX_REPORT_BYTES = 10 * 1024 * 1024  # 10 MB

VISION_MODELS = [
    'nvidia/nemotron-3.5-super-vl:free',
    'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free',
    'google/gemma-4-31b-it:free',
    'google/gemma-4-26b-a4b-it:free',
    'openrouter/free',
]

TEXT_MODELS = [
    'openrouter/free',
    'google/gemma-4-31b-it:free',
    'google/gemma-4-26b-a4b-it:free',
]

REPORT_SYSTEM_PROMPT = (
    'You are MediCate AI, a careful clinical medical report interpreter. '
    'Analyze the provided medical report, lab result, prescription, or radiology scan/report clearly for a patient. '
    'Structure your response with these exact markdown headings:\n'
    '### 1. Report Overview\n'
    '### 2. Key Findings & Values\n'
    '### 3. Plain-Language Explanation\n'
    '### 4. Urgency & Red Flags\n'
    '### 5. Recommended Specialist\n'
    'Under "Recommended Specialist", name ONE best matching specialist from this list: '
    'General Physician, Cardiologist, Gastroenterologist, Neurologist, Endocrinologist, '
    'Pulmonologist, Orthopedic, Dermatologist, Urologist, Ophthalmologist, ENT Specialist, '
    'Psychiatrist, Pediatrician, Gynecologist, Oncologist, Rheumatologist, Nephrologist, '
    'Hematologist, Hepatologist, Infectious Disease.\n'
    'Always end with a brief reminder that this is an AI summary and not a formal medical diagnosis.'
)


def extract_pdf_text(file_obj):
    """Extract readable text from an uploaded PDF file."""
    file_obj.seek(0)
    reader = PdfReader(file_obj)
    chunks = []
    for i, page in enumerate(reader.pages[:12]):
        txt = (page.extract_text() or '').strip()
        if txt:
            chunks.append(f'--- Page {i + 1} ---\n{txt}')
    file_obj.seek(0)
    return '\n\n'.join(chunks)[:12000]


def encode_image_data_url(file_obj):
    """Normalize an uploaded image to RGB JPEG (max 1600px) and return a base64 data URL."""
    file_obj.seek(0)
    img = Image.open(file_obj)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    elif img.mode == 'L':
        img = img.convert('RGB')
    img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    file_obj.seek(0)
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return f'data:image/jpeg;base64,{b64}'


def _call_openrouter(messages, models, max_tokens=900):
    """Call OpenRouter with ordered model fallbacks until one succeeds."""
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        return None, 'AI assistant is not configured. Please add OPENROUTER_API_KEY to .env.'

    last_err = ''
    for model in models:
        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': messages,
                    'max_tokens': max_tokens,
                },
                timeout=35,
            )
            if resp.status_code == 200:
                content = resp.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                if content:
                    return content, None
            last_err = f'{model} returned {resp.status_code}: {resp.text[:180]}'
            logger.warning(f'OpenRouter report model fallback: {last_err}')
        except Exception as e:
            last_err = str(e)
            logger.warning(f'OpenRouter error on {model}: {e}')

    return None, f'AI analysis temporarily unavailable ({last_err}). Please try again.'


def _detect_specialist(ai_text):
    """Extract the matching specialization from the AI response."""
    if not ai_text:
        return 'General Physician'
    # Prefer matching inside the Recommended Specialist section if present
    lower = ai_text.lower()
    sec_idx = lower.find('recommended specialist')
    search_area = ai_text[sec_idx:] if sec_idx != -1 else ai_text
    for spec_val, _ in SPECIALIZATION_CHOICES:
        if spec_val.lower() in search_area.lower():
            return spec_val
    for spec_val, _ in SPECIALIZATION_CHOICES:
        if spec_val.lower() in lower:
            return spec_val
    return 'General Physician'


def analyze_medical_report(file_obj, filename, report_type='other'):
    """Analyze a PDF or image medical report and return a structured result dict."""
    ext = os.path.splitext(filename or '')[1].lower()
    if ext in ALLOWED_PDF_EXTS:
        file_type = 'pdf'
    elif ext in ALLOWED_IMAGE_EXTS:
        file_type = 'image'
    else:
        return {
            'error': 'Unsupported file type. Please upload a PDF, JPG, PNG, or WEBP file.',
        }

    extracted_text = ''
    if file_type == 'pdf':
        try:
            extracted_text = extract_pdf_text(file_obj)
        except Exception as e:
            logger.error(f'PDF extraction failed: {e}')
            return {'error': 'Could not read this PDF file. Please ensure it is not password-protected or corrupted.'}

        if len(extracted_text.strip()) < 30:
            return {
                'file_type': 'pdf',
                'extracted_text': extracted_text,
                'ai_summary': (
                    '### 1. Report Overview\n'
                    'This PDF appears to be a scanned image without selectable text.\n\n'
                    '### 2. How to Analyze It\n'
                    'Please take a screenshot or export the page as a **JPG or PNG image** and upload it — '
                    'our AI Vision analyzer can read scanned X-rays, MRI reports, and prescriptions directly from images.'
                ),
                'recommended_specialist': 'General Physician',
                'error': None,
            }

        messages = [
            {'role': 'system', 'content': REPORT_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': (
                    f'Report Category: {report_type}\n'
                    f'Filename: {filename}\n\n'
                    f'Extracted Report Text:\n{extracted_text}'
                ),
            },
        ]
        summary, err = _call_openrouter(messages, TEXT_MODELS)
    else:
        try:
            data_url = encode_image_data_url(file_obj)
        except Exception as e:
            logger.error(f'Image encoding failed: {e}')
            return {'error': 'Could not process this image file. Please upload a valid JPG, PNG, or WEBP image.'}

        messages = [
            {'role': 'system', 'content': REPORT_SYSTEM_PROMPT},
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': (
                            f'Please examine this medical report / scan image (Category: {report_type}, '
                            f'Filename: {filename}). Transcribe key visible values or impressions and '
                            f'explain everything clearly for the patient.'
                        ),
                    },
                    {
                        'type': 'image_url',
                        'image_url': {'url': data_url},
                    },
                ],
            },
        ]
        summary, err = _call_openrouter(messages, VISION_MODELS)

    if err and not summary:
        return {'error': err}

    return {
        'file_type': file_type,
        'extracted_text': extracted_text,
        'ai_summary': summary,
        'recommended_specialist': _detect_specialist(summary),
        'error': None,
    }
