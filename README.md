# Five Forces Scorer

Porter's Five Forces scorer where every score is computed from cited facts, not chosen.

**Live tool:** https://mwhiz27.github.io/five-forces-scorer/

- `evidence.json` — the PGA Tour Entertainment Inc. analysis: sources, facts (force, driver, direction, section), rationales.
- `rules.json` — forces, drivers, keyword routing table, scoring rules.
- `template.html` — the page (preloaded analysis, paste-a-brief scorer, method).
- `build.py` — validates evidence (3+ cited facts per force, stated score = computed score) and writes `dist/index.html`. No dependencies.

```
python3 build.py --strict
```

To republish: rebuild, copy `dist/index.html` to the `gh-pages` branch as `index.html`, commit, push.
