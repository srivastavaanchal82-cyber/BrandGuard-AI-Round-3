"""Brand logo recognition for Protect.

What this does (and does not do)
--------------------------------
It looks for the brand's *registered reference logos* inside an uploaded image and reports where they were found and how
closely they match. It cannot find logos it has never been given: there is no generic logo-detector model here, because
those models are too large for a small Render instance. Every number below is computed from the pixels; nothing is
hardcoded or random.

Method
------
1. Feature matching: AKAZE keypoints are found in the reference and in the image, matched with a ratio test, and a RANSAC
   homography is fitted. Keypoint matching is tolerant to different logo sizes, positions, rotation, blur and JPEG noise.
   The surviving "inliers" are the geometric evidence; the homography gives the bounding box of the logo in the image.
2. Template fallback: flat logos with very few keypoints are searched with multi-scale edge template matching
   (handles size and position, not rotation).
3. Colour check: hue/saturation histograms of the reference and the located region are compared (only for logos that have
   chromatic colours), which catches recoloured lookalikes.
The structural_score is  min(1, inliers / min(reference_keypoints, 40)).  Thresholds were calibrated on synthetic
transformations; validate them with your own real logos before relying on them (see README).
"""
import base64, io, logging, time
import cv2
import numpy as np
from PIL import Image

log = logging.getLogger("brandguard.logo")

REF_MAX_SIDE = 256        # stored reference size: keeps Firestore documents small
SCENE_MAX_SIDE = 1280     # search image is shrunk to this for speed and bounded memory
MAX_REFERENCES = 10
RATIO = 0.78              # Lowe ratio test
MIN_INLIERS_MATCH = 15
MIN_INLIERS_POSSIBLE = 8
MIN_REF_KEYPOINTS_FOR_FEATURES = 12
TEMPLATE_MATCH = 0.80       # grayscale correlation needed for a template-only match (coloured logo, colour agrees)
TEMPLATE_MONO_MATCH = 0.88  # stricter for black/white/grey logos, where colour cannot corroborate
TEMPLATE_POSSIBLE = 0.70
COLOUR_OK = 0.5


def _make_detector():
    """AKAZE (OpenCV 4.x: cv2.AKAZE_create). OpenCV 5.x removed it, so fall back to ORB rather than failing.
    requirements.txt pins opencv-python<5 so AKAZE is normally used. Both give binary descriptors (Hamming matching)."""
    if hasattr(cv2, "AKAZE_create"): return cv2.AKAZE_create(), "akaze"
    log.warning("cv2.AKAZE unavailable (OpenCV %s); using ORB", cv2.__version__)
    return cv2.ORB_create(nfeatures=3000), "orb"


def _pil_to_gray(im: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(im.convert("RGB")), cv2.COLOR_RGB2GRAY)


def prepare_reference(data: bytes):
    """Normalise an uploaded reference logo: composite transparency on white, shrink, re-encode as PNG.
    Returns (png_bytes, width, height). Raises ValueError with a user-facing message."""
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception:
        raise ValueError("The reference logo is not a valid image.")
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    im = im.convert("RGB")
    if min(im.size) < 24:
        raise ValueError("The reference logo is too small (minimum 24 px on the shortest side).")
    if max(im.size) > REF_MAX_SIDE:
        r = REF_MAX_SIDE / max(im.size); im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    out = io.BytesIO(); im.save(out, "PNG", optimize=True)
    return out.getvalue(), im.width, im.height


