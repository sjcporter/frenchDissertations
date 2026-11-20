#!/usr/bin/env python3
"""Combine ORCID co-author edges and co-supervision edges at the director (PPN) level.

Edge types: coauthor (weight = DOIs shared, ORCID 2026 public file), cosupervision (weight = theses shared).
A pair linked both ways gets one row with both weights.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import networkx as nx
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--data", type=Path, required=True)   # output_2005
ap.add_argument("--net", type=Path, required=True)    # supervision network dir
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args(); a.out.mkdir(exist_ok=True, parents=True)

cand = pd.read_csv(a.data / "fr_director_orcid_candidates.csv", dtype=str, keep_default_na=False).drop_duplicates(["ppn", "orcid"])
o2p = cand.groupby("orcid").ppn.apply(list)
co = pd.read_csv(a.data / "fr_coauthor_edges_orcid.csv", dtype={"a": str, "b": str})
rows = []
for x, y, s in co.itertuples(index=False):
    for p in o2p.get(x, []):
        for q in o2p.get(y, []):
            if p != q:
                rows.append((min(p, q), max(p, q), s))
ca = pd.DataFrame(rows, columns=["source", "target", "coauthor_dois"]).groupby(["source", "target"], as_index=False).coauthor_dois.max()

sv = pd.read_csv(a.net / "advisor_edges.csv", dtype={"source": str, "target": str}, usecols=["source", "target", "weight"])
sv["source"], sv["target"] = sv[["source", "target"]].min(axis=1), sv[["source", "target"]].max(axis=1)
sv = sv.rename(columns={"weight": "cosupervised_theses"})
E = ca.merge(sv, on=["source", "target"], how="outer").fillna({"coauthor_dois": 0, "cosupervised_theses": 0})
E["type"] = ["both" if c and s else "coauthor" if c else "cosupervision" for c, s in zip(E.coauthor_dois, E.cosupervised_theses)]
E.to_csv(a.out / "combined_edges.csv", index=False)

nodes = pd.read_csv(a.net / "advisor_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
nodes["has_orcid"] = nodes.director_key.isin(set(cand.ppn))
nodes.to_csv(a.out / "combined_nodes.csv", index=False)

def stats(name, edges):
    G = nx.Graph(); G.add_nodes_from(nodes.director_key); G.add_edges_from(zip(edges.source, edges.target))
    cc = sorted(nx.connected_components(G), key=len, reverse=True); big = cc[0]
    noorc = set(nodes.director_key[~nodes.has_orcid])
    print(f"{name:14s} edges {G.number_of_edges():>8,} | linked nodes {sum(1 for n in G if G.degree(n)):>7,} | giant {len(big):>7,} ({100*len(big)/len(nodes):.1f}%) | no-ORCID in giant {len(big & noorc):>6,} of {len(noorc):,}")

print(f"{len(nodes):,} directors ({nodes.has_orcid.sum():,} with ORCID), edge types:", E.type.value_counts().to_dict())
stats("coauthor", E[E.coauthor_dois > 0]); stats("cosupervision", E[E.cosupervised_theses > 0]); stats("combined", E)
