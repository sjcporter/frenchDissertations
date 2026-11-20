#!/usr/bin/env python3
"""BatchLayout of the largest components of one discipline's advisor subgraph, plotted side by side by institution.

Each component is laid out separately by BatchLayout (it needs a connected graph) and the
components are placed left to right, largest first.
"""
from __future__ import annotations
import os
import argparse, subprocess, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx, numpy as np, pandas as pd
from matplotlib.collections import LineCollection
from scipy import io

BL = Path(os.environ.get("BATCHLAYOUT_DIR", Path.home() / "batchlayout/BatchLayout/BatchLayoutCode"))
ap = argparse.ArgumentParser()
ap.add_argument("--net", type=Path, required=True); ap.add_argument("--discipline", required=True); ap.add_argument("--slug", required=True)
ap.add_argument("--init", type=int, default=0); ap.add_argument("--iter", type=int, default=600)
ap.add_argument("--ncomp", type=int, default=2, help="how many of the largest components to draw")
ap.add_argument("--gap", type=float, default=0.08, help="gap between components as a fraction of total width")
a = ap.parse_args(); net = a.net.resolve()

n = pd.read_csv(net / "advisor_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
n = n[n.discipline == a.discipline].set_index("director_key")
e = pd.read_csv(net / "advisor_edges.csv", dtype={"source": str, "target": str}, usecols=["source", "target", "weight"])
e = e[e.source.isin(n.index) & e.target.isin(n.index)]
G = nx.Graph(); G.add_nodes_from(n.index); G.add_weighted_edges_from(e.itertuples(index=False))
comps = sorted(nx.connected_components(G), key=len, reverse=True)
print(f"{len(n):,} advisors, {G.number_of_edges():,} edges, {len(comps):,} components; sizes {[len(c) for c in comps[:6]]}; isolated {sum(len(c)==1 for c in comps):,}")


def layout(comp: set[str], k: int) -> pd.DataFrame:
    sub = G.subgraph(comp).copy(); order = list(sub.nodes())
    mtx = net / f"advisor_{a.slug}_c{k}.mtx"; io.mmwrite(str(mtx), nx.to_scipy_sparse_array(sub, nodelist=order))
    outp = net / f"{mtx.name}CACHEMINB256PARAOUT{a.iter}.txt"; outp.unlink(missing_ok=True)
    r = subprocess.run([str(BL / "bin/BatchLayout"), "-input", str(mtx), "-output", f"{net}/", "-iter", str(a.iter), "-batch", "256", "-algo", "2",
                        "-init", str(a.init), "-threads", "16", "-weight", "1"], cwd=BL, capture_output=True, text=True, timeout=3000)
    if r.returncode: sys.exit(f"BatchLayout failed on component {k} ({r.returncode}):\n{r.stdout[-600:]}\n{r.stderr[-400:]}")
    P = pd.read_csv(outp, header=None, sep="\t").sort_values(2)[[0, 1]].to_numpy()
    A = io.mmread(str(mtx)).tocoo(); m = A.row < A.col
    el = np.hypot(*(P[A.row[m]] - P[A.col[m]]).T); rng = np.random.default_rng(0); i, j = rng.integers(0, len(P), 50000), rng.integers(0, len(P), 50000)
    print(f"component {k}: {len(order):,} nodes, {sub.number_of_edges():,} edges, edge/random-pair ratio {np.median(el) / np.median(np.hypot(*(P[i] - P[j]).T)):.3f}")
    return pd.DataFrame({"director_key": order, "x": P[:, 0], "y": P[:, 1], "component": k})


parts = [layout(c, k) for k, c in enumerate(comps[: a.ncomp])]
# place components left to right, vertically centred, with a gap
total_w = sum(np.ptp(p.x) for p in parts); x0 = 0.0
for p in parts:
    p["x"] = p.x - p.x.min() + x0; p["y"] = p.y - (p.y.min() + p.y.max()) / 2
    x0 = p.x.max() + a.gap * total_w
lay = pd.concat(parts).merge(n.reset_index(), on="director_key"); lay.to_csv(net / f"advisor_{a.slug}_layout.csv", index=False)
xy = lay.set_index("director_key")[["x", "y"]]
seg = np.array([[xy.loc[s].values, xy.loc[t].values] for s, t in G.subgraph(lay.director_key).edges()])
top = lay.institution.value_counts().head(19).index.tolist(); pal = dict(zip(top, plt.get_cmap("tab20").colors))

fig, ax = plt.subplots(figsize=(22, 13), dpi=150)
ax.add_collection(LineCollection(seg, colors=(0, 0, 0, 0.12), linewidths=0.3))
ax.scatter(lay.x, lay.y, s=2 + lay.n_theses.clip(upper=15) * 1.2, c=[pal.get(v, (.65, .65, .65)) for v in lay.institution], linewidths=0, alpha=0.9)
ax.set_xlim(lay.x.min(), lay.x.max()); ax.set_ylim(lay.y.min(), lay.y.max()); ax.set_aspect("equal"); ax.axis("off")
for p in parts:
    ax.text(p.x.mean(), lay.y.max(), f"component {int(p.component.iloc[0]) + 1}: {len(p):,} advisors", ha="center", va="bottom", fontsize=10)
ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=pal[k], label=k) for k in top] + [plt.Line2D([], [], marker="o", ls="", color=(.65,) * 3, label="other")],
          loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9, frameon=False, title="Institution")  # outside the plot
shown = len(lay); ax.set_title(f"{a.discipline}: the {a.ncomp} largest components ({shown:,} of {len(n):,} advisors)", fontsize=12, pad=18)
fig.savefig(net / f"advisor_{a.slug}.png", bbox_inches="tight"); print("wrote", net / f"advisor_{a.slug}.png")
