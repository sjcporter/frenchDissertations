"""Join render_segments.py output: loop each hold PNG to its length, then concatenate everything losslessly-ish.

python3 join_segments.py segs_dir out.mp4
"""
import os
import json
import subprocess
import sys
from pathlib import Path

FF = os.environ.get("FFMPEG") or str(Path(__file__).resolve().parent.parent / "tools" / "ffmpeg")
d, out = Path(sys.argv[1]), sys.argv[2]
plan = json.load(open(d / "plan.json"))
fps = plan["fps"]
parts = []
if len(sys.argv) > 4:                                  # prefix mp4 and the number of its frames to keep
    pre = d / "prefix.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-i", sys.argv[3], "-frames:v", sys.argv[4], "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-g", "24", "-r", str(fps), str(pre)], check=True)
    parts.append(pre)
for st in plan["steps"]:
    f = d / st["file"]
    if st["type"] == "hold":
        mp4 = d / (f.stem + ".mp4")
        subprocess.run([FF, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", str(f), "-frames:v", str(st["frames"]),
                        "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-g", "24", "-r", str(fps), str(mp4)], check=True)
        f = mp4
    parts.append(f)
lst = d / "list.txt"
lst.write_text("".join(f"file '{p}'\n" for p in parts))
# re-encode once so differing encoder settings between Blender and ffmpeg segments cannot upset players
subprocess.run([FF, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c:v", "libx264", "-crf", "16",
                "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(fps), out], check=True)
print("wrote", out)
