#!/usr/bin/env python3
"""Gera o card SVG do Spotify na paleta do perfil (preto + azul), no layout do portfólio.

Card gerado em spotify-card/:
    spotify.svg    ouvindo agora + reproduzidas recentemente + músicas favoritas + artistas favoritos

As imagens (capas e fotos) são baixadas e embutidas no SVG como data URI (base64),
porque o GitHub bloqueia imagens externas dentro de SVGs.

Variáveis de ambiente (secrets do repositório):
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REFRESH_TOKEN

Escopos necessários no refresh token:
    user-top-read, user-read-recently-played, user-read-currently-playing

Opcionais:
    SPOTIFY_RANGE    short_term | medium_term | long_term (padrão: short_term)
    SPOTIFY_OUT      pasta de saída (padrão: spotify-card)
    SPOTIFY_SITE     texto do rodapé (padrão: GUSTAVORYAN.VERCEL.APP)
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

# ---------------------------------------------------------------- paleta (a mesma do README)
BG = "#0A0A0A"
BORDER = "#1E1E1E"
TITLE = "#3B82F6"
ACCENT = "#38BDF8"
TEXT = "#FFFFFF"
MUTED = "#A1A1AA"
FAINT = "#6B7280"
BADGE = "#3F3F46"
SPOTIFY_GREEN = "#1DB954"

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', Consolas, monospace"
W, H = 900, 590
PAD = 36
COL_W = (W - 2 * PAD) // 3   # 276
COVER = 44
ROW = 56

RANGES = {
    "short_term": "Últimas 4 semanas",
    "medium_term": "Últimos 6 meses",
    "long_term": "Desde sempre",
}

_img_cache = {}
_uid = [0]


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


def api_optional(path, token):
    """Como api(), mas devolve None se não houver conteúdo (204) ou faltar permissão."""
    req = urllib.request.Request(
        f"https://api.spotify.com/v1{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 204:
                return None
            body = resp.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as err:
        print(f"Aviso: {path} retornou {err.code}.")
        return None


def image_data_uri(images):
    """Baixa a menor imagem da lista (64px) e devolve como data URI. None se falhar."""
    if not images:
        return None
    url = images[-1]["url"]  # a lista vem da maior para a menor
    if url in _img_cache:
        return _img_cache[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "profile-cards"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            mime = resp.headers.get_content_type() or "image/jpeg"
        uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception as err:
        print(f"Aviso: não foi possível baixar a imagem ({err}).")
        uri = None
    _img_cache[url] = uri
    return uri


# ---------------------------------------------------------------- utilidades
def truncate(s, n):
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def artists(track):
    return ", ".join(a["name"] for a in track.get("artists", []))


def track_item(track):
    return {
        "name": track["name"],
        "sub": artists(track),
        "cover": image_data_uri((track.get("album") or {}).get("images")),
        "explicit": bool(track.get("explicit")),
    }


def artist_item(artist):
    return {
        "name": artist["name"],
        "sub": "",
        "cover": image_data_uri(artist.get("images")),
        "explicit": False,
    }


# ---------------------------------------------------------------- SVG
def text(x, y, content, size=14, fill=TEXT, weight=400, anchor="start", family=FONT):
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}">{escape(str(content))}</text>'
    )


def image_svg(x, y, size, uri, circle=False):
    """Imagem com cantos arredondados (ou redonda); sem imagem, um bloco cinza."""
    radius = size / 2 if circle else 6
    if not uri:
        return f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{radius}" fill="{BORDER}"/>'
    _uid[0] += 1
    cid = f"c{_uid[0]}"
    return (
        f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{radius}"/></clipPath>'
        f'<image href="{uri}" x="{x}" y="{y}" width="{size}" height="{size}" '
        f'preserveAspectRatio="xMidYMid slice" clip-path="url(#{cid})"/>'
    )


def explicit_badge(x, y):
    return (
        f'<rect x="{x}" y="{y}" width="14" height="14" rx="3" fill="{BADGE}"/>'
        + text(x + 7, y + 11, "E", 10, TEXT, 700, "middle")
    )


def column(index, title, items, circle=False):
    x0 = PAD + index * COL_W
    body = [text(x0 + COL_W / 2, 226, title, 16, TEXT, 700, "middle")]
    text_x = x0 + 20 + COVER + 12
    for i, item in enumerate(items):
        y = 272 + i * ROW  # linha de base do nome
        body.append(text(x0, y + 5, i + 1, 16, ACCENT, 700))
        body.append(image_svg(x0 + 20, y - 20, COVER, item["cover"], circle))
        if item["sub"]:
            body.append(text(text_x, y, truncate(item["name"], 23), 14.5, TEXT, 600))
            sub_x, limit = text_x, 29
            if item["explicit"]:
                body.append(explicit_badge(text_x, y + 8))
                sub_x, limit = text_x + 20, 26
            body.append(text(sub_x, y + 19, truncate(item["sub"], limit), 12, MUTED))
        else:
            body.append(text(text_x, y + 5, truncate(item["name"], 23), 14.5, TEXT, 600))
    return "".join(body)


def equalizer(x, base):
    bars = []
    for i, (lo, hi, dur) in enumerate(((5, 14, 0.9), (14, 6, 1.1), (8, 14, 0.8))):
        bx = x + i * 5
        bars.append(
            f'<rect x="{bx}" y="{base - lo}" width="3" height="{lo}" rx="1.5" fill="{ACCENT}">'
            f'<animate attributeName="height" values="{lo};{hi};{lo + 3};{hi};{lo}" dur="{dur}s" repeatCount="indefinite"/>'
            f'<animate attributeName="y" values="{base - lo};{base - hi};{base - lo - 3};{base - hi};{base - lo}" '
            f'dur="{dur}s" repeatCount="indefinite"/></rect>'
        )
    return "".join(bars)


def now_playing(track):
    body = [text(W / 2, 112, "Ouvindo agora", 16, TEXT, 700, "middle")]
    if not track:
        body.append(text(W / 2, 146, "Nenhuma música tocando agora.", 14, MUTED, 400, "middle"))
        return "".join(body)
    body.append(equalizer(W / 2 - 84, 112))
    item = track_item(track)
    x = W / 2 - 170
    body.append(image_svg(x, 126, 52, item["cover"]))
    tx = x + 52 + 14
    body.append(text(tx, 148, truncate(item["name"], 40), 17, TEXT, 700))
    sub_x = tx
    if item["explicit"]:
        body.append(explicit_badge(tx, 158))
        sub_x = tx + 20
    body.append(text(sub_x, 169, truncate(item["sub"], 46), 13.5, MUTED))
    return "".join(body)


def spotify_logo(cx, cy):
    return (
        f'<g transform="translate({cx} {cy})">'
        f'<circle r="14" fill="{SPOTIFY_GREEN}"/>'
        f'<g fill="none" stroke="{BG}" stroke-linecap="round">'
        f'<path d="M-7,-4 Q0,-6.5 7.5,-2.5" stroke-width="2.4"/>'
        f'<path d="M-6,0.5 Q0,-1.5 6,2" stroke-width="2"/>'
        f'<path d="M-4.8,4.8 Q0,3.2 4.5,5.2" stroke-width="1.7"/>'
        f"</g></g>"
    )


def render(playing, recent, top_tracks, top_artists, label, site):
    title = "Spotify do Gustavo"
    body = [
        f'<rect x="{W / 2 - 17}" y="28" width="34" height="4" rx="2" fill="url(#g)"/>',
        text(W / 2, 62, title, 22, TITLE, 700, "middle"),
        text(W / 2, 84, f"Músicas e artistas favoritos · {label}", 13, MUTED, 400, "middle"),
        now_playing(playing),
        column(0, "Reproduzidas recentemente", recent),
        column(1, "Músicas favoritas", top_tracks),
        column(2, "Artistas favoritos", top_artists, circle=True),
        f'<line x1="{PAD}" y1="534" x2="{W - PAD}" y2="534" stroke="{BORDER}"/>',
        spotify_logo(PAD + 14, 562),
        text(W - PAD, 566, site, 11.5, FAINT, 400, "end", MONO),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{escape(title)}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="#0D6EFD"/><stop offset="1" stop-color="{ACCENT}"/>'
        f"</linearGradient></defs>"
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{BG}" stroke="{BORDER}"/>'
        f'{"".join(body)}</svg>'
    )


# ---------------------------------------------------------------- principal
def main():
    for var in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REFRESH_TOKEN"):
        if not os.environ.get(var, "").strip():
            sys.exit(f"Defina o secret {var}.")

    time_range = os.environ.get("SPOTIFY_RANGE", "short_term")
    if time_range not in RANGES:
        time_range = "short_term"
    out_dir = os.environ.get("SPOTIFY_OUT", "spotify-card")
    site = os.environ.get("SPOTIFY_SITE", "GUSTAVORYAN.VERCEL.APP")

    token = get_access_token()

    top_tracks = api(f"/me/top/tracks?time_range={time_range}&limit=5", token).get("items", [])
    top_artists = api(f"/me/top/artists?time_range={time_range}&limit=5", token).get("items", [])
    history = api("/me/player/recently-played?limit=50", token).get("items", [])

    current = api_optional("/me/player/currently-playing", token)
    playing = None
    if current and current.get("is_playing") and (current.get("item") or {}).get("type") == "track":
        playing = current["item"]

    recent, seen = [], set()
    for entry in history:
        track = entry["track"]
        if track["id"] in seen:
            continue
        seen.add(track["id"])
        recent.append(track)
        if len(recent) == 5:
            break

    svg = render(
        playing,
        [track_item(t) for t in recent],
        [track_item(t) for t in top_tracks[:5]],
        [artist_item(a) for a in top_artists[:5]],
        RANGES[time_range],
        site,
    )

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "spotify.svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"Gerado {path}")

    for old in ("top-tracks.svg", "recent.svg"):  # cards da versão anterior
        old_path = os.path.join(out_dir, old)
        if os.path.exists(old_path):
            os.remove(old_path)


if __name__ == "__main__":
    main()
