"""Render the 3D FROJA logo with Blender.

the Froja emblem (shutter ring, blue flame, anvil, spark) as a 3D medallion with a copper rim, extruded
brushed-metal FROJA letters (Michroma), a glowing "IMAGE STUDIO" line, and a glossy black floor that gives
soft shading and a reflection under the logo.

    blender.exe -b --factory-startup --python scripts/blender_froja_logo.py -- <project_folder>

Writes public/brand/froja-logo-3d-raw.png (opaque); scripts/finish_logo.py turns it into the transparent
public/brand/froja-logo-3d.png used by the app.
"""
import math
import sys
from pathlib import Path

import bpy

root = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else Path.cwd()
out_dir = root / "public" / "brand"
out_dir.mkdir(parents=True, exist_ok=True)
MARK = root / "public" / "froja-mark.png"
FONT = root / "assets" / "fonts" / "Michroma-Regular.ttf"

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------- render ----------
try:
    bpy.ops.preferences.addon_enable(module="cycles")
except Exception:
    pass
engines = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
scene.render.engine = "CYCLES" if "CYCLES" in engines else next(e for e in engines if "EEVEE" in e)
if scene.render.engine == "CYCLES":
    scene.cycles.samples = 256
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                for d in prefs.devices:
                    d.use = True
                scene.cycles.device = "GPU"
                break
            except Exception:
                continue
    except Exception:
        pass
else:
    for attr, value in (("use_raytracing", True), ("taa_render_samples", 128)):
        try:
            setattr(scene.eevee, attr, value)
        except Exception:
            pass
scene.render.resolution_x, scene.render.resolution_y = 2600, 1000
scene.render.film_transparent = False
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
except Exception:
    pass

world = bpy.data.worlds.new("FrojaWorld")
scene.world = world
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.006, 0.007, 0.009, 1)
bg.inputs[1].default_value = 1.0
wn = world.node_tree
w_out = next(n for n in wn.nodes if n.type == "OUTPUT_WORLD")
w_coord = wn.nodes.new("ShaderNodeTexCoord")
w_sep = wn.nodes.new("ShaderNodeSeparateXYZ")
w_ramp = wn.nodes.new("ShaderNodeValToRGB")
w_ramp.color_ramp.elements[0].position = 0.42
w_ramp.color_ramp.elements[0].color = (0.004, 0.004, 0.005, 1)
w_ramp.color_ramp.elements[1].position = 0.78
w_ramp.color_ramp.elements[1].color = (1.15, 1.18, 1.22, 1)
w_map = wn.nodes.new("ShaderNodeMapRange"); w_map.inputs["From Min"].default_value = -1.0; w_map.inputs["From Max"].default_value = 1.0
w_studio = wn.nodes.new("ShaderNodeBackground")
w_path = wn.nodes.new("ShaderNodeLightPath")
w_mix = wn.nodes.new("ShaderNodeMixShader")
wn.links.new(w_coord.outputs["Generated"], w_sep.inputs["Vector"])
wn.links.new(w_sep.outputs["Z"], w_map.inputs["Value"])
wn.links.new(w_map.outputs["Result"], w_ramp.inputs["Fac"])
wn.links.new(w_ramp.outputs["Color"], w_studio.inputs["Color"])
wn.links.new(w_path.outputs["Is Camera Ray"], w_mix.inputs["Fac"])
wn.links.new(w_studio.outputs["Background"], w_mix.inputs[1])
wn.links.new(bg.outputs["Background"], w_mix.inputs[2])
wn.links.new(bg.outputs["Background"], w_out.inputs["Surface"])  # world stays black; the softbox below lights the letters


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def set_input(node, names, value):
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return True
    return False


