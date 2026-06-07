"""Blender (run inside `blender --background --python`) — build a vintage
raised-relief plate of the Xalapa region and render it with Cycles/OptiX.

Pipeline: subdivided grid -> Displace modifier from the 16-bit heightmap ->
hypsometric albedo material -> low sun for relief shadows -> the plate floats
above a cream "paper" plane (drop shadow) -> orthographic, slightly tilted
camera. Params are read from data/meta.json; output -> output/xalapa_render.png
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "output"
meta = json.loads((DATA / "meta.json").read_text())

# ---- tunables -------------------------------------------------------
EXAG = 2.6            # vertical exaggeration
SUN_AZ = 318.0       # degrees (NW)
SUN_ALT = 37.0       # degrees above horizon -> relief shadows
SUN_ENERGY = 4.2
CAM_TILT = 10.0      # degrees off vertical (shows the raised plate edge)
RES_X = int(sys.argv[-2]) if len(sys.argv) >= 3 else 1400
SAMPLES = int(sys.argv[-1]) if len(sys.argv) >= 3 else 96
CREAM = (0.882, 0.847, 0.788)   # aged paper

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
    # high-res grid sized to the DEM aspect, in km units
    sx = min(meta["width"], 2400)
    sy = int(round(sx * H_km / W_km))
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
    bpy.ops.object.shade_smooth()

    # solid edge + float above the paper for a drop shadow
    sol = g.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.35
    sol.offset = -1.0
    bpy.ops.object.modifier_apply(modifier=sol.name)
    g.location.z = 0.95
    return g


def terrain_material(obj):
    mat = bpy.data.materials.new("hyp")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(DATA / "albedo_hypsometric.png"))
    tex.image.colorspace_settings.name = "sRGB"
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.append(mat)


def paper_plane():
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    p = bpy.context.active_object
    p.scale = (W_km * 2.2, H_km * 2.4, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    p.is_shadow_catcher = True   # capture only the drop shadow (alpha)
    return p


def sun():
    bpy.ops.object.light_add(type="SUN")
    s = bpy.context.active_object
    s.data.energy = SUN_ENERGY
    s.data.angle = math.radians(2.0)   # soft-ish shadows
    az, al = math.radians(SUN_AZ), math.radians(SUN_ALT)
    # unit vector pointing AT the sun (az from north +Y, clockwise to east +X)
    sun_dir = Vector((math.cos(al) * math.sin(az),
                      math.cos(al) * math.cos(az),
                      math.sin(al)))
    travel = -sun_dir                  # direction the light travels
    s.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    return s


def camera():
    bpy.ops.object.camera_add()
    c = bpy.context.active_object
    c.data.type = "ORTHO"
    c.data.ortho_scale = max(W_km, H_km) * 1.12
    t = math.radians(CAM_TILT)
    dist = max(W_km, H_km) * 2.0
    c.location = (0.0, -math.sin(t) * dist, math.cos(t) * dist + 3)
    c.rotation_euler = (t, 0.0, 0.0)
    bpy.context.scene.camera = c
    return c


def setup_render():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    for d in prefs.get_devices_for_type("OPTIX"):
        d.use = ("CPU" not in d.name.upper())
    sc.cycles.device = "GPU"
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.film_transparent = True            # plate + shadow on alpha
    sc.cycles.film_transparent_glass = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    # soft sky fill so shaded slopes aren't pure black
    w = bpy.data.worlds.new("w"); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.86, 0.9, 1.0)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.4


def lonlat_to_world(lon, lat, z):
    bb = meta["bbox"]
    x = ((lon - bb["west"]) / (bb["east"] - bb["west"]) - 0.5) * W_km
    y = ((lat - bb["south"]) / (bb["north"] - bb["south"]) - 0.5) * H_km
    return Vector((x, y, z))


def project_points(cam):
    sc = bpy.context.scene
    dem = np.load(DATA / "elevation.npy")
    h, w = dem.shape
    vmin = meta["elev_min"]

    def terr_z(lon, lat):
        bb = meta["bbox"]
        ix = int((lon - bb["west"]) / (bb["east"] - bb["west"]) * (w - 1))
        iy = int((bb["north"] - lat) / (bb["north"] - bb["south"]) * (h - 1))
        e = float(dem[max(0, min(h - 1, iy)), max(0, min(w - 1, ix))])
        return (e - vmin) / 1000.0 * EXAG + 0.95

    def px(world):
        co = world_to_camera_view(sc, cam, world)
        return [co.x * RES_X, (1 - co.y) * RES_Y]

    places = {
        "Xalapa": (-96.9170, 19.5285), "Cofre de Perote": (-97.150, 19.492),
        "Coatepec": (-96.961, 19.452), "Perote": (-97.241, 19.561),
        "Banderilla": (-96.939, 19.586),
    }
    out = {"places": {n: px(lonlat_to_world(lo, la, terr_z(lo, la)))
                      for n, (lo, la) in places.items()}}
    bb = meta["bbox"]
    lons = [round(x, 2) for x in np.arange(-97.25, -96.45, 0.25)]
    lats = [round(x, 2) for x in np.arange(19.25, 19.85, 0.25)]
    out["grid"] = {"lons": lons, "lats": lats,
                   "pts": {f"{lo},{la}": px(lonlat_to_world(lo, la, 0.95))
                           for lo in lons for la in lats}}
    out["res"] = [RES_X, RES_Y]
    (OUT / "points.json").write_text(json.dumps(out))
    print("projected", len(places), "places +", len(lons) * len(lats), "grid pts")


def main():
    clear()
    t = make_terrain()
    terrain_material(t)
    paper_plane()
    sun()
    cam = camera()
    setup_render()
    project_points(cam)
    bpy.context.scene.render.filepath = str(OUT / "xalapa_render.png")
    print(f"rendering {RES_X}x{RES_Y} samples={SAMPLES} "
          f"plate {W_km:.0f}x{H_km:.0f} km relief {RELIEF_km:.1f}km x{EXAG}")
    bpy.ops.render.render(write_still=True)
    print("saved", OUT / "xalapa_render.png")


main()
