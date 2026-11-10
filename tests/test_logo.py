import io, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "backend")); sys.path.insert(0, str(pathlib.Path(__file__).parent))
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app import logo, vision
from _synthetic import logo_nova, logo_zeta, logo_flat, ad_bg, place, ref_entry

c = TestClient(app)
NOVA, ZETA = ref_entry(logo_nova(), "nova", "Nova"), ref_entry(logo_zeta(), "zeta", "Zeta")
BG = ad_bg()
def top(r): return r["matches"][0]
def png_bytes(im):
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

def test_no_reference_logos_is_reported_not_faked():
    r = logo.compare_logos(place(BG, logo_nova(), .9, (500, 250)), [])
    assert r["status"] == "no_reference_logos" and r["matches"] == []

@pytest.mark.parametrize("kw", [dict(scale=.9, pos=(500, 250)), dict(scale=.6, pos=(600, 300), rot=25), dict(scale=.6, pos=(600, 300), rot=90),
                                dict(scale=.6, pos=(600, 300), blur=1.5, jpeg=40), dict(scale=.7, pos=(600, 300), noise=12, jpeg=25), dict(scale=.3, pos=(900, 500))])
def test_logo_found_across_size_position_rotation_quality(kw):
    img = place(BG, logo_nova(), kw.pop("scale"), kw.pop("pos"), **kw)
    r = logo.compare_logos(img, [NOVA, ZETA])
    assert r["status"] == "found" and top(r)["id"] == "nova" and top(r)["status"] == "match"
    x, y, w, h = top(r)["bbox"]; assert w > 20 and h > 20  # located, not just detected
    assert [m for m in r["matches"] if m["id"] == "zeta"][0]["status"] == "not_found"

def test_bbox_is_near_true_position():
    img = place(BG, logo_nova(), .6, (600, 300)); x, y, w, h = top(logo.compare_logos(img, [NOVA]))["bbox"]
    assert abs(x - 600) < 60 and abs(y - 300) < 60 and abs(w - 180) < 60

def test_other_brand_logo_is_not_reported_as_match():
    r = logo.compare_logos(place(BG, logo_zeta(), .7, (600, 300)), [NOVA])
    assert r["status"] == "not_found" and top(r)["structural_score"] == 0.0

def test_image_without_any_logo_is_not_found():
    r = logo.compare_logos(png_bytes(BG), [NOVA, ZETA])
    assert r["status"] == "not_found"

def test_plain_image_is_reported_as_too_plain():
    assert logo.compare_logos(png_bytes(Image.new("RGB", (1200, 700), "white")), [NOVA])["status"] == "image_too_plain"

def test_recoloured_logo_is_flagged_not_matched():
    img = place(BG, logo_nova(hue=("#d81f1f", "#33cc66")), .7, (600, 300))
    m = top(logo.compare_logos(img, [NOVA]))
    assert m["status"] == "altered" and m["colour_similarity"] < .5

def test_corrupt_image_does_not_raise():
    r = logo.compare_logos(b"garbage", [NOVA]); assert r["error"] and r["status"] == "not_found"

def test_prepare_reference_shrinks_and_flattens_transparency():
    big = Image.new("RGBA", (900, 600), (0, 0, 0, 0)); big.paste((200, 0, 0, 255), (100, 100, 800, 500))
    png, w, h = logo.prepare_reference(png_bytes(big)); assert max(w, h) == logo.REF_MAX_SIDE
    assert Image.open(io.BytesIO(png)).mode == "RGB"
    with pytest.raises(ValueError): logo.prepare_reference(png_bytes(Image.new("RGB", (10, 10))))

# ---- API level ----
def upload_logo(brand, im, name="Nova"): return c.post(f"/api/brand/{brand}/logos", files={"file": ("logo.png", png_bytes(im), "image/png")}, data={"name": name})

