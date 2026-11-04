#!/usr/bin/env python3
"""Gera 3 cards SVG do WakaTime na paleta do perfil (preto + azul).

Cards gerados em waka-card/:
    waka-time.svg      tempo por linguagem (donut)
    waka-percent.svg   porcentagem por linguagem (barras)
    waka-alltime.svg   card largo com o tempo de programação de todo o período

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
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
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
WIDE_W, WIDE_H = 960, 320  # card largo (todo o tempo)
API = "https://wakatime.com/api/v1/users/current"
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


def http_json(url, token):
    """GET autenticado. Retorna (status, json|None); nunca levanta para status HTTP."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as err:
        return err.code, None


def poll(url, token, tries=8, wait=15):
    """O WakaTime responde 202 enquanto calcula; repete por ~2 min e aceita dados parciais."""
    partial = None
    for i in range(tries):
        status, body = http_json(url, token)
        if status == 200 and body:
            return body.get("data")
        if status in (401, 403):
            raise RuntimeError(f"WakaTime recusou o token (HTTP {status}); verifique WAKATIME_ACCESS_TOKEN.")
        if status == 202 and body and (body.get("data") or {}).get("total_seconds"):
            partial = body["data"]
        elif status not in (202, 429) and status < 500:
            print(f"Aviso: {url} -> HTTP {status}.")
            return None
        if i < tries - 1:
            time.sleep(wait)
    return partial


