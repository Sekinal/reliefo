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
EXAG = 4.2            # vertical exaggeration (small municipio range -> push it)
SUN_AZ = 318.0       # degrees (NW)
SUN_ALT = 42.0       # degrees -> gentle, soft relief shadows (Greece-style)
SUN_ENERGY = 3.8
CAM_TILT = 9.0       # degrees off vertical (shows the raised plate edge)
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
    sx = min(meta["width"], 3200)
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

    # --- cut the mesh to the municipio of Xalapa (mask) --------------
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

    # solid edge + float above the paper for a drop shadow
    sol = g.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.4
    sol.offset = -1.0
    bpy.ops.object.modifier_apply(modifier=sol.name)
    g.location.z = 0.55          # sit close to the paper -> small soft shadow
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
    surface = bsdf.outputs["BSDF"]

    # glowing street network (self-lit) if the emission map exists
    emi_path = DATA / "streets_emission.png"
    if emi_path.exists():
        etex = nt.nodes.new("ShaderNodeTexImage")
        etex.image = bpy.data.images.load(str(emi_path))
        etex.image.colorspace_settings.name = "Non-Color"
        etex.interpolation = "Cubic"
        mult = nt.nodes.new("ShaderNodeMath")
        mult.operation = "MULTIPLY"
        mult.inputs[1].default_value = 4.0          # glow strength
        nt.links.new(etex.outputs["Color"], mult.inputs[0])
        emis = nt.nodes.new("ShaderNodeEmission")
        emis.inputs["Color"].default_value = (1.0, 0.82, 0.48, 1.0)   # warm lamp glow
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
    p.is_shadow_catcher = True   # capture only the drop shadow (alpha)
    return p


def sun():
    # key light from the NW (Tanaka/Imhof convention)
    bpy.ops.object.light_add(type="SUN")
    s = bpy.context.active_object
    s.data.energy = SUN_ENERGY
    s.data.angle = math.radians(6.0)   # soft shadow penumbra
    s.data.color = (1.0, 0.99, 0.97)
    az, al = math.radians(SUN_AZ), math.radians(SUN_ALT)
    sun_dir = Vector((math.cos(al) * math.sin(az),
                      math.cos(al) * math.cos(az), math.sin(al)))
    s.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    # weak fill straight down to lift the deep valleys (the "two suns" trick)
    bpy.ops.object.light_add(type="SUN")
    fwd = bpy.context.active_object
    fwd.data.energy = 0.55
    fwd.data.angle = math.radians(10.0)
    fwd.data.color = (0.95, 0.97, 1.0)  # cool fill
    fwd.rotation_euler = (0.0, 0.0, 0.0)
    return s


def camera():
    bpy.ops.object.camera_add()
    c = bpy.context.active_object
    c.data.type = "ORTHO"
    c.data.ortho_scale = max(W_km, H_km) * 1.42   # clean margin around the plate
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
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.90, 0.92, 0.95, 1.0)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.6


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
        return (e - vmin) / 1000.0 * EXAG + 0.9

    def px(world):
        co = world_to_camera_view(sc, cam, world)
        return [co.x * RES_X, (1 - co.y) * RES_Y]

    # places inside the municipio of Xalapa (verified coordinates only)
    places = {
        "Xalapa": (-96.9170, 19.5285),                 # Parque Juarez
        "Cerro de Macuiltepetl": (-96.92083, 19.54833),  # 1,522 m volcanic cone
    }
    out = {"places": {n: px(lonlat_to_world(lo, la, terr_z(lo, la)))
                      for n, (lo, la) in places.items()}}
    lons = [round(x, 2) for x in np.arange(-96.95, -96.79, 0.05)]
    lats = [round(x, 2) for x in np.arange(19.50, 19.61, 0.05)]
    out["grid"] = {"lons": lons, "lats": lats,
                   "pts": {f"{lo},{la}": px(lonlat_to_world(lo, la, 0.9))
                           for lo in lons for la in lats}}
    out["res"] = [RES_X, RES_Y]
    # named zones (OSM), projected onto the relief surface
    zf = DATA / "zones.json"
    if zf.exists():
        zones = json.loads(zf.read_text())
        out["zones"] = [{"name": z["name"], "place": z.get("place", ""),
                         "xy": px(lonlat_to_world(z["lon"], z["lat"],
                                                  terr_z(z["lon"], z["lat"])))}
                        for z in zones]
        print("projected", len(zones), "zones")
    (OUT / "points.json").write_text(json.dumps(out, ensure_ascii=False))
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
