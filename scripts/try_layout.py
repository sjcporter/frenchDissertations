#!/usr/bin/env python3
"""Run BatchLayout with given settings on the giant-component mtx and report edge-length / random-pair-length ratio (lower = better local structure)."""
import os
import argparse, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd

BL = Path(os.environ.get("BATCHLAYOUT_DIR", Path.home() / "batchlayout/BatchLayout/BatchLayoutCode"))
ap = argparse.ArgumentParser()
ap.add_argument("--net", type=Path, required=True); ap.add_argument("--tag", required=True)
ap.add_argument("--algo", type=int, default=2); ap.add_argument("--init", type=int, default=1)
ap.add_argument("--iter", type=int, default=600); ap.add_argument("--batch", type=int, default=256)
a = ap.parse_args(); net = a.net.resolve()
out = net / f"try_{a.tag}"; out.mkdir(exist_ok=True)
r = subprocess.run([str(BL / "bin/BatchLayout"), "-input", str(net / "advisor_gcc.mtx"), "-output", f"{out}/", "-iter", str(a.iter),
                    "-batch", str(a.batch), "-algo", str(a.algo), "-init", str(a.init), "-threads", "16"], cwd=BL, capture_output=True, text=True)
if r.returncode: sys.exit(r.stdout[-800:] + r.stderr[-800:])
f = next(out.glob("*.txt")); P = pd.read_csv(f, header=None, sep="\t").sort_values(2)[[0, 1]].to_numpy()
import scipy.io as io
A = io.mmread(str(net / "advisor_gcc.mtx")).tocoo(); m = A.row < A.col
el = np.hypot(*(P[A.row[m]] - P[A.col[m]]).T); rng = np.random.default_rng(0)
i, j = rng.integers(0, len(P), 50000), rng.integers(0, len(P), 50000)
print(a.tag, "ratio", round(float(np.median(el) / np.median(np.hypot(*(P[i] - P[j]).T))), 3), "file", f.name)
