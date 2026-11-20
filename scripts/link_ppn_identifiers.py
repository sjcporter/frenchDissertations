#!/usr/bin/env python3
"""Resolve IdRef PPNs to ORCID (and ISNI/VIAF/Scopus/HAL/...) via the IdRef idref2id service.

Reads author and director PPNs from supervision_edges.csv and writes:
  idref_identifiers.csv  long form: ppn, source, identifier
  ppn_orcid.csv          one row per PPN: ppn, orcid (blank if none), n_orcids
"""
from __future__ import annotations

import argparse
import csv
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = "https://www.idref.fr/services/idref2id/"
ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


def fetch(batch: list[str], retries: int = 5) -> list[tuple[str, str, str]]:
    url = BASE + ",".join(batch)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "frenchDissertations-research/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                root = ET.fromstring(resp.read())
            out = []
            for q in root.iter("query"):
                ppn = q.findtext("ppn") or ""
                for r in q.findall("result"):
                    out.append((ppn, r.findtext("source") or "", (r.findtext("identifiant") or "").strip()))
            return out
        except urllib.error.HTTPError as e:
            # 401/403: not retryable; 404: nothing for this batch; 5xx incl. 502: retry
            if e.code in (401, 403):
                raise RuntimeError(f"IdRef refused access (HTTP {e.code})") from e
            if e.code == 404:
                return []
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError, ET.ParseError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"batch failed after {retries} attempts: {batch[0]}..")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edges", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch", type=int, default=150)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    ppns: set[str] = set()
    with open(args.edges, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["author_kind"] == "ppn":
                ppns.add(r["author_key"])
            if r["director_kind"] == "ppn":
                ppns.add(r["director_key"])
    ordered = sorted(ppns)
    batches = [ordered[i : i + args.batch] for i in range(0, len(ordered), args.batch)]
    print(f"{len(ordered):,} PPNs in {len(batches):,} batches")

    rows: list[tuple[str, str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, res in enumerate(ex.map(fetch, batches), 1):
            rows.extend(res)
            if i % 200 == 0:
                print(f"  {i}/{len(batches)}")

    with open(args.out / "idref_identifiers.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ppn", "source", "identifier"])
        w.writerows(sorted(set(rows)))

    orcids: dict[str, set[str]] = {}
    for ppn, src, ident in rows:
        if src.upper() == "ORCID":
            m = ORCID_RE.search(ident)
            if m:
                orcids.setdefault(ppn, set()).add(m.group(0))
    with open(args.out / "ppn_orcid.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["ppn", "orcid", "n_orcids"])
        for p in ordered:
            o = sorted(orcids.get(p, []))
            w.writerow([p, o[0] if o else "", len(o)])
    print(f"PPNs with ORCID: {len(orcids):,} of {len(ordered):,} ({100 * len(orcids) / len(ordered):.1f}%)")


if __name__ == "__main__":
    main()
