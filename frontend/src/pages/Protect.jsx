import { useEffect, useRef, useState } from "react";import { Link, useNavigate } from "react-router-dom";
import { analyseImage, errMsg, getLogos } from "../api.js";import { useApp } from "../ctx.jsx";
import { BackendChip, Btn, Card, Dropzone, Err, Field, Finding, Gauge, Head, Tag, Verdict, useHealth } from "../ui.jsx";
const TYPES = ["image/png", "image/jpeg", "image/webp"], MAX = 5 * 1024 * 1024;

// Progress text is driven by elapsed time only, so it never claims a stage the server has not reported.
const stageText = (s) => s < 3 ? "Uploading and checking the image…" : s < 15 ? "Reading text (OCR) and comparing logos…" : s < 60 ? "Still working. The first request after idle can be slow while the server wakes up." : "This is taking unusually long. You can cancel and try again, or use a smaller image.";

const LOGO_TONE = { match: "bg-green-500/20 text-green-300", altered: "bg-amber-500/20 text-amber-300", possible: "bg-amber-500/20 text-amber-300", not_found: "bg-slate-500/30 text-slate-200", error: "bg-red-500/20 text-red-300" };

export default function Protect() {
  const { setLast } = useApp(), nav = useNavigate(), { h, state } = useHealth();
  const [file, setFile] = useState(null), [url, setUrl] = useState(""), [info, setInfo] = useState(""), [dim, setDim] = useState(null), [e, setE] = useState(""), [busy, setBusy] = useState(false), [res, setRes] = useState(null);
  const [ad, setAd] = useState(""), [aw, setAw] = useState(""), [secs, setSecs] = useState(0), [nLogos, setNLogos] = useState(null);
  const ctl = useRef(null), resRef = useRef(null);
  useEffect(() => { getLogos().then((l) => setNLogos(l.length)).catch(() => setNLogos(null)); }, []);
  useEffect(() => { if (!busy) return; setSecs(0); const t = setInterval(() => setSecs((s) => s + 1), 1000); return () => clearInterval(t); }, [busy]);
  useEffect(() => () => { ctl.current?.abort(); }, []);
  useEffect(() => { if (res) resRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, [res]);

  function pick(f) {
    setE(""); setRes(null); if (!f) return;
    if (!TYPES.includes(f.type)) return setE("Only PNG, JPEG or WebP images are accepted.");
    if (f.size > MAX) return setE("Image must be 5 MB or smaller.");
    const u = URL.createObjectURL(f), im = new Image();
    im.onload = () => { setFile(f); setUrl((old) => { old && URL.revokeObjectURL(old); return u; }); setDim([im.naturalWidth, im.naturalHeight]); setInfo(`${f.name} · ${im.naturalWidth}×${im.naturalHeight}px · ${(f.size / 1024).toFixed(1)} KB`); };
    im.onerror = () => setE("This file could not be opened as an image.");
    im.src = u;
  }
  async function run() {
    setE(""); setRes(null); if (!file) return setE("Choose an image first.");
    ctl.current = new AbortController(); setBusy(true);
    try { const r = await analyseImage(file, ad, aw, { signal: ctl.current.signal }); setRes(r); setLast(r); }
    catch (x) { setE(errMsg(x)); }
    finally { setBusy(false); ctl.current = null; }   // always runs, so the page can never stay in the loading state
  }
  const cancel = () => ctl.current?.abort();
  const v = res?.vision?.observations, lg = res?.logo;
  const best = lg?.matches?.[0];
  const logoBox = lg?.matches?.filter((m) => m.bbox && dim)[0];

  return <><Head t="Protect · Visual Brand Checker" s="Upload a suspicious promotional image. Text is read with OCR, logos are compared with your registered reference logos, and the results are checked against your saved Brand DNA and campaign values." />
    <div className="mb-4"><BackendChip state={state} h={h} /></div>
    <Err m={e} />
    {nLogos === 0 && <Card className="border-amber-500/40"><p className="text-sm text-mu"><b className="text-amber-300">No reference logos registered.</b> Logos in uploaded images cannot be compared yet. <Link className="text-sky-300 underline" to="/brand">Add your official logo on the Brand DNA page</Link>. You can also compare typed values on <Link className="text-sky-300 underline" to="/campaign">Campaign DNA Comparison</Link>.</p></Card>}
    <Card>
      <Dropzone disabled={busy} accept={TYPES.join(",")} label="Choose a PNG, JPEG or WebP image (max 5 MB)" onFile={pick} />
      {url ? <div className="mt-4"><div className="relative inline-block max-w-full"><img src={url} alt="Uploaded preview" className="block max-h-80 max-w-full rounded-xl" />
        {logoBox && <div title={`${logoBox.name}: ${logoBox.label}`} className="pointer-events-none absolute rounded-md border-2 border-green-400 shadow-[0_0_0_1px_rgba(0,0,0,.6)]" style={{ left: `${(logoBox.bbox[0] / dim[0]) * 100}%`, top: `${(logoBox.bbox[1] / dim[1]) * 100}%`, width: `${(logoBox.bbox[2] / dim[0]) * 100}%`, height: `${(logoBox.bbox[3] / dim[1]) * 100}%` }} />}</div>
        <p className="mt-2 text-sm text-mu">{info}</p></div> : <p className="mt-3 text-center text-sm text-mu">No image selected yet.</p>}
      <div className="mt-4 grid gap-x-4 sm:grid-cols-2"><Field label="Approved discount (optional, e.g. 20%)" value={ad} onChange={(x) => setAd(x.target.value)} disabled={busy} /><Field label="Approved website (optional, e.g. nova.com)" value={aw} onChange={(x) => setAw(x.target.value)} disabled={busy} /></div>
      <div className="flex flex-wrap items-center gap-2"><Btn busy={busy} disabled={!file} onClick={run}>{busy ? `Analysing… ${secs}s` : "Analyse image"}</Btn>{busy && <Btn v="g" onClick={cancel}>Cancel</Btn>}</div>
      {busy && <div role="status" aria-live="polite" className="mt-3 rounded-xl border border-line bg-[#0a1130] p-3 text-sm text-mu"><div className="mb-2 h-1.5 overflow-hidden rounded-full bg-[#1a2250]"><div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-brand to-sky2" /></div>{stageText(secs)}</div>}
      {!busy && e && file && <Btn v="g" className="mt-3" onClick={run}>Try again</Btn>}
    </Card>
    {res && <div ref={resRef}>
      <Verdict findings={res.findings} extra={res.limitations?.[0]} />
      <Card><div className="flex flex-wrap gap-2"><Tag>Mode: {res.mode}</Tag><Tag c="bg-slate-500/30 text-slate-200">{res.findings.length} finding(s)</Tag></div>
        {res.warnings?.map((w, i) => <p key={i} className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-sm text-amber-200">⚠ {w}</p>)}</Card>
      <Card><h2 className="mb-2 font-bold">Logo recognition</h2>
        {!lg || lg.status === "no_reference_logos" ? <p className="text-sm text-mu">No reference logos are registered, so no logo comparison was made. <Link className="text-sky-300 underline" to="/brand">Add one on the Brand DNA page.</Link></p>
          : <>
            <p className="mb-3 text-sm text-slate-200">{lg.status === "found" ? "A registered logo was found in this image." : lg.status === "possible" ? "A logo similar to a registered one was found, but it is not a confident match. Please verify by eye." : lg.status === "image_too_plain" ? "This image has too little visual detail for logo matching." : "No registered logo was found in this image."}
              <span className="text-mu"> Checked against {lg.references_checked} reference logo(s). Only your registered logos can be recognised.</span></p>
            <div className="grid gap-3 sm:grid-cols-2">{lg.matches.map((m) => <div key={m.id} className="rounded-xl border border-line bg-[#0a1130] p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2"><b>{m.name}</b><Tag c={LOGO_TONE[m.status]}>{m.label}</Tag></div>
              {m.status !== "not_found" && m.status !== "error" ? <><Gauge label="Structural similarity" value={m.structural_score} hint={m.method === "features" ? `${m.inliers} matching keypoints verified geometrically` : "Shape correlation (small or flat logo)"} />
                <Gauge label="Colour similarity" value={m.colour_similarity} hint={m.colour_similarity == null ? "Black/white logo: colour not compared" : undefined} />
                {m.reasons?.map((r, i) => <p key={i} className="mt-1 text-xs text-mu">{r}</p>)}</> : <p className="text-xs text-mu">{m.status === "error" ? "Comparison failed for this logo." : "No evidence of this logo in the image."}</p>}</div>)}</div>
            {best?.bbox && <p className="mt-3 text-xs text-mu">The best match is outlined on the preview above.</p>}</>}</Card>
      <Card><h2 className="mb-2 font-bold">Extracted text (OCR)</h2>
        {res.extracted_text ? <pre className="whitespace-pre-wrap rounded-xl bg-[#0a1130] p-3 text-sm">{res.extracted_text}</pre> : <p className="text-sm text-mu">No readable text found.</p>}
        <div className="mt-3 flex flex-wrap gap-2 text-sm"><span className="text-mu">Detected discounts:</span>{res.details.discounts.length ? res.details.discounts.map((d) => <Tag key={d}>{d}%</Tag>) : <span className="text-mu">none</span>}
          <span className="ml-3 text-mu">Detected websites:</span>{res.details.urls.length ? res.details.urls.map((d) => <Tag key={d}>{d}</Tag>) : <span className="text-mu">none</span>}</div></Card>
      <Card><h2 className="mb-2 font-bold">Gemini Vision observations</h2>
        {v ? <div className="space-y-1 text-sm text-mu">{res.vision.summary && <p className="text-slate-100">{res.vision.summary}</p>}
          {[["Logos", v.logos], ["Colours", v.colours], ["Promotional elements", v.promotional_elements]].map(([k, a]) => <p key={k}><b className="text-slate-100">{k}:</b> {a?.length ? a.join(", ") : "none reported"}</p>)}</div> : <p className="text-sm text-mu">{res.vision.note}</p>}</Card>
      <h2 className="mb-2 font-bold">Findings</h2>
      {res.findings.length ? res.findings.map((f, i) => <Finding key={i} f={f} />) : <Card className="text-green-300">✓ No inconsistencies found with the available checks.</Card>}
      <Card><p className="mb-3 text-sm text-mu">Recommendation: treat findings as alerts for human verification, not proof of wrongdoing.</p><Btn v="wa" onClick={() => nav("/results")}>Review &amp; decide</Btn></Card></div>}</>;
}
