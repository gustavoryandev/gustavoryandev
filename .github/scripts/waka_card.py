#!/usr/bin/env python3
"""Gera um card SVG com o resumo do WakaTime, na paleta Alvinegro + Azul.

Uso (no GitHub Actions):
    WAKATIME_API_KEY=... python3 .github/scripts/waka_card.py

Variáveis opcionais:
    WAKA_RANGE       período da API (padrão: last_30_days)
    WAKA_LANG_COUNT  quantidade de linguagens (padrão: 6)
    WAKA_OUT         arquivo de saída (padrão: waka-card/waka-30d.svg)
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

# Paleta do projeto
BG = "#0A0A0A"
BORDER = "#1E1E1E"
TRACK = "#1E1E1E"
TITLE = "#3B82F6"
TEXT = "#FFFFFF"
MUTED = "#A1A1AA"
FAINT = "#6B7280"
GRAD_A = "#0D6EFD"
GRAD_B = "#38BDF8"

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"

WIDTH = 800
BAR_X = 170
BAR_W = 400
PCT_X = 650
TIME_X = 768


def fmt_time(seconds):
    seconds = int(seconds)
    h, m = seconds // 3600, (seconds % 3600) // 60
    if h:
        return f"{h} h {m:02d} min"
    return f"{m} min"


def fmt_pct(p):
    return f"{p:.2f}".replace(".", ",") + " %"


def fmt_date(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        return ""


def fetch_stats(api_key, wk_range):
    url = f"https://wakatime.com/api/v1/users/current/stats/{wk_range}"
    token = base64.b64encode(api_key.encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    for attempt in range(6):
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


def render(data, lang_count=6, title="Resumo dos últimos 30 dias"):
    langs = [l for l in data.get("languages", []) if l.get("total_seconds", 0) > 0]
    langs = langs[:lang_count]

    total = fmt_time(data.get("total_seconds", 0))
    start, end = fmt_date(data.get("start", "")), fmt_date(data.get("end", ""))
    period = f"{start} – {end}" if start and end else ""
    updated = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    first_row_y = 134
    step = 36
    rows = max(len(langs), 1)
    height = first_row_y + (rows - 1) * step + 54

    out = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="{escape(title)}">'
    )
    out.append(
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{GRAD_A}"/><stop offset="1" stop-color="{GRAD_B}"/>'
        f"</linearGradient></defs>"
    )
    out.append(
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" rx="12" '
        f'fill="{BG}" stroke="{BORDER}"/>'
    )
    out.append(
        f'<text x="32" y="46" font-family="{FONT}" font-size="20" font-weight="600" '
        f'fill="{TITLE}">{escape(title)}</text>'
    )
    if period:
        out.append(
            f'<text x="{WIDTH - 32}" y="46" text-anchor="end" font-family="{FONT}" '
            f'font-size="13" fill="{MUTED}">{escape(period)}</text>'
        )
    out.append(
        f'<text x="32" y="78" font-family="{FONT}" font-size="14" fill="{MUTED}">'
        f'Tempo total de código: <tspan fill="{TEXT}" font-weight="700">{escape(total)}</tspan></text>'
    )
    out.append(f'<line x1="32" y1="98" x2="{WIDTH - 32}" y2="98" stroke="{BORDER}"/>')

    if not langs:
        out.append(
            f'<text x="32" y="{first_row_y}" font-family="{FONT}" font-size="14" '
            f'fill="{MUTED}">Sem dados no período.</text>'
        )
    for i, lang in enumerate(langs):
        y = first_row_y + i * step
        pct = float(lang.get("percent", 0))
        fill_w = max(6, BAR_W * pct / 100)
        name = escape(lang.get("name", "?"))
        out.append(
            f'<text x="32" y="{y}" font-family="{FONT}" font-size="14" font-weight="600" '
            f'fill="{TEXT}">{name}</text>'
        )
        out.append(
            f'<rect x="{BAR_X}" y="{y - 10}" width="{BAR_W}" height="10" rx="5" fill="{TRACK}"/>'
        )
        out.append(
            f'<rect x="{BAR_X}" y="{y - 10}" width="{fill_w:.1f}" height="10" rx="5" fill="url(#g)"/>'
        )
        out.append(
            f'<text x="{PCT_X}" y="{y}" text-anchor="end" font-family="{FONT}" '
            f'font-size="14" font-weight="700" fill="{TEXT}">{fmt_pct(pct)}</text>'
        )
        out.append(
            f'<text x="{TIME_X}" y="{y}" text-anchor="end" font-family="{FONT}" '
            f'font-size="13" fill="{MUTED}">{escape(fmt_time(lang.get("total_seconds", 0)))}</text>'
        )

    out.append(
        f'<text x="{WIDTH - 32}" y="{height - 18}" text-anchor="end" font-family="{FONT}" '
        f'font-size="11" fill="{FAINT}">Dados do WakaTime · atualizado em {updated}</text>'
    )
    out.append("</svg>")
    return "\n".join(out)


def main():
    api_key = os.environ.get("WAKATIME_API_KEY")
    if not api_key:
        sys.exit("Defina a variável WAKATIME_API_KEY.")
    wk_range = os.environ.get("WAKA_RANGE", "last_30_days")
    lang_count = int(os.environ.get("WAKA_LANG_COUNT", "6"))
    out_path = os.environ.get("WAKA_OUT", "waka-card/waka-30d.svg")

    data = fetch_stats(api_key, wk_range)
    svg = render(data, lang_count)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Card gerado em {out_path}")


if __name__ == "__main__":
    main()
