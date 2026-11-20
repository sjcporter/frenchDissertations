"""blender -b University.blend --python render_clip.py -- out.mp4 start end"""
import sys, bpy
a = sys.argv[sys.argv.index("--") + 1:]
s = bpy.context.scene; r = s.render
r.film_transparent = False
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format, r.ffmpeg.codec = "MPEG4", "H264"
r.ffmpeg.constant_rate_factor, r.ffmpeg.ffmpeg_preset = "HIGH", "GOOD"
r.ffmpeg.audio_codec = "NONE"
s.frame_start, s.frame_end = int(a[1]), int(a[2])
r.filepath = a[0]
bpy.ops.render.render(animation=True)
