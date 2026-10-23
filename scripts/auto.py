"""One sign style end to end: trace the labelled sign letters, fit the generated companions to them, build, review.

  python auto.py STYLE_DIR        (reads STYLE_DIR/style.json; writes traced.json, spec.json, build/, review/)

style.json:
  {"name": "Vermilion Heritage", "slug": "VermilionHeritage", "ink": "a", "body": "ບ",
   "labels": {"ບ": [3], ...},                      component ids from seg_<ink>/components.png
   "bases": {"lao": "lao-looped", ...},             optional, defaults below
   "nib": {"shape": "ellipse", "aspect": 0.7, "angle": 20},   optional, default round
   "effects": [{"op": "wobble", "amp": 4, "wave": 240}],      applied before the nib
   "weight_bias": 1.0, "width_bias": 1.0, "wght": 100, "baseline_snap": ["ໃ"], "per_script": {...}}

The generated (Noto-anatomy) letters are fitted to the traced ones by measurement: the nib size makes the
body letter's stem/height ratio match the sign, the wdth axis matches its width/height ratio, and the uniform
scale puts the generated body letter at the traced body height (600 units).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.home() / "Source/fontlab-mcp/src"))
from fontTools.ttLib import TTFont  # noqa: E402

from fontlab_mcp import family, offline, pen  # noqa: E402
from fontlab_mcp.stylize import _hits_horizontal, _poly  # noqa: E402

TOOLS = Path(__file__).resolve().parent
PY = sys.executable
BODY_UNITS = 600.0
DEFAULT_BASES = {"lao": "lao-looped", "thai": "thai-looped", "khmer": "khmer", "latin": "latin"}


def runs(mask_rows):
    out = []
    for row in mask_rows:
        r = np.flatnonzero(np.diff(np.concatenate([[0], row.astype(np.int8), [0]])))
        out += list(r[1::2] - r[::2])
    return out


def traced_metrics(seg: Path, ids):
    """Stem thickness and width of the body letter, both relative to its height (from the sign pixels)."""
    C = {c["id"]: c for c in json.loads((seg / "components.json").read_text())["components"]}
    lab = np.load(seg / "labels.npy")
    m = np.zeros(lab.shape, bool)
    for i in ids:
        if isinstance(i, list):
            x, y, w, h = i
            box = np.zeros(lab.shape, bool); box[y:y + h, x:x + w] = True
            m |= box & (lab > 0)
        else:
            m |= lab == C[i]["label_index"]
    ys, xs = np.nonzero(m)
    y0, y1 = ys.min(), ys.max()
    h = y1 - y0 + 1
    rows = m[int(y0 + 0.3 * h): int(y0 + 0.7 * h)]
    r = [v for v in runs(rows) if v > 1]
    stem = float(np.median(r))
    return stem / h, (xs.max() - xs.min() + 1) / h


def base_metrics(base_key: str, ch: str, wght: float, wdth: float = 100):
    tt = family._instance(family.BASES[base_key], wght, wdth)
    gs = tt.getGlyphSet()
    pc = offline._UFOPointCollector(gs)
    gs[tt.getBestCmap()[ord(ch)]].draw(pc)
    P = [_poly(c) for c in pc.contours]
    xs = [p[0] for q in P for p in q]; ys = [p[1] for q in P for p in q]
    H = max(ys) - min(ys)
    st = []
    for f in (0.35, 0.45, 0.55, 0.65):
        hits = _hits_horizontal(P, min(ys) + H * f)
        st += [hits[i + 1] - hits[i] for i in range(0, len(hits) - 1, 2)]
    return H, float(np.median(st)), max(xs) - min(xs)


def fit(style: dict, seg: Path):
    body = style.get("body", "ບ")
    if "fit" in style:   # no clean sign letter to measure: proportions read off the photograph by eye
        r_stem, r_width = style["fit"]["stem"], style["fit"]["width"]
    else:
        r_stem, r_width = traced_metrics(seg, style["labels"][body])
    r_stem *= style.get("weight_bias", 1.0)
    r_width *= style.get("width_bias", 1.0)
    nibd = style.get("nib", {"shape": "round"})
    shape, aspect, angle = nibd.get("shape", "round"), nibd.get("aspect", 1.0), nibd.get("angle", 0)
    bases = {**DEFAULT_BASES, **style.get("bases", {})}
    wght = style.get("wght", 100)
    H0, S0, W0 = base_metrics(bases["lao"], body, wght)
    # the nib's x/y extent per unit of w (a rotated flat nib is narrower across than its length)
    np_ = pen.nib_polygon(shape, 1.0, aspect if shape != "round" else None, angle)
    ex = max(p[0] for p in np_) - min(p[0] for p in np_)
    ey = max(p[1] for p in np_) - min(p[1] for p in np_)
    # stem after nib = S0 + ex*w ; height after nib = H0 + ey*w   ->  (S0+ex w)/(H0+ey w) = r_stem
    w = max(0.0, (r_stem * H0 - S0) / (ex - r_stem * ey))
    hgt = H0 + ey * w
    # width after nib = k*W0 + ex*w, wanted r_width*hgt -> wdth = 100k
    k = (r_width * hgt - ex * w) / W0
    wdth = float(min(100, max(62.5, 100 * k)))
    if wdth != 100:   # remeasure at that width (stems thin a little in narrow instances)
        H0, S0, W0 = base_metrics(bases["lao"], body, wght, wdth)
        w = max(0.0, (r_stem * H0 - S0) / (ex - r_stem * ey))
        hgt = H0 + ey * w
    scale = BODY_UNITS / hgt
    nib = {"op": "nib", "shape": shape, "w": round(w, 1), "min_hole": nibd.get("min_hole", 1200)}
    if shape != "round":
        nib.update(h=round(w * aspect, 1), angle=angle)
    return {"bases": bases, "wght": wght, "wdth": round(wdth, 1), "scale": round(scale, 4),
            "recipe": style.get("effects", []) + [nib],
            "fit": {"sign_stem_over_height": round(r_stem, 4), "sign_width_over_height": round(r_width, 4),
                    "base_height": round(H0), "base_stem": round(S0), "nib_w": round(w, 1)}}


def main():
    d = Path(sys.argv[1])
    style = json.loads((d / "style.json").read_text())
    seg = d / f"seg_{style.get('ink', 'a')}"
    (d / "labels.json").write_text(json.dumps(style["labels"], ensure_ascii=False))
    if not style["labels"]:
        (d / "traced.json").write_text(json.dumps({"glyphs": {}}))
    else:
      subprocess.run([PY, str(TOOLS / "trace.py"), str(seg), str(d / "labels.json"), str(d / "traced.json"),
                    "--body", style.get("body", "ບ"), "--body-units", str(BODY_UNITS),
                    "--smooth", str(style.get("smooth", 2.5))], check=True)
    # letters from further photos of the same sign, each normalised to its own body letter; first source wins
    for k, ex in enumerate(style.get("extra_sources", [])):
        lj, tj = d / f"labels_x{k}.json", d / f"traced_x{k}.json"
        lj.write_text(json.dumps(ex["labels"], ensure_ascii=False))
        subprocess.run([PY, str(TOOLS / "trace.py"), str((d / ex["seg"]).resolve()), str(lj), str(tj), "--body", ex["body"],
                        "--body-units", str(BODY_UNITS), "--smooth", str(ex.get("smooth", style.get("smooth", 2.5)))], check=True)
        main_t = json.loads((d / "traced.json").read_text())
        for ch, g in json.loads(tj.read_text())["glyphs"].items():
            main_t["glyphs"].setdefault(ch, g)
        (d / "traced.json").write_text(json.dumps(main_t, ensure_ascii=False))
    f = fit(style, seg)
    spec = {"name": style["name"], "slug": style["slug"], "version": "0.010", **f,
            "sidebearing": style.get("sidebearing", 40), "baseline_snap": style.get("baseline_snap", []),
            "copyright": ("Copyright 2026 Robert Martin Campbell. Lao key letters traced from a hand-painted sign "
                          "photographed in Laos (2019); other letters derived from the Noto fonts for Lao, Thai, Khmer and Latin "
                          "(Copyright 2022 The Noto Project Authors).")}
    for k in ("per_script", "tracking"):
        if k in style:
            spec[k] = style[k]
    (d / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    subprocess.run([PY, str(TOOLS / "hybrid.py"), str(d)], check=True)
    # how close did the generated letters land? (stems of generated vs traced letters, same units)
    ttf = d / "build" / f"{style['slug']}-Regular.ttf"
    tt = TTFont(ttf)
    gen = [c for c in "ກຄງນມວອ" if c not in style["labels"]][:3]
    rep = {"spec_fit": f["fit"], "wdth": f["wdth"], "scale": f["scale"]}
    for ch in gen + [style.get("body", "ບ")]:
        gs = tt.getGlyphSet(); pc = offline._UFOPointCollector(gs); gs[tt.getBestCmap()[ord(ch)]].draw(pc)
        P = [_poly(c) for c in pc.contours]; ys = [p[1] for q in P for p in q]
        hits = _hits_horizontal(P, min(ys) + (max(ys) - min(ys)) * 0.5)
        rep[ch] = {"height": round(max(ys) - min(ys)), "stems": [round(hits[i + 1] - hits[i]) for i in range(0, len(hits) - 1, 2)]}
    (d / "fit-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps(rep, ensure_ascii=False))
    subprocess.run([PY, str(TOOLS / "bible.py"), str(d), str(d / "photo.jpg"), style["name"],
                    "--seg", str(seg)], check=True)


if __name__ == "__main__":
    main()
