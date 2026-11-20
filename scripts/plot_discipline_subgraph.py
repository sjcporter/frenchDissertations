#!/usr/bin/env python3
"""Plot the advisor co-supervision subgraph for one discipline label.

The subgraph is fragmented, so each connected component is laid out on its own (spring layout)
and the components are packed into a grid, largest first. Nodes are coloured by institution.
"""
from __future__ import annotations
import argparse, math
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--net", type=Path, required=True)
ap.add_argument("--discipline", required=True)
ap.add_argument("--slug", required=True)
a = ap.parse_args(); net = a.net.resolve()

n = pd.read_csv(net / "advisor_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
e = pd.read_csv(net / "advisor_edges.csv", dtype={"source": str, "target": str}, usecols=["source", "target", "weight"])
n = n[n.discipline == a.discipline].set_index("director_key")
e = e[e.source.isin(n.index) & e.target.isin(n.index)]
G = nx.Graph(); G.add_nodes_from(n.index)
for s, t, w in e.itertuples(index=False): G.add_edge(s, t, weight=w)
comps = sorted(nx.connected_components(G), key=len, reverse=True)
multi = [c for c in comps if len(c) > 1]; singles = [next(iter(c)) for c in comps if len(c) == 1]
print(f"{len(n)} advisors, {G.number_of_edges()} edges, {len(multi)} multi-node components, {len(singles)} isolated")

# lay out + pack: each component gets a square cell sized by sqrt(size)
pos: dict[str, tuple[float, float]] = {}
cells = []
for c in multi:
    sub = G.subgraph(c)
    p = nx.spring_layout(sub, weight="weight", seed=1, k=1.2 / math.sqrt(len(c)), iterations=200)
    xy = np.array(list(p.values())); xy -= xy.mean(0); span = max(np.ptp(xy, axis=0).max(), 1e-9)
    side = 1.2 + 0.9 * math.sqrt(len(c))
    cells.append((list(p.keys()), xy / span * side * 0.85, side))
W = 26.0; x = y = rowh = 0.0
for keys, xy, side in cells:           # simple shelf packing
    if x + side > W: x, y, rowh = 0.0, y - rowh - 0.4, 0.0
    for k, (px, py) in zip(keys, xy): pos[k] = (x + side / 2 + px, y - side / 2 + py)
    x += side + 0.4; rowh = max(rowh, side)
y -= rowh + 1.2; x = 0.0                # isolated advisors: dot grid underneath
for i, k in enumerate(singles):
    pos[k] = (0.4 + (i % 60) * 0.42, y - (i // 60) * 0.42)

top = n.institution.value_counts().head(14).index.tolist()
pal = dict(zip(top, plt.get_cmap("tab20").colors))
col = [pal.get(n.institution[k], (0.7, 0.7, 0.7)) for k in G.nodes]
fig, ax = plt.subplots(figsize=(16, 16 * 0.95), dpi=150)
nx.draw_networkx_edges(G, pos, ax=ax, width=[0.6 + 1.2 * (d["weight"] - 1) for *_, d in G.edges(data=True)], edge_color="#555", alpha=0.7)
sizes = [25 + 22 * n.n_theses[k] for k in G.nodes]
ax.scatter([pos[k][0] for k in G.nodes], [pos[k][1] for k in G.nodes], s=sizes, c=col, edgecolors="white", linewidths=0.4, zorder=3)
for c in multi[:12]:                    # label the most prolific advisors in the biggest components
    for k in sorted(c, key=lambda k: -n.n_theses[k])[:2]:
        ax.annotate(n.label[k], pos[k], fontsize=6.5, xytext=(3, 3), textcoords="offset points", zorder=4)
ax.set_aspect("equal"); ax.axis("off")
ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=pal[i], label=i) for i in top] + [plt.Line2D([], [], marker="o", ls="", color=(.7,) * 3, label="other")],
          loc="upper right", fontsize=8, frameon=False, title="Institution")
ax.set_title(f"{a.discipline}: advisors linked by co-supervision, 2020–2025 (node size = theses; isolated advisors at bottom)", fontsize=10)
out = net / f"advisor_{a.slug}.png"; fig.savefig(out, bbox_inches="tight"); print("wrote", out)
