#!/usr/bin/env python3
"""BatchLayout of the giant component's within-community edges only (greedy init, as in the UniversityExplorer pipeline).

Writes advisor_intra.mtx + node order, runs BatchLayout, and reports edge-length / random-pair ratio.
"""
import os
import argparse, subprocess, sys
from pathlib import Path
import networkx as nx, numpy as np, pandas as pd
from scipy import io

BL = Path(os.environ.get("BATCHLAYOUT_DIR", Path.home() / "batchlayout/BatchLayout/BatchLayoutCode"))
ap = argparse.ArgumentParser()
ap.add_argument("--net", type=Path, required=True)
ap.add_argument("--init", type=int, default=0)
ap.add_argument("--algo", type=int, default=2)
ap.add_argument("--iter", type=int, default=600)
ap.add_argument("--threads", type=int, default=16)
a = ap.parse_args(); net = a.net.resolve()

lay = pd.read_csv(net / "advisor_layout_gcc_communities.csv", dtype={"director_key": str}, keep_default_na=False)
comm = lay.set_index("director_key").community
E = pd.read_csv(net / "advisor_edges.csv", dtype={"source": str, "target": str}, usecols=["source", "target", "weight"])
E = E[E.source.isin(comm.index) & E.target.isin(comm.index)]
E = E[comm.loc[E.source].values == comm.loc[E.target].values]
G = nx.from_pandas_edgelist(E, "source", "target", ["weight"])
order = list(G.nodes())
comps = list(nx.connected_components(G))
print(f"intra-community graph: {len(order):,} nodes, {G.number_of_edges():,} edges, {len(comps):,} components (largest {max(map(len, comps))})")
tag = f"intra_i{a.init}a{a.algo}"
mtx = net / f"advisor_{tag}.mtx"
io.mmwrite(str(mtx), nx.to_scipy_sparse_array(G, nodelist=order))
pd.Series(order, name="director_key").to_csv(net / f"advisor_{tag}_order.csv", index=False)
r = subprocess.run([str(BL / "bin/BatchLayout"), "-input", str(mtx), "-output", f"{net}/", "-iter", str(a.iter), "-batch", "256",
                    "-algo", str(a.algo), "-init", str(a.init), "-threads", str(a.threads), "-weight", "1"], cwd=BL, capture_output=True, text=True, timeout=3000)
if r.returncode:
    sys.exit(f"BatchLayout failed ({r.returncode}):\n{r.stdout[-700:]}\n{r.stderr[-500:]}")
f = net / f"{mtx.name}CACHEMINB256PARAOUT{a.iter}.txt"
P = pd.read_csv(f, header=None, sep="\t").sort_values(2)[[0, 1]].to_numpy()
A = io.mmread(str(mtx)).tocoo(); m = A.row < A.col
el = np.hypot(*(P[A.row[m]] - P[A.col[m]]).T); rng = np.random.default_rng(0)
i, j = rng.integers(0, len(P), 50000), rng.integers(0, len(P), 50000)
print(tag, "edge/random-pair ratio", round(float(np.median(el) / np.median(np.hypot(*(P[i] - P[j]).T))), 3), "extent", np.ptp(P, axis=0).round())
