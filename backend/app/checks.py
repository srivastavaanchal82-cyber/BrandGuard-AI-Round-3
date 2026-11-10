"""Deterministic brand checks. These are rules, not AI."""
import re
from urllib.parse import urlparse

SUP = re.compile(r"\b(cheapest|best|number one|leading|fastest|greatest|world[- ]class|unbeatable|lowest price)\b", re.I)
GUA = re.compile(r"(?:we\s+)?guarantee[sd]?(?:\s+\d{1,3}%\s*\w+)?|\b\d{1,3}%\s+(?:results|success|accuracy|satisfaction)", re.I)

def lines(s):
    return [x.strip() for x in re.split(r"[\n,;]+", s or "") if x.strip()]

def F(text, cat, sev, rule, why, fix, evidence="Verification required", source="rule"):
    return dict(flagged_text=text, category=cat, severity=sev, brand_rule=rule,
                explanation=why, suggested_correction=fix, evidence=evidence, source=source)

def run_checks(text, b):
    out, seen = [], set()
    def add(f):
        if f["flagged_text"].lower() not in seen:
            seen.add(f["flagged_text"].lower()); out.append(f)
    name = (b.get("brand_name") or "").strip()
    claims = [c.lower() for c in lines(b.get("approved_claims"))]
    ok = lambda t: any(c in t.lower() for c in claims)
    if name:
        toks = name.split()
        for m in re.finditer(r"\b" + re.escape(toks[0]) + r"(?:\s+([A-Za-z]+))?", text, re.I):
            if text[m.start():m.start() + len(name)] == name:
                continue
            w = m.group(1)
            ph = m.group(0) if (w and len(toks) > 1 and toks[1].lower().startswith(w.lower())) else text[m.start():m.start() + len(toks[0])]
            add(F(ph, "Incorrect brand name", "High", f"Always use the exact name {name}",
                  f"'{ph}' is not the approved brand name.", f"Replace with '{name}'.", "Compared with Brand DNA brand name"))
    prohibited = [p.lower() for p in lines(b.get("prohibited_words"))]
    for m in SUP.finditer(text):
        if ok(m.group(0)): continue
        hard = m.group(0).lower() in prohibited
        add(F(m.group(0), "Unsupported superlative", "High" if hard else "Medium",
              "Prohibited word" if hard else "Superlatives need verified evidence",
              "No verified source for this superlative in the Brand DNA. It is unsupported, not proven false.",
              "Remove it or replace it with an approved, sourced claim.", "No matching approved claim found"))
    for p in prohibited:
        for m in re.finditer(r"\b" + re.escape(p) + r"\b", text, re.I):
            add(F(m.group(0), "Prohibited word", "High", f"Prohibited words: {p}", "Word is on the prohibited list.", "Remove or rephrase."))
    for m in GUA.finditer(text):
        if ok(m.group(0)): continue
        g = re.search(r"\d{1,3}%\s*\w+", m.group(0))
        add(F(g.group(0) if g else m.group(0), "Unsupported guarantee", "High", "No unsupported guarantees",
              "Promises an outcome that no approved claim supports.", "Use a soft, evidence-based claim.", "No approved guarantee claim found"))
    for l in (b.get("approved_terminology") or "").splitlines():
        p = re.split(r"→|->|=>", l)
        if len(p) == 2 and p[0].strip():
            for m in re.finditer(r"\b" + re.escape(p[0].strip()) + r"\b", text, re.I):
                add(F(m.group(0), "Off-brand terminology", "Medium", f"Use '{p[1].strip()}'", "Not approved terminology.", f"Replace with '{p[1].strip()}'."))
    return out

def _host(u):
    u = u.strip().lower()
    return (urlparse(u if "//" in u else "//" + u).hostname or "").removeprefix("www.")

def compare_campaign(ad, od, aw, ow):
    out, num = [], lambda s: re.findall(r"\d+(?:\.\d+)?", s or "")
    if ad and od and num(ad) != num(od):
        out.append(dict(mismatch_type="Discount mismatch", severity="High", extracted_evidence=f"Observed {od}", approved=ad,
                        explanation=f"Observed discount {od} differs from approved {ad}.", suggested_action="Requires human verification."))
    a, o = _host(aw or ""), _host(ow or "")
    if a and o and not (o == a or o.endswith("." + a)):
        out.append(dict(mismatch_type="Unapproved website", severity="High", extracted_evidence=f"Observed {ow}", approved=aw,
                        explanation=f"{o} is not {a} or one of its subdomains.", suggested_action="Requires human verification. An alert is not proof of wrongdoing."))
    return out
