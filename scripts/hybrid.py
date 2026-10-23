"""Sign hybrid: generated four-script family + traced sign letters substituted for the Lao letters the sign shows.

  python hybrid.py STYLE_DIR   (reads STYLE_DIR/spec.json, STYLE_DIR/traced.json; writes STYLE_DIR/build/)

spec.json: family spec for fontlab_mcp.family plus {"sidebearing": 40, "baseline_snap": ["ໃ"]}.
Traced base letters replace the generated outline; their GPOS attachment anchors are remapped linearly from
the generated glyph's ink box to the traced one, so marks still land on the traced letter. Traced marks are
placed over the generated mark's ink box (same centre x), keeping their traced height.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Source/fontlab-mcp/src"))
from fontTools.pens.cu2quPen import Cu2QuPen  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402

from fontlab_mcp import family  # noqa: E402


def tt_glyph(contours, dx=0.0, dy=0.0):
    pen = TTGlyphPen(None)
    q = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
    for c in contours:
        i = next(k for k, p in enumerate(c) if p["type"] != "offcurve")
        pts = c[i:] + c[:i]
        q.moveTo((pts[0]["x"] + dx, pts[0]["y"] + dy))
        offs = []
        for p in pts[1:] + [pts[0]]:
            xy = (p["x"] + dx, p["y"] + dy)
            if p["type"] == "offcurve":
                offs.append(xy)
            elif p["type"] == "curve":
                q.curveTo(*offs, xy); offs = []
            else:
                q.lineTo(xy)
        q.closePath()
    return pen.glyph()


def remap_anchors(tt: TTFont, maps: dict):
    """maps[glyph] = (old_xmin, old_w, new_xmin, new_w, dy): x' = new_xmin + (x-old_xmin)*new_w/old_w."""
    if "GPOS" not in tt:
        return
    def mv(a, g):
        if a is None or g not in maps:
            return
        ox, ow, nx, nw, dy = maps[g]
        a.XCoordinate = int(round(nx + (a.XCoordinate - ox) * (nw / ow if ow else 1)))
    for lookup in tt["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            t = lookup.LookupType
            if t == 9:
                t, st = st.ExtensionLookupType, st.ExtSubTable
            if t == 4:
                for g, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                    for a in rec.BaseAnchor:
                        mv(a, g)
            if t in (4, 6):
                cov, arr = (st.MarkCoverage, st.MarkArray) if t == 4 else (st.Mark1Coverage, st.Mark1Array)
                for g, rec in zip(cov.glyphs, arr.MarkRecord):
                    mv(rec.MarkAnchor, g)
            if t == 6:
                for g, rec in zip(st.Mark2Coverage.glyphs, st.Mark2Array.Mark2Record):
                    for a in rec.Mark2Anchor:
                        mv(a, g)


def main():
    d = Path(sys.argv[1])
    spec = json.loads((d / "spec.json").read_text())
    traced = json.loads((d / "traced.json").read_text())["glyphs"]
    sb = spec.get("sidebearing", 40)
    out = d / "build"
    # the generated family depends only on the recipe, not on the traced letters: cache it by recipe
    import hashlib, shutil
    key = hashlib.sha256(json.dumps({k: v for k, v in spec.items() if k not in ("name", "slug", "copyright", "version",
                                     "sidebearing", "baseline_snap")}, sort_keys=True).encode()).hexdigest()[:16]
    out.mkdir(parents=True, exist_ok=True)
    cached = out / f"generated-{key}.ttf"
    if not cached.exists():
        shutil.copy2(family.build_family(spec, out), cached)
    tt = TTFont(cached)
    glyf, hmtx, cmap = tt["glyf"], tt["hmtx"], tt.getBestCmap()
    maps, report = {}, {}
    for ch, g in traced.items():
        name = cmap.get(ord(ch))
        if not name:
            continue
        old = glyf[name]
        old.recalcBounds(glyf)
        o_xmin, o_xmax = getattr(old, "xMin", 0), getattr(old, "xMax", 0)
        o_ymin = getattr(old, "yMin", 0)
        adv = hmtx[name][0]
        dy = (-g["ymin"]) if ch in spec.get("baseline_snap", []) else 0.0
        if ch.isascii() and ch.isdigit():   # sign numerals are painted at their own size: match the font's digits
            o_ymax = getattr(old, "yMax", 0)
            f = (o_ymax - o_ymin) / max(1.0, g["ymax"] - g["ymin"])
            g = {**g, "contours": [[{**p, "x": p["x"] * f, "y": (p["y"] - g["ymin"]) * f + o_ymin} for p in c]
                                   for c in g["contours"]], "ink_width": g["ink_width"] * f, "ymin": o_ymin}
        if adv > 0:   # spacing letter: traced ink + sidebearings
            new = tt_glyph(g["contours"], dx=sb, dy=dy)
            new.recalcBounds(glyf)
            glyf[name] = new
            hmtx[name] = (int(round(g["ink_width"] + 2 * sb)), new.xMin)
            maps[name] = (o_xmin, o_xmax - o_xmin, new.xMin, new.xMax - new.xMin, dy)
        else:         # mark: centre traced ink over the generated mark's ink, at the generated mark's height
            cx = (o_xmin + o_xmax) / 2   # (above marks keep their bottom, below marks their top, so GPOS stacking holds)
            o_ymax = getattr(old, "yMax", 0)
            dy = (o_ymin - g["ymin"]) if o_ymin > 0 else (o_ymax - g["ymax"])
            new = tt_glyph(g["contours"], dx=cx - g["ink_width"] / 2, dy=dy)
            new.recalcBounds(glyf)
            glyf[name] = new
            hmtx[name] = (0, new.xMin)
            maps[name] = (o_xmin, o_xmax - o_xmin, new.xMin, new.xMax - new.xMin, dy)
        report[ch] = {"glyph": name, "advance": hmtx[name][0]}
    remap_anchors(tt, maps)
    family.finish(tt, spec)
    final = out / f"{spec['slug']}-Regular.ttf"
    tt.save(final)
    w = TTFont(final); w.flavor = "woff2"; w.save(final.with_suffix(".woff2"))
    print(json.dumps({"ttf": str(final), "traced_substituted": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
