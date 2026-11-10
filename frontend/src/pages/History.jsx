import { useEffect, useState } from "react";import { getReviews, errMsg } from "../api.js";import { Btn, Card, Empty, Err, Head, Spin, Tag } from "../ui.jsx";
const C = { Approved: "bg-green-500/20 text-green-300", Rejected: "bg-red-500/20 text-red-300", "Changes Requested": "bg-amber-500/20 text-amber-300", Escalated: "bg-violet-500/30 text-violet-200" };
export default function History() {
  const [rows, setRows] = useState(null), [e, setE] = useState("");
  const load = () => { setE(""); getReviews().then(setRows).catch((x) => setE(errMsg(x))); };
  useEffect(load, []);
  return <><Head t="Review History" s="Every human decision stored by the backend." /><Err m={e} /><Btn v="g" className="mb-4" onClick={load}>Refresh</Btn>
    {!rows && !e && <p className="text-mu"><Spin />Loading…</p>}{rows?.length === 0 && <Empty>No decisions recorded yet.</Empty>}
    {rows?.length > 0 && <Card className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-mu"><tr><th className="py-2">When</th><th>Type</th><th>Decision</th><th>Findings</th><th>Analysis ID</th></tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-line"><td className="py-2">{new Date(r.at).toLocaleString()}</td><td>{r.review_type}</td><td><Tag c={C[r.decision]}>{r.decision}</Tag></td><td>{r.findings.length}</td><td className="font-mono text-xs text-mu">{r.analysis_id.slice(0, 8)}</td></tr>)}</tbody></table></Card>}</>;
}
