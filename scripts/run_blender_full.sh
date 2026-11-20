#!/bin/bash
# Full chain: prepare inputs -> Blender build -> render frame 81
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
A=fr-directors-2005-2025
P=${UE_PIPELINE:-$HOME/Documents/UniversityExplorer/graph-pipeline}
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
python3 scripts/prepare_blender_inputs.py --asset $A
echo "== prepared $(date)"
$B -b $P/templates/University_template.blend --python $ROOT/scripts/geonodes_directors.py -- $A $ROOT/blender/
echo "== built $(date)"
$B -b blender/$A/University.blend -o blender/$A/${A}A0# -f 81
echo "== rendered $(date)"
