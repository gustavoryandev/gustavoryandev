#!/usr/bin/env python3
"""Troca os verdes do gráfico do Pac-Man pelos azuis da paleta do perfil.

Uso:
    python3 .github/scripts/recolor_pacman.py dist/pacman-contribution-graph-dark.svg

Não depende dos códigos exatos de cor do tema: detecta as cores em que o verde
predomina, ordena da mais escura para a mais clara do tema (menos -> mais commits) e
mapeia para a escala de azuis abaixo.
"""
import re
import sys

# mesmas cores do heatmap do portfólio, do menos ao mais commits
PALETTE = ["#103454", "#145C91", "#167AB6", "#38BDF8"]
BACKGROUND = "#0B192B"  # fundo do painel do portfólio (substitui o #0d1117 do tema GitHub Dark)
BORDER = "#163A59"      # borda dos painéis do portfólio
LABEL = "#A5BDDF"       # cor dos rótulos (meses) no portfólio
RADIUS = 8              # cantos arredondados, como o rounded-lg do portfólio

HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def rgb(h):
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def is_green(h):
    r, g, b = rgb(h)
    return g > r + 10 and g > b + 10


def luminance(h):
    r, g, b = rgb(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def recolor(svg):
    greens = sorted({m.lower() for m in HEX.findall(svg) if is_green(m)}, key=luminance)
    mapping = {}
    for i, color in enumerate(greens):
        if len(greens) == 1:
            idx = len(PALETTE) - 2
        else:
            idx = round(i * (len(PALETTE) - 1) / (len(greens) - 1))
        mapping[color] = PALETTE[idx]

    svg = HEX.sub(lambda m: mapping.get(m.group(0).lower(), m.group(0)), svg)
    svg = re.sub(r"#0d1117\b", BACKGROUND, svg, flags=re.I)
    return svg, mapping


def recolor_text(svg):
    """Deixa os textos (meses) na cor de rótulo do portfólio."""

    def fix_tag(m):
        tag = m.group(0)
        if re.search(r'fill="[^"]*"', tag):
            tag = re.sub(r'fill="[^"]*"', f'fill="{LABEL}"', tag)
        elif not re.search(r"fill:", tag):
            tag = tag[:-1].rstrip("/") + f' fill="{LABEL}">'
        return re.sub(r"fill:\s*[^;\"]+", f"fill:{LABEL}", tag)

    svg = re.sub(r"<text\b[^>]*>", fix_tag, svg)

    def fix_rule(m):
        selector, body = m.group(1), m.group(2)
        if re.search(r"text|month|label|week", selector, re.I):
            body = re.sub(r"fill:\s*[^;}]+", f"fill:{LABEL}", body)
        return f"{selector}{{{body}}}"

    return re.sub(r"([^{}<>]+)\{([^{}]*)\}", fix_rule, svg)


def add_card_border(svg):
    """Arredonda o fundo e adiciona a borda #163A59, como o card do portfólio."""
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

    # fundo com cantos arredondados (primeiro rect com a cor de fundo)
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
        new_svg, mapping = recolor(svg)
        new_svg = add_card_border(recolor_text(new_svg))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_svg)
        print(f"{path}: {len(mapping)} cores trocadas -> {mapping}")
        rest = sorted({c.lower() for c in HEX.findall(new_svg)})
        print(f"Cores presentes no resultado: {rest}")


if __name__ == "__main__":
    main()
