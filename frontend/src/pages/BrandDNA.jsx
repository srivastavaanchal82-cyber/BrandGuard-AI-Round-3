import { useEffect, useState } from "react";import { getBrand, saveBrand, errMsg, getLogos, addLogo, deleteLogo } from "../api.js";import { Btn, Card, Dropzone, Err, Field, Head, Ok, Skeleton } from "../ui.jsx";
const E = { brand_name: "", approved_terminology: "", prohibited_words: "", tone: "Professional", communication_guidelines: "", verified_facts: "", approved_claims: "", approved_domains: "", approved_campaign: "" };
const SAMPLE = { brand_name: "ABC Technologies", approved_terminology: "clients → customers", prohibited_words: "cheapest, guaranteed returns", tone: "Professional", communication_guidelines: "Always use the exact name ABC Technologies.\nDo not use the unverified word “cheapest”.\nDo not make unsupported “100% results” guarantees.", verified_facts: "ABC Technologies was founded in 2015.", approved_claims: "", approved_domains: "abctechnologies.com", approved_campaign: "" };
const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"];
function LogoManager() {
  const [logos, setLogos] = useState(null), [name, setName] = useState(""), [busy, setBusy] = useState(false), [del, setDel] = useState(""), [e, setE] = useState(""), [ok, setOk] = useState("");
  const load = () => getLogos().then(setLogos).catch((x) => { setLogos([]); setE(errMsg(x)); });
  useEffect(() => { load(); }, []);
  async function upload(f) {
    setE(""); setOk("");
    if (!LOGO_TYPES.includes(f.type)) return setE("Logo must be a PNG, JPEG or WebP image.");
    if (f.size > 5 * 1024 * 1024) return setE("Logo must be 5 MB or smaller.");
    setBusy(true); try { const l = await addLogo(f, name); setLogos((a) => [...(a || []), l]); setName(""); setOk(`Reference logo "${l.name}" added.`); } catch (x) { setE(errMsg(x)); } finally { setBusy(false); }
  }
  async function remove(l) {
    if (!window.confirm(`Delete reference logo "${l.name}"?`)) return;
    setE(""); setOk(""); setDel(l.id); try { await deleteLogo(l.id); setLogos((a) => a.filter((x) => x.id !== l.id)); setOk("Reference logo deleted."); } catch (x) { setE(errMsg(x)); } finally { setDel(""); }
  }
  return <Card><h2 className="mb-1 font-bold">Reference logos</h2>
    <p className="mb-3 max-w-prose text-sm text-mu">Upload your official logo (a clean, high-resolution PNG works best; transparent backgrounds are fine). Protect searches uploaded images for these logos and reports where they appear and how closely they match. Only logos registered here can be recognised.</p>
    <Err m={e} /><Ok m={ok} />
    {logos === null ? <Skeleton className="h-24 w-full" /> : logos.length === 0 ? <p className="mb-3 rounded-xl border border-line bg-[#0a1130] p-3 text-sm text-mu">No reference logos yet. Add one below to enable logo recognition.</p>
      : <ul className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">{logos.map((l) => <li key={l.id} className="rounded-xl border border-line bg-white/95 p-2 text-center">
        <img src={l.thumbnail} alt={`Reference logo ${l.name}`} className="mx-auto h-20 w-full object-contain" /><div className="mt-1 truncate text-xs font-semibold text-slate-800" title={l.name}>{l.name}</div>
        <button type="button" disabled={del === l.id} onClick={() => remove(l)} className="mt-1 text-xs font-semibold text-red-600 underline disabled:opacity-50">{del === l.id ? "Deleting…" : "Delete"}</button></li>)}</ul>}
    <Field label="Logo name (optional, e.g. Primary logo)" value={name} onChange={(x) => setName(x.target.value)} maxLength={80} disabled={busy} />
    <Dropzone disabled={busy} accept={LOGO_TYPES.join(",")} label={busy ? "Uploading logo…" : "Add a reference logo (PNG, JPEG or WebP, max 5 MB)"} onFile={upload} />
    <p className="mt-2 text-xs text-mu">Up to 10 logos. Logos are stored with your Brand DNA (Firestore when configured, otherwise in memory until the server restarts).</p></Card>;
}

export default function BrandDNA() {
  const [f, setF] = useState(E), [busy, setBusy] = useState(false), [e, setE] = useState(""), [ok, setOk] = useState(""), [load, setLoad] = useState(true);
  useEffect(() => { getBrand().then((b) => setF({ ...E, ...b })).catch((x) => { if (x.response?.status !== 404) setE(errMsg(x)); }).finally(() => setLoad(false)); }, []);
  const set = (k) => (ev) => setF({ ...f, [k]: ev.target.value });
  async function save() {
    setE(""); setOk(""); if (!f.brand_name.trim()) return setE("Brand name is required.");
    setBusy(true); try { await saveBrand(f); setOk("Brand DNA saved to the backend. It will be used by every check."); } catch (x) { setE(errMsg(x)); } finally { setBusy(false); }
  }
  return <><Head t="Brand DNA" s="Your approved source of truth, stored by the backend (Firestore when configured)." /><Err m={e} /><Ok m={ok} />
    <Card>{load ? <p className="text-mu">Loading saved Brand DNA…</p> : <>
      <Btn v="g" onClick={() => { setF(SAMPLE); setOk("Sample loaded. Click Save Brand DNA to store it."); }}>Load ABC Technologies sample</Btn>
      <div className="mt-3"><Field label="Brand name *" value={f.brand_name} onChange={set("brand_name")} />
        <Field area label="Approved terminology (one per line, use “wrong → right”)" value={f.approved_terminology} onChange={set("approved_terminology")} />
        <Field label="Prohibited words (comma separated)" value={f.prohibited_words} onChange={set("prohibited_words")} />
        <label className="mb-3 block text-xs text-mu">Preferred tone<select className="mt-1" value={f.tone} onChange={set("tone")}>{["Professional", "Friendly", "Bold", "Playful"].map((t) => <option key={t}>{t}</option>)}</select></label>
        <Field area label="Communication guidelines" value={f.communication_guidelines} onChange={set("communication_guidelines")} />
        <Field area label="Verified facts (one per line)" value={f.verified_facts} onChange={set("verified_facts")} />
        <Field area label="Approved marketing claims" value={f.approved_claims} onChange={set("approved_claims")} />
        <Field label="Approved website domains" value={f.approved_domains} onChange={set("approved_domains")} />
        <Field area label="Approved campaign details" value={f.approved_campaign} onChange={set("approved_campaign")} /></div>
      <Btn busy={busy} onClick={save}>Save Brand DNA</Btn></>}</Card>
    <LogoManager /></>;
}
