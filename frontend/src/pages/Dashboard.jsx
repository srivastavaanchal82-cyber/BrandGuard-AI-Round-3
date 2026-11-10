import { useEffect, useState } from "react";import { Link } from "react-router-dom";
import { getStats, errMsg } from "../api.js";import { Card, Head, Err, Empty, Btn, Skeleton, BackendChip, useHealth } from "../ui.jsx";
const ACTIONS = [["/brand", "◈", "Set up Brand DNA", "Rules, facts and reference logos every check uses."], ["/prevent", "✎", "Check content", "Paste copy and find off-brand wording."], ["/protect", "◉", "Check an image", "OCR, logo recognition and campaign checks."]];
export default function Dashboard() {
  const [s, setS] = useState(null), [e, setE] = useState(""), { h, state } = useHealth();
  const load = () => { setE(""); setS(null); getStats().then(setS).catch((x) => setE(errMsg(x))); };
  useEffect(load, []);
  const cells = s && [["Total content checks", s.total_checks], ["Issues detected", s.issues], ["Approved content", s.approved], ["Pending reviews", s.pending], ["Prevent analyses", s.prevent], ["Protect analyses", s.protect]];
  return <><Head t="Dashboard" s="Live statistics from your stored analyses. One Brand DNA. Two layers of protection. Zero guesswork." />
    <div className="mb-4"><BackendChip state={state} h={h} /></div><Err m={e} />
    {e && <Btn v="g" className="mb-4" onClick={load}>Retry</Btn>}
    <div className="mb-4 grid gap-3 sm:grid-cols-3">{ACTIONS.map(([to, i, t, d]) => <Link key={to} to={to} className="rounded-2xl border border-line bg-gradient-to-br from-[#131c42] to-card p-4 transition hover:border-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand"><div className="text-lg" aria-hidden>{i}</div><div className="font-semibold">{t}</div><div className="mt-1 text-xs text-mu">{d}</div></Link>)}</div>
    {!s && !e && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" role="status" aria-label="Loading statistics">{[...Array(6)].map((_, i) => <Card key={i} className="!mb-0"><Skeleton className="h-3 w-24" /><Skeleton className="mt-3 h-8 w-12" /></Card>)}</div>}
    {s && s.total_checks === 0 && <Empty>No analyses yet. <Link className="text-sky-300 underline" to="/brand">Save your Brand DNA</Link>, then run a check in <Link className="text-sky-300 underline" to="/prevent">Prevent</Link> or <Link className="text-sky-300 underline" to="/protect">Protect</Link>.</Empty>}
    {s && <><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{cells.map(([l, v]) => <Card key={l} className="!mb-0"><div className="text-xs text-mu">{l}</div><div className="text-3xl font-bold">{v}</div></Card>)}</div>
      <Card className="mt-4"><div className="text-xs text-mu">Approval rate</div><div className="text-3xl font-bold">{s.total_checks ? Math.round((s.approved / s.total_checks) * 100) + "%" : "n/a"}</div><div className="text-xs text-mu">Approved checks divided by all checks. Storage: {s.storage}.{s.storage === "in-memory" && " In-memory data is lost when the backend restarts."}</div></Card></>}</>;
}
