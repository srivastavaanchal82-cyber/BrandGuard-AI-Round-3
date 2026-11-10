import io, sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend"))
import pytest
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from app.main import app
from app import vision
c = TestClient(app)

def png(text=None):
    im = Image.new("RGB", (1500, 300), "white")
    if text: ImageDraw.Draw(im).text((20, 100), text, fill="black", font=ImageFont.load_default(size=48))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()
def post(data, name="ad.png", ctype="image/png", **form):
    return c.post("/api/protect/analyse-image", files={"file": (name, data, ctype)}, data=form)
needs_ocr = pytest.mark.skipif(not vision.run_ocr(png("TEST 20%"))[0], reason="OCR library unavailable")

@needs_ocr
def test_real_ocr_and_comparison(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    c.put("/api/brand/default", json=dict(brand_name="Nova Electronics", approved_domains="nova.com"))
    r = post(png("NOVA ELECTRONICS 80% OFF nova-deals.xyz"), approved_discount="20%", approved_website="nova.com").json()
    assert "80" in r["details"]["discounts"] and any("nova-deals" in u for u in r["details"]["urls"])
    cats = {f["category"] for f in r["findings"]}
    assert {"Discount mismatch", "Unapproved website"} <= cats and r["mode"] == "ocr+rules (no vision)"
    assert "Incorrect brand name" not in cats  # all-caps brand and brand-in-URL are not misspellings
    assert r["extracted_text"] and any("Gemini Vision not configured" in w for w in r["warnings"])

def test_rejects_bad_files():
    assert post(b"not an image", "x.png").status_code == 400
    gif = io.BytesIO(); Image.new("RGB", (5, 5)).save(gif, "GIF")
    assert post(gif.getvalue(), "x.gif", "image/gif").status_code == 415
    assert post(b"", "e.png").status_code == 400

@needs_ocr
def test_unreadable_image_gives_error_not_fake_results(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = post(png())
    assert r.status_code == 422 and "could not be analysed" in r.json()["detail"]

def test_gemini_response_parsing_with_mocked_http(monkeypatch):
    """Mocked HTTP: verifies request/response handling only. This is NOT a live Gemini test."""
    import json
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    class R:
        def raise_for_status(self): pass
        def json(self): return {"candidates": [{"content": {"parts": [{"text": json.dumps({"observations": {"logos": ["blue shield"], "colours": ["navy"], "promotional_elements": ["banner"]}, "summary": "ok", "findings": [{"flagged_text": "blurred logo", "category": "Visual inconsistency", "severity": "Medium", "explanation": "x", "suggested_correction": "y"}]})}]}}]}
    seen = {}
    def fake(url, headers=None, json=None, timeout=None): seen["h"], seen["body"] = headers, json; return R()
    monkeypatch.setattr(vision.httpx, "post", fake)
    out, note = vision.gemini_vision(png("hi"), "image/png", {"brand_name": "X"}, "hi")
    assert out["findings"][0]["source"] == "gemini" and out["observations"]["logos"] == ["blue shield"]
    assert seen["h"]["x-goog-api-key"] == "fake" and "inline_data" in seen["body"]["contents"][0]["parts"][0]
    monkeypatch.setattr(vision.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(vision.httpx.ConnectError("x")))
    assert vision.gemini_vision(png("hi"), "image/png", {}, "")[0] is None
