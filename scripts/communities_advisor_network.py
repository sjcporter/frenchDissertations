#!/usr/bin/env python3
"""Leiden community detection on the advisor network, then re-plot the BatchLayout layout.

Communities are found on the whole network (weighted by shared theses). The plot shows the
giant component with only within-community edges, each node coloured by its community's
most common discipline.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import igraph as ig
import leidenalg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, required=True)
    ap.add_argument("--resolution", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ncolours", type=int, default=19, help="disciplines given their own colour; the rest are grey")
    ap.add_argument("--tag", default="")
    ap.add_argument("--layout", default="advisor_layout_gcc.csv", help="BatchLayout coordinates CSV in --net")
    args = ap.parse_args()
    net = args.net.resolve()

    nodes = pd.read_csv(net / "advisor_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
    edges = pd.read_csv(net / "advisor_edges.csv", dtype={"source": str, "target": str}, usecols=["source", "target", "weight"])
    idx = {k: i for i, k in enumerate(nodes.director_key)}
    g = ig.Graph(n=len(nodes), edges=[(idx[a], idx[b]) for a, b in zip(edges.source, edges.target)], directed=False)
    g.es["weight"] = edges.weight.tolist()

    part = leidenalg.find_partition(
        g, leidenalg.RBConfigurationVertexPartition, weights="weight", resolution_parameter=args.resolution, seed=args.seed, n_iterations=-1
    )
    nodes["community"] = part.membership
    size = nodes.community.value_counts()
    # rank communities by size so ids are stable and readable (0 = largest)
    rank = {c: r for r, c in enumerate(size.index)}
    nodes["community"] = nodes.community.map(rank)
    print(f"communities {nodes.community.nunique():,}; modularity {part.modularity:.3f}; resolution {args.resolution}")

    def top(s: pd.Series) -> str:
        s = s[s != ""]
        return s.value_counts().index[0] if len(s) else ""

    comm = nodes.groupby("community").agg(
        size=("director_key", "size"),
        top_discipline=("discipline", top),
        top_institution=("institution", top),
        n_theses=("n_theses", "sum"),
    )
    comm["top_discipline_share"] = nodes.groupby("community").apply(
        lambda d: (d.discipline == top(d.discipline)).mean(), include_groups=False
    ).round(3)
    comm.to_csv(net / f"advisor_communities{args.tag}.csv")
    nodes[["director_key", "community"]].to_csv(net / f"advisor_node_community{args.tag}.csv", index=False)
    print(comm.head(12).to_string())

    # ---- plot
    lay = pd.read_csv(net / args.layout, dtype={"director_key": str}, keep_default_na=False)
    lay = lay.drop(columns=[c for c in ("community",) if c in lay]).merge(nodes[["director_key", "community"]], on="director_key")
    lay["comm_disc"] = lay.community.map(comm.top_discipline)
    # colour by discipline, ranked by how many GCC nodes sit in communities topped by it
    ranked = lay.comm_disc.value_counts()
    ranked = ranked[ranked.index != ""].head(args.ncolours).index.tolist()
    pal = list(plt.get_cmap("tab20").colors)[: args.ncolours]
    colour = dict(zip(ranked, pal))
    lay["rgba"] = [colour.get(d, (0.65, 0.65, 0.65)) for d in lay.comm_disc]

    xy = lay.set_index("director_key")[["x", "y"]]
    comm_of = lay.set_index("director_key").community
    keep = edges[edges.source.isin(xy.index) & edges.target.isin(xy.index)]
    same = comm_of.loc[keep.source].values == comm_of.loc[keep.target].values
    intra = keep[same]
    print(f"edges in giant component {len(keep):,}; within-community {len(intra):,} ({100 * same.mean():.1f}%)")
    seg = np.stack([xy.loc[intra.source].to_numpy(), xy.loc[intra.target].to_numpy()], axis=1)
    ecol = [colour.get(d, (0.5, 0.5, 0.5)) + (0.35,) for d in comm_of.loc[intra.source].map(comm.top_discipline)]

    fig, ax = plt.subplots(figsize=(18, 18), dpi=150)
    ax.add_collection(LineCollection(seg, colors=ecol, linewidths=0.35))
    ax.scatter(lay.x, lay.y, s=1.5 + lay.n_theses.clip(upper=15) * 0.9, c=list(lay.rgba), linewidths=0, alpha=0.9)
    # label the largest communities at their centroid
    cen = lay.groupby("community")[["x", "y"]].median()
    for c in comm.index[:15]:
        if c in cen.index:
            ax.text(*cen.loc[c], f"{comm.loc[c, 'top_discipline']}\n({int(lay[lay.community == c].shape[0]):,})", fontsize=8, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.7))
    ax.set_xlim(lay.x.min(), lay.x.max())
    ax.set_ylim(lay.y.min(), lay.y.max())
    ax.set_aspect("equal")
    ax.axis("off")
    ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=colour[d], label=d) for d in ranked] + [plt.Line2D([], [], marker="o", ls="", color=(0.65,) * 3, label="other")],
              loc="lower left", fontsize=9, frameon=False, title="Community's top discipline")
    fig.savefig(net / f"advisor_gcc_communities{args.tag}.png", bbox_inches="tight")
    lay.drop(columns=["rgba"]).to_csv(net / f"advisor_layout_gcc_communities{args.tag}.csv", index=False)
    print("wrote", net / f"advisor_gcc_communities{args.tag}.png")


if __name__ == "__main__":
    main()
