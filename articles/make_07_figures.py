"""Render the tables and the formula of monograph 07 as images for platforms that
cannot display Markdown tables or math (X Articles, LinkedIn, Medium import).

Style follows articles/img/03_benchmark_metrics_table_en.png.
Run:  python articles/make_07_figures.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "img")
FONT_DIR = r"C:\Windows\Fonts"
REG = os.path.join(FONT_DIR, "segoeui.ttf")
BOLD = os.path.join(FONT_DIR, "segoeuib.ttf")

BG = (15, 17, 22)
HEAD_BG = (27, 32, 45)
ROW_BG = (20, 24, 33)
ROW_ALT = (24, 28, 38)
GOOD_BG = (17, 31, 28)
GRID = (42, 48, 62)
WHITE = (255, 255, 255)
GREY = (160, 170, 186)
AMBER = (245, 158, 11)
GREEN = (16, 185, 129)

W = 2000
PAD = 110


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def table(name, title, subtitle, header, rows, col_frac, good_col=None, footer=None):
    f_title, f_sub = font(BOLD, 46), font(REG, 30)
    f_head, f_first, f_cell = font(BOLD, 30), font(BOLD, 29), font(REG, 29)
    inner = W - 2 * PAD
    cols = [int(inner * c) for c in col_frac]
    cols[-1] = inner - sum(cols[:-1])
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    cell_pad, line_h = 28, 42

    def row_lines(cells, fonts):
        out = []
        for i, (c, fnt) in enumerate(zip(cells, fonts)):
            out.append(wrap(probe, c, fnt, cols[i] - 2 * cell_pad))
        return out

    head_lines = row_lines(header, [f_head] * len(header))
    head_h = max(len(l) for l in head_lines) * line_h + 2 * cell_pad
    body = []
    for r in rows:
        fonts = [f_first] + [f_cell] * (len(r) - 1)
        ls = row_lines(r, fonts)
        body.append((ls, fonts, max(len(l) for l in ls) * line_h + 2 * cell_pad))
    top = 230
    H = top + head_h + sum(h for _, _, h in body) + (150 if footer else 110)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((W / 2, 95), title, font=f_title, fill=WHITE, anchor="mm")
    d.text((W / 2, 160), subtitle, font=f_sub, fill=AMBER, anchor="mm")

    def draw_row(y, h, lines, fonts, bgs, colors):
        x = PAD
        for i, w in enumerate(cols):
            d.rectangle([x, y, x + w, y + h], fill=bgs[i], outline=GRID, width=2)
            n = len(lines[i])
            ty = y + (h - n * line_h) / 2 + line_h / 2
            for k, ln in enumerate(lines[i]):
                if i == 0:
                    d.text((x + cell_pad, ty + k * line_h), ln, font=fonts[i], fill=colors[i], anchor="lm")
                else:
                    d.text((x + w / 2, ty + k * line_h), ln, font=fonts[i], fill=colors[i], anchor="mm")
            x += w

    y = top
    draw_row(y, head_h, head_lines, [f_head] * len(cols), [HEAD_BG] * len(cols), [AMBER] * len(cols))
    y += head_h
    for j, (ls, fonts, h) in enumerate(body):
        base = ROW_BG if j % 2 == 0 else ROW_ALT
        bgs = [base] * len(cols)
        colors = [WHITE] + [GREY] * (len(cols) - 1)
        if good_col is not None:
            bgs[good_col] = GOOD_BG
            colors[good_col] = GREEN
        draw_row(y, h, ls, fonts, bgs, colors)
        y += h
    if footer:
        d.text((W / 2, y + 60), footer, font=font(REG, 24), fill=GREY, anchor="mm")
    path = os.path.join(OUT, name)
    im.save(path, optimize=True)
    return path


def formula(name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["mathtext.fontset"] = "cm"
    fig = plt.figure(figsize=(16, 3.0), dpi=125)
    fig.patch.set_facecolor("#0f1116")
    fig.text(0.5, 0.80, "ZERO-PHASE RESONANCE CORRECTION, APPLIED ONLY WHERE THE BUMP WAS FOUND",
             ha="center", va="center", color="#f59e0b", fontsize=15, family="Segoe UI")
    fig.text(0.5, 0.45, r"$y(t) = x(t) + w(t)\,\left[(H_{\mathrm{cut}} * x)(t) - x(t)\right],\qquad w(t) \in [0,\,1]$",
             ha="center", va="center", color="white", fontsize=34)
    fig.text(0.5, 0.12, "Where w(t) = 0, the audio stays bit-identical to the original.",
             ha="center", va="center", color="#a0aaba", fontsize=14, family="Segoe UI")
    path = os.path.join(OUT, name)
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(table(
        "07_table_audit_findings.png",
        "WHAT THE AUDIT FOUND",
        "PHARMAKON 3.1 ENGINE  //  EVERY FORMULA TESTED AGAINST A KNOWN ANSWER",
        ["Module", "What was wrong", "Consequence"],
        [
            ["LUFS meter", "K-weighting filter built with the wrong formula",
             "Filter off by up to 0.41 dB; EBU reference test 0.25 LU off (tolerance ±0.1 LU)"],
            ["Resonance detector", "Looked for the sharpest peak in the spectrum",
             "Cut notes by 8–10 dB, missed real resonances, flagged clean music every time"],
            ["De-harsher", "Compared amplitude with bandwidth instead of its square root",
             "A constant ~5.5 dB cut even on clean material"],
            ["Saturation", "HF pre-emphasis never compensated; distortion set by the source level",
             "Harsher top end; up to 3% distortion on acoustic guitar"],
            ["Sub-Sync", "Broken window blending around kicks", "Bass dips and clicks"],
            ["Stems saturation", "Bass and drums saturated without oversampling",
             "Aliasing at −31…−33 dB: digital grit on the kick"],
            ["Track Map", "Tempo from the sub band only; fixed section grid from 0:00; bass notes counted as kicks",
             "Wrong tempo on most non-four-on-the-floor music, misplaced sections, kick counts up to 2× too high"],
        ],
        [0.21, 0.37, 0.42],
    ))
    print(table(
        "07_table_sound_results.png",
        "WHAT CHANGED IN SOUND",
        "12 TRACKS ACROSS STYLES  //  LOUDNESS-MATCHED  //  CLASSIC 3.1 VS CLEAN CHAIN 3.2",
        ["Measure", "Classic 3.1", "Clean Chain 3.2"],
        [
            ["Persistent AI resonances (6 tracks)", "left in place on 4 of 6, +3.8…+6.5 dB",
             "below the 3 dB threshold on all 6; fully gone on 5"],
            ["Added sharpness (acum)", "+0.05…+0.07 on every track", "−0.01…+0.01"],
            ["\"Air\" 10–20 kHz", "+1.4…+1.9 dB", "+0.2…+0.3 dB"],
            ["Saturation distortion on music (8 tracks)", "−30…−38 dB, set by the source", "−43…−45 dB on every track"],
            ["Chain intermodulation (SMPTE test signal)", "−24 dB", "−33 dB"],
            ["Dynamics: crest factor vs. original", "−1.4…+0.2 dB (median −0.6)", "−0.2…+0.4 dB (median +0.1)"],
        ],
        [0.36, 0.30, 0.34],
        good_col=2,
        footer="Full-chain metrics on 6 tracks; saturation on 8 (2 tracks in both sets).",
    ))
    print(formula("07_formula_resonance_correction.png"))
