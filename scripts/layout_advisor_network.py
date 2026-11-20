#!/usr/bin/env python3
"""First-pass BatchLayout of the advisor network's giant component, plus a PNG plot.

BatchLayout needs a connected, symmetric Matrix Market file, so we lay out the giant
component. Settings mirror the UniversityExplorer pipeline (algo 2, 600 iters, batch 256) but with random init: greedy init (-init 0) gave a structureless layout on this graph.
"""
from __future__ import annotations
import os

import argparse
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy import io

BL_DIR = Path(os.environ.get("BATCHLAYOUT_DIR", Path.home() / "batchlayout/BatchLayout/BatchLayoutCode"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, required=True, help="network directory with advisor_nodes/edges.csv")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--iter", type=int, default=600)
    ap.add_argument("--init", type=int, default=1, help="0 greedy (UniversityExplorer default), 1 random")
    ap.add_argument("--tag", default="", help="suffix for output files")
    args = ap.parse_args()
    args.net = args.net.resolve()

    nodes = pd.read_csv(args.net / "advisor_nodes.csv", dtype={"director_key": str})
    edges = pd.read_csv(args.net / "advisor_edges.csv", dtype={"source": str, "target": str}, usecols=["source", "target", "weight"])

    G = nx.from_pandas_edgelist(edges, "source", "target", ["weight"])
    gcc = max(nx.connected_components(G), key=len)
    G0 = G.subgraph(gcc).copy()
    order = list(G0.nodes())
    print(f"giant component: {len(order):,} nodes, {G0.number_of_edges():,} edges")

    mtx = args.net / "advisor_gcc.mtx"
    io.mmwrite(str(mtx), nx.to_scipy_sparse_array(G0, nodelist=order))

    cmd = [str(BL_DIR / "bin" / "BatchLayout"), "-input", str(mtx), "-output", str(args.net) + "/",
           "-iter", str(args.iter), "-batch", "256", "-algo", "2", "-init", str(args.init), "-threads", str(args.threads), "-weight", "1"]
    out = args.net / f"{mtx.name}CACHEMINB256PARAOUT{args.iter}.txt"
    tag = args.tag
    if out.exists():
        print("reusing existing layout", out.name)
        res = None
    else:
        print(" ".join(cmd))
        res = subprocess.run(cmd, cwd=BL_DIR, capture_output=True, text=True, timeout=3000)
    if res is not None and res.returncode != 0:
        raise RuntimeError(f"BatchLayout failed ({res.returncode}):\n{res.stdout[-1500:]}\n{res.stderr[-1500:]}")

    pos = pd.read_csv(out, header=None, sep="\t", names=["x", "y", "idx"])
    if len(pos) != len(order):
        raise RuntimeError(f"layout rows {len(pos)} != nodes {len(order)}")
    # The third column is the node index; map it back rather than assuming row order.
    pos["director_key"] = [order[int(i) - 1] for i in pos["idx"]]
    lay = pos[["director_key", "x", "y"]].merge(nodes, on="director_key", how="left")
    lay.to_csv(args.net / f"advisor_layout_gcc{tag}.csv", index=False)

    # plot: edges light, nodes sized by theses, coloured by discipline group (top 12 + other)
    xy = lay.set_index("director_key")[["x", "y"]]
    seg = np.array([[xy.loc[a].values, xy.loc[b].values] for a, b in G0.edges()])
    top = lay["discipline"].value_counts().head(12).index
    cmap = plt.get_cmap("tab20")
    colour = {d: cmap(i) for i, d in enumerate(top)}
    cols = [colour.get(d, (0.6, 0.6, 0.6, 1)) for d in lay["discipline"]]

    fig, ax = plt.subplots(figsize=(18, 18), dpi=150)
    from matplotlib.collections import LineCollection

    ax.add_collection(LineCollection(seg, colors=(0, 0, 0, 0.06), linewidths=0.2))
    ax.scatter(lay.x, lay.y, s=1 + lay["n_theses"].clip(upper=15) * 0.8, c=cols, linewidths=0, alpha=0.85)
    ax.set_xlim(lay.x.min(), lay.x.max())
    ax.set_ylim(lay.y.min(), lay.y.max())
    ax.set_aspect("equal")
    ax.axis("off")
    ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=colour[d], label=d) for d in top], loc="lower left", fontsize=9, frameon=False)
    fig.savefig(args.net / f"advisor_gcc_layout{tag}.png", bbox_inches="tight")
    print("wrote", args.net / f"advisor_gcc_layout{tag}.png")


if __name__ == "__main__":
    main()
