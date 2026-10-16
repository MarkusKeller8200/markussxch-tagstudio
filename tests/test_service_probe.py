"""Hilfslauf (#205): echte IDs für die Beispielwerte im Integrationsfenster ermitteln. Nur mit ONLINE_TESTS=1;
gibt die Werte als GitHub-Anmerkungen aus (::notice::). Wird nach dem Ermitteln wieder entfernt."""
import os
import sys
import unittest
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import onlinematch as om  # noqa: E402

LIVE = os.environ.get("ONLINE_TESTS") == "1"


LINES = []


def note(k, v):
    LINES.append(f"{k}: {str(v)[:400]}")


def flush(name):
    """GitHub zeigt höchstens 10 Hinweise je Schritt – je Dienst einer, Zeilen mit „ | “ getrennt."""
    print(f"::notice title=probe {name}::{' | '.join(LINES)[:3800]}", flush=True)
    LINES.clear()


@unittest.skipUnless(LIVE, "nur mit ONLINE_TESTS=1")
class Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import servicekit
        cls.cl = om.Client(servicekit.USER_AGENT, om.INTERVALS, throttle=om.SHARED)

    def j(self, url):
        try:
            return self.cl.json(url) or {}
        except Exception as ex:  # noqa: BLE001
            note("ERR " + url[:80], ex)
            return {}

    def test_mb(self):
        import time
        time.sleep(3)
        d = self.j("https://musicbrainz.org/ws/2/isrc/GBDUW0000053?inc=artists+releases+release-groups&fmt=json")
        for r in (d.get("recordings") or [])[:3]:
            note("mb rec", f"{r.get('id')} {r.get('title')} {r.get('length')} " +
                 " ; ".join(f"{x.get('id')} {x.get('title')} {x.get('status')} {x.get('date')} rg={(x.get('release-group') or {}).get('id')}"
                            for x in (r.get("releases") or [])[:4]))
        q = urllib.parse.quote('release:"Discovery" AND artist:"Daft Punk" AND status:official AND format:CD')
        d = self.j(f"https://musicbrainz.org/ws/2/release?query={q}&limit=3&fmt=json")
        for r in d.get("releases") or []:
            note("mb release", f"{r.get('id')} {r.get('date')} {r.get('country')} rg={(r.get('release-group') or {}).get('id')} "
                 f"labels={[(li.get('label') or {}).get('id') for li in r.get('label-info') or []]}")
        d = self.j("https://musicbrainz.org/ws/2/work?query=" + urllib.parse.quote('work:"One More Time" AND artist:"Daft Punk"') + "&limit=3&fmt=json")
        for w in d.get("works") or []:
            note("mb work", f"{w.get('id')} {w.get('title')}")
        d = self.j("https://musicbrainz.org/ws/2/discid/I5l9cCSFccLKFEKS.7wqSZAorPU-?fmt=json")
        note("mb discid", f"{len(d.get('releases') or [])} releases")
        d = self.j("https://musicbrainz.org/ws/2/artist/056e4f3e-d505-4dad-8ec1-d04f521cbb56?fmt=json")
        note("mb artist", d.get("name"))

        flush('mb')
    def test_deezer(self):
        d = self.j("https://api.deezer.com/track/isrc:GBDUW0000053")
        note("dz isrc", f"{d.get('id')} {d.get('title')} {d.get('duration')} album={(d.get('album') or {}).get('id')} art={(d.get('artist') or {}).get('id')} err={d.get('error')}")
        d = self.j("https://api.deezer.com/search/track?q=" + urllib.parse.quote('track:"One More Time" artist:"Daft Punk"') + "&limit=5")
        for t in d.get("data") or []:
            note("dz search", f"{t.get('id')} {t.get('title')} {t.get('duration')} album={(t.get('album') or {}).get('id')} {(t.get('album') or {}).get('title')}")
        a = self.j("https://api.deezer.com/album/302127")
        note("dz album tracks", [(t.get("id"), t.get("title"), t.get("duration")) for t in ((a.get("tracks") or {}).get("data") or [])[:3]])
        for aid in [302127]:
            a = self.j(f"https://api.deezer.com/album/{aid}")
            note("dz album", f"{aid} {a.get('title')} upc={a.get('upc')} label={a.get('label')} err={a.get('error')}")
        c = self.j("https://api.deezer.com/chart")
        note("dz chart playlists", [(p.get("id"), p.get("title")) for p in ((c.get("playlists") or {}).get("data") or [])[:3]])
        a = self.j("https://api.deezer.com/artist/27")
        note("dz artist 27", a.get("name"))

        flush('deezer')
    def test_itunes(self):
        d = self.j("https://itunes.apple.com/search?term=" + urllib.parse.quote("Daft Punk One More Time") + "&media=music&entity=song&limit=5&country=CH")
        for r in d.get("results") or []:
            note("it", f"track={r.get('trackId')} coll={r.get('collectionId')} artist={r.get('artistId')} {r.get('trackName')} / {r.get('collectionName')} {r.get('trackTimeMillis')}")

        flush('itunes')
    def test_lrclib(self):
        d = self.j("https://lrclib.net/api/search?track_name=" + urllib.parse.quote("One More Time") + "&artist_name=" + urllib.parse.quote("Daft Punk"))
        for r in (d if isinstance(d, list) else [])[:5]:
            note("lrclib", f"{r.get('id')} {r.get('trackName')} / {r.get('albumName')} {r.get('duration')} synced={bool(r.get('syncedLyrics'))}")

        flush('lrclib')
    def test_discogs(self):
        d = self.j("https://api.discogs.com/artists/1289")
        note("dc artist 1289", d.get("name"))
        d = self.j("https://api.discogs.com/artists/1289/releases?per_page=100")
        for r in d.get("releases") or []:
            if r.get("title") in ("Discovery", "One More Time") and r.get("type") == "master":
                note("dc master", f"{r.get('id')} {r.get('title')} main_release={r.get('main_release')} {r.get('year')}")
        m = d.get("releases") and next((r for r in d["releases"] if r.get("title") == "Discovery" and r.get("type") == "master"), None)
        if m:
            rel = self.j(f"https://api.discogs.com/releases/{m.get('main_release')}")
            note("dc release", f"{rel.get('id')} {rel.get('title')} labels={[(x.get('id'), x.get('name')) for x in rel.get('labels') or []]}")
        flush('discogs')


if __name__ == "__main__":
    unittest.main()
