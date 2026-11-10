# BrandGuard AI: Round 3 Implementation Report

Built on top of the Round 2 ZIP. Nothing was rebuilt. Stack unchanged: FastAPI + React/Vite/Tailwind + Firestore (optional) + Render + Vercel.

## 0. Read this first: honest status

| Item | Status |
|---|---|
| Backend automated tests | **28 passed** (6 original + 22 new), Python 3.12, real RapidOCR, real OpenCV |
| Frontend production build | **Passes** (`npm run build`) |
| Real HTTP run (uvicorn + curl): health, CORS preflight, logo upload, OCR + logo analysis, 400/413 errors, logging | **Verified locally** |
| Logo recognition accuracy | Verified on **synthetic** logos/scenes only. **Not yet validated on your real logos** |
| Render deployment | **NOT verified.** I have no access to your Render account. Fixes are in place; follow section 6 and the checks there |
| Vercel deployment | **NOT verified** (same reason) |
| Live Gemini / live Firestore | **NOT verified** (need your credentials) |
| Browser click-through of the UI, real phones | **NOT verified** (no browser in my environment). Only build + API round trips were verified |
| Login / authentication | **Does not exist in the Round 2 ZIP.** Nothing was added or broken. Not part of the regression test |

## 1. Round 3 improvements completed

### Improvement 1: Brand logo recognition (new: Round 2 had none)
- **Brand DNA page → "Reference logos"**: upload / list / delete up to 10 official logos (stored via the existing `Store`: Firestore or in-memory).
- **Protect**: every image analysis now also searches the image for each registered logo (`backend/app/logo.py`).
- Method (all computed from pixels, nothing hardcoded or random):
  1. AKAZE feature matching + ratio test + RANSAC homography → inlier count and a bounding box (handles size, position, rotation, blur, JPEG noise).
  2. Grayscale multi-scale template fallback for small/flat logos (size and position only, **not rotation**). Requires colour corroboration; never reported as "altered".
  3. Hue/saturation colour comparison inside the located region (skipped for black/white logos, and the UI says so).
- Verdicts: **Found**, **Possible/altered** (becomes a Medium finding for human review), **Not found**, **Too plain**, or **No reference logos** (clearly stated).
- UI: per-logo score bars, plain-language summary, and the located logo outlined on the image preview.
- Calibration results (synthetic, AKAZE, 1200×700 ad background, 3 references registered):

| Scenario | Result |
|---|---|
| Logo 0.9× / 0.3× / 0.18× size | Found (feature / template / template) |
| Rotated 25° and 90° | Found (23 and 24 inliers) |
| Blur + JPEG q40 | Found (15 inliers) |
| Noise + JPEG q25 | Found (26 inliers) |
| Same logo, recoloured | **Altered** (32 inliers, colour similarity 0%) |
| A different registered logo only | Other logo found; Nova **not found** |
| Flat red/white logo (few keypoints) | **Possible** only (correlation 0.76) |
| Background with no logo | **Not found** |
| Plain white image | **Too plain** |

- Bug found and fixed during calibration: my first template fallback (edge maps) gave false positives on logo-free images. It was replaced and the table above is from the fixed version.

### Improvement 2: OCR deployment reliability
Causes identified (evidence in brackets) and what was changed:

| Cause | Evidence | Fix |
|---|---|---|
| Python version: `rapidocr-onnxruntime` is `Requires-Python <3.13`; Render's default is 3.13+ for new services | Package metadata; Render docs | `backend/.python-version` = 3.12 and `PYTHON_VERSION` in `render.yaml` |
| Unpinned dependencies; OpenCV 5 removed AKAZE | Observed: fresh install got OpenCV 5.0 | Pinned tested versions; `opencv-python<5`; ORB fallback in code |
| Memory spikes, no pixel cap | Measured peak RSS 504 → 622 → 836 MB as image size grew; an 8000×6000 PNG (258 KB) was decoded unchecked | 25 MP cap (HTTP 413), downscale to 1280 px before OCR, pad extreme banners, single-flight lock. **Measured after: ~355 MB worst case (banner), ~300 MB typical** |
| Startup crash if Firestore credentials path is wrong (`.env.example` shipped `./serviceAccount.json`) | Code inspection (`Store()` raised at import) | Logged fallback to in-memory; shown on `/api/health` and Settings |
| Real errors hidden: any import failure reported as "not installed" | Code inspection | Real exception type/message returned and logged |
| Browser shows "Network Error" instead of the real error | A raw 500/502 carries no CORS headers | Image endpoint converts unexpected errors to JSON `HTTPException`; frontend explains 502/503/504, timeouts, CORS |
| No logging | Code inspection | `logging` throughout (OCR timing, logo timing, failures) |
| Infinite loading | 150 s timeout, no cancel, static label | 120 s hard timeout, Cancel button, elapsed timer, staged messages, Try again; `finally` always clears loading |
| Missing deploy files | Inspection | `render.yaml`, `frontend/vercel.json` (SPA rewrite), `requirements-dev.txt` |

