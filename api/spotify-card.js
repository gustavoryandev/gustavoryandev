// api/spotify-card.js
// Gera o card do Spotify (SVG) na hora, a cada visita ao README.
// Variáveis de ambiente (Vercel): SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REFRESH_TOKEN
// Escopos do refresh token: user-top-read, user-read-recently-played, user-read-currently-playing
// Query opcional: ?range=short_term | medium_term | long_term

const BG = "#0A0A0A";
const BORDER = "#1E1E1E";
const TITLE = "#3B82F6";
const ACCENT = "#38BDF8";
const TEXT = "#FFFFFF";
const MUTED = "#A1A1AA";
const FAINT = "#6B7280";
const BADGE = "#3F3F46";
const SPOTIFY_GREEN = "#1DB954";

const FONT = "Inter, 'Segoe UI', Helvetica, Arial, sans-serif";
const MONO = "'JetBrains Mono', 'Fira Code', Consolas, monospace";
const W = 900;
const H = 590;
const PAD = 36;
const COL_W = Math.floor((W - 2 * PAD) / 3);
const COVER = 44;
const ROW = 56;
const SITE = "GUSTAVORYAN.VERCEL.APP";

const RANGES = {
  short_term: "Últimas 4 semanas",
  medium_term: "Últimos 6 meses",
  long_term: "Desde sempre",
};

// ------------------------------------------------------------ cache entre execuções "quentes"
let tokenCache = { value: null, exp: 0 };
const imgCache = new Map();

// ------------------------------------------------------------ API
async function getAccessToken() {
  if (tokenCache.value && Date.now() < tokenCache.exp) return tokenCache.value;

  const id = (process.env.SPOTIFY_CLIENT_ID || "").trim();
  const secret = (process.env.SPOTIFY_CLIENT_SECRET || "").trim();
  const refresh = (process.env.SPOTIFY_REFRESH_TOKEN || "").trim();
  if (!id || !secret || !refresh) throw new Error("Variáveis do Spotify ausentes");

  const basic = Buffer.from(`${id}:${secret}`).toString("base64");
  const r = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: refresh }),
  });
  if (!r.ok) throw new Error(`Token do Spotify: ${r.status}`);
  const j = await r.json();
  tokenCache = { value: j.access_token, exp: Date.now() + (j.expires_in - 60) * 1000 };
  return j.access_token;
}

async function api(path, token, optional = false) {
  const r = await fetch(`https://api.spotify.com/v1${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (r.status === 204) return null;
  if (!r.ok) {
    if (optional) return null;
    throw new Error(`${path}: ${r.status}`);
  }
  return r.json();
}

async function imageUri(images) {
  if (!images || !images.length) return null;
  const url = images[images.length - 1].url; // a lista vem da maior para a menor
  if (imgCache.has(url)) return imgCache.get(url);
  let uri = null;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(String(r.status));
    const buf = Buffer.from(await r.arrayBuffer());
    const mime = r.headers.get("content-type") || "image/jpeg";
    uri = `data:${mime};base64,${buf.toString("base64")}`;
  } catch (err) {
    console.warn("Imagem não baixada:", err.message);
  }
  if (imgCache.size > 200) imgCache.clear();
  imgCache.set(url, uri);
  return uri;
}

// ------------------------------------------------------------ utilidades
const esc = (s) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const truncate = (s, n) => {
  s = String(s);
  return s.length <= n ? s : s.slice(0, n - 1).trimEnd() + "…";
};

const artistsOf = (track) => (track.artists || []).map((a) => a.name).join(", ");

async function trackItem(track) {
  return {
    name: track.name,
    sub: artistsOf(track),
    cover: await imageUri((track.album || {}).images),
    explicit: Boolean(track.explicit),
  };
}

async function artistItem(artist) {
  return { name: artist.name, sub: "", cover: await imageUri(artist.images), explicit: false };
}

// ------------------------------------------------------------ SVG
function text(x, y, content, size = 14, fill = TEXT, weight = 400, anchor = "start", family = FONT) {
  return (
    `<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" font-weight="${weight}" ` +
    `fill="${fill}" text-anchor="${anchor}">${esc(content)}</text>`
  );
}

