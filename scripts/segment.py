"""Deskew a source-ink image, find letter components, save a numbered overview + component data."""
import json, sys
from pathlib import Path
import cv2, numpy as np
src, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
img = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE)
ink = (img < 128).astype(np.uint8)
# deskew: angle of the best-fit line through component bottoms
n, lab, stats, cent = cv2.connectedComponentsWithStats(ink, 8)
big = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 400]
xs = np.array([stats[i, 0] + stats[i, 2] / 2 for i in big]); ys = np.array([stats[i, 1] + stats[i, 3] for i in big])
ang = np.degrees(np.arctan(np.polyfit(xs, ys, 1)[0])) if len(big) > 2 else 0.0
h, w = ink.shape
M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
cos, sin = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
rot = cv2.warpAffine(ink * 255, M, (nw, nh), flags=cv2.INTER_CUBIC)
rot = (rot > 127).astype(np.uint8)
rot = cv2.morphologyEx(rot, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))   # remove paint speckle
if "--vclose" in sys.argv:   # bridge a horizontal gap left by a wire/crack crossing the letters
    k = int(sys.argv[sys.argv.index("--vclose") + 1])
    rot = cv2.morphologyEx(rot, cv2.MORPH_CLOSE, np.ones((k, 3), np.uint8))
if "--close" in sys.argv:    # fill paint pitting inside strokes
    k = int(sys.argv[sys.argv.index("--close") + 1])
    rot = cv2.morphologyEx(rot, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
cv2.imwrite(str(out / "deskewed.png"), 255 - rot * 255)
n, lab, stats, cent = cv2.connectedComponentsWithStats(rot, 8)
comps = []
for i in range(1, n):
    x, y, cw, ch, a = stats[i]
    if a < 150: continue
    comps.append({"id": len(comps), "label_index": int(i), "bbox": [int(x), int(y), int(cw), int(ch)], "area": int(a)})
comps.sort(key=lambda c: c["bbox"][0])
for k, c in enumerate(comps): c["id"] = k
vis = cv2.cvtColor(255 - rot * 255, cv2.COLOR_GRAY2BGR)
for c in comps:
    x, y, cw, ch = c["bbox"]
    cv2.rectangle(vis, (x, y), (x + cw, y + ch), (40, 120, 255), 2)
    cv2.putText(vis, str(c["id"]), (x, max(15, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 30, 30), 2)
cv2.imwrite(str(out / "components.png"), vis)
np.save(out / "labels.npy", lab)
(out / "components.json").write_text(json.dumps({"deskew_degrees": round(float(ang), 2), "components": comps}, indent=1))
print("deskew", round(float(ang), 2), "components", len(comps))
