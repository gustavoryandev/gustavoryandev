#!/usr/bin/env python3
"""Gera 2 cards SVG do WakaTime na paleta do perfil (preto + azul).

Cards gerados em waka-card/:
    waka-time.svg      tempo por linguagem (donut)
    waka-percent.svg   porcentagem por linguagem (barras)

Uso (no GitHub Actions):
    WAKATIME_ACCESS_TOKEN=... python3 .github/scripts/waka_card.py

Variáveis opcionais:
    WAKA_RANGE   período da API (padrão: last_30_days)
    WAKA_OUT     pasta de saída (padrão: waka-card)
"""
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- paleta (a mesma do README)
BG = "#0A0A0A"       # fundo
BORDER = "#1E1E1E"   # borda / divisórias
TRACK = "#1E1E1E"    # trilho das barras e do donut
TITLE = "#3B82F6"    # títulos dos cards
ACCENT = "#38BDF8"   # destaques (pico, sequências)
LEVEL3 = "#3B82F6"
LEVEL2 = "#1D4ED8"
LEVEL1 = "#1E1E1E"
TEXT = "#FFFFFF"
WHITE = "#FFFFFF"
MUTED = "#A1A1AA"    # texto secundário
FAINT = "#6B7280"
OTHER = "#52525B"
SLICES = ["#38BDF8", "#3B82F6", "#6366F1", "#1D4ED8", "#A1A1AA"]

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
W, H = 480, 280
PAD = 28


# ---------------------------------------------------------------- utilidades
def fmt_time(seconds):
    seconds = int(seconds)
    h, m = seconds // 3600, (seconds % 3600) // 60
    return f"{h} h {m:02d} min" if h else f"{m} min"


def fmt_pct(p):
    return f"{p:.1f}".replace(".", ",") + "%"


def fmt_day(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m")
    except Exception:
        return ""


def fetch_stats(access_token, wk_range):
    url = f"https://wakatime.com/api/v1/users/current/stats/{wk_range}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    for _ in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 202:  # o WakaTime ainda está calculando
                    time.sleep(10)
                    continue
                return json.load(resp)["data"]
        except urllib.error.HTTPError as err:
            if err.code == 202:
                time.sleep(10)
                continue
            raise
    raise RuntimeError("WakaTime não retornou os dados a tempo.")


# ---------------------------------------------------------------- SVG
def text(x, y, content, size=13, fill=TEXT, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{escape(str(content))}</text>'
    )


def frame(title, subtitle, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{escape(title)}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="#0D6EFD"/><stop offset="1" stop-color="{ACCENT}"/>'
        f"</linearGradient></defs>"
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<rect x="{PAD}" y="24" width="26" height="3" rx="1.5" fill="url(#g)"/>'
        f'<text x="{PAD}" y="50" font-family="{FONT}" font-size="17" font-weight="700" fill="{TITLE}">{escape(title)}</text>'
        f'<text x="{PAD}" y="70" font-family="{FONT}" font-size="12" fill="{MUTED}">{escape(subtitle)}</text>'
        f"{body}</svg>"
    )


def donut(cx, cy, r, sw, shares, colors):
    circ = 2 * math.pi * r
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{TRACK}" stroke-width="{sw}"/>']
    offset = 0.0
    for share, color in zip(shares, colors):
        length = circ * share
        gap = 2 if length > 4 else 0
        dash = max(length - gap, 0.1)
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{dash:.2f} {circ - dash:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += length
    return "".join(out)


def languages(data):
    return [l for l in data.get("languages", []) if l.get("total_seconds", 0) > 0]


def subtitle_for(data, extra):
    start, end = fmt_day(data.get("start", "")), fmt_day(data.get("end", ""))
    period = f"{start} – {end}" if start and end else "Últimos 30 dias"
    return f"{period} · {extra}"


def render_time(data, limit=5):
    langs = languages(data)
    total = data.get("total_seconds") or sum(l["total_seconds"] for l in langs)
    subtitle = subtitle_for(data, f"total {fmt_time(total)}")
    if not langs or not total:
        return frame("Tempo por linguagem", subtitle, text(PAD, 150, "Sem dados no período.", 13, MUTED))

    items = [(l["name"], l["total_seconds"]) for l in langs[:limit]]
    rest = sum(l["total_seconds"] for l in langs[limit:])
    if rest:
        items.append(("Outras", rest))
    shares = [sec / total for _, sec in items]
    colors = [OTHER if name == "Outras" else SLICES[i % len(SLICES)] for i, (name, _) in enumerate(items)]

    hours, minutes = int(total) // 3600, (int(total) % 3600) // 60
    big, small = (f"{hours} h", f"{minutes:02d} min") if hours else (f"{minutes}", "min")
    body = [donut(112, 178, 50, 22, shares, colors)]
    body.append(text(112, 180, big, 22, WHITE, 700, "middle"))
    body.append(text(112, 197, small, 10.5, MUTED, 400, "middle"))
    for i, ((name, sec), color) in enumerate(zip(items, colors)):
        y = 128 + i * 25
        body.append(f'<circle cx="212" cy="{y - 4}" r="5" fill="{color}"/>')
        body.append(text(226, y, name, 13, TEXT))
        body.append(text(W - PAD, y, fmt_time(sec), 13, MUTED, 600, "end"))
    return frame("Tempo por linguagem", subtitle, "".join(body))


def render_percent(data, limit=6):
    langs = languages(data)[:limit]
    subtitle = subtitle_for(data, "participação no tempo total")
    if not langs:
        return frame("Porcentagem por linguagem", subtitle, text(PAD, 150, "Sem dados no período.", 13, MUTED))

    bar_x, bar_w = 142, 232
    body = []
    for i, lang in enumerate(langs):
        y = 108 + i * 28
        p = float(lang.get("percent", 0))
        fill_w = max(6, bar_w * p / 100)
        body.append(text(PAD, y, lang.get("name", "?"), 13, TEXT, 600))
        body.append(f'<rect x="{bar_x}" y="{y - 10}" width="{bar_w}" height="10" rx="5" fill="{TRACK}"/>')
        body.append(f'<rect x="{bar_x}" y="{y - 10}" width="{fill_w:.1f}" height="10" rx="5" fill="url(#g)"/>')
        body.append(text(W - PAD, y, fmt_pct(p), 13, WHITE, 700, "end"))
    return frame("Porcentagem por linguagem", subtitle, "".join(body))


# ---------------------------------------------------------------- principal
def main():
    access_token = os.environ.get("WAKATIME_ACCESS_TOKEN", "").strip()
    if not access_token:
        sys.exit("Defina a variável WAKATIME_ACCESS_TOKEN.")
    wk_range = os.environ.get("WAKA_RANGE", "last_30_days")
    out_dir = os.environ.get("WAKA_OUT", "waka-card")

    data = fetch_stats(access_token, wk_range)
    cards = {
        "waka-time.svg": render_time(data),
        "waka-percent.svg": render_percent(data),
    }
    os.makedirs(out_dir, exist_ok=True)
    for name, svg in cards.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"Gerado {out_dir}/{name}")

    old = os.path.join(out_dir, "waka-30d.svg")  # card largo da versão anterior
    if os.path.exists(old):
        os.remove(old)


if __name__ == "__main__":
    main()
