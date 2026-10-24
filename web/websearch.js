/* MarKusSXCH TagStudio – „Online suchen ›“ im Rechtsklick-Menü (#283): Tagger, Playlists und DJ-Set.
   Öffnet die Suche des gewählten Dienstes im Browser mit Künstler + Titel (+ Mix, ohne „Original Mix“).
   Reihenfolge nach Wunsch des Users: Beatport, Spotify, SoundCloud, Apple Music, YouTube. */
"use strict";

const WEB_SEARCH = [
  { name: "Beatport", url: (q) => `https://www.beatport.com/search?q=${q}` },
  { name: "Spotify", url: (q) => `https://open.spotify.com/search/${q}` },
  { name: "SoundCloud", url: (q) => `https://soundcloud.com/search?q=${q}` },
  { name: "Apple Music", url: (q) => `https://music.apple.com/search?term=${q}` },
  { name: "YouTube", url: (q) => `https://www.youtube.com/results?search_query=${q}` },
];

/** Suchbegriff aus Künstler, Titel und Mix; „Original Mix“ fällt weg, Mix nur, wenn er nicht schon im Titel steht */
function webSearchQuery(artist, title, mix = "") {
  const a = String(artist || "").replace(/\s*;\s*|\u0000/g, ", ").trim();
  let t = String(title || "").trim();
  let m = String(mix || "").trim();
  if (/^original( mix| version)?$/i.test(m)) m = "";
  t = t.replace(/\s*[([]original( mix| version)?[)\]]\s*$/i, "");
  if (m && t.toLowerCase().includes(m.toLowerCase())) m = "";
  return [a, t, m].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}

function webSearchOpen(svc, q) { call("open_url", svc.url(encodeURIComponent(q))); }

/** Menüeintrag „Online suchen ›“ – öffnet an derselben Stelle die Liste der Dienste. null ohne Suchbegriff. */
function webSearchItem(e, artist, title, mix = "") {
  const q = webSearchQuery(artist, title, mix);
  if (!q) return null;
  const x = e.clientX, y = e.clientY;
  return { label: "Online suchen ›", run: () => setTimeout(() => showMenu(x, y,
    WEB_SEARCH.map((s) => ({ label: `${s.name}`, run: () => webSearchOpen(s, q) }))), 0) };
}