API compatibility: all existing endpoints and response fields are unchanged. New fields only: `logo` in the image response; `ocr_installed`, `ocr_loaded`, `logo_matching`, `storage_error`, `max_image_mb` in health. New endpoints: `GET/POST /api/brand/{id}/logos`, `DELETE /api/brand/{id}/logos/{logo_id}`.

**I am not claiming Render is fixed.** The code and configuration now remove every cause I could identify, but only a deploy can confirm it (section 6, step 4).

### Improvement 3: UI/UX
Branding, palette, layout and navigation kept. Changes:
- **Protect**: drag-and-drop upload, preview, file info, disabled states, staged progress + elapsed timer, Cancel, Try again, backend status chip (also wakes a sleeping Render service), result summary ("Needs attention / Review recommended / No issues found" with severity counts), logo card with score bars, logo outline on the preview, auto-scroll to results.
- **Dashboard**: quick-action cards, skeleton loading, error + Retry, in-memory storage warning.
- **Brand DNA**: reference logo manager (thumbnails, delete with confirmation, validation messages, empty state).
- **Results**: the same plain-language summary on top.
- **Settings**: OCR / logo matching status and Firestore fallback warning.
- **App/CSS**: skip link, nav landmarks, visible keyboard focus, larger touch targets on phones, 16 px inputs (no iOS zoom), reduced-motion support, line-height.
- Honesty rules kept: the UI never says a logo is "authentic" or "fake"; it reports what matched.

## 2. Files

**Modified (16):** `README.md`, `backend/.env.example`, `backend/requirements.txt`, `backend/app/main.py`, `backend/app/vision.py`, `backend/app/store.py`, `frontend/.env.example`, `frontend/src/App.jsx`, `api.js`, `index.css`, `ui.jsx` (all existing exports kept), `pages/BrandDNA.jsx`, `pages/Dashboard.jsx`, `pages/Protect.jsx`, `pages/Results.jsx`, `pages/Settings.jsx`.

**New (8):** `backend/app/logo.py`, `backend/.python-version`, `backend/requirements-dev.txt`, `render.yaml`, `frontend/vercel.json`, `tests/test_logo.py`, `tests/_synthetic.py`, `ROUND3_REPORT.md`.

**Unchanged:** `checks.py`, `ai.py`, `Prevent.jsx`, `Campaign.jsx`, `History.jsx`, `ctx.jsx`, `main.jsx`, `vite.config.js`, `package.json` + lockfile, `firestore.rules`, `tests/test_api.py`, `tests/test_image.py`.

**New dependencies: none.** `numpy`, `opencv-python` and `onnxruntime` were already installed transitively by `rapidocr-onnxruntime`; they are now listed and pinned explicitly because the logo module imports them directly. `pytest` moved to `requirements-dev.txt`.

## 3. Local setup
Backend (Python **3.11 or 3.12**):
```
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
copy .env.example .env                 # optional: add GEMINI_API_KEY
uvicorn app.main:app --reload
```
Frontend: `cd frontend && npm install && npm run dev` → http://localhost:5173

## 4. Backend testing
`python -m pytest tests -q` from the project root → expect **28 passed**. Tests skip OCR cases only if the OCR library is unavailable.
Manual: open http://127.0.0.1:8000/api/health (expect `ocr_installed: true`, `logo_matching: true`), then http://127.0.0.1:8000/docs.

## 5. Frontend testing
`cd frontend && npm run build` (verified). Then follow the checklist in section 8 in a browser.

## 6. Render deployment (backend)
1. Push the project to GitHub (`.env` and service-account files are git-ignored).
2. Render → **New → Blueprint** → select the repo (uses `render.yaml`). *Or* New → Web Service with: Root Directory `backend`; Build `pip install -r requirements.txt`; Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; Health Check Path `/api/health`.
3. Environment tab: `PYTHON_VERSION=3.12.8`; `GEMINI_API_KEY` (your key, entered in the dashboard only); `CORS_ORIGINS=https://<your-vercel-domain>` (no trailing slash; comma-separate several). Optional Firestore: add a **Secret File** `serviceAccount.json` and set `FIREBASE_CREDENTIALS=/etc/secrets/serviceAccount.json`.
4. **Verify the OCR fix on Render (not done by me):**
   - Open `https://<service>.onrender.com/api/health` → `ocr_installed` must be `true`. If the build fails with a "no matching distribution" error for rapidocr, `PYTHON_VERSION` is not applied.
   - Upload a test image via the site; in Render **Logs** you should see `Loading OCR models` then `OCR ok`.
   - Watch Render **Metrics → Memory** during an upload. If the instance restarts (OOM), lower `OCR_MAX_SIDE` (try 960) or move to a larger instance. I measured ~300–355 MB peak locally, but Render's real overhead may differ, and the free tier's 512 MB is tight.
