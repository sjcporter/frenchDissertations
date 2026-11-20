#!/usr/bin/env python3
"""Prepare the UniversityExplorer Blender inputs from the combined French director network.

Reuses graph-pipeline/process_graph.py (draw_network_c, get_node_height) unchanged, feeding it:
  nodes   = directors; FOR1 = broad field (discipline_fields.py); publications = 10 x theses;
            'current_research_org' = 'orcid' for directors with an ORCID (drawn as circles,
            the template's 'search' highlight), blank otherwise (diamonds)
  layout  = existing BatchLayout coordinates (combined_layout_gcc.csv); the sfdp overlap step is skipped
  clusters= Leiden communities (combined_node_community.csv), small ones folded into the neighbouring
            community they are most strongly linked to

Writes <out>/<asset>/{summary,<asset>testbundleNodes,<asset>fulltestbundle,<asset>cluster_details}.csv
and a preview PNG, in the layout geonodes_*.py expects.
"""
from __future__ import annotations
import os

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import networkx as nx
import numpy as np
import pandas as pd

PIPELINE = Path(os.environ.get("UE_PIPELINE", Path.home() / "Documents/UniversityExplorer/graph-pipeline"))
sys.path.insert(0, str(PIPELINE))
sys.path.insert(0, str(Path(__file__).parent))
import process_graph as pg  # noqa: E402
from discipline_fields import field_of  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, default=Path("network_2005_2025"))
    ap.add_argument("--out", type=Path, default=Path("blender"))
    ap.add_argument("--asset", default="fr-directors-2005-2025")
    ap.add_argument("--min-cluster", type=int, default=100, help="communities smaller than this are folded into neighbours")
    ap.add_argument("--sub-resolution", type=float, default=0.0, help="Leiden resolution for sub-clusters inside each community (0 = no sub-clusters)")
    ap.add_argument("--min-sub", type=int, default=150, help="sub-clusters smaller than this are folded into a sibling")
    ap.add_argument("--limit", type=int, default=0, help="debug: keep only the N highest-degree nodes' neighbourhood (0 = all)")
    args = ap.parse_args()
    net = args.net.resolve()
    out = args.out.resolve() / args.asset
    out.mkdir(parents=True, exist_ok=True)

    nodes = pd.read_csv(net / "combined_nodes.csv", dtype={"director_key": str}, keep_default_na=False)
    edges = pd.read_csv(net / "combined_edges.csv", dtype={"source": str, "target": str})
    lay = pd.read_csv(net / "combined_layout_gcc.csv", dtype={"director_key": str}, usecols=["director_key", "x", "y"])
    comm = pd.read_csv(net / "combined_node_community.csv", dtype={"director_key": str}).set_index("director_key").community

    known = set(nodes.director_key) & set(lay.director_key)
    edges = edges[edges.source.isin(known) & edges.target.isin(known)].copy()
    edges["weight"] = 1 + np.log1p(edges.coauthor_dois.fillna(0) + edges.cosupervised_theses.fillna(0))
    G = nx.from_pandas_edgelist(edges, "source", "target", ["weight"])
    G0 = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    if args.limit:
        keep = sorted(G0.degree, key=lambda t: -t[1])[: args.limit]
        G0 = G0.subgraph(max(nx.connected_components(G0.subgraph([k for k, _ in keep])), key=len)).copy()
    print(f"graph {G0.number_of_nodes():,} nodes, {G0.number_of_edges():,} edges")

    nd = nodes[nodes.director_key.isin(G0.nodes)].copy()
    nd["community"] = nd.director_key.map(comm)

    # --- clusters: fold small communities into the neighbouring large one with most edge weight
    size = nd.community.value_counts()
    big = set(size[size >= args.min_cluster].index)
    cl = nd.set_index("director_key").community.to_dict()
    for _ in range(5):
        moved = 0
        for n in [k for k, c in cl.items() if c not in big]:
            tally: dict[int, float] = {}
            for m, d in G0[n].items():
                if cl[m] in big:
                    tally[cl[m]] = tally.get(cl[m], 0) + d["weight"]
            if tally:
                cl[n] = max(tally, key=tally.get)
                moved += 1
        if not moved:
            break
    nd["community"] = nd.director_key.map(cl)
    left = ~nd.community.isin(big)
    print(f"clusters kept {len(big)}; nodes still in small communities {left.sum():,} (dropped from rendering)")
    nd = nd[~left]
    G0 = G0.subgraph(nd.director_key).copy()
    G0 = G0.subgraph(max(nx.connected_components(G0), key=len)).copy()
    nd = nd[nd.director_key.isin(G0.nodes)]

    # --- sub-clusters: Leiden again inside each parent community, small ones folded into a sibling
    nd["parent"] = nd.community
    if args.sub_resolution > 0:
        import igraph as ig
        import leidenalg
        sub: dict[str, str] = {}
        for par, grp in nd.groupby("parent"):
            keys = list(grp.director_key)
            H = G0.subgraph(keys)
            ix = {k: i for i, k in enumerate(keys)}
            g = ig.Graph(n=len(keys), edges=[(ix[a], ix[b]) for a, b in H.edges], directed=False)
            part = leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition,
                                            weights=[d["weight"] for *_, d in H.edges(data=True)],
                                            resolution_parameter=args.sub_resolution, seed=42, n_iterations=-1)
            m = dict(zip(keys, part.membership))
            sz = pd.Series(part.membership).value_counts()
            ok = set(sz[sz >= args.min_sub].index) or {sz.index[0]}
            for _ in range(5):
                for k in [k for k in keys if m[k] not in ok]:
                    tally: dict[int, float] = {}
                    for q, d in H[k].items():
                        if m[q] in ok:
                            tally[m[q]] = tally.get(m[q], 0) + d["weight"]
                    if tally:
                        m[k] = max(tally, key=tally.get)
            for k in keys:
                sub[k] = f"{par}.{m[k] if m[k] in ok else min(ok)}"
        nd["community"] = nd.director_key.map(sub)
        print(f"sub-clusters: {nd.community.nunique()} inside {nd.parent.nunique()} communities")

    # --- broad field; unmatched labels take their cluster's modal field
    nd["field"] = nd.discipline.map(field_of)
    modal = nd[nd.field != ""].groupby("community").field.agg(lambda s: s.value_counts().index[0])
    nd["field"] = [f if f else modal.get(c, "44") for f, c in zip(nd.field, nd.community)]

    researchers = pd.DataFrame({
        "id": nd.director_key.values,
        "current_research_org": np.where(nd.has_orcid.astype(str) == "True", "orcid", ""),
        "last_name": nd.label.values,
        "total_publications": nd.n_theses.values,
        "publications": (10 * nd.n_theses.astype(int)).values,
        "first_publication_year": nd.first_year.values,
        "FOR1": nd.field.values,
        "FOR": nd.field.values,
        "country_code": "FR", "state_code": "",
        "institution_name": nd.institution.values,
        "discipline": nd.discipline.values,
        "n_theses": nd.n_theses.values,
    })
    clusters = pd.DataFrame({"cluster_id": nd.community.astype("category").cat.codes.values, "coupling": nd.director_key.values})
    pos = lay.set_index("director_key").loc[list(G0.nodes)].apply(lambda r: (float(r.x), float(r.y)), axis=1).to_dict()
    nx.set_node_attributes(G0, pos, "pos")

    fors_present = {c for c in researchers.FOR1.unique()}
    fors = [str(c) for c, _ in pg.FOR_PARTITION if str(c) in fors_present]
    cluster_details = pg.get_node_height(clusters, researchers)
    code_of = dict(zip(clusters.coupling, clusters.cluster_id))
    parent_of = nd.assign(cid=nd.director_key.map(code_of)).groupby("cid").parent.first()
    cluster_details["parent"] = cluster_details.cluster_id.map(parent_of)
    cluster_details.drop_duplicates(subset="cluster_id").to_csv(out / f"{args.asset}cluster_details.csv")

    scope = SimpleNamespace(type="grid", grid_id="orcid", asset_id=args.asset, country_code="FR", admin1_code="")
    display = "French thesis supervisors 2005-2025"
    ax, posC, fig, hb_clusters, node_details = pg.draw_network_c(
        G0, pos, clusters, researchers, pg.FOR_ORDER, fors, display, scope, str(out),
        cluster_details=cluster_details, initial_bandwidth=pg.INITIAL_BANDWIDTH, linewidth=pg.LINEWIDTH,
        alpha=pg.ALPHA, variant_label="", window_label="2005–2025")

    pd.DataFrame([dict(org_name=display, display_name=display, scope_type="grid", asset_id=args.asset, variant="baseline",
                       window="2005-2025", percentage=100.0)]).to_csv(out / "summary.csv")
    cl_nodes = clusters.rename(columns={"coupling": "id"}).merge(node_details, on="id")
    cl_nodes.to_csv(out / f"{args.asset}testbundleNodes.csv")
    order = pg.get_cluster_order(clusters, researchers, "FOR1").merge(
        pg.get_cluster_order(clusters, researchers, "FOR")[["cluster_id", "FOR"]], on="cluster_id", how="left")
    cleaned = []
    for i, b in enumerate(hb_clusters):
        b["cluster_id"] = i
        cleaned.append(b.merge(order[["cluster_id", "FOR1", "FOR"]], on="cluster_id", how="left"))
    if cleaned:
        pd.concat(cleaned).to_csv(out / f"{args.asset}fulltestbundle.csv")
    print("wrote", out, "| clusters bundled:", len(hb_clusters))


if __name__ == "__main__":
    main()
