"""Full pipeline: load original -> merge by material -> decimate
proportionally to a total face budget -> split normals at a crease angle ->
measure Hausdorff distance -> write meshes/visual_lowpoly/<name>.dae.
"""
import sys

import numpy as np
import trimesh

from collada_write import write_collada
from mesh_pipeline import decimate, hausdorff_fraction_of_bbox, split_normals


def color_key(geom):
    mat = getattr(geom.visual, 'material', None)
    if mat is None:
        return (1.0, 1.0, 1.0, 1.0)
    bcf = np.array(mat.baseColorFactor, dtype=float)
    if bcf.max() > 1.5:
        bcf = bcf / 255.0
    return tuple(np.round(bcf, 4))


def build(src_path: str, dst_path: str, total_target_faces: int,
          skip_floor: int = 1500, min_target: int = 200, crease_deg: float = 40.0):
    scene = trimesh.load(src_path, process=False)
    if not isinstance(scene, trimesh.Scene):
        raise SystemExit(f'{src_path}: not a multi-geometry scene')

    groups = {}
    for name, geom in scene.geometry.items():
        groups.setdefault(color_key(geom), []).append(geom)

    merged_groups = {}
    total_faces_orig = 0
    for color, geoms in groups.items():
        m = trimesh.util.concatenate(geoms)
        merged_groups[color] = m
        total_faces_orig += len(m.faces)

    print(f'{src_path}: {len(scene.geometry)} geoms -> {len(groups)} materials, '
          f'{total_faces_orig} faces total -> budget {total_target_faces}')

    out_meshes = []
    worst_hausdorff_pct = 0.0
    for color, m in sorted(merged_groups.items(), key=lambda kv: -len(kv[1].faces)):
        n_orig = len(m.faces)
        if n_orig < skip_floor:
            v_out, f_out = np.asarray(m.vertices), np.asarray(m.faces)
            print(f'  color {color}: {n_orig} faces, below skip floor -- kept at full detail')
        else:
            target = max(min_target, round(total_target_faces * n_orig / total_faces_orig))
            v_out, f_out = decimate(np.asarray(m.vertices), np.asarray(m.faces), target)
            print(f'  color {color}: {n_orig} -> {len(f_out)} faces (target {target})')

            hd, diag, frac, stats = hausdorff_fraction_of_bbox(
                np.asarray(m.vertices), np.asarray(m.faces), v_out, f_out)
            worst_hausdorff_pct = max(worst_hausdorff_pct, frac * 100)
            print(f'    Hausdorff: max {stats["max_mm"]:.2f}mm ({stats["max_pct"]:.2f}% of '
                  f'{stats["diag_mm"]:.0f}mm diag), p99 {stats["p99_mm"]:.2f}mm '
                  f'({stats["p99_pct"]:.2f}%), median {stats["median_mm"]:.2f}mm '
                  f'({stats["median_pct"]:.2f}%)')

        v_split, n_split, f_split = split_normals(v_out, f_out, crease_deg=crease_deg)
        name = 'mat_{:.0f}_{:.0f}_{:.0f}'.format(*(np.array(color[:3]) * 255))
        out_meshes.append({
            'name': name, 'vertices': v_split, 'normals': n_split, 'faces': f_split,
            'color': color[:3],
        })

    total_out = sum(len(m['faces']) for m in out_meshes)
    write_collada(dst_path, out_meshes)
    print(f'  TOTAL: {total_faces_orig} -> {total_out} faces '
          f'({100*(1-total_out/total_faces_orig):.1f}% reduction)')
    print(f'  worst-case Hausdorff (any decimated group): {worst_hausdorff_pct:.2f}% of bbox diagonal')
    print(f'  wrote {dst_path}')
    return total_out, worst_hausdorff_pct


if __name__ == '__main__':
    src, dst, budget = sys.argv[1], sys.argv[2], int(sys.argv[3])
    build(src, dst, budget)
