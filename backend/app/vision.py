"""Image analysis for Protect: validation, OCR (RapidOCR), detail extraction, Gemini Vision.
Nothing here invents findings: every finding comes from OCR text, a comparison with saved values, or the Gemini response."""
import base64, importlib.util, io, json, logging, os, re, threading, time
import httpx
from PIL import Image, ImageOps
from .checks import _host

log = logging.getLogger("brandguard.vision")
MAX_BYTES = 5 * 1024 * 1024
# A small PNG can decode to hundreds of megapixels (decompression bomb) and exhaust RAM on small hosts, so cap pixels.
MAX_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", 25_000_000))
# Images are shrunk before OCR so memory use and latency stay bounded on a 512 MB Render instance.
OCR_MAX_SIDE = int(os.getenv("OCR_MAX_SIDE", 1280))
_ocr_lock = threading.Lock()  # one OCR run at a time: onnxruntime is memory hungry and the engine is not documented as thread-safe
MIME = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
_engine = None

def validate_image(data: bytes) -> str:
    """Return the mime type or raise ValueError with a user-facing message."""
    if not data: raise ValueError("The uploaded file is empty.")
    if len(data) > MAX_BYTES: raise ValueError("Image must be 5 MB or smaller.")
    try:
        im = Image.open(io.BytesIO(data)); fmt = im.format; size = im.size  # header only: pixels are not decoded yet
    except Exception:
        raise ValueError("The file is not a valid image.")
    if fmt not in MIME: raise ValueError("Only PNG, JPEG or WebP images are accepted.")
    if size[0] * size[1] > MAX_PIXELS: raise ValueError(f"Image dimensions are too large ({size[0]}x{size[1]}). Maximum is {MAX_PIXELS // 1_000_000} megapixels.")
    try: im.verify()
    except Exception: raise ValueError("The file is not a valid image.")
    return MIME[fmt]

def load_rgb(data: bytes, max_side: int = 0) -> Image.Image:
    """Decode to RGB, honour EXIF rotation (phone photos) and optionally shrink so the longest side is <= max_side."""
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    im = im.convert("RGB")
    if max_side and max(im.size) > max_side:
        r = max_side / max(im.size); im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    return im

