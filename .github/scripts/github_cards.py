#!/usr/bin/env python3
"""Gera 4 cards SVG de estatísticas do GitHub na paleta do portfólio.

Cards gerados em github-cards/:
    stats.svg          contribuições, commits, PRs, issues, estrelas, seguidores e sequências
    langs-repo.svg     linguagens por repositório (donut)
    langs-commit.svg   linguagens por commit (donut)
    commit-hours.svg   horários dos commits (horário de Brasília)

Variáveis de ambiente:
    GH_TOKEN         token da API (no Actions: GH_PAT, se existir, senão GITHUB_TOKEN)
    GH_LOGIN         usuário (padrão: dono do repositório)
    CARDS_OUT        pasta de saída (padrão: github-cards)
"""
import json
import math
import os
import sys
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from xml.sax.saxutils import escape

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("America/Sao_Paulo")
except Exception:  # sem tzdata: Brasília é UTC-3 o ano todo
    TZ = timezone(timedelta(hours=-3))

# ---------------------------------------------------------------- paleta
BG = "#0B192B"       # superfície do portfólio
BORDER = "#163A59"
TRACK = "#112238"
ACCENT = "#38BDF8"   # brand-400
LEVEL3 = "#167AB6"
LEVEL2 = "#145C91"
LEVEL1 = "#103454"
TEXT = "#E5E7EB"
WHITE = "#FFFFFF"
MUTED = "#A5BDDF"
FAINT = "#6E839E"
OTHER = "#41536B"
SLICES = ["#38BDF8", "#3B82F6", "#167AB6", "#6366F1", "#A5BDDF"]

FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
W, H = 480, 280
PAD = 28

PERIODS = [
    ("madrugada", 0, 5, "de madrugada"),
    ("manhã", 6, 11, "pela manhã"),
    ("tarde", 12, 17, "à tarde"),
    ("noite", 18, 23, "à noite"),
]


# ---------------------------------------------------------------- utilidades
def num(n):
    return f"{int(round(n)):,}".replace(",", ".")


def pct(p):
    return f"{p:.1f}".replace(".", ",") + "%"


def plural(n, one, many):
    return one if n == 1 else many


# ---------------------------------------------------------------- API
def gql(query, variables=None):
    token = os.environ["GH_TOKEN"]
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    if payload.get("errors") and not payload.get("data"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


MAIN_QUERY = """
query($login: String!) {
  user(login: $login) {
    id
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      nodes { stargazerCount forkCount primaryLanguage { name } }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository { name owner { login } primaryLanguage { name } }
        contributions { totalCount }
      }
    }
  }
}
"""


def fetch_commit_hours(user_id, repos, since):
    """Histograma de commits por hora (Brasília), com amostra de até 100 commits por repo."""
    hours = [0] * 24
    for start in range(0, len(repos), 10):
        parts = []
        for i, repo in enumerate(repos[start:start + 10]):
            owner = json.dumps(repo["owner"]["login"])
            name = json.dumps(repo["name"])
            parts.append(
                f"r{i}: repository(owner: {owner}, name: {name}) {{ defaultBranchRef {{ target {{ "
                f"... on Commit {{ history(first: 100, since: $since, author: {{id: $uid}}) "
                f"{{ nodes {{ committedDate }} }} }} }} }} }}"
            )
        query = "query($uid: ID!, $since: GitTimestamp!) {" + " ".join(parts) + "}"
        data = gql(query, {"uid": user_id, "since": since})
        for value in data.values():
            try:
                nodes = value["defaultBranchRef"]["target"]["history"]["nodes"]
            except (TypeError, KeyError):
                continue
            for node in nodes:
                stamp = datetime.fromisoformat(node["committedDate"].replace("Z", "+00:00"))
                hours[stamp.astimezone(TZ).hour] += 1
    return hours


# ---------------------------------------------------------------- sequências
def streaks(days, today):
    """days: {date: contribuições}. Retorna (atual, maior)."""
    current, d = 0, today
    if days.get(d, 0) <= 0:
        d -= timedelta(days=1)  # hoje ainda pode ganhar contribuições
    while days.get(d, 0) > 0:
        current += 1
        d -= timedelta(days=1)

    longest = run = 0
    previous = None
    for day in sorted(days):
        if days[day] > 0:
            run = run + 1 if previous and day - previous == timedelta(days=1) else 1
            longest = max(longest, run)
        else:
            run = 0
        previous = day
    return current, longest


def top_with_other(counter, limit=5):
    items = counter.most_common()
    head, tail = items[:limit], items[limit:]
    if tail:
        head.append(("Outras", sum(n for _, n in tail)))
    return head


# ---------------------------------------------------------------- SVG
def frame(title, subtitle, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{escape(title)}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="#0D6EFD"/><stop offset="1" stop-color="{ACCENT}"/>'
        f"</linearGradient></defs>"
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<rect x="{PAD}" y="24" width="26" height="3" rx="1.5" fill="url(#g)"/>'
        f'<text x="{PAD}" y="50" font-family="{FONT}" font-size="17" font-weight="700" fill="{ACCENT}">{escape(title)}</text>'
        f'<text x="{PAD}" y="70" font-family="{FONT}" font-size="12" fill="{MUTED}">{escape(subtitle)}</text>'
        f"{body}</svg>"
    )


def text(x, y, content, size=13, fill=TEXT, weight=400, anchor="start", extra=""):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(content))}</text>'
    )


