# visual_lowpoly

Decimated, merged-by-material visual meshes for `limo_base.dae` and
`limo_wheel.dae`. Generated 2026-09-21. Regenerate with:

```bash
python3 build_lowpoly.py <path-to-original>/limo_base.dae limo_base.dae 75000
python3 build_lowpoly.py <path-to-original>/limo_wheel.dae limo_wheel.dae 15000
```

Requires `trimesh`, `pycollada==0.8` (0.9.x needs Python 3.9+ for
`functools.cache`, this workspace runs 3.8), and `open3d` (has aarch64
wheels; `fast_simplification`/`pymeshlab` do not, and pymeshlab in
particular has no aarch64 PyPI wheel at all).

Pipeline: merge every `<geometry>` sharing a material's base color into one
mesh (lossless, cuts limo_base.dae's draw calls 1619->4, limo_wheel.dae's
3->1) -> quadric edge collapse decimation per merged group, proportional to
that group's share of the total face budget, groups under 1500 faces kept at
full detail -> split normals at a 40 degree crease angle so decimated flat/
machined surfaces read as faceted rather than smoothed/melted -> write back
out as COLLADA 1.4.1 (trimesh can read .dae via pycollada but not write it,
so `collada_write.py` is a small custom writer -- switching the shipped
format to something trimesh could export, e.g. glTF, was considered and
rejected: no confirmation the visualization bridge's loader handles anything but dae/
stl, and this pipeline already works end to end for dae).

Last run's numbers:

| | faces before | faces after | reduction | worst-case Hausdorff |
|---|---:|---:|---:|---:|
| limo_base.dae | 755,790 | 75,730 | 90.0% | 2.22% of bbox diagonal |
| limo_wheel.dae | 140,290 | 15,000 | 89.3% | 3.33% of bbox diagonal |

Both worst-case numbers are a single rare, highly localized outlier point
(open3d's `compute_point_cloud_distance`, 20k-sample two-sided Hausdorff);
median error across both meshes is under 0.5% of bounding-box diagonal, and
99th-percentile is under 2%. `limo_wheel.dae`'s original is unusually
fragmented -- 87,954 separate connected components before decimation -- which
is almost certainly why its worst case is higher than limo_base.dae's,
despite a smaller face-count cut.
