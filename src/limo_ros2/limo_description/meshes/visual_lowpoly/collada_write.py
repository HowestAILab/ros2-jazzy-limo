"""Minimal COLLADA 1.4.1 writer for a handful of flat-diffuse-color meshes.

trimesh can read DAE (via pycollada) but cannot write it -- only glTF/OBJ/STL/
PLY are supported export targets. Switching the shipped format away from DAE
was rejected: the existing pipeline (URDF -> package:// -> visualization bridge ->
three.js) is confirmed working for .dae today, and there's no confirmation
the bridge's loader handles glTF, so a format change risks silently breaking
rendering. This writer targets exactly what limo_base.dae/limo_wheel.dae
already are: COLLADA 1.4.1, Z_UP, meter units, Phong materials, one geometry
per node with an identity transform (matches what AgileX's own export does --
verified 0/1619 nodes in the original have a non-identity transform, so
vertices are already baked into final position and no scene-graph transform
handling is needed here either).
"""
import xml.etree.ElementTree as ET

import numpy as np

NS = "http://www.collada.org/2005/11/COLLADASchema"
ET.register_namespace('', NS)


def _floats(arr):
    return ' '.join(f'{x:.6f}' for x in np.asarray(arr).reshape(-1))


def write_collada(path: str, meshes: list):
    """meshes: list of dicts {name, vertices (N,3), normals (N,3), faces (M,3), color (r,g,b) in 0..1}"""
    root = ET.Element(f'{{{NS}}}COLLADA', version='1.4.1')
    asset = ET.SubElement(root, f'{{{NS}}}asset')
    ET.SubElement(asset, f'{{{NS}}}contributor')
    ET.SubElement(asset, f'{{{NS}}}created').text = '2026-09-21T00:00:00'
    ET.SubElement(asset, f'{{{NS}}}modified').text = '2026-09-21T00:00:00'
    ET.SubElement(asset, f'{{{NS}}}unit', name='meter', meter='1.0')
    ET.SubElement(asset, f'{{{NS}}}up_axis').text = 'Z_UP'

    lib_effects = ET.SubElement(root, f'{{{NS}}}library_effects')
    lib_materials = ET.SubElement(root, f'{{{NS}}}library_materials')
    lib_geoms = ET.SubElement(root, f'{{{NS}}}library_geometries')
    lib_vscenes = ET.SubElement(root, f'{{{NS}}}library_visual_scenes')
    vscene = ET.SubElement(lib_vscenes, f'{{{NS}}}visual_scene', id='Scene', name='Scene')

    for m in meshes:
        name = m['name']
        eff_id = f'effect_{name}'
        mat_id = f'material_{name}'
        geom_id = f'geometry_{name}'
        r, g, b = m['color']

        effect = ET.SubElement(lib_effects, f'{{{NS}}}effect', id=eff_id, name=eff_id)
        profile = ET.SubElement(effect, f'{{{NS}}}profile_COMMON')
        technique = ET.SubElement(profile, f'{{{NS}}}technique', sid='common')
        phong = ET.SubElement(technique, f'{{{NS}}}phong')
        emission = ET.SubElement(phong, f'{{{NS}}}emission')
        ET.SubElement(emission, f'{{{NS}}}color').text = '0.0 0.0 0.0 1.0'
        diffuse = ET.SubElement(phong, f'{{{NS}}}diffuse')
        ET.SubElement(diffuse, f'{{{NS}}}color').text = f'{r:.6f} {g:.6f} {b:.6f} 1.0'
        specular = ET.SubElement(phong, f'{{{NS}}}specular')
        ET.SubElement(specular, f'{{{NS}}}color').text = '0.0 0.0 0.0 1.0'

        material = ET.SubElement(lib_materials, f'{{{NS}}}material', id=mat_id, name=mat_id)
        ET.SubElement(material, f'{{{NS}}}instance_effect', url=f'#{eff_id}')

        verts = np.asarray(m['vertices'], dtype=float)
        norms = np.asarray(m['normals'], dtype=float)
        faces = np.asarray(m['faces'], dtype=int)
        nvert = len(verts)

        geometry = ET.SubElement(lib_geoms, f'{{{NS}}}geometry', id=geom_id, name=geom_id)
        mesh_el = ET.SubElement(geometry, f'{{{NS}}}mesh')

        pos_src_id = f'{geom_id}-positions'
        src = ET.SubElement(mesh_el, f'{{{NS}}}source', id=pos_src_id)
        arr = ET.SubElement(src, f'{{{NS}}}float_array', id=f'{pos_src_id}-array', count=str(nvert * 3))
        arr.text = _floats(verts)
        acc_tech = ET.SubElement(src, f'{{{NS}}}technique_common')
        acc = ET.SubElement(acc_tech, f'{{{NS}}}accessor', source=f'#{pos_src_id}-array',
                             count=str(nvert), stride='3')
        for ax in 'XYZ':
            ET.SubElement(acc, f'{{{NS}}}param', name=ax, type='float')

        norm_src_id = f'{geom_id}-normals'
        src_n = ET.SubElement(mesh_el, f'{{{NS}}}source', id=norm_src_id)
        arr_n = ET.SubElement(src_n, f'{{{NS}}}float_array', id=f'{norm_src_id}-array', count=str(nvert * 3))
        arr_n.text = _floats(norms)
        acc_tech_n = ET.SubElement(src_n, f'{{{NS}}}technique_common')
        acc_n = ET.SubElement(acc_tech_n, f'{{{NS}}}accessor', source=f'#{norm_src_id}-array',
                               count=str(nvert), stride='3')
        for ax in 'XYZ':
            ET.SubElement(acc_n, f'{{{NS}}}param', name=ax, type='float')

        vertices_id = f'{geom_id}-vertices'
        vertices_el = ET.SubElement(mesh_el, f'{{{NS}}}vertices', id=vertices_id)
        ET.SubElement(vertices_el, f'{{{NS}}}input', semantic='POSITION', source=f'#{pos_src_id}')

        tris = ET.SubElement(mesh_el, f'{{{NS}}}triangles', count=str(len(faces)), material=f'material_symbol_{name}')
        ET.SubElement(tris, f'{{{NS}}}input', semantic='VERTEX', source=f'#{vertices_id}', offset='0')
        ET.SubElement(tris, f'{{{NS}}}input', semantic='NORMAL', source=f'#{norm_src_id}', offset='0')
        p = ET.SubElement(tris, f'{{{NS}}}p')
        idx = faces.reshape(-1)
        p.text = ' '.join(str(i) for i in np.repeat(idx, 1))

        node = ET.SubElement(vscene, f'{{{NS}}}node', id=f'node_{name}', name=name)
        inst_geom = ET.SubElement(node, f'{{{NS}}}instance_geometry', url=f'#{geom_id}')
        bind_mat = ET.SubElement(inst_geom, f'{{{NS}}}bind_material')
        tech_common = ET.SubElement(bind_mat, f'{{{NS}}}technique_common')
        ET.SubElement(tech_common, f'{{{NS}}}instance_material',
                      symbol=f'material_symbol_{name}', target=f'#{mat_id}')

    scene = ET.SubElement(root, f'{{{NS}}}scene')
    ET.SubElement(scene, f'{{{NS}}}instance_visual_scene', url='#Scene')

    tree = ET.ElementTree(root)
    tree.write(path, xml_declaration=True, encoding='utf-8')
