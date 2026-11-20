#!/usr/bin/env python3
"""Build clean supervision tables from the theses.fr data.gouv.fr dump.

Outputs (CSV, in the output directory):
  theses.csv             one row per thesis
  persons.csv            one row per distinct person key (PPN, or name-based fallback)
  supervision_edges.csv  one row per (thesis, author, director) pair
  jury_edges.csv         one row per (thesis, author, jury member, role)
  coverage_by_year.csv   share of edges where both ends carry a PPN
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator

UNKNOWN_RE = re.compile(r"\binconnu\b|\bunknown\b|^\s*$", re.IGNORECASE)
PPN_RE = re.compile(r"^\d{8}[\dX]$")


def norm(s: str | None) -> str:
    """Lower-case, accent-stripped, whitespace-collapsed form for name keys."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def person_key(p: dict[str, Any]) -> tuple[str, str]:
    """Return (key, kind). PPN where valid, else a name-based fallback key."""
    ppn = (p.get("idref") or "").strip().upper()
    if PPN_RE.match(ppn):
        return ppn, "ppn"
    return f"name:{norm(p.get('nom'))}|{norm(p.get('prenom'))}", "name"


def is_placeholder(p: dict[str, Any]) -> bool:
    return bool(UNKNOWN_RE.search(f"{p.get('nom') or ''} {p.get('prenom') or ''}"))


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:  # type: ignore[operator]
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def year_of(d: dict[str, Any]) -> str:
    return (d.get("date_soutenance") or "")[:4]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--min-year", type=int, default=0, help="drop soutenances before this year (0 = keep all)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    persons: dict[str, dict[str, Any]] = {}
    # coverage[year] = [edges, both_ppn, director_ppn, unknown_director_theses, theses]
    cov: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])

    def reg(p: dict[str, Any]) -> tuple[str, str]:
        key, kind = person_key(p)
        rec = persons.setdefault(
            key, {"person_key": key, "key_kind": kind, "nom": p.get("nom") or "", "prenom": p.get("prenom") or "", "n_theses_as_author": 0, "n_theses_supervised": 0}
        )
        return key, kind

    with (
        open(args.out / "theses.csv", "w", newline="", encoding="utf-8") as ft,
        open(args.out / "supervision_edges.csv", "w", newline="", encoding="utf-8") as fe,
        open(args.out / "jury_edges.csv", "w", newline="", encoding="utf-8") as fj,
    ):
        wt = csv.writer(ft)
        we = csv.writer(fe)
        wj = csv.writer(fj)
        wt.writerow(["nnt", "year", "date_soutenance", "status", "source", "discipline", "institution_ppn", "institution", "n_authors", "n_directors", "title"])
        we.writerow(["nnt", "year", "author_key", "author_kind", "director_key", "director_kind", "n_directors_on_thesis", "director_rank", "institution_ppn", "discipline"])
        wj.writerow(["nnt", "year", "author_key", "jury_key", "jury_kind", "role"])

        for d in read_jsonl(args.input):
            yr = year_of(d)
            if args.min_year and (not yr.isdigit() or int(yr) < args.min_year):
                continue
            nnt = d.get("nnt") or ""
            inst = (d.get("etablissements_soutenance") or [{}])[0]
            authors = [a for a in d.get("auteurs") or [] if not is_placeholder(a)]
            directors = [p for p in d.get("directeurs_these") or [] if not is_placeholder(p)]
            title = (d.get("titres") or {}).get("fr") or next(iter((d.get("titres") or {}).values()), "")

            wt.writerow([nnt, yr, d.get("date_soutenance") or "", d.get("status") or "", d.get("source") or "", d.get("discipline") or "", inst.get("idref") or "", inst.get("nom") or "", len(authors), len(directors), title])
            c = cov[yr or "unknown"]
            c[4] += 1
            if not directors:
                c[3] += 1

            akeys = [reg(a) for a in authors]
            for k, _ in akeys:
                persons[k]["n_theses_as_author"] += 1
            for rank, dpers in enumerate(directors, start=1):
                dk, dkind = reg(dpers)
                persons[dk]["n_theses_supervised"] += 1
                for ak, akind in akeys:
                    we.writerow([nnt, yr, ak, akind, dk, dkind, len(directors), rank, inst.get("idref") or "", d.get("discipline") or ""])
                    c[0] += 1
                    c[1] += akind == "ppn" and dkind == "ppn"
                    c[2] += dkind == "ppn"

            roles = [("rapporteur", d.get("rapporteurs")), ("membre_jury", d.get("membres_jury")), ("president_jury", d.get("president_jury"))]
            for role, plist in roles:
                if isinstance(plist, dict):
                    plist = [plist]
                for jp in plist or []:
                    if is_placeholder(jp):
                        continue
                    jk, jkind = reg(jp)
                    for ak, _ in akeys:
                        wj.writerow([nnt, yr, ak, jk, jkind, role])

    with open(args.out / "persons.csv", "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["person_key", "key_kind", "nom", "prenom", "n_theses_as_author", "n_theses_supervised"])
        w.writeheader()
        w.writerows(persons.values())

    with open(args.out / "coverage_by_year.csv", "w", newline="", encoding="utf-8") as fc:
        w = csv.writer(fc)
        w.writerow(["year", "theses", "theses_without_named_director", "edges", "edges_director_ppn", "edges_both_ppn", "pct_both_ppn"])
        for yr in sorted(cov):
            e, both, dppn, nodir, nth = cov[yr]
            w.writerow([yr, nth, nodir, e, dppn, both, f"{100 * both / e:.1f}" if e else ""])

    print(f"theses/persons written to {args.out}; {len(persons):,} persons")


if __name__ == "__main__":
    main()
