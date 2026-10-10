"""MarKusSXCH TagStudio – Herkunft der Tags: welche Anwendung hat ein Feld geschrieben?

Eine Kennungsliste ordnet Feldschlüssel (z. B. „TXXX:MusicBrainz Album Id“, „GEOB:Serato Markers2“,
„PRIV:TRAKTOR4“) per Muster einer Quelle zu. Reihenfolge der Prüfung: eigene Zuordnungen aus den Einstellungen
(„tag_origins“), dann Felder, die TagStudio-Plugins in plugin.json angeben („fields“), dann die eingebaute Liste.
Groß-/Kleinschreibung spielt keine Rolle; „*“ und „?“ wie bei Dateinamen. Nur Standardbibliothek.
"""
from __future__ import annotations

import fnmatch
import re

# id → (Name, Erklärung)
SOURCES = {
    "musicbrainz": ("MusicBrainz", "MusicBrainz Picard bzw. AcoustID: IDs von Aufnahme, Album, Künstler, Fingerabdruck"),
    "serato": ("Serato", "Serato DJ: Cue-Punkte, Loops, Beatgrid, Wellenform-Übersicht, Autogain"),
    "mik": ("Mixed In Key", "Mixed In Key: Energie-Level und Cue-Punkte"),
    "spotify": ("Spotify", "Spotify: Track-/Album-IDs, Links und Audio-Merkmale aus der Spotify-API (z. B. über Tagger-Tools)"),
    "discogs": ("Discogs", "Discogs: Release-/Master-IDs, Katalog-, Label- und Stilangaben"),
    "beatport": ("Beatport", "Beatport (Download bzw. Beatport-Dienste): Track-ID und Shop-Daten"),
    "traktor": ("Traktor", "Native Instruments Traktor: eigene Analyse- und Cue-Daten"),
    "rekordbox": ("Rekordbox", "Pioneer/AlphaTheta Rekordbox"),
    "beatunes": ("beaTunes", "beaTunes: Analyse (Segmente, Ähnlichkeiten, genaue BPM, Algorithmen)"),
    "lexicon": ("Lexicon", "Lexicon DJ (Bibliotheksverwaltung)"),
    "platinum": ("Platinum Notes", "Mixed In Key Platinum Notes: Bearbeitung/Lautheit"),
    "itunes": ("iTunes / Musik", "Apple iTunes bzw. Musik: Lautheit, Lückenlos-Daten, Sortierfelder, Werk/Satz"),
    "wmp": ("Windows Media Player", "Windows Media Player: Pegel, Medien-IDs"),
    "amazon": ("Amazon Music", "Amazon Music (Kauf-/Download-Kennung)"),
    "replaygain": ("ReplayGain", "Lautheitsanpassung (foobar2000, Mp3tag, MP3Gain …)"),
    "encoder": ("Kodierer", "Programm, das die MP3 erzeugt hat (LAME, FFmpeg …)"),
    "tagstudio": ("TagStudio", "MarKusSXCH TagStudio"),
}

