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

# do menos ao mais commits: azul claro = poucos commits, azul escuro = muitos
PALETTE = ["#7DD3FC", "#38BDF8", "#3B82F6", "#1D4ED8"]
BACKGROUND = "#0A0A0A"  # fundo da paleta (substitui o #0d1117 do tema GitHub Dark)

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
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_svg)
        print(f"{path}: {len(mapping)} cores trocadas -> {mapping}")


if __name__ == "__main__":
    main()