def material(name, color, metallic=0.0, rough=0.4, emission=None, strength=0.0, aniso=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = principled(m)
    set_input(p, ["Base Color"], (*color, 1))
    set_input(p, ["Metallic"], metallic)
    set_input(p, ["Roughness"], rough)
    if aniso:
        set_input(p, ["Anisotropic", "Specular Anisotropic"], aniso)
    if emission:
        set_input(p, ["Emission Color", "Emission"], (*emission, 1))
        set_input(p, ["Emission Strength"], strength)
    return m


chrome = material("BrushedChrome", (0.92, 0.94, 0.96), metallic=1.0, rough=0.2, aniso=0.55)
nt = chrome.node_tree
noise = nt.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 300.0; noise.inputs["Detail"].default_value = 6.0
mapping = nt.nodes.new("ShaderNodeMapping"); mapping.inputs["Scale"].default_value = (1.0, 80.0, 1.0)
coord = nt.nodes.new("ShaderNodeTexCoord")
rng = nt.nodes.new("ShaderNodeMapRange"); rng.inputs["To Min"].default_value = 0.14; rng.inputs["To Max"].default_value = 0.26
nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
nt.links.new(noise.outputs["Fac"], rng.inputs["Value"])
nt.links.new(rng.outputs["Result"], principled(chrome).inputs["Roughness"])

steel_side = material("BrushedSteelSide", (0.42, 0.44, 0.47), metallic=0.45, rough=0.42)
copper = material("Copper", (0.80, 0.42, 0.22), metallic=1.0, rough=0.3)
gunmetal = material("Gunmetal", (0.06, 0.065, 0.075), metallic=0.9, rough=0.35)
led = material("CyanLED", (0.0, 0.5, 0.65), emission=(0.0, 0.78, 1.0), strength=6.0)
floor_mat = material("GlossFloor", (0.004, 0.005, 0.006), metallic=0.0, rough=0.12)
set_input(principled(floor_mat), ["Specular IOR Level", "Specular"], 0.6)

# ---------- emblem medallion ----------
ex, ez, er = -3.15, 1.45, 1.42
bpy.ops.mesh.primitive_cylinder_add(vertices=160, radius=er, depth=0.28, location=(ex, 0.14, ez), rotation=(math.radians(90), 0, 0))
disc = bpy.context.object; disc.data.materials.append(gunmetal); bpy.ops.object.shade_smooth()
bev = disc.modifiers.new("Bevel", "BEVEL"); bev.width = 0.05; bev.segments = 6

bpy.ops.mesh.primitive_torus_add(major_radius=er + 0.02, minor_radius=0.07, major_segments=200, minor_segments=32,
                                 location=(ex, -0.02, ez), rotation=(math.radians(90), 0, 0))
rim = bpy.context.object; rim.data.materials.append(copper); bpy.ops.object.shade_smooth()

bpy.ops.mesh.primitive_torus_add(major_radius=er + 0.16, minor_radius=0.022, major_segments=200, minor_segments=16,
                                 location=(ex, 0.02, ez), rotation=(math.radians(90), 0, 0))
halo = bpy.context.object; halo.data.materials.append(led); bpy.ops.object.shade_smooth()

# the emblem artwork on the face of the medallion
face = bpy.data.materials.new("EmblemFace")
face.use_nodes = True
fp = principled(face)
tex = face.node_tree.nodes.new("ShaderNodeTexImage")
tex.image = bpy.data.images.load(str(MARK))
face.node_tree.links.new(tex.outputs["Color"], fp.inputs["Base Color"])
face.node_tree.links.new(tex.outputs["Alpha"], fp.inputs["Alpha"])
emit_name = "Emission Color" if "Emission Color" in fp.inputs else "Emission"
face.node_tree.links.new(tex.outputs["Color"], fp.inputs[emit_name])
set_input(fp, ["Emission Strength"], 0.9)
set_input(fp, ["Metallic"], 0.35)
set_input(fp, ["Roughness"], 0.32)
try:
    face.surface_render_method = "DITHERED"
except Exception:
    pass
side = er * 2 * 1.02
bpy.ops.mesh.primitive_plane_add(size=side, location=(ex, -0.012, ez), rotation=(math.radians(90), 0, 0))
plate = bpy.context.object; plate.data.materials.append(face)

# ---------- divider ----------
bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.35, 0.0, 1.45))
div = bpy.context.object; div.scale = (0.012, 0.012, 2.3); div.data.materials.append(led)

# ---------- FROJA letters ----------
def text_object(body, size, extrude, bevel, mat, location, spacing=1.0, thicken=0.0):
    bpy.ops.object.text_add(location=location)
    t = bpy.context.object
    t.data.body = body
    if FONT.exists():
        t.data.font = bpy.data.fonts.load(str(FONT))
    t.data.align_x = "LEFT"
    t.data.align_y = "BOTTOM"
    t.data.size = size
    t.data.space_character = spacing
    t.data.extrude = extrude
    t.data.bevel_depth = bevel
    t.data.bevel_resolution = 6
    t.data.offset = thicken
    t.rotation_euler = (math.radians(90), 0, 0)
    t.data.materials.append(mat)
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.shade_smooth()
    return bpy.context.object

