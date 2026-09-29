"""Decimate + split-normal + measure pipeline for the merged (by-material)
Limo meshes. Uses open3d's quadric edge collapse (confirmed on the real data
to hit exact face-count targets on this disconnected-CAD-shell geometry,
unlike fast_simplification -- see test_decimate_open3d.py), then splits
normals across a 40 degree crease angle so decimated flat/machined surfaces
don't read as smoothed/melted, then measures Hausdorff distance against the
pre-decimation mesh as a fraction of that mesh's bounding-box diagonal.
"""
import numpy as np
import open3d as o3d


def decimate(vertices, faces, target_faces):
    m = o3d.geometry.TriangleMesh()
    m.vertices = o3d.utility.Vector3dVector(vertices)
    m.triangles = o3d.utility.Vector3iVector(faces)
    if target_faces >= len(faces):
        return vertices, faces
    out = m.simplify_quadric_decimation(target_number_of_triangles=target_faces)
    out.remove_duplicated_vertices()
    out.remove_degenerate_triangles()
    out.remove_unreferenced_vertices()
    return np.asarray(out.vertices), np.asarray(out.triangles)


def split_normals(vertices, faces, crease_deg=40.0):
    """Duplicate vertices at hard edges so each output vertex has one normal.

    For each vertex, incident faces are greedily grouped: a face joins an
    existing group if its face normal is within crease_deg of that group's
    running average normal, else it starts a new group. Each group becomes
    one output vertex (duplicated from the original position) with that
    group's averaged, renormalized normal.
    """
    faces = np.asarray(faces)
    vertices = np.asarray(vertices)

    # face normals
    v0, v1, v2 = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    face_normals = np.cross(v1 - v0, v2 - v0)
    lens = np.linalg.norm(face_normals, axis=1, keepdims=True)
    lens[lens == 0] = 1.0
    face_normals = face_normals / lens

    cos_thresh = np.cos(np.radians(crease_deg))

    # vertex -> list of (face_idx, corner) it appears in
    incident = [[] for _ in range(len(vertices))]
    for fi, f in enumerate(faces):
        for corner in range(3):
            incident[f[corner]].append(fi)

    new_vertices = []
    new_normals = []
    # map (orig_vertex, face_idx) -> new_vertex_index
    remap = {}

    for vidx, face_list in enumerate(incident):
        if not face_list:
            continue
        groups = []  # list of [sum_normal, count, [face_idx,...]]
        for fi in face_list:
            n = face_normals[fi]
            placed = False
            for g in groups:
                avg = g[0] / np.linalg.norm(g[0])
                if np.dot(avg, n) >= cos_thresh:
                    g[0] = g[0] + n
                    g[1] += 1
                    g[2].append(fi)
                    placed = True
                    break
            if not placed:
                groups.append([n.copy(), 1, [fi]])

        for g in groups:
            avg_n = g[0] / np.linalg.norm(g[0])
            new_idx = len(new_vertices)
            new_vertices.append(vertices[vidx])
            new_normals.append(avg_n)
            for fi in g[2]:
                remap[(vidx, fi)] = new_idx

    new_faces = np.zeros_like(faces)
    for fi, f in enumerate(faces):
        for corner in range(3):
            new_faces[fi, corner] = remap[(f[corner], fi)]

    return np.array(new_vertices), np.array(new_normals), new_faces


def hausdorff_fraction_of_bbox(orig_vertices, orig_faces, new_vertices, new_faces, n_samples=20000):
    """Approximate (sampled) two-sided Hausdorff distance, as a fraction of
    orig's bounding-box diagonal. Sampled, not exact -- exact Hausdorff on
    meshes this size is not worth the cost, and a dense sample is standard
    practice for this kind of QA number."""
    m_orig = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(orig_vertices), o3d.utility.Vector3iVector(orig_faces))
    m_new = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(new_vertices), o3d.utility.Vector3iVector(new_faces))

    pc_orig = m_orig.sample_points_uniformly(number_of_points=n_samples)
    pc_new = m_new.sample_points_uniformly(number_of_points=n_samples)

    d_orig_to_new = np.asarray(pc_orig.compute_point_cloud_distance(pc_new))
    d_new_to_orig = np.asarray(pc_new.compute_point_cloud_distance(pc_orig))
    d_all = np.concatenate([d_orig_to_new, d_new_to_orig])
    hausdorff = d_all.max()

    bbox = orig_vertices.max(axis=0) - orig_vertices.min(axis=0)
    diag = np.linalg.norm(bbox)
    stats = {
        'max_mm': hausdorff * 1000,
        'p99_mm': np.percentile(d_all, 99) * 1000,
        'median_mm': np.median(d_all) * 1000,
        'diag_mm': diag * 1000,
        'max_pct': hausdorff / diag * 100,
        'p99_pct': np.percentile(d_all, 99) / diag * 100,
        'median_pct': np.median(d_all) / diag * 100,
    }
    return hausdorff, diag, hausdorff / diag, stats
