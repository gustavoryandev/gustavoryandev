#!/usr/bin/env python3
"""Deixa o SVG da GitHub City com o mesmo acabamento dos outros cards do perfil:
cantos arredondados e borda #1E1E1E.

Uso:
    python3 .github/scripts/style_city.py profile-3d-contrib/profile-city.svg
"""
import re
import sys

BACKGROUND = "#0A0A0A"  # mesmo fundo definido em conf/github-profile-3d-contrib.json
BORDER = "#1E1E1E"
RADIUS = 12  # igual aos cards do GitHub e do WakaTime


def style(svg):
    root = re.search(r"<svg\b[^>]*>", svg)
    if not root:
        return svg
    tag = root.group(0)

    view = re.search(r'viewBox="\s*[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)[ ,]+([\d.]+)\s*"', tag)
    if view:
        width, height = float(view.group(1)), float(view.group(2))
    else:
        w = re.search(r'\bwidth="([\d.]+)', tag)
        h = re.search(r'\bheight="([\d.]+)', tag)
        if not (w and h):
            return svg
        width, height = float(w.group(1)), float(h.group(1))

    # primeiro retângulo com a cor de fundo ganha cantos arredondados
    def round_bg(m):
        rect = m.group(0)
        return rect if " rx=" in rect else rect.replace("<rect", f'<rect rx="{RADIUS}"', 1)

    svg = re.sub(rf'<rect\b[^>]*fill="{BACKGROUND}"[^>]*>', round_bg, svg, count=1, flags=re.I)

    border = (
        f'<rect x="0.5" y="0.5" width="{width - 1:g}" height="{height - 1:g}" '
        f'rx="{RADIUS}" fill="none" stroke="{BORDER}" pointer-events="none"/>'
    )
    return svg.replace("</svg>", border + "</svg>")


def main():
    if len(sys.argv) < 2:
        sys.exit("Informe o caminho do SVG.")
    for path in sys.argv[1:]:
        try:
            with open(path, encoding="utf-8") as fh:
                svg = fh.read()
        except FileNotFoundError:
            print(f"Aviso: {path} não encontrado, pulando.")
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(style(svg))
        print(f"{path}: estilizado.")


if __name__ == "__main__":
    main()