BUILTIN = [
    ("TXXX:MusicBrainz*", "musicbrainz"), ("UFID:http://musicbrainz.org*", "musicbrainz"),
    ("TXXX:Acoustid*", "musicbrainz"), ("TXXX:ARTISTS", "musicbrainz"), ("TXXX:SCRIPT", "musicbrainz"),
    ("TXXX:originalyear", "musicbrainz"), ("TXXX:MusicMagic*", "musicbrainz"),
    ("GEOB:Serato*", "serato"), ("TXXX:SERATO*", "serato"), ("PRIV:Serato*", "serato"),
    ("GEOB:CuePoints", "mik"), ("GEOB:Energy", "mik"), ("GEOB:Key", "mik"), ("TXXX:CuePoints", "mik"), ("TXXX:EnergyLevel", "mik"), ("TXXX:MIK*", "mik"),
    ("TXXX:MixedInKey*", "mik"), ("TXXX:Mixed In Key*", "mik"),
    ("TXXX:BEATPORT*", "beatport"), ("PRIV:www.beatport.com*", "beatport"), ("WXXX:Beatport*", "beatport"),
    # Beatport-Downloads (#100): Shop-Daten als TXXX ohne Präfix
    ("TXXX:FILEOWNER", "beatport"), ("TXXX:LABEL", "beatport"), ("TXXX:LABEL_URL", "beatport"),
    ("TXXX:RELEASE_TIME", "beatport"), ("TXXX:TRACK_URL", "beatport"), ("TXXX:WWWAUDIOFILE", "beatport"),
    ("TXXX:BPM", "beatport"), ("TXXX:COMMENT", "beatport"), ("TXXX:FILETYPE", "beatport"),
    ("TXXX:INITIAL_KEA", "beatport"), ("TXXX:INITIAL_KEY", "beatport"), ("TXXX:ISRC", "beatport"),
    ("TXXX:ORGANIZATION", "beatport"), ("TXXX:YEAR", "beatport"),
    ("PRIV:TRAKTOR*", "traktor"), ("TXXX:TRAKTOR*", "traktor"), ("GEOB:TRAKTOR*", "traktor"),
    ("TXXX:rekordbox*", "rekordbox"), ("GEOB:rekordbox*", "rekordbox"), ("PRIV:rekordbox*", "rekordbox"),
    ("TXXX:beaTunes*", "beatunes"), ("TXXX:AnalysisDate", "beatunes"), ("TXXX:*Algorithm", "beatunes"), ("TXXX:Segments", "beatunes"),
    ("TXXX:Similarities", "beatunes"), ("TXXX:fBPM*", "beatunes"), ("TXXX:Meter", "beatunes"),
    ("TXXX:MOOD_*", "beatunes"),
    ("TXXX:SPOTIFY*", "spotify"), ("WXXX:Spotify*", "spotify"), ("PRIV:*spotify*", "spotify"),
    ("TXXX:DISCOGS*", "discogs"), ("WXXX:Discogs*", "discogs"), ("TXXX:*discogs*", "discogs"),
    ("TXXX:Lexicon*", "lexicon"), ("GEOB:Lexicon*", "lexicon"),
    ("GEOB:PlatinumNotes*", "platinum"), ("GEOB:Platinum Notes*", "platinum"), ("TXXX:Platinum*", "platinum"), ("COMM:Platinum*", "platinum"), ("PRIV:Platinum*", "platinum"),
    ("COMM:iTun*", "itunes"), ("TXXX:iTun*", "itunes"), ("PRIV:iTun*", "itunes"), ("TCMP", "itunes"),
    ("TSO2", "itunes"), ("TSOC", "itunes"), ("GRP1", "itunes"), ("MVNM", "itunes"), ("MVIN", "itunes"),
    ("PRIV:WM/*", "wmp"), ("TXXX:WM/*", "wmp"), ("PRIV:AverageLevel", "wmp"), ("PRIV:PeakValue", "wmp"),
    ("PRIV:www.amazon.com*", "amazon"), ("PRIV:Amazon*", "amazon"),
    ("TXXX:replaygain*", "replaygain"), ("TXXX:MP3GAIN*", "replaygain"),
    ("TSSE", "encoder"), ("TENC", "encoder"),
    ("TXXX:TagStudio*", "tagstudio"),
]


def _slug(name: str) -> str:
    return "u:" + re.sub(r"\s+", " ", name.strip())[:60]


def clean_custom(rules) -> list[dict]:
    """Eigene Zuordnungen aus der Oberfläche prüfen: [{"pattern", "source"}]."""
    out, seen = [], set()
    for r in rules or []:
        if not isinstance(r, dict):
            continue
        pat, src = str(r.get("pattern") or "").strip(), str(r.get("source") or "").strip()
        if not pat or not src or len(pat) > 200 or len(src) > 60 or pat.lower() in seen:
            continue
        seen.add(pat.lower())
        out.append({"pattern": pat, "source": src})
    return out[:300]


class Origins:
    def __init__(self, custom=None, plugin_fields=None):
        """custom: [{"pattern", "source"}]; plugin_fields: [(muster, plugin_name)]."""
        self.sources = {k: {"name": n, "desc": d, "kind": "builtin"} for k, (n, d) in SOURCES.items()}
        self.rules: list[tuple[str, str]] = []
        for r in clean_custom(custom):
            sid = r["source"].lower()
            known = next((k for k, v in self.sources.items() if v["name"].lower() == sid or k == sid), None)
            if known is None:
                known = _slug(r["source"])
                self.sources.setdefault(known, {"name": r["source"], "desc": "eigene Zuordnung", "kind": "custom"})
            self.rules.append((r["pattern"].lower(), known))
        for pat, pname in plugin_fields or []:
            sid = "p:" + pname
            self.sources.setdefault(sid, {"name": f"TagStudio · {pname}", "desc": f"geschrieben vom TagStudio-Plugin „{pname}“",
                                          "kind": "plugin"})
            self.rules.append((str(pat).lower(), sid))
        self.rules += [(p.lower(), s) for p, s in BUILTIN]
        self._cache: dict[str, str | None] = {}

    def of(self, key: str) -> str | None:
        k = key.split("#")[0].lower()
        if k not in self._cache:
            self._cache[k] = next((s for p, s in self.rules if fnmatch.fnmatchcase(k, p)), None)
        return self._cache[k]

    def patterns(self, sid: str) -> list[str]:
        """Muster einer Quelle in Original-Schreibweise (für „unwichtige Felder“)."""
        builtin = [p for p, s in BUILTIN if s == sid]
        return builtin or [p for p, s in self.rules if s == sid]

    def catalog(self) -> dict:
        return {k: dict(v) for k, v in self.sources.items()}
