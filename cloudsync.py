"""MarKusSXCH TagStudio – Abgleich über die Dienste (Cloud Weg 2, #317, docs/KONZEPT-CLOUD.md).

Abgeglichen werden Ordner-Rollen (Playlists, Export) und Teile der Programmdaten (Playlists-Speicher, Käufe,
Entdecken, Einstellungen ohne Zugangsdaten) mit einem Ordner bei OneDrive, Google Drive oder Dropbox – über ein
Dienst-Plugin mit der Fähigkeit „cloud_sync“ (Funktionen ``cloud_list``, ``cloud_get``, ``cloud_put``,
``cloud_delete`` im plugin.py).

Entscheide C1–C4 (User 25.10.2026): beide Richtungen; ändern sich dieselbe Datei hier **und** im Dienst, fragt
TagStudio nach (beide Fassungen) – nie still überschreiben. Löschen nie automatisch: entfernte Dateien werden gemeldet
und erst nach Rückfrage gelöscht. Zugangsdaten nie abgleichen. Snapshots, Arbeit, Cache nie.

Zustand je Ziel (Dienst + Ordner) in ``~/TagStudio/Cloud/abgleich.json``: je Datei Prüfsumme (SHA-256) und Revision der
letzten gemeinsamen Fassung → „nur hier geändert“, „nur dort geändert“, „beide geändert“ (Konflikt).
Nur Standardbibliothek.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time

import paths

MODES = ("both", "up", "down")
MAX_FILE = 50 * 1024 * 1024            # grössere Dateien werden nicht abgeglichen (gemeldet)
LOCK = threading.RLock()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clean_rel(rel: str) -> str:
    """Relativer Pfad mit „/“, ohne „..“ und ohne führenden Schrägstrich – sonst ValueError."""
    r = str(rel or "").replace("\\", "/").strip("/")
    parts = [p for p in r.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise ValueError(f"Ungültiger Pfad: {rel}")
    return "/".join(parts)


def clean_sync(s) -> dict | None:
    """Einstellung eines Abgleichs: {"provider", "remote", "mode"} – None = aus."""
    if not isinstance(s, dict) or not s.get("provider"):
        return None
    prov = "".join(c for c in str(s["provider"]) if c.isalnum() or c in "_-")[:40]
    remote = clean_rel(s.get("remote") or "TagStudio")
    mode = s.get("mode") if s.get("mode") in MODES else "both"
    return {"provider": prov, "remote": remote, "mode": mode} if prov else None


def atomic_write(path: str, data: bytes):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


# =========================================================================== Teile (was abgeglichen wird)
class Part:
    """Basis: ein Satz Dateien mit relativen Pfaden. read/write arbeiten mit Bytes; write ist atomar."""
    id = ""
    label = ""

    def files(self) -> dict:                 # {rel: bytes}
        raise NotImplementedError

    def write(self, rel: str, data: bytes):
        raise NotImplementedError

    def delete(self, rel: str):
        raise NotImplementedError

    def after(self):                         # nach dem Herunterladen (z. B. Zwischenspeicher der Sitzung leeren)
        pass


class FolderPart(Part):
    """Dateien eines Ordners (rekursiv), nur erlaubte Endungen; „.part“, versteckte Dateien und Konfliktkopien der
    Desktop-Clients bleiben aussen vor."""

    def __init__(self, pid: str, label: str, root: str, exts=None, names=None):
        self.id, self.label, self.root = pid, label, root
        self.exts = tuple(e.lower() for e in exts) if exts else None
        self.names = set(names) if names else None

    def _ok(self, rel: str) -> bool:
        base = rel.rsplit("/", 1)[-1]
        if base.startswith((".", "~")) or base.endswith((".part", ".tmp")):
            return False
        if self.names is not None and rel not in self.names:
            return False
        if self.exts is not None and not base.lower().endswith(self.exts):
            return False
        try:
            import cloud
            return not cloud.is_conflict(base)
        except Exception:  # noqa: BLE001
            return True

    def accepts(self, rel: str) -> bool:
        return self._ok(rel)

    def files(self) -> dict:
        out = {}
        if not self.root or not os.path.isdir(self.root):
            return out
        for dirpath, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
            for n in names:
                p = os.path.join(dirpath, n)
                rel = os.path.relpath(p, self.root).replace(os.sep, "/")
                if not self._ok(rel):
                    continue
                try:
                    if os.path.getsize(p) > MAX_FILE:
                        continue
                    with open(p, "rb") as fh:
                        out[rel] = fh.read()
                except OSError:
                    continue
        return out

    def _path(self, rel: str) -> str:
        p = os.path.normpath(os.path.join(self.root, *clean_rel(rel).split("/")))
        if os.path.commonpath([os.path.abspath(p), os.path.abspath(self.root)]) != os.path.abspath(self.root):
            raise ValueError(f"Pfad ausserhalb des Ordners: {rel}")
        return p

    def write(self, rel: str, data: bytes):
        atomic_write(self._path(rel), data)

    def delete(self, rel: str):
        os.remove(self._path(rel))


class DiscoverPart(FolderPart):
    """Entdecken: SonoVault-Einträge nie hochladen (Nutzungsbedingungen), beim Herunterladen die hiesigen behalten."""

    def __init__(self, root: str):
        super().__init__("discover", "Entdecken", root, names=["entdecken.json"])

    @staticmethod
    def _strip(data: bytes) -> bytes:
        try:
            d = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return data
        if isinstance(d, dict) and isinstance(d.get("items"), dict):
            d["items"] = {k: v for k, v in d["items"].items() if not (isinstance(v, dict) and v.get("src") == "sonovault")}
            if isinstance(d.get("follow"), dict) and isinstance(d["follow"].get("sources"), list):
                d["follow"]["sources"] = [s for s in d["follow"]["sources"] if s != "sonovault"]
        return json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")

    def files(self) -> dict:
        return {k: self._strip(v) for k, v in super().files().items()}

    def write(self, rel: str, data: bytes):
        mine = {}
        try:
            with open(self._path(rel), "rb") as fh:
                cur = json.loads(fh.read().decode("utf-8"))
            mine = {k: v for k, v in (cur.get("items") or {}).items() if isinstance(v, dict) and v.get("src") == "sonovault"}
        except (OSError, ValueError, AttributeError):
            pass
        try:
            d = json.loads(data.decode("utf-8"))
            if isinstance(d, dict) and mine:
                d.setdefault("items", {}).update(mine)
                data = json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8")
        except (UnicodeDecodeError, ValueError):
            pass
        super().write(rel, data)


SETTINGS_GROUPS = ("design", "view", "trivial", "djset", "origin", "plugins", "update")   # ohne Pfade/Fenster


class SettingsPart(Part):
    """Einstellungen ohne Zugangsdaten und ohne rechnerabhängige Gruppen als eine Datei „einstellungen.json“."""
    id, label, NAME = "settings", "Einstellungen (ohne Zugangsdaten)", "einstellungen.json"

    def files(self) -> dict:
        import appsettings
        cfg = appsettings.shareable(appsettings.read_file())
        keep = {k: v for k, v in cfg.items() if appsettings.group_of(k) in SETTINGS_GROUPS}
        data = {"format": appsettings.FORMAT, "settings": keep}
        return {self.NAME: json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")}

    def accepts(self, rel: str) -> bool:
        return rel == self.NAME

    def write(self, rel: str, data: bytes):
        import appsettings
        if rel != self.NAME:
            raise ValueError(f"Unbekannte Datei: {rel}")
        appsettings.import_apply(data.decode("utf-8"), list(SETTINGS_GROUPS))

    def delete(self, rel: str):
        raise ValueError("Die Einstellungen werden nicht gelöscht.")


# Programmdaten-Teile (C2) – Pfade im Datenordner des Profils
APP_PARTS = [("pl_store", "Playlists-Speicher"), ("purchases", "Käufe"), ("discover", "Entdecken"),
             ("settings", "Einstellungen (ohne Zugangsdaten)")]
ROLE_EXTS = {"playlists": (".m3u8", ".m3u", ".xml", ".csv", ".txt", ".json"), "export": None}
REMOTE_DEFAULT = {"playlists": "TagStudio/Playlists", "export": "TagStudio/Export", "pl_store": "TagStudio/Programmdaten/Playlists",
                  "purchases": "TagStudio/Programmdaten/Käufe", "discover": "TagStudio/Programmdaten/Entdecken",
                  "settings": "TagStudio/Programmdaten/Einstellungen"}


def app_part(pid: str) -> Part:
    if pid == "pl_store":
        return FolderPart(pid, "Playlists-Speicher", paths.sub("Playlists"), exts=(".json",))
    if pid == "purchases":
        return FolderPart(pid, "Käufe", paths.sub("Käufe"), names=["kaeufe.json"])
    if pid == "discover":
        return DiscoverPart(paths.sub("Entdecken"))
    if pid == "settings":
        return SettingsPart()
    raise ValueError(f"Unbekannter Teil: {pid}")


# =========================================================================== Zustand
def state_path() -> str:
    return os.path.join(paths.sub("Cloud"), "abgleich.json")


def load_state() -> dict:
    try:
        with open(state_path(), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(d: dict):
    atomic_write(state_path(), json.dumps(d, ensure_ascii=False, indent=1).encode("utf-8"))


def target_key(part_id: str, sync: dict) -> str:
    return f"{part_id}|{sync['provider']}|{sync['remote']}"


# =========================================================================== Abgleich
def plan(part: Part, local: dict, remote: dict, known: dict, mode: str = "both") -> dict:
    """Was ist zu tun? local {rel: bytes}, remote {rel: {"rev", "size"}}, known {rel: {"hash", "rev"}}.
    → {"up": [rel], "down": [rel], "check": [rel], "conflict": [rel], "gone_remote": [rel], "gone_local": [rel],
       "same": [rel]}. check = beide vorhanden, kein Zustand → Inhalt vergleichen."""
    out = {k: [] for k in ("up", "down", "check", "conflict", "gone_remote", "gone_local", "same")}
    accepts = getattr(part, "accepts", lambda rel: True)
    for rel in sorted(set(local) | set(remote)):
        if rel in remote and rel not in local and not accepts(rel):
            continue                                   # fremde Datei im Dienst: unberührt lassen
        k = known.get(rel)
        here, there = rel in local, rel in remote
        lch = here and (k is None or sha(local[rel]) != k.get("hash"))
        rch = there and (k is None or str(remote[rel].get("rev")) != str(k.get("rev")))
        if here and not there:
            if k is not None:
                out["gone_remote"].append(rel)         # im Dienst gelöscht → nur melden
            elif mode != "down":
                out["up"].append(rel)
        elif there and not here:
            if k is not None:
                out["gone_local"].append(rel)          # hier gelöscht → nur melden
            elif mode != "up":
                out["down"].append(rel)
        elif k is None:
            out["check"].append(rel)
        elif lch and rch:
            out["conflict"].append(rel)
        elif lch:
            (out["up"] if mode != "down" else out["same"]).append(rel)
        elif rch:
            (out["down"] if mode != "up" else out["same"]).append(rel)
        else:
            out["same"].append(rel)
    return out


def run(part: Part, provider, sync: dict, state: dict | None = None, log=None, cancel=None) -> dict:
    """Einen Teil mit seinem Ziel abgleichen. provider: list(folder) → {rel: {"rev", "size"}}, get(path) → bytes,
    put(path, data) → rev, delete(path). → {"up", "down", "conflicts": [{"rel", "local", "remote", "rev"}],
    "gone_remote", "gone_local", "errors"}"""
    own = state is None
    with LOCK:
        state = load_state() if own else state
        key = target_key(part.id, sync)
        known = state.setdefault(key, {})
        local = part.files()
        remote = {clean_rel(k): v for k, v in (provider.list(sync["remote"]) or {}).items()}
        p = plan(part, local, remote, known, sync.get("mode", "both"))
        res = {"part": part.id, "label": part.label, "up": 0, "down": 0, "conflicts": [], "gone_remote": p["gone_remote"],
               "gone_local": p["gone_local"], "errors": []}
        rpath = lambda rel: f"{sync['remote']}/{rel}"          # noqa: E731

        def stop():
            if cancel is not None:
                cancel()
        for rel in p["check"]:
            stop()
            data = provider.get(rpath(rel))
            if data == local[rel]:
                known[rel] = {"hash": sha(data), "rev": remote[rel].get("rev")}
            else:
                res["conflicts"].append({"rel": rel, "local": local[rel], "remote": data, "rev": remote[rel].get("rev")})
        for rel in p["conflict"]:
            stop()
            data = provider.get(rpath(rel))
            if data == local[rel]:                             # gleich geändert → kein Konflikt
                known[rel] = {"hash": sha(data), "rev": remote[rel].get("rev")}
            else:
                res["conflicts"].append({"rel": rel, "local": local[rel], "remote": data, "rev": remote[rel].get("rev")})
        for rel in p["up"]:
            stop()
            try:
                rev = provider.put(rpath(rel), local[rel])
                known[rel] = {"hash": sha(local[rel]), "rev": rev}
                res["up"] += 1
            except Exception as ex:  # noqa: BLE001 – eine Datei darf den Abgleich nicht abbrechen
                if type(ex).__name__ == "Cancelled":
                    raise
                res["errors"].append(f"{rel}: {ex}")
        for rel in p["down"]:
            stop()
            try:
                data = provider.get(rpath(rel))
                part.write(rel, data)
                after = part.files().get(rel, data)            # gefilterte Fassung (z. B. Entdecken) als Stand
                known[rel] = {"hash": sha(after), "rev": remote[rel].get("rev")}
                res["down"] += 1
            except Exception as ex:  # noqa: BLE001
                if type(ex).__name__ == "Cancelled":
                    raise
                res["errors"].append(f"{rel}: {ex}")
        if res["down"]:
            part.after()
        state.setdefault("_last", {})[key] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "up": res["up"], "down": res["down"],
                                              "conflicts": len(res["conflicts"]),
                                              "deleted": len(p["gone_remote"]) + len(p["gone_local"]),
                                              "errors": len(res["errors"])}
        if own:
            save_state(state)
        if log:
            log(f"{part.label}: {res['up']} hochgeladen, {res['down']} heruntergeladen, {len(res['conflicts'])} Konflikt(e)")
    return res


def resolve(part: Part, provider, sync: dict, rel: str, choice: str, remote_data: bytes, rev=None) -> dict:
    """Konflikt lösen: here = hiesige Fassung hochladen, there = Fassung aus dem Dienst übernehmen,
    both = beide behalten (die aus dem Dienst als „Name (Cloud).ext“ daneben)."""
    with LOCK:
        state = load_state()
        known = state.setdefault(target_key(part.id, sync), {})
        rpath = f"{sync['remote']}/{rel}"
        if choice == "here":
            data = part.files().get(rel)
            if data is None:
                raise ValueError("Die hiesige Datei gibt es nicht mehr.")
            known[rel] = {"hash": sha(data), "rev": provider.put(rpath, data)}
        elif choice == "there":
            part.write(rel, remote_data)
            known[rel] = {"hash": sha(part.files().get(rel, remote_data)), "rev": rev}
            part.after()
        elif choice == "both":
            if isinstance(part, SettingsPart):
                raise ValueError("Bei den Einstellungen geht nur „hier“ oder „aus dem Dienst“.")
            stem, ext = os.path.splitext(rel)
            n, alt = 1, f"{stem} (Cloud){ext}"
            have = part.files()
            while alt in have:
                n += 1
                alt = f"{stem} (Cloud {n}){ext}"
            part.write(alt, remote_data)
            data = have.get(rel, b"")
            known[rel] = {"hash": sha(data), "rev": provider.put(rpath, data)}
        else:
            raise ValueError("here, there oder both erwartet")
        save_state(state)
    return {"ok": True}


def delete(part: Part, provider, sync: dict, rel: str, where: str) -> dict:
    """Nur nach Rückfrage: where = local (hier löschen, weil im Dienst gelöscht) oder remote (im Dienst löschen)."""
    with LOCK:
        state = load_state()
        known = state.setdefault(target_key(part.id, sync), {})
        if where == "local":
            part.delete(rel)
        elif where == "remote":
            provider.delete(f"{sync['remote']}/{rel}")
        else:
            raise ValueError("local oder remote erwartet")
        known.pop(rel, None)
        save_state(state)
    return {"ok": True}


def forget(part_id: str, sync: dict, rel: str):
    """Gelöschte Datei nicht mehr melden (ohne zu löschen): Stand vergessen – beim nächsten Abgleich gilt sie als neu."""
    with LOCK:
        state = load_state()
        state.get(target_key(part_id, sync), {}).pop(rel, None)
        save_state(state)


def last(part_id: str, sync: dict) -> dict:
    return (load_state().get("_last") or {}).get(target_key(part_id, sync), {})


def preview(data: bytes, limit: int = 4000) -> str:
    """Textvorschau einer Fassung für den Konflikt-Dialog."""
    try:
        t = data.decode("utf-8")
    except UnicodeDecodeError:
        return f"(Binärdatei, {len(data)} Bytes)"
    return t[:limit] + ("\n…" if len(t) > limit else "")
