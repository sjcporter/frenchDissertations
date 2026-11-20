"""Render single frames: blender -b University.blend --python render_stills.py -- out_dir f1 f2 ..."""
import sys, bpy
a = sys.argv[sys.argv.index("--") + 1:]
s = bpy.context.scene
s.render.film_transparent = False
s.render.image_settings.file_format = "PNG"
for f in a[1:]:
    s.frame_set(int(f))
    s.render.filepath = f"{a[0]}/f{int(f):04d}.png"
    bpy.ops.render.render(write_still=True)