function makeRenderer() {
  let uid = 0;

  function imageSvg(x, y, size, uri, circle = false) {
    const radius = circle ? size / 2 : 6;
    if (!uri) {
      return `<rect x="${x}" y="${y}" width="${size}" height="${size}" rx="${radius}" fill="${BORDER}"/>`;
    }
    uid += 1;
    const cid = `c${uid}`;
    return (
      `<clipPath id="${cid}"><rect x="${x}" y="${y}" width="${size}" height="${size}" rx="${radius}"/></clipPath>` +
      `<image href="${uri}" x="${x}" y="${y}" width="${size}" height="${size}" ` +
      `preserveAspectRatio="xMidYMid slice" clip-path="url(#${cid})"/>`
    );
  }

  const explicitBadge = (x, y) =>
    `<rect x="${x}" y="${y}" width="14" height="14" rx="3" fill="${BADGE}"/>` +
    text(x + 7, y + 11, "E", 10, TEXT, 700, "middle");

  function column(index, title, items, circle = false) {
    const x0 = PAD + index * COL_W;
    const body = [text(x0 + COL_W / 2, 226, title, 16, TEXT, 700, "middle")];
    const textX = x0 + 20 + COVER + 12;
    items.forEach((item, i) => {
      const y = 272 + i * ROW;
      body.push(text(x0, y + 5, i + 1, 16, ACCENT, 700));
      body.push(imageSvg(x0 + 20, y - 20, COVER, item.cover, circle));
      if (item.sub) {
        body.push(text(textX, y, truncate(item.name, 23), 14.5, TEXT, 600));
        let subX = textX;
        let limit = 29;
        if (item.explicit) {
          body.push(explicitBadge(textX, y + 8));
          subX = textX + 20;
          limit = 26;
        }
        body.push(text(subX, y + 19, truncate(item.sub, limit), 12, MUTED));
      } else {
        body.push(text(textX, y + 5, truncate(item.name, 23), 14.5, TEXT, 600));
      }
    });
    return body.join("");
  }

  function equalizer(x, base) {
    return [
      [5, 14, 0.9],
      [14, 6, 1.1],
      [8, 14, 0.8],
    ]
      .map(([lo, hi, dur], i) => {
        const bx = x + i * 5;
        return (
          `<rect x="${bx}" y="${base - lo}" width="3" height="${lo}" rx="1.5" fill="${ACCENT}">` +
          `<animate attributeName="height" values="${lo};${hi};${lo + 3};${hi};${lo}" dur="${dur}s" repeatCount="indefinite"/>` +
          `<animate attributeName="y" values="${base - lo};${base - hi};${base - lo - 3};${base - hi};${base - lo}" ` +
          `dur="${dur}s" repeatCount="indefinite"/></rect>`
        );
      })
      .join("");
  }

  function nowPlaying(item) {
    const body = [text(W / 2, 112, "Ouvindo agora", 16, TEXT, 700, "middle")];
    if (!item) {
      body.push(text(W / 2, 146, "Nenhuma música tocando agora.", 14, MUTED, 400, "middle"));
      return body.join("");
    }
    body.push(equalizer(W / 2 - 84, 112));
    const x = W / 2 - 170;
    body.push(imageSvg(x, 126, 52, item.cover));
    const tx = x + 52 + 14;
    body.push(text(tx, 148, truncate(item.name, 40), 17, TEXT, 700));
    let subX = tx;
    if (item.explicit) {
      body.push(explicitBadge(tx, 158));
      subX = tx + 20;
    }
    body.push(text(subX, 169, truncate(item.sub, 46), 13.5, MUTED));
    return body.join("");
  }

  const spotifyLogo = (cx, cy) =>
    `<g transform="translate(${cx} ${cy})">` +
    `<circle r="14" fill="${SPOTIFY_GREEN}"/>` +
    `<g fill="none" stroke="${BG}" stroke-linecap="round">` +
    `<path d="M-7,-4 Q0,-6.5 7.5,-2.5" stroke-width="2.4"/>` +
    `<path d="M-6,0.5 Q0,-1.5 6,2" stroke-width="2"/>` +
    `<path d="M-4.8,4.8 Q0,3.2 4.5,5.2" stroke-width="1.7"/>` +
    `</g></g>`;

  function render({ playing, recent, topTracks, topArtists, label }) {
    const title = "Spotify do Gustavo";
    const body = [
      `<rect x="${W / 2 - 17}" y="28" width="34" height="4" rx="2" fill="url(#g)"/>`,
      text(W / 2, 62, title, 22, TITLE, 700, "middle"),
      text(W / 2, 84, `Músicas e artistas favoritos · ${label}`, 13, MUTED, 400, "middle"),
      nowPlaying(playing),
      column(0, "Reproduzidas recentemente", recent),
      column(1, "Músicas favoritas", topTracks),
      column(2, "Artistas favoritos", topArtists, true),
      `<line x1="${PAD}" y1="534" x2="${W - PAD}" y2="534" stroke="${BORDER}"/>`,
      spotifyLogo(PAD + 14, 562),
      text(W - PAD, 566, SITE, 11.5, FAINT, 400, "end", MONO),
    ];
    return (
      `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" ` +
      `role="img" aria-label="${esc(title)}">` +
      `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">` +
      `<stop offset="0" stop-color="#0D6EFD"/><stop offset="1" stop-color="${ACCENT}"/>` +
      `</linearGradient></defs>` +
      `<rect x="0.5" y="0.5" width="${W - 1}" height="${H - 1}" rx="14" fill="${BG}" stroke="${BORDER}"/>` +
      `${body.join("")}</svg>`
    );
  }

  return { render };
}

