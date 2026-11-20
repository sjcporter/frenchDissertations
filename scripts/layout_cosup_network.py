#!/usr/bin/env python3
"""BatchLayout of the co-supervision-only network (the 'supervisor graph'), aligned to the combined layout.

Used as the start state of the animation morph. Only the giant component can be laid out; the rest are
left out (the animation grows them in place). The result is rotated/scaled/translated (orthogonal Procrustes,
reflection allowed) onto the combined layout over the shared nodes so the morph travels as little as possible.
"""
from __future__ import annotations
import os

import argparse
import subprocess
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy import io

BL_DIR = Path(os.environ.get("BATCHLAYOUT_DIR", Path.home() / "batchlayout/BatchLayout/BatchLayoutCode"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", type=Path, required=True)
    ap.add_argument("--iter", type=int, default=600)
    ap.add_argument("--init", type=int, default=0)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--target", type=Path, default=None, help="Blender nodes CSV (id,x,y) whose rotated frame to align to; default combined layout")
    args = ap.parse_args()
    net = args.net.resolve()

    comb = pd.read_csv(net / "combined_layout_gcc.csv", dtype={"director_key": str}, keep_default_na=False, usecols=["director_key", "x", "y"])
    e = pd.read_csv(net / "combined_edges.csv", dtype={"source": str, "target": str})
    known = set(comb.director_key)
    e = e[e.type.isin(["cosupervision", "both"]) & e.source.isin(known) & e.target.isin(known)]
    e = e.assign(w=1 + np.log1p(e.cosupervised_theses.fillna(1)))
    G = nx.from_pandas_edgelist(e, "source", "target", ["w"])
    order = list(G.subgraph(max(nx.connected_components(G), key=len)).nodes())
    G0 = G.subgraph(order)
    print(f"cosupervision giant component: {len(order):,} nodes, {G0.number_of_edges():,} edges")

    mtx = net / "cosup_gcc.mtx"
    io.mmwrite(str(mtx), nx.to_scipy_sparse_array(G0, nodelist=order, weight="w"))
    out = net / f"{mtx.name}CACHEMINB256PARAOUT{args.iter}.txt"
    if not out.exists():
        cmd = [str(BL_DIR / "bin" / "BatchLayout"), "-input", str(mtx), "-output", str(net) + "/", "-iter", str(args.iter),
               "-batch", "256", "-algo", "2", "-init", str(args.init), "-threads", str(args.threads), "-weight", "1"]
        res = subprocess.run(cmd, cwd=BL_DIR, capture_output=True, text=True, timeout=6000)
        if res.returncode != 0:
            raise RuntimeError(res.stdout[-1500:] + res.stderr[-1500:])
    pos = pd.read_csv(out, header=None, sep="\t", names=["x", "y", "idx"])
    pos["director_key"] = [order[int(i) - 1] for i in pos.idx]
    pos = pos[["director_key", "x", "y"]]
    if args.target is not None:  # the Blender pipeline rotates/flips the layout, so align to its frame
        comb = pd.read_csv(args.target, dtype={"id": str}, usecols=["id", "x", "y"]).rename(columns={"id": "director_key"})

    # orthogonal Procrustes (allow reflection) of the cosup layout onto the combined layout
    m = pos.merge(comb, on="director_key", suffixes=("", "_c"))
    A, B = m[["x", "y"]].to_numpy(), m[["x_c", "y_c"]].to_numpy()
    ma, mb = A.mean(0), B.mean(0)
    A0, B0 = A - ma, B - mb
    U, S, Vt = np.linalg.svd(A0.T @ B0)
    R = U @ Vt
    scale = S.sum() / (A0 ** 2).sum()
    P = (pos[["x", "y"]].to_numpy() - ma) @ R * scale + mb
    pos["x"], pos["y"] = P[:, 0], P[:, 1]
    d0 = np.linalg.norm(B - mb, axis=1).mean()
    d1 = np.linalg.norm((A0 @ R * scale) - B0, axis=1).mean()
    print(f"mean travel after alignment {d1:.1f} vs mean radius {d0:.1f}; det(R)={np.linalg.det(R):+.0f}")
    pos.to_csv(net / "cosup_layout_gcc.csv", index=False)
    print("wrote", net / "cosup_layout_gcc.csv")


if __name__ == "__main__":
    main()
