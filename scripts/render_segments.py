"""Render University.blend as an mp4, rendering each static card hold only once (run inside Blender).

Usage: blender -b University.blend --python render_segments.py -- out_dir
Writes seg_XXX.mp4 (animated stretches) and hold_XXX.png (one frame per static hold) plus plan.json for the joiner.
"""
import json
import os
import sys

import bpy

out_dir = sys.argv[sys.argv.index("--") + 1]
os.makedirs(out_dir, exist_ok=True)
s = bpy.context.scene
r = s.render
r.film_transparent = False
plan = json.load(open(os.path.join(os.path.dirname(bpy.data.filepath), "holds.json")))
holds, end = plan["holds"], s.frame_end
fps = s.render.fps

FROM = int(os.environ.get("FR_FROM", 0))                   # render only from this frame (an earlier render supplies the rest)
segs, cur = [], FROM                                   # animated stretches between holds
for a, b in holds:
    segs.append((cur, a - 1))                      # up to just before the hold
    cur = b + 1                                    # frame after the hold
segs.append((cur, end))

steps = []
for i, (a, b) in enumerate(segs):
    if b >= a:
        steps.append({"type": "seg", "file": f"seg_{i:03d}.mp4", "frames": b - a + 1, "a": a, "b": b})
    if i < len(holds):
        a, b = holds[i]
        steps.append({"type": "hold", "file": f"hold_{i:03d}.png", "frames": b - a + 1, "a": a})
json.dump({"fps": fps, "steps": steps}, open(os.path.join(out_dir, "plan.json"), "w"), indent=1)

for st in steps:
    path = os.path.join(out_dir, st["file"])
    if os.path.exists(path):
        print("SEG skip", st["file"])
        continue
    if st["type"] == "seg":
        r.image_settings.file_format = "FFMPEG"
        r.ffmpeg.format, r.ffmpeg.codec = "MPEG4", "H264"
        r.ffmpeg.constant_rate_factor, r.ffmpeg.ffmpeg_preset = "HIGH", "GOOD"
        r.ffmpeg.gopsize, r.ffmpeg.audio_codec = 24, "NONE"
        s.frame_start, s.frame_end = st["a"], st["b"]
        r.filepath = path
        bpy.ops.render.render(animation=True)
    else:
        r.image_settings.file_format = "PNG"
        r.image_settings.color_depth = "8"
        s.frame_set(st["a"])
        r.filepath = path
        bpy.ops.render.render(write_still=True)
    print("SEG done", st["file"], flush=True)
print("ANIM done segments", len(steps))
