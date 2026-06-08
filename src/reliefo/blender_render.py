"""Runs *inside* Blender:  ``blender --background --factory-startup --python
blender_render.py -- <render_cfg.json> <res_x> <samples>``.

Builds a raised-relief plate from the 16-bit heightmap, cuts it to the
municipio with a Mask modifier, lights it with a soft NW key + cool fill, and
renders with Cycles/OptiX onto transparency + a shadow catcher. All tunables
come from the JSON the pipeline writes; this file imports only ``bpy``/``numpy``
so it can run in Blender's bundled Python.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

# ---- args + config --------------------------------------------------------
_argv = sys.argv[sys.argv.index("--") + 1:]
CFG = json.loads(Path(_argv[0]).read_text())
RES_X = int(_argv[1])
SAMPLES = int(_argv[2])

DATA = Path(CFG["data"])
OUT = Path(CFG["out"])
meta = json.loads((DATA / "meta.json").read_text())

EXAG = CFG["exaggeration"]
SUN_AZ = CFG["sun_azimuth"]
SUN_ALT = CFG["sun_altitude"]
SUN_ENERGY = CFG["sun_energy"]
CAM_TILT = CFG["cam_tilt"]
STREETS_GLOW = CFG["streets_glow"]
EMISSION_COLOR = tuple(CFG["emission_color"])

W_km = meta["width"] * meta["px_m"][0] / 1000.0
H_km = meta["height"] * meta["px_m"][1] / 1000.0
RELIEF_km = (meta["elev_max"] - meta["elev_min"]) / 1000.0
RES_Y = int(round(RES_X * H_km / W_km))


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
                bpy.data.textures, bpy.data.lights, bpy.data.cameras):
        for x in list(blk):
            blk.remove(x)


def make_terrain():
    # cap the LARGER grid dimension (keeps tall/portrait plates from ballooning
    # to ~2x the vertices and running the render out of memory)
    cap = CFG.get("subdiv_max", 3000)
    if W_km >= H_km:
        sx = min(meta["width"], cap)
        sy = int(round(sx * H_km / W_km))
    else:
        sy = min(meta["height"], cap)
        sx = int(round(sy * W_km / H_km))
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=sx, y_subdivisions=sy, size=1.0)
    g = bpy.context.active_object
    g.scale = (W_km, H_km, 1.0)
    bpy.ops.object.transform_apply(scale=True)

    img = bpy.data.images.load(str(DATA / "heightmap_16bit.png"))
    img.colorspace_settings.name = "Non-Color"
    tex = bpy.data.textures.new("disp", "IMAGE")
    tex.image = img
    m = g.modifiers.new("disp", "DISPLACE")
    m.texture = tex
    m.texture_coords = "UV"
    m.mid_level = 0.0
    m.strength = RELIEF_km * EXAG
    bpy.ops.object.modifier_apply(modifier=m.name)

    # cut the mesh to the municipio (mask vertex group from the boundary raster)
    mask = np.load(DATA / "mask.npy")
    mh, mw = mask.shape
    n = len(g.data.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    g.data.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    col = np.clip(((co[:, 0] + W_km / 2) / W_km * (mw - 1)).round().astype(int), 0, mw - 1)
    row = np.clip(((H_km / 2 - co[:, 1]) / H_km * (mh - 1)).round().astype(int), 0, mh - 1)
    inside = mask[row, col] > 0
    grp = g.vertex_groups.new(name="inside")
    grp.add(np.nonzero(inside)[0].astype(int).tolist(), 1.0, "REPLACE")
    mm = g.modifiers.new("mask", "MASK")
    mm.vertex_group = "inside"
    mm.threshold = 0.5
    bpy.ops.object.modifier_apply(modifier=mm.name)
    bpy.ops.object.shade_smooth()

    sol_thick = CFG.get("solidify", 0.4)
    if sol_thick > 0:
        sol = g.modifiers.new("sol", "SOLIDIFY")
        sol.thickness = sol_thick
        sol.offset = -1.0
        bpy.ops.object.modifier_apply(modifier=sol.name)
    g.location.z = 0.55
    return g


def terrain_material(obj):
    mat = bpy.data.materials.new("hyp")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(DATA / "albedo.png"))
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    surface = bsdf.outputs["BSDF"]

    emi_path = DATA / "streets_emission.png"
    if emi_path.exists():
        etex = nt.nodes.new("ShaderNodeTexImage")
        etex.image = bpy.data.images.load(str(emi_path))
        etex.image.colorspace_settings.name = "Non-Color"
        etex.interpolation = "Cubic"
        mult = nt.nodes.new("ShaderNodeMath")
        mult.operation = "MULTIPLY"
        mult.inputs[1].default_value = STREETS_GLOW
        nt.links.new(etex.outputs["Color"], mult.inputs[0])
        emis = nt.nodes.new("ShaderNodeEmission")
        emis.inputs["Color"].default_value = (*EMISSION_COLOR, 1.0)
        nt.links.new(mult.outputs[0], emis.inputs["Strength"])
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(bsdf.outputs["BSDF"], add.inputs[0])
        nt.links.new(emis.outputs["Emission"], add.inputs[1])
        surface = add.outputs["Shader"]

    nt.links.new(surface, out.inputs["Surface"])
    obj.data.materials.append(mat)


def paper_plane():
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    p = bpy.context.active_object
    p.scale = (W_km * 2.2, H_km * 2.4, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    p.is_shadow_catcher = True
    return p


def sun():
    bpy.ops.object.light_add(type="SUN")
    s = bpy.context.active_object
    s.data.energy = SUN_ENERGY
    s.data.angle = math.radians(6.0)
    s.data.color = (1.0, 0.99, 0.97)
    az, al = math.radians(SUN_AZ), math.radians(SUN_ALT)
    sun_dir = Vector((math.cos(al) * math.sin(az),
                      math.cos(al) * math.cos(az), math.sin(al)))
    s.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    bpy.ops.object.light_add(type="SUN")
    fwd = bpy.context.active_object
    fwd.data.energy = 0.55
    fwd.data.angle = math.radians(10.0)
    fwd.data.color = (0.95, 0.97, 1.0)
    fwd.rotation_euler = (0.0, 0.0, 0.0)
    return s


def camera():
    bpy.ops.object.camera_add()
    c = bpy.context.active_object
    c.data.type = "ORTHO"
    c.data.ortho_scale = max(W_km, H_km) * 1.42
    t = math.radians(CAM_TILT)
    dist = max(W_km, H_km) * 2.0
    c.location = (0.0, -math.sin(t) * dist, math.cos(t) * dist + 3)
    c.rotation_euler = (t, 0.0, 0.0)
    # default clip_end is 1000; a large (state-scale) plate sits past it -> set
    # the clip planes from the scene size so the plate is always in range.
    c.data.clip_start = max(0.1, dist * 0.05)
    c.data.clip_end = dist * 4.0
    bpy.context.scene.camera = c
    return c


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.refresh_devices()                     # enumerate GPUs on a fresh Blender
    gpus = [d for d in prefs.get_devices_for_type("OPTIX") if d.type != "CPU"]
    for d in prefs.get_devices_for_type("OPTIX"):
        d.use = d.type != "CPU"
    sc.cycles.device = "GPU" if gpus else "CPU"
    print("Cycles devices:", [(d.name, d.use) for d in prefs.devices])
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.film_transparent = True
    sc.cycles.film_transparent_glass = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.90, 0.92, 0.95, 1.0)
    w.node_tree.nodes["Background"].inputs[1].default_value = CFG.get("sky", 0.6)


def lonlat_to_world(lon, lat, z):
    bb = meta["bbox"]
    x = ((lon - bb["west"]) / (bb["east"] - bb["west"]) - 0.5) * W_km
    y = ((lat - bb["south"]) / (bb["north"] - bb["south"]) - 0.5) * H_km
    return Vector((x, y, z))


def project_zones(cam):
    """Project the named zones onto the relief surface -> output/points.json."""
    sc = bpy.context.scene
    dem = np.load(DATA / "elevation.npy")
    h, w = dem.shape
    vmin = meta["elev_min"]

    def terr_z(lon, lat):
        bb = meta["bbox"]
        ix = int((lon - bb["west"]) / (bb["east"] - bb["west"]) * (w - 1))
        iy = int((bb["north"] - lat) / (bb["north"] - bb["south"]) * (h - 1))
        e = float(dem[max(0, min(h - 1, iy)), max(0, min(w - 1, ix))])
        return (e - vmin) / 1000.0 * EXAG + 0.9

    def px(world):
        co = world_to_camera_view(sc, cam, world)
        return [co.x * RES_X, (1 - co.y) * RES_Y]

    out = {"res": [RES_X, RES_Y], "zones": []}
    zf = DATA / "zones.json"
    if zf.exists():
        zones = json.loads(zf.read_text())
        out["zones"] = [{"name": z["name"], "place": z.get("place", ""),
                         "n": z.get("n", 0),
                         "xy": px(lonlat_to_world(z["lon"], z["lat"],
                                                  terr_z(z["lon"], z["lat"])))}
                        for z in zones]
        print("projected", len(zones), "zones")
    (Path(CFG["points_json"])).write_text(json.dumps(out, ensure_ascii=False))


def main():
    clear()
    t = make_terrain()
    terrain_material(t)
    paper_plane()
    sun()
    cam = camera()
    setup_render()
    project_zones(cam)
    bpy.context.scene.render.filepath = CFG["render_png"]
    print(f"rendering {RES_X}x{RES_Y} samples={SAMPLES} "
          f"plate {W_km:.0f}x{H_km:.0f} km relief {RELIEF_km:.1f}km x{EXAG}")
    bpy.ops.render.render(write_still=True)
    print("saved", CFG["render_png"])


main()
