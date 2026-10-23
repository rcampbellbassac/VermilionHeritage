# Vermilion Heritage ດອກໄມ້

**A free display font for Lao, Thai, Khmer and English, drawn from a hand-painted sign photographed in Laos.**
Licensed under the [SIL Open Font License 1.1](OFL.txt). **Status: beta (0.100).** Some letters are still drafts.

[Try it online](https://rcampbellbassac.github.io/VermilionHeritage/) ·
[Download](https://github.com/rcampbellbassac/VermilionHeritage/releases/latest/download/VermilionHeritage.zip) ·
[All our fonts](https://rcampbellbassac.github.io/fonts/)

![The sign](docs/photo.jpg)

## The sign

Tall, narrow heritage sign-painting with moderate contrast and small carved curls.
Sign text: ມີເບ້ຍດອກໄມ້ຂາຍ ຫຼາຍຊະນິດ

Lao letters traced from the sign: **ມ ເ ບ ້ ຍ ດ ອ ຂ າ ຫ ຼ ຊ ະ ນ ິ**.
Every other letter, and all of Thai, Khmer and Latin, is generated to match their stroke and proportions, and is a
draft to be redrawn before 1.0.

## Install

1. Download `VermilionHeritage.zip` from the [latest release](https://github.com/rcampbellbassac/VermilionHeritage/releases/latest).
2. Unzip it, open `VermilionHeritage-Regular.ttf` and click **Install**.
3. On a website, use `VermilionHeritage-Regular.woff2`.

## Quality checks

- Shaping corpus (21 Lao/Thai/Khmer/Latin cases): 0 missing glyphs
- Required characters: 653/653; recommended: 607/625
- Full report: [qa/report.json](qa/report.json)

## Files

| Path | What |
|---|---|
| `fonts/` | TTF and WOFF2 |
| `sources/` | sign ink extraction, letter labels, traced outlines, build spec |
| `scripts/` | segmentation, tracing, fitting and merge tools |
| `docs/` | the website (GitHub Pages) |

## Credits

Designed by Robert Martin Campbell from his photograph. Generated letters derive from the
[Noto fonts](https://github.com/notofonts) (SIL OFL 1.1). See [FONTLOG.txt](FONTLOG.txt).