def pad_extreme_aspect(im: Image.Image, max_ratio: float = 3.0) -> Image.Image:
    """Banners (e.g. 1500x300) make RapidOCR upscale the short side hugely, which spikes RAM. Pad with white to <= max_ratio:1.
    White padding adds no text, so results are unchanged."""
    w, h = im.size
    if w / h > max_ratio: nh = round(w / max_ratio); bg = Image.new("RGB", (w, nh), "white"); bg.paste(im, (0, (nh - h) // 2)); return bg
    if h / w > max_ratio: nw = round(h / max_ratio); bg = Image.new("RGB", (nw, h), "white"); bg.paste(im, ((nw - w) // 2, 0)); return bg
    return im

def ocr_status():
    """Cheap status for /api/health. Does not load the models (that costs ~0.5 GB RAM)."""
    return {"ocr_installed": importlib.util.find_spec("rapidocr_onnxruntime") is not None, "ocr_loaded": _engine is not None}

def run_ocr(data: bytes):
    """Return (lines, error). lines = [{'text','confidence'}]. Never raises."""
    global _engine
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except Exception as e:  # ImportError, but also OSError such as a missing libGL: report the real cause
        log.error("OCR library could not be imported: %s: %s", type(e).__name__, e)
        return [], f"OCR library could not be loaded ({type(e).__name__}: {e}). Check the Python version (3.11/3.12) and installed packages."
    t0 = time.time()
    try:
        with _ocr_lock:
            if _engine is None:
                log.info("Loading OCR models (first request after start)")
                _engine = RapidOCR()
            im = pad_extreme_aspect(load_rgb(data, OCR_MAX_SIDE))
            res, _ = _engine(np.array(im)[:, :, ::-1])
        lines = [{"text": r[1], "confidence": round(float(r[2]), 3)} for r in (res or [])]
        log.info("OCR ok: %d line(s), %dx%d, %.1fs", len(lines), im.width, im.height, time.time() - t0)
        return lines, None
    except MemoryError:
        log.error("OCR ran out of memory")
        return [], "OCR ran out of memory. Try a smaller image."
    except Exception as e:
        log.exception("OCR failed")
        return [], f"OCR failed ({type(e).__name__})."

DISC = re.compile(r"(\d[\dOo]{0,2}(?:\.\d+)?)\s?%")  # OCR often reads 0 as O
URL = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/[^\s]*)?", re.I)

def extract_details(text: str):
    return {"discounts": sorted({m.group(1).replace("O", "0").replace("o", "0") for m in DISC.finditer(text)}, key=float),
            "urls": sorted({m.group(0).rstrip(".,;)").lower() for m in URL.finditer(text)})}

def gemini_vision(data: bytes, mime: str, brand: dict, ocr_text: str):
    """Return (result|None, note). result = {observations, summary, findings}."""
    key = os.getenv("GEMINI_API_KEY")
    if not key: return None, "Gemini Vision not configured (no GEMINI_API_KEY): visual analysis was not performed."
    prompt = ("You review a promotional advertisement image for brand compliance. Describe only what is actually visible. "
              "No reference logo file is available, so do NOT claim a logo is authentic or fake; you may only note visible oddities "
              "(distorted, mismatched or unusual logo/typography) as observations needing human verification. "
              "Compare the ad with the brand profile. Return JSON: {\"observations\":{\"logos\":[],\"colours\":[],\"promotional_elements\":[]},"
              "\"summary\":\"...\",\"findings\":[{\"flagged_text\":\"\",\"category\":\"\",\"severity\":\"High|Medium|Low\",\"brand_rule\":\"\","
              "\"explanation\":\"\",\"suggested_correction\":\"\",\"evidence\":\"\"}]}. Use an empty findings list if nothing is inconsistent.\n"
              f"Brand: {brand.get('brand_name') or 'unknown'} | Tone: {brand.get('tone')}\nGuidelines: {brand.get('communication_guidelines') or ''}\n"
              f"Approved domains: {brand.get('approved_domains') or ''}\nOCR text from the image: {ocr_text or '(none)'}")
    try:
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')}:generateContent",
                       headers={"x-goog-api-key": key}, timeout=60,
                       json={"contents": [{"parts": [{"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}, {"text": prompt}]}],
                             "generationConfig": {"responseMimeType": "application/json"}})
        r.raise_for_status()
        out = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        out["findings"] = [{**f, "source": "gemini"} for f in out.get("findings", []) if isinstance(f, dict) and f.get("flagged_text")]
        return out, "Gemini Vision analysis included."
    except httpx.HTTPStatusError as e:
        return None, f"Gemini Vision request was rejected (HTTP {e.response.status_code}). Check the API key and model."
    except Exception as e:
        return None, f"Gemini Vision call failed ({type(e).__name__})."

def mismatches(details, approved_discount, approved_hosts):
    """Compare extracted discounts/URLs with approved values. Returns (findings, warnings)."""
    out, warn = [], []
    nums = set(re.findall(r"\d+(?:\.\d+)?", approved_discount or ""))
    if details["discounts"] and nums:
        for d in details["discounts"]:
            if d not in nums:
                out.append(dict(flagged_text=f"{d}%", category="Discount mismatch", severity="High", brand_rule=f"Approved discount: {approved_discount}",
                                explanation=f"The image shows {d}% but the approved campaign discount is {approved_discount}.",
                                suggested_correction="Treat as a possibly manipulated offer. Requires human verification.", evidence=f"OCR text contained {d}%", source="ocr"))
    elif details["discounts"]:
        warn.append("A discount was found in the image but no approved discount is configured, so it could not be compared.")
    if details["urls"] and approved_hosts:
        for u in details["urls"]:
            h = _host(u)
            if not any(h == a or h.endswith("." + a) for a in approved_hosts):
                out.append(dict(flagged_text=u, category="Unapproved website", severity="High", brand_rule="Approved domains: " + ", ".join(approved_hosts),
                                explanation=f"{h} is not an approved domain or subdomain of one.", suggested_correction="Requires human verification. An alert is not proof of wrongdoing.",
                                evidence=f"OCR text contained {u}", source="ocr"))
    elif details["urls"]:
        warn.append("A website was found in the image but no approved domain is configured, so it could not be compared.")
    return out, warn
