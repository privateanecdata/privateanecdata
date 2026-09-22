"""
Static SVG figures for a release. Pure string generation, deterministic, no dependencies.

Every figure carries its denominator, its intervals where shown, and the caveat sentence inside
the image (RELEASE_SPEC.md, presentation rules 1–3), so a screenshot cannot lose them. Presentation
attributes only — no <style>, no CSS — so the file renders identically under the site's
Content-Security-Policy when opened directly.
"""
import textwrap

W = 760
PAD = 28
LABEL_W = 250
VALUE_W = 150
ROW_H = 26
FONT = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
INK = "#1A1A1A"
MUTED = "#5F6B6A"
RULE = "#D8DEDD"
ACCENT = "#1F6F6B"
ACCENT_SOFT = "#8FBFBC"
SUPPRESSED = "#C7CFCE"
BG = "#FFFFFF"
CAVEAT = "Self-reported. Not evidence of effectiveness or safety. See methodology."


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def text(x, y, s, size=13, fill=INK, anchor="start", weight="normal"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')


def wrap(label, width=32):
    lines = textwrap.wrap(str(label), width=width) or [""]
    return lines[:2] if len(lines) <= 2 else lines[:1] + [lines[1][: width - 1] + "…"]


def value_text(cell, percent):
    if cell.get("count") is None:
        return cell.get("display", "fewer than 5")
    if percent and "pct" in cell:
        lo, hi = cell["ci95"]
        return f"{cell['pct']:.1f}%  ({lo:.0f}–{hi:.0f})   n={cell['count']}"
    return str(cell["count"])


def header(title, subtitle, y=PAD + 8):
    out = [text(PAD, y, title, size=17, weight="600")]
    y += 20
    for ln in (wrap(subtitle, 105) if subtitle else []):
        out.append(text(PAD, y, ln, size=12, fill=MUTED))
        y += 15
    return out, y + 18


def footer(y, release, n_label):
    out = [f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{RULE}" stroke-width="1"/>',
           text(PAD, y + 18, CAVEAT, size=11, fill=MUTED),
           text(W - PAD, y + 18, f"Private Anecdata · {release} · {n_label}", size=11, fill=MUTED, anchor="end")]
    return out, y + 32


def document(height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" role="img">\n'
            f'<rect width="{W}" height="{height}" fill="{BG}"/>\n' + "\n".join(body) + "\n</svg>\n")


def bar_chart(title, subtitle, table, release):
    """One-way distribution. `table` is the JSON table: {n, percent, cells:[...]}."""
    body, y = header(title, subtitle)
    n, percent = table["n"], table["percent"]
    bar_x = PAD + LABEL_W
    bar_w = W - PAD - VALUE_W - bar_x
    y += 4
    for cell in table["cells"]:
        lines = wrap(cell["label"])
        h = ROW_H if len(lines) == 1 else ROW_H + 14
        ty = y + 17
        for i, ln in enumerate(lines):
            body.append(text(PAD, ty + i * 14, ln, size=12))
        sup = cell.get("count") is None
        if sup:
            body.append(f'<rect x="{bar_x}" y="{y + 7}" width="6" height="12" fill="{SUPPRESSED}"/>')
        else:
            frac = cell["count"] / n if n else 0
            body.append(f'<rect x="{bar_x}" y="{y + 7}" width="{max(2, round(bar_w * frac, 1))}" height="12" fill="{ACCENT}"/>')
        body.append(text(W - PAD, ty, value_text(cell, percent), size=12, fill=MUTED if sup else INK, anchor="end"))
        y += h
    y += 8
    foot, y = footer(y, release, f"n = {n}")
    body += foot
    return document(y, body)


def grid_chart(title, subtitle, columns, rows, release, n_label):
    """
    Cross-tabulation rendered as a grid: one row per stratum, one column per category. Each cell
    shows its count (or "fewer than 5") with a small inline bar proportional to the stratum.
    `rows` items: {label, n (or None), display (when n is None), cells:[...], percent}.
    """
    body, y = header(title, subtitle)
    ncol = len(columns)
    grid_x = PAD + LABEL_W
    col_w = (W - PAD - 70 - grid_x) / ncol
    # column headings, wrapped to the column
    for j, col in enumerate(columns):
        for i, ln in enumerate(wrap(col, max(8, int(col_w / 6.5)))):
            body.append(text(grid_x + j * col_w, y + 10 + i * 13, ln, size=11, fill=MUTED))
    body.append(text(W - PAD, y + 10, "n", size=11, fill=MUTED, anchor="end"))
    y += 32
    body.append(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{RULE}" stroke-width="1"/>')
    for row in rows:
        lines = wrap(row["label"], 30)
        h = 34 if len(lines) == 1 else 46
        ty = y + 20
        for i, ln in enumerate(lines):
            body.append(text(PAD, ty + i * 14, ln, size=12))
        if row.get("n") is None:
            body.append(text(grid_x, ty, row.get("display", "not enough reports"), size=12, fill=MUTED))
        else:
            n = row["n"]
            for j, cell in enumerate(row["cells"]):
                cx = grid_x + j * col_w
                if cell.get("count") is None:
                    body.append(f'<rect x="{cx}" y="{y + 24}" width="6" height="4" fill="{SUPPRESSED}"/>')
                    body.append(text(cx, ty, "fewer than 5", size=11, fill=MUTED))
                else:
                    frac = cell["count"] / n
                    body.append(f'<rect x="{cx}" y="{y + 24}" width="{max(2, round((col_w - 10) * frac, 1))}" height="4" fill="{ACCENT}"/>')
                    label = f"{cell['pct']:.0f}% ({cell['ci95'][0]:.0f}–{cell['ci95'][1]:.0f})" if row.get("percent") and "pct" in cell else str(cell["count"])
                    body.append(text(cx, ty, label, size=12))
            body.append(text(W - PAD, ty, str(n), size=12, anchor="end"))
        y += h
        body.append(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" stroke="{RULE}" stroke-width="0.5"/>')
    y += 10
    foot, y = footer(y, release, n_label)
    body += foot
    return document(y, body)
