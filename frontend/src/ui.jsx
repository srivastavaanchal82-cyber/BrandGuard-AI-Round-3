import { useEffect, useRef, useState } from "react";
import { getHealth } from "./api.js";
export const Card = ({ children, className = "" }) => <div className={`mb-4 rounded-2xl border border-line bg-gradient-to-br from-[#131c42] to-card p-5 ${className}`}>{children}</div>;
export const Spin = () => <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white align-[-3px]" />;
const V = { p: "bg-gradient-to-r from-brand to-sky2", g: "border border-line bg-[#1a2250]", ok: "bg-green-600", no: "bg-red-600", wa: "bg-amber-500 !text-black" };
export const Btn = ({ busy, v = "p", className = "", children, ...p }) => (
  <button {...p} disabled={busy || p.disabled} className={`rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-px disabled:cursor-wait disabled:opacity-60 ${V[v]} ${className}`}>{busy && <Spin />}{children}</button>);
export const SEV = { High: "bg-red-500/20 text-red-300", Medium: "bg-amber-500/20 text-amber-300", Low: "bg-sky-500/20 text-sky-300" };
export const Tag = ({ c = "bg-brand/30 text-violet-200", children }) => <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${c}`}>{children}</span>;
export const Err = ({ m }) => m ? <div role="alert" className="mb-4 rounded-xl border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-200">{m}</div> : null;
export const Ok = ({ m }) => m ? <div className="mb-4 rounded-xl border border-green-500/50 bg-green-500/10 p-3 text-sm text-green-200">{m}</div> : null;
export const Head = ({ t, s }) => <div className="mb-5"><h1 className="text-2xl font-bold">{t}</h1>{s && <p className="text-sm text-mu">{s}</p>}</div>;
export const Field = ({ label, area, ...p }) => <label className="mb-3 block text-xs text-mu">{label}{area ? <textarea rows={3} className="mt-1" {...p} /> : <input className="mt-1" {...p} />}</label>;
export const Empty = ({ children }) => <Card className="text-center text-mu">{children}</Card>;
export function Finding({ f }) {
  const t = f.flagged_text ?? f.mismatch_type, sev = f.severity;
  const row = (k, v) => v ? <p className="mt-1 text-sm text-mu"><b className="text-slate-100">{k}:</b> {v}</p> : null;
  return <div className={`mb-3 rounded-xl border-l-4 bg-[#0a1130] p-4 ${sev === "High" ? "border-red-500" : sev === "Medium" ? "border-amber-500" : "border-sky-400"}`}>
    <div className="flex flex-wrap items-center gap-2"><b>“{t}”</b><Tag c={SEV[sev]}>{sev}</Tag><Tag>{f.category ?? f.mismatch_type}</Tag>{f.source && <Tag c="bg-slate-500/30 text-slate-200">{{ gemini: "Gemini", logo: "Logo match", ocr: "OCR" }[f.source] || "Rule"}</Tag>}</div>
    {row("Brand rule", f.brand_rule)}{row("Approved", f.approved)}{row("Evidence", f.evidence ?? f.extracted_evidence)}{row("Why", f.explanation)}
    {(f.suggested_correction || f.suggested_action) && <p className="mt-1 text-sm text-green-300"><b>Suggested {f.suggested_correction ? "correction" : "action"}:</b> {f.suggested_correction ?? f.suggested_action}</p>}</div>;
}

// ---- Round 3 additions (existing exports above are unchanged) ----
export const Skeleton = ({ className = "h-4 w-full" }) => <div aria-hidden className={`animate-pulse rounded-lg bg-[#1a2250] ${className}`} />;
export const Stat = ({ label, value, hint, tone = "" }) => <Card className="!mb-0"><div className="text-xs text-mu">{label}</div><div className={`mt-1 text-3xl font-bold ${tone}`}>{value}</div>{hint && <div className="mt-1 text-xs text-mu">{hint}</div>}</Card>;