def render_stats(login, s):
    metrics = [
        ("Contribuições", s["contributions"]),
        ("Commits", s["commits"]),
        ("Pull requests", s["prs"]),
        ("Issues", s["issues"]),
        ("Estrelas", s["stars"]),
        ("Seguidores", s["followers"]),
    ]
    body = []
    for i, (label, value) in enumerate(metrics):
        x = PAD + (i % 3) * 148
        y = 108 + (i // 3) * 62
        body.append(text(x, y, label.upper(), 10.5, MUTED, 600, extra='letter-spacing="0.8"'))
        body.append(text(x, y + 28, num(value), 26, WHITE, 700))
    body.append(f'<line x1="{PAD}" y1="220" x2="{W - PAD}" y2="220" stroke="{BORDER}"/>')
    for x, label, value in (
        (PAD, "SEQUÊNCIA ATUAL", s["current"]),
        (252, "MAIOR SEQUÊNCIA", s["longest"]),
    ):
        body.append(text(x, 242, label, 10.5, MUTED, 600, extra='letter-spacing="0.8"'))
        body.append(text(x, 264, f"{num(value)} {plural(value, 'dia', 'dias')}", 17, ACCENT, 700))
    return frame("Estatísticas do GitHub", f"@{login} · últimos 12 meses", "".join(body))


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


def render_langs(title, subtitle, counter, unit):
    total = sum(counter.values())
    if not total:
        return frame(title, subtitle, text(PAD, 150, "Sem dados no período.", 13, MUTED))
    items = top_with_other(counter, 5)
    shares = [n / total for _, n in items]
    colors = [OTHER if name == "Outras" else SLICES[i % len(SLICES)] for i, (name, _) in enumerate(items)]
    body = [donut(112, 178, 50, 22, shares, colors)]
    body.append(text(112, 180, num(total), 22, WHITE, 700, "middle"))
    body.append(text(112, 197, unit, 10.5, MUTED, 400, "middle"))
    for i, ((name, _), share, color) in enumerate(zip(items, shares, colors)):
        y = 128 + i * 25
        body.append(f'<circle cx="{212}" cy="{y - 4}" r="5" fill="{color}"/>')
        body.append(text(226, y, name, 13, TEXT))
        body.append(text(W - PAD, y, pct(share * 100), 13, MUTED, 700, "end"))
    return frame(title, subtitle, "".join(body))


def render_hours(hours):
    total = sum(hours)
    title, base = "Horários dos commits", "Horário de Brasília"
    if not total:
        return frame(title, base, text(PAD, 150, "Sem commits na amostra.", 13, MUTED))

    peak = max(range(24), key=lambda h: hours[h])
    best = max(PERIODS, key=lambda p: sum(hours[p[1]:p[2] + 1]))
    best_share = sum(hours[best[1]:best[2] + 1]) / total * 100
    subtitle = f"Pico às {peak}h · {pct(best_share)} dos commits {best[3]}"

    x0, width, baseline, max_h = PAD, W - 2 * PAD, 222, 118
    slot = width / 24
    bar_w = slot * 0.62
    biggest = max(hours)
    body = [f'<line x1="{PAD}" y1="{baseline}" x2="{W - PAD}" y2="{baseline}" stroke="{BORDER}"/>']
    for h, count in enumerate(hours):
        x = x0 + h * slot + (slot - bar_w) / 2
        if count:
            bar_h = max(3, count / biggest * max_h)
            color = ACCENT if h == peak else (LEVEL3 if count / biggest > 0.5 else LEVEL2)
            body.append(
                f'<rect x="{x:.1f}" y="{baseline - bar_h:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'rx="2.5" fill="{color}"/>'
            )
            if h == peak:
                body.append(text(f"{x + bar_w / 2:.1f}", f"{baseline - bar_h - 7:.1f}",
                                 pct(count / total * 100), 11, WHITE, 700, "middle"))
        else:
            body.append(
                f'<rect x="{x:.1f}" y="{baseline - 2}" width="{bar_w:.1f}" height="2" rx="1" fill="{LEVEL1}"/>'
            )
        if h % 3 == 0:
            body.append(text(f"{x + bar_w / 2:.1f}", 241, f"{h}h", 10, FAINT, 400, "middle"))
    body.append(text(PAD, 268, f"Amostra de {num(total)} commits · Horário de Brasília", 10, FAINT))
    return frame(title, subtitle, "".join(body))


# ---------------------------------------------------------------- principal
def main():
    login = os.environ.get("GH_LOGIN") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    if not login or not os.environ.get("GH_TOKEN"):
        sys.exit("Defina GH_TOKEN e GH_LOGIN (ou GITHUB_REPOSITORY_OWNER).")
    out_dir = os.environ.get("CARDS_OUT", "github-cards")

    user = gql(MAIN_QUERY, {"login": login})["user"]
    collection = user["contributionsCollection"]
    repos = user["repositories"]["nodes"] or []

    today = datetime.now(TZ).date()
    days = {}
    for week in collection["contributionCalendar"]["weeks"]:
        for d in week["contributionDays"]:
            day = date.fromisoformat(d["date"])
            if day <= today:
                days[day] = d["contributionCount"]
    current, longest = streaks(days, today)

    stats = {
        "contributions": collection["contributionCalendar"]["totalContributions"],
        "commits": collection["totalCommitContributions"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": user["followers"]["totalCount"],
        "current": current,
        "longest": longest,
    }

    by_repo = Counter(r["primaryLanguage"]["name"] for r in repos if r.get("primaryLanguage"))
    by_commit = Counter()
    commit_repos = collection["commitContributionsByRepository"] or []
    for item in commit_repos:
        language = (item["repository"].get("primaryLanguage") or {}).get("name")
        if language:
            by_commit[language] += item["contributions"]["totalCount"]

    hours = [0] * 24
    try:
        ranked = sorted(commit_repos, key=lambda i: -i["contributions"]["totalCount"])[:25]
        since = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hours = fetch_commit_hours(user["id"], [i["repository"] for i in ranked], since)
    except Exception as err:  # o card de horários é opcional
        print(f"Aviso: não foi possível obter os horários dos commits ({err}).")

    cards = {
        "stats.svg": render_stats(login, stats),
        "langs-repo.svg": render_langs("Linguagens por repositório", "Linguagem principal de cada repositório", by_repo, "repos"),
        "langs-commit.svg": render_langs("Linguagens por commit", "Commits dos últimos 12 meses", by_commit, "commits"),
        "commit-hours.svg": render_hours(hours),
    }
    os.makedirs(out_dir, exist_ok=True)
    for name, svg in cards.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print(f"Gerado {out_dir}/{name}")


if __name__ == "__main__":
    main()
