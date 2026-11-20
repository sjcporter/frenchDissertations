#!/usr/bin/env python3
"""Build the national advisor co-supervision network.

Nodes: thesis directors. Edge: two directors who co-supervised at least one thesis in the
year window; weight = number of distinct theses they share.
"""
from __future__ import annotations

import argparse
import itertools
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import pandas as pd


def top(series: pd.Series) -> str:
    s = series.dropna()
    s = s[s != ""]
    return s.value_counts().index[0] if len(s) else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="directory holding the output_2005 tables")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--from-year", type=int, default=2020)
    ap.add_argument("--to-year", type=int, default=2025)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    edges = pd.read_csv(args.data / "supervision_edges.csv", dtype=str, keep_default_na=False)
    theses = pd.read_csv(args.data / "theses.csv", dtype=str, keep_default_na=False, usecols=["nnt", "institution"])
    persons = pd.read_csv(args.data / "persons.csv", dtype=str, keep_default_na=False).set_index("person_key")
    orcid = pd.read_csv(args.data / "ppn_orcid.csv", dtype=str, keep_default_na=False).set_index("ppn")["orcid"]

    edges["yr"] = edges["year"].astype(int)
    edges = edges[(edges.yr >= args.from_year) & (edges.yr <= args.to_year)]
    # one row per (thesis, director): supervision_edges has one row per author too
    td = edges.drop_duplicates(["nnt", "director_key"]).merge(theses.drop_duplicates("nnt"), on="nnt", how="left")
    print(f"{td.nnt.nunique():,} theses, {td.director_key.nunique():,} directors, {args.from_year}-{args.to_year}")

    # co-supervision pairs
    pair_theses: dict[tuple[str, str], set[str]] = defaultdict(set)
    for nnt, grp in td.groupby("nnt")["director_key"]:
        for a, b in itertools.combinations(sorted(set(grp)), 2):
            pair_theses[(a, b)].add(nnt)

    G = nx.Graph()
    for key, grp in td.groupby("director_key"):
        p = persons.loc[key] if key in persons.index else None
        G.add_node(
            key,
            label=f"{p['prenom']} {p['nom']}".strip() if p is not None else key,
            n_theses=int(grp.nnt.nunique()),
            first_year=int(grp.yr.min()),
            last_year=int(grp.yr.max()),
            institution=top(grp["institution"]),
            discipline=top(grp["discipline"]),
            orcid=orcid.get(key, ""),
            key_kind="ppn" if key[:1].isdigit() else "name",
        )
    for (a, b), ts in pair_theses.items():
        G.add_edge(a, b, weight=len(ts), theses=";".join(sorted(ts)))

    # node metrics
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    comp_of = {n: i for i, c in enumerate(comps) for n in c}
    nx.set_node_attributes(G, {n: {"degree": G.degree(n), "w_degree": G.degree(n, weight="weight"), "component": comp_of[n]} for n in G}, )
    giant = G.subgraph(comps[0])
    gcc_deg = nx.degree_centrality(giant)
    nx.set_node_attributes(G, {n: round(v, 6) for n, v in gcc_deg.items()}, "degree_centrality_gcc")

    nodes = pd.DataFrame.from_dict(dict(G.nodes(data=True)), orient="index").rename_axis("director_key").reset_index()
    nodes.to_csv(args.out / "advisor_nodes.csv", index=False)
    pd.DataFrame([{"source": a, "target": b, "weight": d["weight"], "theses": d["theses"]} for a, b, d in G.edges(data=True)]).to_csv(
        args.out / "advisor_edges.csv", index=False
    )
    H = G.copy()
    for _, _, d in H.edges(data=True):
        d.pop("theses", None)  # keep the GEXF small
    nx.write_gexf(H, args.out / "advisor_network.gexf")

    sizes = [len(c) for c in comps]
    nonisolated = sum(1 for n in G if G.degree(n) > 0)
    print(f"nodes {G.number_of_nodes():,}  edges {G.number_of_edges():,}  with >=1 co-advisor {nonisolated:,}")
    print(f"components {len(comps):,} (excluding singletons {sum(1 for s in sizes if s > 1):,}); giant {sizes[0]:,} ({100 * sizes[0] / G.number_of_nodes():.1f}% of nodes)")
    print("next largest components:", sizes[1:6])
    print("edge weight distribution:", dict(Counter(min(d['weight'], 5) for *_, d in G.edges(data=True))))
    print("top by weighted degree:")
    print(nodes.sort_values("w_degree", ascending=False).head(8)[["label", "institution", "discipline", "n_theses", "degree", "w_degree"]].to_string(index=False))


if __name__ == "__main__":
    main()
