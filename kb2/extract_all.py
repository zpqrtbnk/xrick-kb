#!/usr/bin/env python3
"""Run the whole RD2 asset extraction in order.   py -3 kb2/extract_all.py      (extract_gfx / extract_levels need Pillow)

    extract_hnk     kb2/assets/hnk/RICK_0N.HNK      -> kb2/assets/maps/map<N>_{demo,level_stage1,level}.bin, demos.json, manifest.json
    verify_hnk      independent checks of the above (raw disk sectors, live RAM, loader snapshots)
    extract_tables  level images                    -> kb2/assets/levels/tables.json      (submap headers, trigger/spawn tables, monster types)
    decode_scripts                                  -> kb2/assets/levels/scripts.json     (enemy move/animation byte-code)
    decode_scenes                                   -> kb2/assets/levels/scenes.json      (cut-scene scripts and their background images)
    extract_levels                                  -> kb2/assets/gfx/levelmap_map<N>_sub<I>.png, levelmaps.json
    extract_gfx                                     -> tiles, animated tiles, sprites, font, scene images (PNG)
Documentation of the container format and the loader: kb2/hnk-system.md.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for step in ("extract_hnk", "verify_hnk", "extract_tables", "decode_scripts", "decode_scenes", "extract_levels", "extract_gfx"):
    print("== " + step)
    r = subprocess.run([sys.executable, os.path.join(HERE, step + ".py")], cwd=os.path.dirname(HERE))
    if r.returncode:
        sys.exit("%s failed (%d)" % (step, r.returncode))
