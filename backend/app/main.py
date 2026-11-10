import base64, logging, os, uuid, datetime as dt
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("brandguard.api")
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, Optional
from .checks import run_checks, compare_campaign
from .ai import retrieve, gemini_findings
from .store import Store
from .checks import lines as _lines, run_checks as _run_checks, _host
from . import vision, logo

app = FastAPI(title="BrandGuard AI")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()], allow_methods=["*"], allow_headers=["*"])
db = Store()
now = lambda: dt.datetime.now(dt.timezone.utc).isoformat()

class Brand(BaseModel):
    brand_name: str = Field(min_length=1, max_length=120)
    approved_terminology: str = ""; prohibited_words: str = ""; tone: str = "Professional"
    communication_guidelines: str = ""; verified_facts: str = ""; approved_claims: str = ""
    approved_domains: str = ""; approved_campaign: str = ""
class Content(BaseModel):
    text: str = Field(min_length=1, max_length=10000); brand_id: str = "default"
class Campaign(BaseModel):
    approved_discount: str = ""; observed_discount: str = ""; approved_website: str = ""; observed_website: str = ""
class Review(BaseModel):
    analysis_id: str; decision: Literal["Approved", "Rejected", "Changes Requested", "Escalated"]
    review_type: Literal["Prevent", "Protect"] = "Prevent"; reviewer: Optional[str] = None

