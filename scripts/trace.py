"""Vectorize labelled sign components into UFO-style cubic contours (potrace), on a common baseline/scale.

  python trace.py SEGDIR LABELS.json OUT.json --body ບ --body-units 600
LABELS.json: {"ສ": [0], "ະ": [1, 2], ...}  (component ids from segment.py, merged per glyph)
"""
import json, sys
from pathlib import Path
import numpy as np, potrace
seg = Path(sys.argv[1]); labels = json.loads(Path(sys.argv[2]).read_text()); out = Path(sys.argv[3])
body_char = sys.argv[sys.argv.index("--body") + 1] if "--body" in sys.argv else None
body_units = float(sys.argv[sys.argv.index("--body-units") + 1]) if "--body-units" in sys.argv else 600.0
C = json.loads((seg / "components.json").read_text())["components"]
lab = np.load(seg / "labels.npy")
byid = {c["id"]: c for c in C}
def mask(ids):
    """ids: component numbers, or [x, y, w, h] boxes (all ink inside, for letters touching their neighbours)."""
    m = np.zeros(lab.shape, bool)
    for i in ids:
        if isinstance(i, list):
            x, y, w, h = i
            box = np.zeros(lab.shape, bool); box[y:y + h, x:x + w] = True
            m |= box & (lab > 0)
        else:
            m |= lab == byid[i]["label_index"]
    return m
def bbox(ids):
    ys, xs = np.nonzero(mask(ids))
    return [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
# baseline = median bottom of the base letters that sit on it; scale from the body letter's height
sitting = [bbox(ids) for ch, ids in labels.items() if ch in "ກຂຄງຈຊຍດຕຖທນບປຜຝພຟມຢຣລວສຫອຮາ"]
body_h = bbox(labels[body_char])[3]
scale = body_units / body_h
def baseline_for(b):
    """Signs have several text lines: use the bottoms of sitting letters on the same line as this glyph."""
    cy = b[1] + b[3] / 2
    line = [s for s in sitting if abs((s[1] + s[3] / 2) - cy) < 0.75 * body_h]
    # sloped or curved lines: only the nearest letters on the same line set the baseline here
    cx = b[0] + b[2] / 2
    line.sort(key=lambda s: abs(s[0] + s[2] / 2 - cx))
    same = [s[1] + s[3] for s in line[:3]]
    if not same:   # a mark: the nearest line below its centre
        below = [s for s in sitting if s[1] + s[3] / 2 > cy]
        ref = min(below or sitting, key=lambda s: abs((s[1] + s[3] / 2) - cy))
        same = [t[1] + t[3] for t in sitting if abs((t[1] + t[3] / 2) - (ref[1] + ref[3] / 2)) < 0.75 * body_h]
    return float(np.median(same))
glyphs = {}
import cv2
SMOOTH = float(sys.argv[sys.argv.index("--smooth") + 1]) if "--smooth" in sys.argv else 2.5
for ch, ids in labels.items():
    m = mask(ids)
    baseline = baseline_for(bbox(ids))
    if SMOOTH > 0:  # paint speckle and pixel steps are not letter geometry: blur and re-threshold
        b = cv2.GaussianBlur(m.astype(np.float32), (0, 0), SMOOTH)
        m = b > 0.5
    ys, xs = np.nonzero(m); x0 = xs.min()
    bmp = potrace.Bitmap(~m[::-1])          # potracer fills "dark" (False) pixels; y up
    plist = bmp.trace(turdsize=40, alphamax=1.1, opticurve=True, opttolerance=0.6)
    H = m.shape[0]
    def P(pt):  # image coords (y up from bottom of image) -> font units, x from glyph's left ink, y from baseline
        return {"x": round((pt.x - x0) * scale, 1), "y": round((pt.y - (H - baseline)) * scale, 1)}
    contours = []
    for curve in plist:
        pts = []
        start = curve.start_point
        for seg_ in curve.segments:
            if seg_.is_corner:
                pts.append({**P(seg_.c), "type": "line"}); pts.append({**P(seg_.end_point), "type": "line"})
            else:
                pts.append({**P(seg_.c1), "type": "offcurve"}); pts.append({**P(seg_.c2), "type": "offcurve"})
                pts.append({**P(seg_.end_point), "type": "curve"})
        contours.append(pts)
    glyphs[ch] = {"cp": f"{ord(ch):04X}", "contours": contours, "ink_width": round((xs.max() - x0 + 1) * scale, 1),
                  "ymin": round((baseline - ys.max()) * scale, 1), "ymax": round((baseline - ys.min()) * scale, 1)}
out.write_text(json.dumps({"scale": scale, "baseline_px": baseline, "glyphs": glyphs}, ensure_ascii=False))
print({ch: (g["ink_width"], g["ymin"], g["ymax"], len(g["contours"])) for ch, g in glyphs.items()})
