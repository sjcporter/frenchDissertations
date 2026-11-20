#!/usr/bin/env python3
"""Leiden communities on the combined co-author + co-supervision network.

Communities are found on all edges (weight = 1 + log1p(coauthor_dois + cosupervised_theses)),
then the existing BatchLayout is re-plotted with between-community edges hidden and nodes
coloured by their community's top discipline.
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


def top(s: pd.Series) -> str:
    s = s[s != ""]
    return s.value_counts().index[0] if len(s) else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, required=True)
    ap.add_argument("--resolution", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ncolours", type=int, default=19)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    net = args.net.resolve()

    nodes = pd.read_csv(net / "combined_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
    edges = pd.read_csv(net / "combined_edges.csv", dtype={"source": str, "target": str})
    known = set(nodes.director_key)  # drop co-author edges to ORCID PPNs outside the 2005-2025 director set
    edges = edges[edges.source.isin(known) & edges.target.isin(known)].copy()
    edges["w"] = 1 + np.log1p(edges.coauthor_dois.fillna(0) + edges.cosupervised_theses.fillna(0))
    idx = {k: i for i, k in enumerate(nodes.director_key)}
    g = ig.Graph(n=len(nodes), edges=[(idx[a], idx[b]) for a, b in zip(edges.source, edges.target)], directed=False)
    part = leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition, weights=edges.w.tolist(),
                                    resolution_parameter=args.resolution, seed=args.seed, n_iterations=-1)
    nodes["community"] = part.membership
    rank = {c: r for r, c in enumerate(nodes.community.value_counts().index)}
    nodes["community"] = nodes.community.map(rank)
    nodes["has_orcid"] = nodes.has_orcid.astype(str) == "True"
    print(f"communities {nodes.community.nunique():,}; modularity {part.modularity:.3f}; resolution {args.resolution}")

    comm = nodes.groupby("community").agg(size=("director_key", "size"), top_discipline=("discipline", top),
                                          top_institution=("institution", top), pct_orcid=("has_orcid", "mean"))
    comm["top_discipline_share"] = nodes.groupby("community").apply(lambda d: (d.discipline == top(d.discipline)).mean(), include_groups=False)
    comm.round(3).to_csv(net / f"combined_communities{args.tag}.csv")
    nodes[["director_key", "community"]].to_csv(net / f"combined_node_community{args.tag}.csv", index=False)
    print(comm.head(15).round(2).to_string())

    # how edge types split between and within communities
    c = nodes.set_index("director_key").community
    edges["same"] = c.loc[edges.source].to_numpy() == c.loc[edges.target].to_numpy()
    print("\nshare of edges within a community, by type:")
    print(edges.groupby("type").same.agg(["mean", "size"]).round(3).to_string())
    o = nodes.set_index("director_key").has_orcid
    edges["both_orcid"] = o.loc[edges.source].to_numpy() & o.loc[edges.target].to_numpy()
    print("\nwithin-community share by whether both ends have an ORCID:")
    print(edges.groupby("both_orcid").same.agg(["mean", "size"]).round(3).to_string())
    sizes = comm["size"]
    print(f"\ncommunities >=50 nodes: {(sizes >= 50).sum()} holding {sizes[sizes >= 50].sum():,} directors; singletons {(sizes == 1).sum():,}")

    # plot on the existing layout
    lay = pd.read_csv(net / "combined_layout_gcc.csv", dtype={"director_key": str}, keep_default_na=False)
    lay = lay[["director_key", "x", "y"]].merge(nodes[["director_key", "community", "n_theses"]], on="director_key")
    lay["disc"] = lay.community.map(comm.top_discipline)
    ranked = lay.disc.value_counts()
    ranked = ranked[ranked.index != ""].head(args.ncolours).index.tolist()
    colour = dict(zip(ranked, list(plt.get_cmap("tab20").colors)[: args.ncolours]))
    grey = (0.65,) * 3
    xy = lay.set_index("director_key")[["x", "y"]]
    intra = edges[edges.same & edges.source.isin(xy.index) & edges.target.isin(xy.index)]
    seg = np.stack([xy.loc[intra.source].to_numpy(), xy.loc[intra.target].to_numpy()], axis=1)
    ecol = [colour.get(d, (0.5,) * 3) + (0.25,) for d in c.loc[intra.source].map(comm.top_discipline)]
    fig, ax = plt.subplots(figsize=(20, 20), dpi=150)
    ax.add_collection(LineCollection(seg, colors=ecol, linewidths=0.2))
    ax.scatter(lay.x, lay.y, s=1 + lay.n_theses.clip(upper=15) * 0.8, c=[colour.get(d, grey) for d in lay.disc], linewidths=0, alpha=0.9)
    ax.set_xlim(lay.x.min(), lay.x.max()); ax.set_ylim(lay.y.min(), lay.y.max())
    ax.set_aspect("equal"); ax.axis("off")
    ax.legend(handles=[plt.Line2D([], [], marker="o", ls="", color=colour[d], label=d) for d in ranked] + [plt.Line2D([], [], marker="o", ls="", color=grey, label="other")],
              loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=10, frameon=False, title="Community's top discipline")
    fig.savefig(net / f"combined_gcc_communities{args.tag}.png", bbox_inches="tight")
    print("wrote", net / f"combined_gcc_communities{args.tag}.png")


if __name__ == "__main__":
    main()
