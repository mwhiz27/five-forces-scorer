#!/usr/bin/env python3
"""Build dist/index.html by inlining rules.json and evidence.json into template.html.

No third-party dependencies. Usage:

    python3 build.py            # validate + build
    python3 build.py --strict   # also fail on warnings

Scoring rules below mirror scoreForce() in template.html.
If you change one, change the other.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

DIRS = {"raises": 1, "lowers": -1, "mixed": 0}
RV = {"Low": 1, "Medium": 2, "High": 3}

_TTY = sys.stdout.isatty()


def c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def has(v) -> bool:
    return v is not None and str(v).strip() != ""


def score_force(force: dict, facts: list[dict]) -> dict:
    mine = [f for f in facts if f["force"] == force["id"]]
    ratings = []
    for d in force["drivers"]:
        df = [f for f in mine if f["driver"] == d["id"]]
        if not df:
            continue
        net = sum(DIRS[f["direction"]] for f in df)
        ratings.append("High" if net > 0 else "Low" if net < 0 else "Medium")
    if not ratings:
        return {"score": None, "raw": None, "n": len(mine)}
    avg = sum(RV[r] for r in ratings) / len(ratings)
    raw = 1 + 2 * (avg - 1)
    score = min(5, max(1, math.floor(raw + 0.5)))
    frac = raw - math.floor(raw)
    return {"score": score, "raw": raw, "n": len(mine), "tension": 0.33 <= frac <= 0.67,
            "docs": len({f["source"] for f in mine})}


def sentences(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“$])", text.strip()) if s])


def validate(rules: dict, ev: dict) -> tuple[list[str], list[str], list[dict]]:
    errors, warnings = [], []
    forces = {f["id"]: f for f in rules["forces"]}
    sources = ev.get("sources", {})
    facts = ev.get("facts", [])
    seen = set()

    for f in facts:
        fid = f.get("id", "?")
        if fid in seen:
            errors.append(f"{fid}: duplicate fact id")
        seen.add(fid)
        if f.get("force") not in forces:
            errors.append(f"{fid}: unknown force '{f.get('force')}'")
            continue
        if f.get("driver") not in {d["id"] for d in forces[f["force"]]["drivers"]}:
            errors.append(f"{fid}: unknown driver '{f.get('driver')}' for {f['force']}")
        if f.get("direction") not in DIRS:
            errors.append(f"{fid}: direction must be raises/lowers/mixed")
        if f.get("source") not in sources:
            errors.append(f"{fid}: source '{f.get('source')}' not in sources")
        if not has(f.get("section")):
            errors.append(f"{fid}: missing section/page")
        if not has(f.get("fact")):
            errors.append(f"{fid}: empty fact text")

    for sid, s in sources.items():
        for k in ("doc", "url", "date"):
            if k == "url" and s.get("type") == "brief":
                continue  # the brief is inlined into the page, not hosted
            if not has(s.get(k)):
                warnings.append(f"source {sid}: missing {k}")

    results = []
    analysis = ev.get("analysis", {})
    for fid, force in forces.items():
        r = score_force(force, [f for f in facts if f.get("force") in forces])
        r["name"] = force["name"]
        r["id"] = fid
        results.append(r)
        a = analysis.get(fid, {})
        if r["n"] < 3:
            errors.append(f"{force['name']}: only {r['n']} cited facts (need 3+)")
        stated = a.get("score")
        if not isinstance(stated, int) or not 1 <= stated <= 5:
            errors.append(f"{force['name']}: stated score must be a whole number 1-5")
        elif stated != r["score"]:
            errors.append(f"{force['name']}: stated score {stated} != computed {r['score']} (raw {r['raw']:.2f})")
        n = sentences(a.get("rationale", ""))
        if not 2 <= n <= 3:
            warnings.append(f"{force['name']}: rationale has {n} sentences (assignment asks 2-3)")
        if r.get("tension") and not re.search(r"between|vs\.?|torn", a.get("rationale", ""), re.I):
            warnings.append(f"{force['name']}: raw score {r['raw']:.2f} is a tension case but the rationale doesn't name it")

    n = sentences(analysis.get("overall", ""))
    if not 3 <= n <= 5:
        warnings.append(f"overall read has {n} sentences (assignment asks 3-5)")
    lc = analysis.get("leastConfident", {})
    if lc.get("force") not in forces or not has(lc.get("settle")):
        errors.append("leastConfident needs a valid force and a 'settle' explanation")
    return errors, warnings, results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="rules.json")
    ap.add_argument("--data", default="evidence.json")
    ap.add_argument("--template", default="template.html")
    ap.add_argument("--out", default="dist/index.html")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    here = Path(__file__).parent
    rules = json.loads((here / args.rules).read_text())
    ev = json.loads((here / args.data).read_text())
    brief = here / "brief.md"
    if brief.exists():  # powers the "Load example" button on the scorer tab
        ev["exampleBrief"] = brief.read_text()
        ev["exampleBriefDoc"] = "Industry Brief (Sept 19, 2026) / IBISWorld 516210"
    errors, warnings, results = validate(rules, ev)

    print(c("1", "Five Forces — computed scores"))
    total = 0
    for r in results:
        total += r["score"] or 0
        flag = c("33", "  tension") if r.get("tension") else ""
        print(f"  {r['name']:<40} {r['score']}  (raw {r['raw']:.2f}, {r['n']} facts, {r.get('docs', 0)} docs){flag}")
    print(f"  {'Total':<40} {total} / 25")
    for w in warnings:
        print(c("33", "warning: ") + w)
    for e in errors:
        print(c("31", "error: ") + e)
    if errors or (args.strict and warnings):
        print(c("31", "Build failed."))
        return 1

    def inline(obj) -> str:  # keep '</script>' from closing the tag early
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    html = (here / args.template).read_text()
    html = html.replace("__RULES_JSON__", inline(rules)).replace("__EVIDENCE_JSON__", inline(ev))
    out = here / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(c("32", f"Built {out} ({len(html):,} bytes)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
