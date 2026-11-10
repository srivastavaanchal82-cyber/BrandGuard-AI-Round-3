import { useState } from "react";import { Link } from "react-router-dom";
import { review, errMsg } from "../api.js";import { useApp } from "../ctx.jsx";import { Btn, Card, Empty, Err, Finding, Head, Ok, Tag, Verdict } from "../ui.jsx";
export default function Results() {
  const { last, setLast } = useApp(), [busy, setBusy] = useState(""), [e, setE] = useState(""), [ok, setOk] = useState("");
  if (!last) return <><Head t="Analysis Results" /><Empty>No analysis yet. <Link className="text-sky-300 underline" to="/prevent">Run a check in Prevent</Link> or <Link className="text-sky-300 underline" to="/protect">Protect</Link>.</Empty></>;
  async function decide(d) {
    setE(""); setOk(""); setBusy(d);
    try { await review(last.id, d, last.type); setLast({ ...last, status: d }); setOk(`Decision recorded: ${d}`); } catch (x) { setE(errMsg(x)); } finally { setBusy(""); }
  }
  return <><Head t="Analysis Results" s={`${last.type} analysis · ${new Date(last.at).toLocaleString()}`} /><Err m={e} /><Ok m={ok} />
    <Verdict findings={last.findings} extra={last.logo && last.logo.status !== "no_reference_logos" ? `Logo recognition: ${{ found: "a registered logo was found", possible: "a possible or altered logo needs review", not_found: "no registered logo found", image_too_plain: "image too plain to compare" }[last.logo.status] || last.logo.status}.` : undefined} />
    <Card><div className="flex flex-wrap items-center gap-2"><Tag c="bg-violet-500/30 text-violet-200">Mode: {last.mode}</Tag><Tag c="bg-slate-500/30 text-slate-200">Status: {last.status}</Tag><Tag c="bg-slate-500/30 text-slate-200">{last.findings.length} finding(s)</Tag></div>
      {last.note && <p className="mt-3 text-sm text-mu">{last.note}</p>}{last.text && <p className="mt-3 whitespace-pre-wrap rounded-xl bg-[#0a1130] p-3 text-sm">{last.text}</p>}</Card>
    {last.findings.length ? last.findings.map((f, i) => <Finding key={i} f={f} />) : <Card className="text-green-300">✓ No issues found against your saved Brand DNA.</Card>}
    {last.retrieved_context?.length > 0 && <Card><h2 className="mb-2 font-bold">Retrieved guideline context</h2><ul className="list-disc pl-5 text-sm text-mu">{last.retrieved_context.map((c, i) => <li key={i}>{c}</li>)}</ul></Card>}
    <Card><h2 className="mb-3 font-bold">Human review</h2><div className="flex flex-wrap gap-2">
      <Btn v="ok" busy={busy === "Approved"} onClick={() => decide("Approved")}>Approve</Btn><Btn v="no" busy={busy === "Rejected"} onClick={() => decide("Rejected")}>Reject</Btn>
      <Btn v="wa" busy={busy === "Changes Requested"} onClick={() => decide("Changes Requested")}>Request Changes</Btn><Btn v="g" busy={busy === "Escalated"} onClick={() => decide("Escalated")}>Escalate to Human Reviewer</Btn></div></Card></>;
}