def _chromatic_hist(bgr: np.ndarray):
    """2-D hue/saturation histogram over chromatic pixels only. Returns (hist|None, chromatic_fraction)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 50)).astype(np.uint8) * 255
    frac = float(mask.mean() / 255)
    if frac < 0.05: return None, frac
    h = cv2.calcHist([hsv], [0, 1], mask, [18, 8], [0, 180, 0, 256])
    cv2.normalize(h, h, 1, 0, cv2.NORM_L1)
    return h, frac


def _colour_similarity(ref_bgr, region_bgr):
    """Return similarity 0..1, or None when the logo has no meaningful colour (black/white/grey logos)."""
    if region_bgr is None or region_bgr.size == 0: return None
    hr, _ = _chromatic_hist(ref_bgr); hq, _ = _chromatic_hist(region_bgr)
    if hr is None: return None
    if hq is None: return 0.0  # reference is coloured but the located region is not
    return round(max(0.0, float(cv2.compareHist(hr, hq, cv2.HISTCMP_INTERSECT))), 3)


def _valid_quad(quad: np.ndarray, scene_shape) -> bool:
    """Reject degenerate homographies: must be a convex, reasonably sized quadrilateral."""
    if not np.all(np.isfinite(quad)): return False
    q = quad.reshape(-1, 2).astype(np.float32)
    if not cv2.isContourConvex(q): return False
    area = cv2.contourArea(q); sh, sw = scene_shape[:2]
    return 0.0005 * sw * sh < area < 4.0 * sw * sh


def _feature_match(ref_gray, scene_gray, scene_bgr, ref_bgr, detector):
    kr, dr = detector.detectAndCompute(ref_gray, None)
    ks, ds = detector.detectAndCompute(scene_gray, None)
    info = {"ref_keypoints": len(kr or []), "scene_keypoints": len(ks or [])}
    if dr is None or ds is None or len(kr) < MIN_REF_KEYPOINTS_FOR_FEATURES or len(ks) < 8:
        return None, info
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    good = [m for m, n in (p for p in bf.knnMatch(dr, ds, k=2) if len(p) == 2) if m.distance < RATIO * n.distance]
    info["good_matches"] = len(good)
    if len(good) < 6: return {"inliers": 0, **info}, info
    src = np.float32([kr[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([ks[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if H is None or mask is None: return {"inliers": 0, **info}, info
    inliers = int(mask.sum())
    h, w = ref_gray.shape
    quad = cv2.perspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2), H)
    if not _valid_quad(quad, scene_gray.shape): return {"inliers": 0, **info}, info
    return {"inliers": inliers, "quad": quad.reshape(-1, 2), "inlier_ratio": round(inliers / len(good), 3)}, info


def _template_match(ref_gray, scene_gray):
    """Multi-scale grayscale normalised cross-correlation. Returns (score, (x,y,w,h)) or (0, None).
    Handles size and position but not rotation. Edge maps were tried first and produced false positives on busy backgrounds."""
    best, box = 0.0, None
    sh, sw = scene_gray.shape
    scene = cv2.GaussianBlur(scene_gray, (3, 3), 0)
    for s in np.geomspace(0.15, 1.6, 16):
        w, h = int(ref_gray.shape[1] * s), int(ref_gray.shape[0] * s)
        if w < 40 or h < 40 or w >= sw or h >= sh: continue
        t = cv2.GaussianBlur(cv2.resize(ref_gray, (w, h), interpolation=cv2.INTER_AREA), (3, 3), 0)
        if t.std() < 8: continue  # near-uniform template: correlation is meaningless
        res = cv2.matchTemplate(scene, t, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best: best, box = float(mx), (int(loc[0]), int(loc[1]), w, h)
    return round(best, 3), box


def _bbox_from_quad(quad, scene_shape):
    sh, sw = scene_shape[:2]
    x0, y0 = np.clip(quad.min(axis=0), 0, [sw - 1, sh - 1]); x1, y1 = np.clip(quad.max(axis=0), 0, [sw - 1, sh - 1])
    return int(x0), int(y0), int(x1 - x0), int(y1 - y0)


def _verdict(method, inliers, struct, template, colour):
    """Turn computed evidence into a label. Returns (status, label, reasons)."""
    if method == "features":
        if inliers >= MIN_INLIERS_MATCH:
            if colour is not None and colour < COLOUR_OK:
                return "altered", "Logo shape matches but colours differ", [f"{inliers} geometric inliers, but colour similarity is only {colour:.0%}."]
            return "match", "Registered logo found", [f"{inliers} keypoints agree geometrically with the reference."]
        if inliers >= MIN_INLIERS_POSSIBLE:
            return "possible", "Possible match or altered logo", [f"Only {inliers} keypoints agree (>= {MIN_INLIERS_MATCH} needed for a confident match). The logo may be small, cropped, blurred or modified."]
    if method == "template":
        # Template-only evidence has no geometric verification, so colour must corroborate it, and it is never reported as "altered":
        # a colour mismatch here more likely means the wrong region was found than that the logo was recoloured.
        if colour is None:   # monochrome logo
            if template >= TEMPLATE_MONO_MATCH:
                return "match", "Registered logo found (outline match)", [f"Correlation {template:.2f} (flat black/white logo, so only shape could be compared)."]
            if template >= TEMPLATE_POSSIBLE + 0.1:
                return "possible", "Possible match", [f"Correlation {template:.2f} is below the confident threshold {TEMPLATE_MONO_MATCH}."]
        elif colour >= COLOUR_OK:
            if template >= TEMPLATE_MATCH:
                return "match", "Registered logo found (shape and colour match)", [f"Correlation {template:.2f}, colour similarity {colour:.0%}. Small or flat logo, so template matching was used."]
            if template >= TEMPLATE_POSSIBLE:
                return "possible", "Possible match", [f"Correlation {template:.2f}, colour similarity {colour:.0%}; below the confident threshold {TEMPLATE_MATCH}."]
    return "not_found", "Not found", []


def compare_logos(image_bytes: bytes, references: list):
    """Search one image for each reference logo.

    references: [{"id","name","png_b64"}]. Returns a dict that is safe to JSON-encode:
      status: no_reference_logos | found | possible | not_found | image_too_plain
      matches: [{id,name,status,label,structural_score,colour_similarity,inliers,bbox,method,...}] sorted best first
    Never raises: failures are reported in `error`.
    """
    t0 = time.time()
    out = {"status": "no_reference_logos", "references_checked": 0, "matches": [], "error": None}
    if not references: return out
    try:
        arr = np.frombuffer(image_bytes, np.uint8)
        scene_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if scene_bgr is None:  # e.g. WebP on a build without codec: fall back to PIL
            scene_bgr = cv2.cvtColor(np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB")), cv2.COLOR_RGB2BGR)
        H0, W0 = scene_bgr.shape[:2]
        scale = min(1.0, SCENE_MAX_SIDE / max(H0, W0))
        if scale < 1.0: scene_bgr = cv2.resize(scene_bgr, (round(W0 * scale), round(H0 * scale)), interpolation=cv2.INTER_AREA)
        scene_gray = cv2.cvtColor(scene_bgr, cv2.COLOR_BGR2GRAY)
        detector, detector_name = _make_detector()
        out["detector"] = detector_name
        out["image_size"] = [W0, H0]
    except Exception as e:
        log.exception("Logo comparison could not read the image")
        out.update(status="not_found", seconds=round(time.time() - t0, 2), error=f"Logo comparison failed ({type(e).__name__}).")
        return out

    results, plain = [], 0
    for ref in references[:MAX_REFERENCES]:
        try:
            ref_bgr = cv2.cvtColor(np.array(Image.open(io.BytesIO(base64.b64decode(ref["png_b64"]))).convert("RGB")), cv2.COLOR_RGB2BGR)
            ref_gray = cv2.cvtColor(ref_bgr, cv2.COLOR_BGR2GRAY)
            feat, info = _feature_match(ref_gray, scene_gray, scene_bgr, ref_bgr, detector)
            method, inliers, quad, template, tbox = "features", 0, None, 0.0, None
            if feat is not None:
                inliers, quad = feat.get("inliers", 0), feat.get("quad")
            if feat is None or inliers < MIN_INLIERS_POSSIBLE:
                # Few keypoints (flat logo) or no feature evidence: try outline matching.
                template, tbox = _template_match(ref_gray, scene_gray)
                if feat is None or template >= TEMPLATE_POSSIBLE:
                    method = "template"
            if method == "features" and quad is not None: x, y, w, h = _bbox_from_quad(quad, scene_gray.shape)
            elif method == "template" and tbox: x, y, w, h = tbox
            else: x = y = w = h = 0
            region = scene_bgr[y:y + h, x:x + w] if w > 2 and h > 2 and (inliers >= MIN_INLIERS_POSSIBLE or template >= TEMPLATE_POSSIBLE) else None
            colour = _colour_similarity(ref_bgr, region)
            status, label, reasons = _verdict(method, inliers, None, template, colour)
            struct = round(min(1.0, inliers / max(1, min(info["ref_keypoints"], 40))), 3) if method == "features" else round(max(0.0, template), 3)
            raw_corr = template
            if status == "not_found": struct = 0.0  # a rejected candidate must not display as a score; raw value kept in best_template_correlation
            if info["scene_keypoints"] < 8 and status == "not_found": plain += 1
            m = {"id": ref["id"], "name": ref.get("name") or "Reference logo", "status": status, "label": label, "reasons": reasons,
                 "method": method, "structural_score": struct, "colour_similarity": colour, "inliers": inliers,
                 "ref_keypoints": info["ref_keypoints"], "scene_keypoints": info["scene_keypoints"], "best_template_correlation": raw_corr}
            if status != "not_found":
                # bbox in ORIGINAL image pixels, so the frontend can draw it over the preview
                m["bbox"] = [round(v / scale) for v in (x, y, w, h)]
            results.append(m)
        except Exception as e:
            log.exception("Logo comparison failed for reference %s", ref.get("id"))
            results.append({"id": ref.get("id"), "name": ref.get("name"), "status": "error", "label": f"Comparison failed ({type(e).__name__})",
                            "reasons": [], "method": None, "structural_score": 0, "colour_similarity": None, "inliers": 0})
    rank = {"match": 0, "altered": 1, "possible": 2, "not_found": 3, "error": 4}
    results.sort(key=lambda m: (rank[m["status"]], -m["structural_score"]))
    out["matches"], out["references_checked"] = results, len(results)
    best = results[0]["status"] if results else "not_found"
    out["status"] = {"match": "found", "altered": "possible", "possible": "possible"}.get(best, "image_too_plain" if plain == len(results) and plain else "not_found")
    out["seconds"] = round(time.time() - t0, 2)
    log.info("Logo comparison: status=%s refs=%d %.2fs", out["status"], len(results), out["seconds"])
    return out