def fetch_summaries(token, days):
    """Plano B síncrono: soma os resumos diários (sem fila de cálculo do /stats)."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    status, body = http_json(f"{API}/summaries?start={start}&end={end}", token)
    if status != 200 or not body:
        return None
    seconds = {}
    for day in body.get("data", []):
        for lang in day.get("languages", []):
            seconds[lang["name"]] = seconds.get(lang["name"], 0) + lang.get("total_seconds", 0)
    total = sum(seconds.values())
    if not total:
        return None
    langs = [
        {"name": n, "total_seconds": sec, "percent": sec / total * 100}
        for n, sec in sorted(seconds.items(), key=lambda kv: -kv[1])
    ]
    return {"languages": langs, "total_seconds": total,
            "start": f"{start}T00:00:00Z", "end": f"{end}T23:59:59Z"}


def fetch_stats(token, wk_range):
    data = poll(f"{API}/stats/{wk_range}", token)
    if data and data.get("total_seconds"):
        return data
    m = re.fullmatch(r"last_(\d+)_days", wk_range)
    if m:
        print("Aviso: /stats indisponível; usando /summaries.")
        return fetch_summaries(token, int(m.group(1)))
    return None


def fetch_alltime(token):
    """Total de todo o período (all_time_since_today) + detalhes (stats/all_time), se disponíveis."""
    base = poll(f"{API}/all_time_since_today", token) or {}
    try:
        details = poll(f"{API}/stats/all_time", token, tries=4) or {}
    except RuntimeError:
        details = {}
    total = base.get("total_seconds") or details.get("total_seconds")
    if not total:
        return None
    rng = base.get("range") or {}
    since = rng.get("start_date") or (details.get("start") or "")[:10]
    avg = details.get("daily_average")
    if not avg and since:
        try:
            days = (date.today() - date.fromisoformat(since[:10])).days + 1
            avg = total / max(days, 1)
        except ValueError:
            avg = None
    return {
        "total": total, "since": since, "avg": avg,
        "best": details.get("best_day") or {},
        "languages": [l for l in details.get("languages", []) if l.get("total_seconds", 0) > 0],
        "editors": [e for e in details.get("editors", []) if e.get("total_seconds", 0) > 0],
    }


# ---------------------------------------------------------------- SVG
def text(x, y, content, size=13, fill=TEXT, weight=400, anchor="start", extra=""):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(content))}</text>'
    )


def frame(title, subtitle, body, w=W, h=H):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="{escape(title)}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="#0D6EFD"/><stop offset="1" stop-color="{ACCENT}"/>'
        f"</linearGradient></defs>"
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
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


def fmt_date(iso):
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return "—"


def bar_row(x, y, w, name, p):
    fill_w = max(5, w * p / 100)
    return (
        text(x, y, name, 13, TEXT, 600)
        + text(x + w, y, fmt_pct(p), 13, WHITE, 700, "end")
        + f'<rect x="{x}" y="{y + 8}" width="{w}" height="6" rx="3" fill="{TRACK}"/>'
        + f'<rect x="{x}" y="{y + 8}" width="{fill_w:.1f}" height="6" rx="3" fill="url(#g)"/>'
    )


def render_alltime(a):
    total = a["total"]
    since = fmt_date(a["since"]) if a["since"] else "—"
    title, subtitle = "Todo o tempo de programação", f"Desde {since} · WakaTime"
    label = 'letter-spacing="0.8"'
    hours = int(total) // 3600
    body = [text(PAD, 104, "TEMPO TOTAL", 10.5, MUTED, 600, extra=label),
            text(PAD, 146, f"{f'{hours:,}'.replace(',', '.')} h", 40, WHITE, 700),
            text(PAD, 166, f"≈ {f'{total / 86400:.1f}'.replace('.', ',')} dias sem parar", 12, MUTED)]
    best = a["best"]
    metrics = [
        ("MÉDIA DIÁRIA", fmt_time(a["avg"]) if a["avg"] else "—"),
        ("PRIMEIRO REGISTRO", since),
        ("MELHOR DIA", f"{fmt_time(best['total_seconds'])} · {fmt_date(best['date'])[:5]}" if best.get("date") else "—"),
    ]
    for i, (name, value) in enumerate(metrics):
        y = 198 + i * 42
        body.append(text(PAD, y, name, 10.5, MUTED, 600, extra=label))
        body.append(text(PAD, y + 22, value, 17, ACCENT, 700))

    cols = ((328, 300, "LINGUAGENS", a["languages"][:5]), (680, 252, "EDITORES", a["editors"][:4]))
    for x, w, head, items in cols:
        body.append(f'<line x1="{x - 28}" y1="92" x2="{x - 28}" y2="{WIDE_H - 24}" stroke="{BORDER}"/>')
        body.append(text(x, 104, head, 10.5, MUTED, 600, extra=label))
        if not items:
            body.append(text(x, 140, "Sem detalhes disponíveis.", 13, MUTED))
        for i, item in enumerate(items):
            body.append(bar_row(x, 136 + i * 38, w, item.get("name", "?"), float(item.get("percent", 0))))
    return frame(title, subtitle, "".join(body), WIDE_W, WIDE_H)


# ---------------------------------------------------------------- principal
def main():
    access_token = os.environ.get("WAKATIME_ACCESS_TOKEN", "").strip()
    if not access_token:
        sys.exit("Defina a variável WAKATIME_ACCESS_TOKEN.")
    wk_range = os.environ.get("WAKA_RANGE", "last_30_days")
    out_dir = os.environ.get("WAKA_OUT", "waka-card")

    cards = {}
    for label, job in (
        ("stats", lambda: fetch_stats(access_token, wk_range)),
        ("todo o período", lambda: fetch_alltime(access_token)),
    ):
        try:
            data = job()
        except Exception as err:
            print(f"Aviso: falha ao obter {label} ({err}).")
            continue
        if not data:
            print(f"Aviso: sem dados de {label}.")
        elif label == "stats":
            cards["waka-time.svg"] = render_time(data)
            cards["waka-percent.svg"] = render_percent(data)
        else:
            cards["waka-alltime.svg"] = render_alltime(data)

    os.makedirs(out_dir, exist_ok=True)
    if not cards:  # mantém os SVGs anteriores em vez de quebrar o workflow
        if any(f.endswith(".svg") for f in os.listdir(out_dir)):
            print("Aviso: WakaTime indisponível; cards anteriores mantidos.")
            return
        sys.exit("WakaTime não retornou dados e não há cards anteriores.")
    for name, svg in cards.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"Gerado {out_dir}/{name}")

    old = os.path.join(out_dir, "waka-30d.svg")  # card largo da versão anterior
    if os.path.exists(old):
        os.remove(old)


if __name__ == "__main__":
    main()
