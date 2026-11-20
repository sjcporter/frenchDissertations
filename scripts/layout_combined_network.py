#!/usr/bin/env python3
"""BatchLayout of the combined ORCID co-author + co-supervision network (giant component).

Edge weight for layout = 1 + log1p(coauthor_dois + cosupervised_theses), so prolific
co-author pairs do not dominate. Plot: edges coloured by type (co-author, co-supervision,
both), nodes coloured by ORCID presence and sized by theses supervised.
"""
from __future__ import annotations
import os

import argparse
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from scipy import io

BL_DIR = Path(os.environ.get("BATCHLAYOUT_DIR", Path.home() / "batchlayout/BatchLayout/BatchLayoutCode"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--iter", type=int, default=600)
    ap.add_argument("--init", type=int, default=0)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    net = args.net.resolve()

    nodes = pd.read_csv(net / "combined_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
    edges = pd.read_csv(net / "combined_edges.csv", dtype={"source": str, "target": str})
    known = set(nodes.director_key)  # drop co-author edges to ORCID PPNs outside the 2005-2025 director set
    edges = edges[edges.source.isin(known) & edges.target.isin(known)].copy()
    edges["w"] = 1 + np.log1p(edges.coauthor_dois.fillna(0) + edges.cosupervised_theses.fillna(0))

    G = nx.from_pandas_edgelist(edges, "source", "target", ["w", "type"])
    order = list(G.subgraph(max(nx.connected_components(G), key=len)).nodes())
    G0 = G.subgraph(order)
    print(f"giant component: {len(order):,} nodes, {G0.number_of_edges():,} edges")

    mtx = net / f"combined_gcc{args.tag}.mtx"
    io.mmwrite(str(mtx), nx.to_scipy_sparse_array(G0, nodelist=order, weight="w"))
    out = net / f"{mtx.name}CACHEMINB256PARAOUT{args.iter}.txt"
    if out.exists():
        print("reusing", out.name)
    else:
        cmd = [str(BL_DIR / "bin" / "BatchLayout"), "-input", str(mtx), "-output", str(net) + "/", "-iter", str(args.iter),
               "-batch", "256", "-algo", "2", "-init", str(args.init), "-threads", str(args.threads), "-weight", "1"]
        print(" ".join(cmd))
        t = time.time()
        res = subprocess.run(cmd, cwd=BL_DIR, capture_output=True, text=True, timeout=6000)
        print(f"BatchLayout {time.time() - t:.0f}s")
        if res.returncode != 0:
            raise RuntimeError(f"BatchLayout failed ({res.returncode}):\n{res.stdout[-1500:]}\n{res.stderr[-1500:]}")

    pos = pd.read_csv(out, header=None, sep="\t", names=["x", "y", "idx"])
    if len(pos) != len(order):
        raise RuntimeError(f"layout rows {len(pos)} != nodes {len(order)}")
    pos["director_key"] = [order[int(i) - 1] for i in pos["idx"]]
    lay = pos[["director_key", "x", "y"]].merge(nodes, on="director_key", how="left")
    lay.to_csv(net / f"combined_layout_gcc{args.tag}.csv", index=False)

    xy = lay.set_index("director_key")[["x", "y"]]
    # quality: median edge length / median random-pair distance
    e = edges[edges.source.isin(xy.index) & edges.target.isin(xy.index)].copy()
    a, b = xy.loc[e.source].to_numpy(), xy.loc[e.target].to_numpy()
    rng = np.random.default_rng(0)
    r = xy.to_numpy()[rng.integers(0, len(xy), (200000, 2))]
    print(f"edge/random distance ratio {np.median(np.linalg.norm(a - b, axis=1)) / np.median(np.linalg.norm(r[:, 0] - r[:, 1], axis=1)):.3f}")

    style = {"cosupervision": ((0.20, 0.45, 0.80, 0.07), 0.15), "coauthor": ((0.90, 0.40, 0.10, 0.07), 0.15), "both": ((0.10, 0.10, 0.10, 0.35), 0.4)}
    fig, ax = plt.subplots(figsize=(20, 20), dpi=150)
    for t in ("cosupervision", "coauthor", "both"):  # 'both' drawn last, on top
        s = e[e.type == t]
        seg = np.stack([xy.loc[s.source].to_numpy(), xy.loc[s.target].to_numpy()], axis=1)
        ax.add_collection(LineCollection(seg, colors=[style[t][0]] * len(seg), linewidths=style[t][1]))
    has = lay.has_orcid.astype(str) == "True"
    size = 1.0 + lay.n_theses.clip(upper=15) * 0.8
    ax.scatter(lay.x[~has], lay.y[~has], s=size[~has], c=[(0.85, 0.2, 0.2)], linewidths=0, alpha=0.8)
    ax.scatter(lay.x[has], lay.y[has], s=size[has], c=[(0.1, 0.55, 0.3)], linewidths=0, alpha=0.8)
    ax.set_xlim(lay.x.min(), lay.x.max())
    ax.set_ylim(lay.y.min(), lay.y.max())
    ax.set_aspect("equal")
    ax.axis("off")
    H = plt.Line2D
    ax.legend(handles=[
        H([], [], marker="o", ls="", color=(0.1, 0.55, 0.3), label=f"director with ORCID ({has.sum():,})"),
        H([], [], marker="o", ls="", color=(0.85, 0.2, 0.2), label=f"director without ORCID ({(~has).sum():,})"),
        H([], [], color=style["cosupervision"][0][:3], label="co-supervision edge"),
        H([], [], color=style["coauthor"][0][:3], label="ORCID co-author edge"),
        H([], [], color="k", label="both"),
    ], loc="lower left", fontsize=11, frameon=False)
    fig.savefig(net / f"combined_gcc{args.tag}.png", bbox_inches="tight")
    print("wrote", net / f"combined_gcc{args.tag}.png")


if __name__ == "__main__":
    main()
