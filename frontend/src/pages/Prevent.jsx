import { useState } from "react";import { Link, useNavigate } from "react-router-dom";
import { analyse, errMsg } from "../api.js";import { useApp } from "../ctx.jsx";import { Btn, Card, Err, Head } from "../ui.jsx";
export default function Prevent() {
  const { draft, setDraft, setLast } = useApp(), nav = useNavigate(), [busy, setBusy] = useState(false), [e, setE] = useState(""), [noBrand, setNoBrand] = useState(false);
  async function run() {
    setE(""); setNoBrand(false); if (!draft.trim()) return setE("Enter some content to analyse.");
    setBusy(true);
    try { setLast(await analyse(draft)); nav("/results"); }
    catch (x) { if (x.response?.status === 404) setNoBrand(true); else setE(errMsg(x)); } finally { setBusy(false); }
  }
  return <><Head t="Prevent · AI Content Checker" s="Check content against your saved Brand DNA before it is published." />
    {noBrand && <Err m={<>No Brand DNA is saved yet. <Link className="underline" to="/brand">Save one on the Brand DNA page</Link> first.</>} />}<Err m={e} />
    <Card><textarea className="min-h-[180px]" placeholder="Paste a draft headline, post or ad copy…" value={draft} onChange={(x) => setDraft(x.target.value)} maxLength={10000} />
      <div className="mt-3 flex flex-wrap gap-2"><Btn busy={busy} onClick={run}>{busy ? "Analysing…" : "Analyse Content"}</Btn>
        <Btn v="g" onClick={() => setDraft("ABC Tech is the cheapest company in India. We guarantee 100% results!")}>Example content</Btn><Btn v="g" onClick={() => setDraft("")}>Clear</Btn></div></Card></>;
}