/** Horizontal score bar. value is 0..1. Colour is secondary: the number is always printed too. */
export const Gauge = ({ label, value, hint }) => {
  const pct = Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100);
  return <div className="mb-2"><div className="flex justify-between text-xs text-mu"><span>{label}</span><span className="font-semibold text-slate-100">{value == null ? "n/a" : pct + "%"}</span></div>
    <div className="mt-1 h-2 overflow-hidden rounded-full bg-[#1a2250]" role="img" aria-label={`${label}: ${value == null ? "not applicable" : pct + " percent"}`}><div className="h-full rounded-full bg-gradient-to-r from-brand to-sky2" style={{ width: pct + "%" }} /></div>{hint && <div className="mt-1 text-xs text-mu">{hint}</div>}</div>;
};

/** Plain-language summary of a findings list. Never claims an item is genuine or fake: only what the checks did or did not find. */
export function Verdict({ findings = [], extra }) {
  const n = (s) => findings.filter((f) => f.severity === s).length, hi = n("High"), me = n("Medium"), lo = n("Low");
  const tone = hi ? ["border-red-500/60 bg-red-500/10", "text-red-200", "Needs attention", `${hi} high-severity issue${hi > 1 ? "s" : ""} found. Have a person verify before this is used or published.`]
    : findings.length ? ["border-amber-500/60 bg-amber-500/10", "text-amber-200", "Review recommended", "Some items could not be matched to your approved Brand DNA."]
    : ["border-green-500/50 bg-green-500/10", "text-green-200", "No issues found", "The available checks found no inconsistencies. This is not proof that the content is genuine."];
  return <div className={`mb-4 rounded-2xl border p-4 ${tone[0]}`}><div className={`text-lg font-bold ${tone[1]}`}>{tone[2]}</div><p className="mt-1 text-sm text-slate-200">{tone[3]}</p>
    <div className="mt-2 flex flex-wrap gap-2"><Tag c={SEV.High}>{hi} High</Tag><Tag c={SEV.Medium}>{me} Medium</Tag><Tag c={SEV.Low}>{lo} Low</Tag></div>{extra && <p className="mt-2 text-sm text-mu">{extra}</p>}</div>;
}

/** Drag-and-drop / click image picker. Calls onFile(File). Keyboard accessible. */
export function Dropzone({ onFile, accept, label, disabled }) {
  const [over, setOver] = useState(false), ref = useRef();
  const take = (f) => f && onFile(f);
  return <div role="button" tabIndex={0} aria-label={label} aria-disabled={disabled} onClick={() => !disabled && ref.current.click()}
    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !disabled && (e.preventDefault(), ref.current.click())}
    onDragOver={(e) => { e.preventDefault(); !disabled && setOver(true); }} onDragLeave={() => setOver(false)}
    onDrop={(e) => { e.preventDefault(); setOver(false); !disabled && take(e.dataTransfer.files?.[0]); }}
    className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition ${over ? "border-brand bg-brand/10 text-white" : "border-line text-mu hover:border-brand"} ${disabled ? "cursor-not-allowed opacity-60" : ""}`}>
    <div className="text-2xl" aria-hidden>⬆</div><div className="mt-1 text-sm">{label}</div><div className="text-xs">Drag a file here or click to browse</div>
    <input ref={ref} type="file" accept={accept} hidden disabled={disabled} onChange={(e) => { take(e.target.files?.[0]); e.target.value = ""; }} /></div>;
}

/** Backend status chip. Also pings /api/health on mount, which wakes a sleeping Render service before the user uploads. */
export function useHealth() {
  const [h, setH] = useState(null), [state, setState] = useState("checking");
  const check = () => { setState("checking"); getHealth().then((x) => { setH(x); setState("ready"); }).catch(() => { setH(null); setState("down"); }); };
  useEffect(check, []);
  return { h, state, check };
}
export function BackendChip({ state, h }) {
  const m = { checking: ["bg-amber-500/20 text-amber-300", "Backend: connecting… (may be waking up)"], down: ["bg-red-500/20 text-red-300", "Backend: unreachable"], ready: ["bg-green-500/20 text-green-300", "Backend: ready"] }[state];
  return <span className="inline-flex flex-wrap items-center gap-2"><Tag c={m[0]}>{m[1]}</Tag>{h && <Tag c={h.ocr_installed ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"}>OCR: {h.ocr_installed ? (h.ocr_loaded ? "loaded" : "installed (loads on first use)") : "not installed"}</Tag>}</span>;
}