function errorCard(message) {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="140" viewBox="0 0 ${W} 140" role="img" aria-label="Erro">` +
    `<rect x="0.5" y="0.5" width="${W - 1}" height="139" rx="14" fill="${BG}" stroke="${BORDER}"/>` +
    text(W / 2, 66, "Spotify do Gustavo", 20, TITLE, 700, "middle") +
    text(W / 2, 94, message, 14, MUTED, 400, "middle") +
    `</svg>`
  );
}

// ------------------------------------------------------------ handler
export default async function handler(req, res) {
  // sem cache: o GitHub busca de novo a cada carregamento do perfil
  res.setHeader("Content-Type", "image/svg+xml; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-store, max-age=0, must-revalidate");

  try {
    const range = RANGES[req.query.range] ? req.query.range : "short_term";
    const token = await getAccessToken();

    const [topTracksRes, topArtistsRes, historyRes, currentRes] = await Promise.all([
      api(`/me/top/tracks?time_range=${range}&limit=5`, token),
      api(`/me/top/artists?time_range=${range}&limit=5`, token),
      api("/me/player/recently-played?limit=50", token),
      api("/me/player/currently-playing", token, true),
    ]);

    let playingTrack = null;
    if (currentRes && currentRes.is_playing && currentRes.item && currentRes.item.type === "track") {
      playingTrack = currentRes.item;
    }

    const recentTracks = [];
    const seen = new Set();
    for (const entry of historyRes.items || []) {
      if (seen.has(entry.track.id)) continue;
      seen.add(entry.track.id);
      recentTracks.push(entry.track);
      if (recentTracks.length === 5) break;
    }

    const [playing, recent, topTracks, topArtists] = await Promise.all([
      playingTrack ? trackItem(playingTrack) : null,
      Promise.all(recentTracks.map(trackItem)),
      Promise.all((topTracksRes.items || []).slice(0, 5).map(trackItem)),
      Promise.all((topArtistsRes.items || []).slice(0, 5).map(artistItem)),
    ]);

    const svg = makeRenderer().render({
      playing,
      recent,
      topTracks,
      topArtists,
      label: RANGES[range],
    });
    res.status(200).send(svg);
  } catch (err) {
    console.error("spotify-card:", err);
    res.status(200).send(errorCard("Não foi possível carregar os dados do Spotify agora."));
  }
}