5. Free instances sleep after idle time; the first request can take about a minute. The UI now says so and pre-warms with a health ping.

## 7. Vercel deployment (frontend)
1. Vercel → New Project → import repo → **Root Directory `frontend`** (framework Vite, build `npm run build`, output `dist`).
2. Environment variable `VITE_API_URL=https://<service>.onrender.com` (no trailing slash). It is baked in at build time, so **redeploy after changing it**.
3. Copy the final Vercel URL into Render's `CORS_ORIGINS` and redeploy the backend. Preview deployment URLs differ per deploy and are blocked unless listed.
4. `vercel.json` makes refreshing a deep link such as `/protect` work.

## 8. Regression checklist
Mark each ✅ / ❌ yourself; items marked (V) I verified, (U) are unverified.

**Existing features**
- [ ] Login: **N/A, none existed in Round 2**
- [ ] Dashboard loads stats, shows skeleton then numbers; offline backend shows error + Retry (U in browser)
- [ ] Brand DNA: load sample → Save → reload page → values persist (API V, UI U)
- [ ] Prevent: Example content → Analyse → 3 findings (V by test_api)
- [ ] Results: approve/reject/request changes/escalate recorded; History shows it (V by API test)
- [ ] Campaign DNA: defaults give Discount mismatch + Unapproved website (V)
- [ ] Review History table renders (U in browser)
- [ ] Settings: Test connection shows storage, Gemini, OCR, logo matching (U in browser)
- [ ] Refresh on `/protect` works on Vercel (U)

**Image upload / OCR**
- [ ] PNG, JPEG, WebP accepted; GIF/txt rejected with message (V backend, U UI)
- [ ] File over 5 MB rejected; image over 25 MP rejected with HTTP 413 (V)
- [ ] Ad with "80% OFF nova-deals.xyz" → discount and URL detected, mismatch findings (V)
- [ ] Image with no readable text and no logos → clear error, not fake results (V)
- [ ] Wide banner (e.g. 1500×300) works (V)
- [ ] Cancel button stops the request; loading never exceeds 120 s (U in browser)
- [ ] 502/timeout shows the explanatory message (U; simulate by stopping the backend)

**Logo recognition**
- [ ] Add reference logo → thumbnail appears; delete asks for confirmation (API V, UI U)
- [ ] Upload ad containing the logo → "Found", outline drawn on preview (API V, overlay U)
- [ ] Ad without the logo → "Not found" (V)
- [ ] Recoloured / modified logo → "possible/altered" finding (V)
- [ ] No reference logos → clear "not compared" message (V)
- [ ] **With your real logos and real ads**: check for false positives/negatives (U; required)

**AI analysis**
- [ ] Without `GEMINI_API_KEY`: modes say rules-only / no vision (V)
- [ ] With key: Gemini findings appear and are tagged "Gemini" (U)

**Responsive / accessibility**
- [ ] 360 px phone: nav scrolls horizontally, no sideways page scroll, buttons ≥44 px (U)
- [ ] Keyboard: Tab to upload zone, Enter opens picker, focus ring visible (U)

**Deployment**
- [ ] `/api/health` on Render shows `ocr_installed: true` (U)
- [ ] CORS: site on Vercel can call Render (U)
- [ ] Render memory stays under the limit during an upload (U)

## 9. Remaining limitations
- Logo recognition only finds **registered** logos; it cannot detect unknown logos or judge authenticity beyond similarity to the reference. A generic logo-detector model was not used because of memory limits on small hosts.
- Thresholds were calibrated on synthetic logos. Very small, heavily cropped, or low-detail logos may be reported as "possible" or missed; logos on coloured backgrounds that differ from the reference's white background score lower. Template fallback does not handle rotation.
- OCR can misread characters (e.g. `80%` read as `8O%`; handled for discounts) and may glue words together. A human must verify.
- Render's free tier sleeps, and memory headroom is thin. A larger instance is the reliable fix if restarts persist.
- In-memory storage (no Firestore) loses brands, logos and history on restart.
- No authentication exists; anyone with the URL can use the API. Add auth before real use.
- Gemini and Firestore paths remain untested live.