def test_logo_api_flow_and_protect_integration(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    b = "logo-test"; c.put(f"/api/brand/{b}", json=dict(brand_name="Nova Electronics"))
    r = upload_logo(b, logo_nova()); assert r.status_code == 200 and r.json()["thumbnail"].startswith("data:image/png;base64,")
    assert len(c.get(f"/api/brand/{b}/logos").json()) == 1
    ad = png_bytes(Image.open(io.BytesIO(place(BG, logo_nova(), .6, (600, 300)))))
    res = c.post("/api/protect/analyse-image", files={"file": ("ad.png", ad, "image/png")}, data={"brand_id": b}).json()
    assert res["logo"]["status"] == "found" and res["logo"]["matches"][0]["name"] == "Nova"
    assert not any(f["category"] == "Possible altered or lookalike logo" for f in res["findings"])
    # recoloured copy -> a finding for human review
    bad = png_bytes(Image.open(io.BytesIO(place(BG, logo_nova(hue=("#d81f1f", "#33cc66")), .7, (600, 300)))))
    res = c.post("/api/protect/analyse-image", files={"file": ("ad.png", bad, "image/png")}, data={"brand_id": b}).json()
    assert any(f["category"] == "Possible altered or lookalike logo" and f["source"] == "logo" for f in res["findings"])
    lid = c.get(f"/api/brand/{b}/logos").json()[0]["id"]
    assert c.delete(f"/api/brand/{b}/logos/{lid}").status_code == 200 and c.get(f"/api/brand/{b}/logos").json() == []
    assert c.delete(f"/api/brand/{b}/logos/{lid}").status_code == 404

def test_logo_upload_rejects_non_images_and_limits():
    assert upload_logo("x", Image.new("RGB", (5, 5))).status_code == 400  # too small
    assert c.post("/api/brand/x/logos", files={"file": ("a.png", b"nope", "image/png")}).status_code == 400
    for _ in range(logo.MAX_REFERENCES): assert upload_logo("full", logo_nova()).status_code == 200
    assert upload_logo("full", logo_nova()).status_code == 409

def test_image_without_text_but_with_references_returns_result_not_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    b = "logo-notext"; upload_logo(b, logo_nova())
    r = c.post("/api/protect/analyse-image", files={"file": ("a.png", png_bytes(BG.crop((0, 300, 1200, 700))), "image/png")}, data={"brand_id": b})
    assert r.status_code == 200 and r.json()["logo"]["status"] in ("not_found", "image_too_plain")

# ---- OCR reliability / deployment hardening ----
def test_oversized_pixel_count_is_rejected_before_decoding():
    r = c.post("/api/protect/analyse-image", files={"file": ("big.png", png_bytes(Image.new("RGB", (8000, 6000), "white")), "image/png")})
    assert r.status_code == 413 and "too large" in r.json()["detail"]

def test_health_reports_ocr_and_storage_fields():
    h = c.get("/api/health").json()
    assert h["ok"] and {"ocr_installed", "ocr_loaded", "logo_matching", "storage", "storage_error", "max_image_mb"} <= set(h)

def test_bad_firebase_path_falls_back_instead_of_crashing(monkeypatch):
    from app.store import Store
    monkeypatch.setenv("FIREBASE_CREDENTIALS", "./does-not-exist.json")
    s = Store(); assert s.mode == "in-memory" and "not found" in s.init_error
    s.put("a", "1", {"x": 1}); assert s.get("a", "1") == {"x": 1}; s.delete("a", "1"); assert s.get("a", "1") is None

def test_unexpected_crash_returns_json_500_not_bare_error(monkeypatch):
    monkeypatch.setattr(vision, "run_ocr", lambda d: (_ for _ in ()).throw(RuntimeError("boom")))
    r = c.post("/api/protect/analyse-image", files={"file": ("a.png", png_bytes(Image.new("RGB", (50, 50), "white")), "image/png")})
    assert r.status_code == 500 and "failed unexpectedly" in r.json()["detail"]

def test_extreme_aspect_ratio_is_padded():
    assert vision.pad_extreme_aspect(Image.new("RGB", (1500, 300))).size == (1500, 500)
    assert vision.pad_extreme_aspect(Image.new("RGB", (800, 600))).size == (800, 600)
