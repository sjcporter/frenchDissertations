"""Render the saved University.blend as an H.264 mp4 (run inside Blender: blender -b file --python render_animation.py -- out.mp4)."""
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
s = bpy.context.scene
r = s.render
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "HIGH"
r.ffmpeg.ffmpeg_preset = "GOOD"
r.ffmpeg.gopsize = 24
r.ffmpeg.audio_codec = "NONE"
r.film_transparent = False  # the stills use transparent film for the poster; video needs the background
r.filepath = out
import os
if os.environ.get("FR_START"):
    s.frame_start = int(os.environ["FR_START"])  # render only the new tail of the timeline
print("ANIM frames", s.frame_start, s.frame_end, "size", r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100)
bpy.ops.render.render(animation=True)
print("ANIM done", out)
