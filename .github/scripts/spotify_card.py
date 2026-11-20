#!/usr/bin/env python3
"""Gera 2 cards SVG do Spotify na paleta do perfil (preto + azul).

Cards gerados em spotify-card/:
    top-tracks.svg      músicas mais ouvidas (top 5)
    recent.svg          tocadas recentemente (5 únicas)

Variáveis de ambiente (secrets do repositório):
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REFRESH_TOKEN

Opcionais:
    SPOTIFY_RANGE    short_term | medium_term | long_term (padrão: short_term)
    SPOTIFY_OUT      pasta de saída (padrão: spotify-card)
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- paleta (a mesma do README)
BG = "#0A0A0A"
BORDER = "#1E1E1E"
TITLE = "#3B82F6"
ACCENT = "#38BDF8"
TEXT = "#FFFFFF"
MUTED = "#A1A1AA"
FAINT = "#6B7280"

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
W, H = 480, 280
PAD = 28

RANGES = {
    "short_term": "Últimas 4 semanas",
    "medium_term": "Últimos 6 meses",
    "long_term": "Desde sempre",
}


# ---------------------------------------------------------------- API
def get_access_token():
    cid = os.environ["SPOTIFY_CLIENT_ID"].strip()
    secret = os.environ["SPOTIFY_CLIENT_SECRET"].strip()
    refresh = os.environ["SPOTIFY_REFRESH_TOKEN"].strip()
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode(
            {"grant_type": "refresh_token", "refresh_token": refresh}
        ).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["access_token"]


def api(path, token):
    req = urllib.request.Request(
        f"https://api.spotify.com/v1{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


# ---------------------------------------------------------------- utilidades
def truncate(s, n):
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def artists(track):
    return ", ".join(a["name"] for a in track.get("artists", []))


def ago(iso):
    try:
        then = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    sec = max(0, int((datetime.now(timezone.utc) - then).total_seconds()))
    if sec < 3600:
        return f"há {max(1, sec // 60)} min"
    if sec < 86400:
        return f"há {sec // 3600} h"
    days = sec // 86400
    return f"há {days} {'dia' if days == 1 else 'dias'}"


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


def rows(items):
    """items: lista de (título, subtítulo, texto à direita)."""
    body = []
    for i, (name, sub, right) in enumerate(items):
        y = 104 + i * 34
        body.append(text(PAD, y + 4, i + 1, 15, ACCENT, 700))
        body.append(text(PAD + 26, y, truncate(name, 34 if right else 44), 13, TEXT, 600))
        body.append(text(PAD + 26, y + 15, truncate(sub, 44), 11, MUTED))
        if right:
            body.append(text(W - PAD, y, right, 11, FAINT, 400, "end"))
    return "".join(body)


def render_top(tracks, label):
    title = "Músicas mais ouvidas"
    if not tracks:
        return frame(title, label, text(PAD, 150, "Sem dados no período.", 13, MUTED))
    items = [(t["name"], artists(t), "") for t in tracks[:5]]
    return frame(title, f"{label} · Spotify", rows(items))


def render_recent(history):
    title = "Tocadas recentemente"
    items, seen = [], set()
    for entry in history:
        track = entry["track"]
        if track["id"] in seen:
            continue
        seen.add(track["id"])
        items.append((track["name"], artists(track), ago(entry["played_at"])))
        if len(items) == 5:
            break
    if not items:
        return frame(title, "Spotify", text(PAD, 150, "Sem reproduções recentes.", 13, MUTED))
    return frame(title, "Últimas músicas · Spotify", rows(items))


# ---------------------------------------------------------------- principal
def main():
    for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN"):
        if not os.environ.get(var, "").strip():
            sys.exit(f"Defina o secret {var}.")

    time_range = os.environ.get("SPOTIFY_RANGE", "short_term")
    if time_range not in RANGES:
        time_range = "short_term"
    out_dir = os.environ.get("SPOTIFY_OUT", "spotify-card")

    token = get_access_token()
    top = api(f"/me/top/tracks?time_range={time_range}&limit=5", token).get("items", [])
    recent = api("/me/player/recently-played?limit=50", token).get("items", [])

    cards = {
        "top-tracks.svg": render_top(top, RANGES[time_range]),
        "recent.svg": render_recent(recent),
    }
    os.makedirs(out_dir, exist_ok=True)
    for name, svg in cards.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"Gerado {out_dir}/{name}")


if __name__ == "__main__":
    main()