@app.get("/api/health")
def health():
    return {"ok": True, "storage": db.mode, "storage_error": db.init_error, "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            **vision.ocr_status(), "logo_matching": True, "max_image_mb": vision.MAX_BYTES // (1024 * 1024)}

@app.put("/api/brand/{brand_id}")
def save_brand(brand_id: str, b: Brand):
    db.put("brands", brand_id, b.model_dump()); db.put("activity_logs", uuid.uuid4().hex, {"at": now(), "event": "brand_saved", "brand_id": brand_id}); return b

@app.get("/api/brand/{brand_id}")
def get_brand(brand_id: str):
    b = db.get("brands", brand_id)
    if not b: raise HTTPException(404, "No Brand DNA saved yet")
    return b

@app.post("/api/prevent/analyse")
def analyse(c: Content):
    b = db.get("brands", c.brand_id)
    if not b: raise HTTPException(404, "Save a Brand DNA first")
    ctx = retrieve(c.text, b)
    ai, note = gemini_findings(c.text, b, ctx)
    found = run_checks(c.text, b); have = {f["flagged_text"].lower() for f in found}
    found += [f for f in ai if f["flagged_text"].lower() not in have]
    rec = {"id": uuid.uuid4().hex, "type": "Prevent", "at": now(), "text": c.text, "findings": found, "status": "Pending",
           "mode": "rules+gemini" if ai or "included" in note else "rules-only (demo)", "note": note, "retrieved_context": ctx}
    db.put("content_analyses", rec["id"], rec); return rec

@app.post("/api/protect/campaign-compare")
def campaign(c: Campaign):
    f = compare_campaign(c.approved_discount, c.observed_discount, c.approved_website, c.observed_website)
    rec = {"id": uuid.uuid4().hex, "type": "Protect", "at": now(), "inputs": c.model_dump(), "findings": f, "status": "Pending", "mode": "rule-based comparison of entered values"}
    db.put("protect_analyses", rec["id"], rec); return rec

@app.post("/api/reviews")
def review(r: Review):
    col = "content_analyses" if r.review_type == "Prevent" else "protect_analyses"
    a = db.get(col, r.analysis_id)
    if not a: raise HTTPException(404, "Unknown analysis")
    a["status"] = r.decision; db.put(col, r.analysis_id, a)
    d = {**r.model_dump(), "at": now(), "findings": a["findings"]}; db.put("review_decisions", uuid.uuid4().hex, d); return d

@app.get("/api/reviews")
def reviews(): return sorted(db.all("review_decisions"), key=lambda x: x["at"], reverse=True)

@app.get("/api/stats")
def stats():
    a = db.all("content_analyses") + db.all("protect_analyses")
    n = lambda s: sum(x["status"] == s for x in a)
    return {"total_checks": len(a), "prevent": len(db.all("content_analyses")), "protect": len(db.all("protect_analyses")),
            "issues": sum(len(x["findings"]) for x in a), "approved": n("Approved"), "pending": n("Pending"), "storage": db.mode}

@app.post("/api/protect/analyse-image")
def analyse_image(file: UploadFile = File(...), approved_discount: str = Form(""), approved_website: str = Form(""), brand_id: str = Form("default")):
    t0 = __import__("time").time()
    try:
        r = _analyse_image(file, approved_discount, approved_website, brand_id)
        log.info("analyse-image ok id=%s findings=%d mode=%s %.1fs", r["id"], len(r["findings"]), r["mode"], __import__("time").time() - t0)
        return r
    except HTTPException: raise
    except Exception:
        # HTTPException responses pass through the CORS middleware; a raw exception would not, and the browser would show a
        # misleading "Network Error". Always answer with JSON.
        log.exception("analyse-image crashed")
        raise HTTPException(500, "Image analysis failed unexpectedly on the server. Please try a smaller or different image.")

def _analyse_image(file, approved_discount, approved_website, brand_id):
    data = file.file.read(vision.MAX_BYTES + 1)
    try: mime = vision.validate_image(data)
    except ValueError as e: raise HTTPException(415 if "accepted" in str(e) else 413 if ("5 MB" in str(e) or "too large" in str(e)) else 400, str(e))
    brand = db.get("brands", brand_id) or {}
    lines, ocr_err = vision.run_ocr(data)
    text = "\n".join(l["text"] for l in lines)
    vis, vnote = vision.gemini_vision(data, mime, brand, text)
    refs = [l for l in db.all("brand_logos") if l.get("brand_id") == brand_id]
    lg = logo.compare_logos(data, refs)  # real feature/template matching against the registered reference logos; never raises
    if not text.strip() and not vis and lg["status"] in ("no_reference_logos",) :
        raise HTTPException(422, "This image could not be analysed. " + (ocr_err or "No readable text was found.") + " " + vnote)
    if not text.strip() and not vis and lg.get("error"):
        raise HTTPException(422, "This image could not be analysed. " + (ocr_err or "No readable text was found.") + " " + lg["error"])
    warnings = [m for m in (ocr_err, None if vis else vnote) if m]
    if not brand: warnings.append("No Brand DNA is saved, so brand-name and rule checks were skipped.")
    details = vision.extract_details(text)
    ad = approved_discount.strip() or (__import__("re").search(r"\d+(?:\.\d+)?\s?%", brand.get("approved_campaign", "")) or [""])[0]
    hosts = [h for h in (_host(x) for x in [approved_website] + _lines(brand.get("approved_domains", ""))) if h]
    found, w2 = vision.mismatches(details, ad, hosts); warnings += w2
    seen = {f["flagged_text"].lower() for f in found}
    if brand.get("brand_name") and text.strip():
        bl = brand["brand_name"].lower()
        for f in _run_checks(text, brand):
            ft = f["flagged_text"].lower()
            # Ads often use capitals, and URLs often contain the brand name: neither is a misspelling.
            if f["category"] == "Incorrect brand name" and (ft == bl or any(ft in u for u in details["urls"])): continue
            if f["flagged_text"].lower() not in seen: found.append({**f, "source": "ocr"}); seen.add(f["flagged_text"].lower())
        if brand["brand_name"].lower() not in text.lower() and not any(f["category"] == "Incorrect brand name" for f in found):
            found.append(dict(flagged_text=brand["brand_name"], category="Brand name not found in text", severity="Low", brand_rule=f"Brand name: {brand['brand_name']}",
                              explanation="The brand name was not found in the readable text. It may appear only inside a logo, or the ad may not use the brand name.",
                              suggested_correction="Check the logo and branding manually.", evidence="Absent from OCR text", source="ocr"))
    for m in lg["matches"]:  # only altered / possible matches become findings; a clean match or a not-found is shown in the logo card
        if m["status"] in ("altered", "possible"):
            found.append(dict(flagged_text=m["name"], category="Possible altered or lookalike logo", severity="Medium",
                              brand_rule=f"Registered reference logo: {m['name']}", explanation=m["label"] + ". " + " ".join(m["reasons"]),
                              suggested_correction="Compare the logo with the official artwork. This is an alert for human verification, not proof of forgery.",
                              evidence=f"Method: {m['method']}; structural score {m['structural_score']}; colour similarity {m['colour_similarity']}", source="logo"))
    if lg.get("error"): warnings.append(lg["error"])
    for f in (vis or {}).get("findings", []):
        if f["flagged_text"].lower() not in seen: found.append(f); seen.add(f["flagged_text"].lower())
    rec = {"id": uuid.uuid4().hex, "type": "Protect", "at": now(), "filename": file.filename, "findings": found, "status": "Pending",
           "mode": "ocr+gemini-vision" if vis else "ocr+rules (no vision)", "extracted_text": text, "ocr_lines": lines, "details": details,
           "vision": {"observations": (vis or {}).get("observations"), "summary": (vis or {}).get("summary"), "note": vnote},
           "warnings": warnings, "logo": lg,
           "limitations": (["Logo matching compares the image only with the reference logos you registered; unknown logos cannot be detected. Results are alerts for human review."]
                           if lg["status"] != "no_reference_logos" else ["No reference logos are registered (Brand DNA page), so logos were not compared."])}
    db.put("protect_analyses", rec["id"], rec); return rec


# ---- Reference logos (used by logo recognition in Protect) ----
def _logo_public(l): return {"id": l["id"], "name": l["name"], "at": l["at"], "width": l["width"], "height": l["height"], "thumbnail": "data:image/png;base64," + l["png_b64"]}

@app.get("/api/brand/{brand_id}/logos")
def list_logos(brand_id: str):
    return sorted((_logo_public(l) for l in db.all("brand_logos") if l.get("brand_id") == brand_id), key=lambda x: x["at"])

@app.post("/api/brand/{brand_id}/logos")
def add_logo(brand_id: str, file: UploadFile = File(...), name: str = Form("")):
    data = file.file.read(vision.MAX_BYTES + 1)
    try: vision.validate_image(data)
    except ValueError as e: raise HTTPException(415 if "accepted" in str(e) else 413 if ("5 MB" in str(e) or "too large" in str(e)) else 400, str(e))
    if len([1 for l in db.all("brand_logos") if l.get("brand_id") == brand_id]) >= logo.MAX_REFERENCES:
        raise HTTPException(409, f"At most {logo.MAX_REFERENCES} reference logos can be stored. Delete one first.")
    try: png, w, h = logo.prepare_reference(data)
    except ValueError as e: raise HTTPException(400, str(e))
    rec = {"id": uuid.uuid4().hex, "brand_id": brand_id, "name": (name.strip() or (file.filename or "Reference logo"))[:80], "at": now(),
           "width": w, "height": h, "png_b64": base64.b64encode(png).decode()}
    db.put("brand_logos", rec["id"], rec); log.info("reference logo added id=%s brand=%s %dx%d", rec["id"], brand_id, w, h)
    return _logo_public(rec)

@app.delete("/api/brand/{brand_id}/logos/{logo_id}")
def delete_logo(brand_id: str, logo_id: str):
    l = db.get("brand_logos", logo_id)
    if not l or l.get("brand_id") != brand_id: raise HTTPException(404, "Unknown logo")
    db.delete("brand_logos", logo_id); return {"deleted": logo_id}