word = text_object("FROJA", 1.95, 0.55, 0.06, chrome, (-0.75, 0.0, 1.02), spacing=1.22, thicken=0.022)
word.data.materials.append(steel_side)
to_world = word.matrix_world.to_3x3()
for poly in word.data.polygons:
    # use the WORLD direction of each face: faces looking at the camera (-Y) stay polished silver,
    # the depth (top, sides, inner walls) gets the darker steel
    normal = (to_world @ poly.normal).normalized()
    poly.material_index = 0 if normal.y < -0.55 else 1
sub = text_object("IMAGE  STUDIO", 0.42, 0.02, 0.006, led, (-0.68, -0.05, 0.28), spacing=1.9)

# ---------- glossy floor: shading + reflection under the logo ----------
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
floor = bpy.context.object; floor.data.materials.append(floor_mat)

# ---------- studio softbox: a tall panel in front of the logo, bright at the top, dark at the bottom.
# Only the letters reflect it (the camera does not see it and the floor reflects the other way).
box_mat = bpy.data.materials.new("SoftboxGradient")
box_mat.use_nodes = True
bn = box_mat.node_tree
for node in list(bn.nodes):
    if node.type != "OUTPUT_MATERIAL":
        bn.nodes.remove(node)
b_out = next(n for n in bn.nodes if n.type == "OUTPUT_MATERIAL")
b_coord = bn.nodes.new("ShaderNodeTexCoord")
b_sep = bn.nodes.new("ShaderNodeSeparateXYZ")
b_ramp = bn.nodes.new("ShaderNodeValToRGB")
b_ramp.color_ramp.elements[0].position = 0.05
b_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1)
b_ramp.color_ramp.elements[1].position = 0.95
b_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1)
b_emit = bn.nodes.new("ShaderNodeEmission"); b_emit.inputs["Strength"].default_value = 2.6
bn.links.new(b_coord.outputs["Generated"], b_sep.inputs["Vector"])
bn.links.new(b_sep.outputs["Y"], b_ramp.inputs["Fac"])
bn.links.new(b_ramp.outputs["Color"], b_emit.inputs["Color"])
bn.links.new(b_emit.outputs["Emission"], b_out.inputs["Surface"])
bpy.ops.mesh.primitive_plane_add(size=1, location=(0.75, -12.0, 2.0), rotation=(math.radians(90), 0, 0))
softbox = bpy.context.object
softbox.scale = (40, 9, 1)
softbox.data.materials.append(box_mat)
for attr in ("visible_camera", "visible_shadow"):
    try:
        setattr(softbox, attr, False)
    except Exception:
        pass

# ---------- lights ----------
def area(name, loc, rot, energy, size, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.size, data.color = energy, size, color
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location, obj.rotation_euler = loc, rot
    return obj

area("Key", (1.5, -7.5, 6.5), (math.radians(48), 0, math.radians(10)), 1500, 6)
area("FrontSoftbox", (0.5, -14.0, 7.0), (math.radians(62), 0, 0), 1400, 14)
area("FrontLow", (0.5, -12.0, 0.6), (math.radians(95), 0, 0), 250, 10, (0.75, 0.9, 1.0))
area("TopStrip", (1.5, 0.0, 6.5), (0, 0, 0), 1600, 14)
area("RimCyan", (8.0, 3.0, 2.5), (math.radians(-70), math.radians(25), math.radians(110)), 900, 3, (0.45, 0.85, 1.0))
area("RimLeft", (-8.0, 2.0, 3.0), (math.radians(-70), math.radians(-25), math.radians(-110)), 500, 3, (0.5, 0.85, 1.0))

cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 135
cam = bpy.data.objects.new("Cam", cam_data); scene.collection.objects.link(cam); scene.camera = cam
aim = bpy.data.objects.new("Aim", None); scene.collection.objects.link(aim)
aim.location = (0.75, 0, 1.0)
cam.location = (0.75, -50.0, 8.2)
track = cam.constraints.new("TRACK_TO"); track.target = aim
track.track_axis = "TRACK_NEGATIVE_Z"; track.up_axis = "UP_Y"

scene.render.filepath = str(out_dir / "froja-logo-3d-raw.png")
bpy.ops.render.render(write_still=True)
print("RENDERED", scene.render.filepath, scene.render.engine)
