#!/usr/bin/env python3
"""Download the theses.fr dump (theses-soutenues.jsonl.gz) and usage guide from data.gouv.fr into data/.

The current file URL is looked up through the data.gouv.fr API, so it keeps working when the dump is refreshed.
Usage: python3 scripts/load_theses_data.py [--out data] [--force]
Then:  python3 scripts/build_supervision_graph.py  (see its --help for arguments)
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

DATASET = "theses-soutenues-en-france-depuis-1985"
API = f"https://www.data.gouv.fr/api/1/datasets/{DATASET}/"
WANTED = ("theses-soutenues.jsonl.gz", "guide-utilisation-donnees-theses-fr.pdf")


def fetch_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"Could not read {url}: {e}")


def download(url: str, dest: Path, size: int | None) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as fh:
            done = 0
            while chunk := r.read(1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if size:
                    print(f"\r{dest.name}: {done / 1e6:,.0f} / {size / 1e6:,.0f} MB", end="", flush=True)
        print()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        tmp.unlink(missing_ok=True)
        sys.exit(f"Download failed for {url}: {e}")
    tmp.replace(dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "data")
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    res = {r["title"]: r for r in fetch_json(API)["resources"]}
    for name in WANTED:
        if name not in res:
            sys.exit(f"{name} not listed in dataset {DATASET}; available: {', '.join(res)}")
        dest = a.out / name
        size = res[name].get("filesize")
        if dest.exists() and not a.force and (not size or dest.stat().st_size >= 0.99 * size):
            print(f"{name}: already present ({dest.stat().st_size / 1e6:,.0f} MB), skipping")
            continue
        download(res[name]["url"], dest, size)
    print("done:", a.out)


if __name__ == "__main__":
    main()
