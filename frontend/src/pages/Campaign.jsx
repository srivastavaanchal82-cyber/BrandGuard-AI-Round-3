import { useState } from "react";import { useNavigate } from "react-router-dom";
import { compare, errMsg } from "../api.js";import { useApp } from "../ctx.jsx";import { Btn, Card, Err, Field, Finding, Head, Tag } from "../ui.jsx";
export default function Campaign() {
  const [f, setF] = useState({ approved_discount: "20%", observed_discount: "80%", approved_website: "nova.com", observed_website: "nova-deals.xyz" });
  const [res, setRes] = useState(null), [busy, setBusy] = useState(false), [e, setE] = useState(""), { setLast } = useApp(), nav = useNavigate();
  const set = (k) => (ev) => setF({ ...f, [k]: ev.target.value });
  async function run() {
    setE(""); if (!Object.values(f).some((v) => v.trim())) return setE("Enter at least one approved and one observed value.");
    setBusy(true); try { const r = await compare(f); setRes(r); setLast(r); } catch (x) { setE(errMsg(x)); } finally { setBusy(false); }
  }
  return <><Head t="Campaign DNA Comparison" s="Does it match the brand’s approved campaign identity? Defaults use the fictional Nova Electronics example; edit them freely." /><Err m={e} />
    <Card><div className="grid gap-x-4 sm:grid-cols-2"><Field label="Approved discount" value={f.approved_discount} onChange={set("approved_discount")} /><Field label="Observed discount" value={f.observed_discount} onChange={set("observed_discount")} />
      <Field label="Approved website" value={f.approved_website} onChange={set("approved_website")} /><Field label="Observed website" value={f.observed_website} onChange={set("observed_website")} /></div>
      <Btn busy={busy} onClick={run}>Compare with Campaign DNA</Btn></Card>
    {res && <><div className="mb-3 flex gap-2"><Tag c="bg-violet-500/30 text-violet-200">{res.mode}</Tag></div>
      {res.findings.length ? <>{res.findings.map((x, i) => <Finding key={i} f={x} />)}<p className="mb-3 text-sm text-mu">Result: requires human verification. An alert is not proof of wrongdoing.</p><Btn v="wa" onClick={() => nav("/results")}>Review &amp; decide</Btn></> : <Card className="text-green-300">✓ Matches the approved campaign values you entered.</Card>}</>}</>;
}
