"""MarKusSXCH TagStudio – Anmeldung bei Online-Diensten mit OAuth 2 und PKCE (#280: Spotify, SoundCloud).

Ablauf „Im Browser anmelden“: TagStudio öffnet die Anmeldeseite des Dienstes; nach der Zustimmung leitet der Dienst
auf die eingetragene Adresse `http://127.0.0.1:<Port>/callback` um, die TagStudio für kurze Zeit selbst beantwortet
(nur auf diesem Rechner erreichbar). Geht das nicht (Port belegt, Dienst erlaubt keine solche Adresse), wird die
Adresse aus der Adresszeile des Browsers eingefügt („Adresse einfügen“).

Zugangsdaten (Client-ID, Client-Secret) und Token liegen verschlüsselt im Datenordner des Plugins
(`servicekit.save_keys`), nie im Protokoll, nie im Einstellungs-Export. Token werden vor Ablauf erneuert.
Nur Standardbibliothek; Netzaufrufe über `http_post` / `onlinematch.http_get` – in Tests ersetzbar.
"""
from __future__ import annotations

import base64
import hashlib
import html
import http.server
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import onlinematch as om
import servicekit as sk

TIMEOUT = 30
WAIT_LOGIN = 180                    # Sekunden, die auf die Anmeldung im Browser gewartet wird
DONE_PAGE = ("<!doctype html><meta charset='utf-8'><title>TagStudio</title><body style='font-family:sans-serif;"
             "padding:40px'><h2>{title}</h2><p>{text}</p></body>")


class OAuthError(Exception):
    pass


def pkce() -> tuple[str, str]:
    """→ (code_verifier, code_challenge) nach RFC 7636 (S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def http_post(url: str, data: dict, headers: dict | None = None) -> tuple[int, dict]:
    """POST als Formular → (Status, JSON). In Tests ersetzbar."""
    body = urllib.parse.urlencode(data).encode("ascii")
    h = {"User-Agent": sk.USER_AGENT, "Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded",
         **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw, st = r.read(), r.status
    except urllib.error.HTTPError as ex:
        raw, st = (ex.read() if hasattr(ex, "read") else b""), ex.code
    except (urllib.error.URLError, OSError) as ex:
        raise OAuthError(f"Keine Verbindung: {getattr(ex, 'reason', ex)}") from ex
    try:
        return st, json.loads(raw.decode("utf-8") or "{}")
    except ValueError:
        return st, {}


def parse_redirect(url: str, state: str) -> str:
    """Code aus der Rückleitungs-Adresse (eingefügt oder vom Loopback-Server). Prüft den state."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(url or "").strip()).query)
    if q.get("error"):
        raise OAuthError(f"Anmeldung abgelehnt: {q['error'][0]}")
    if (q.get("state") or [""])[0] != state:
        raise OAuthError("Die Adresse passt nicht zu dieser Anmeldung – bitte nochmals anmelden.")
    code = (q.get("code") or [""])[0]
    if not code:
        raise OAuthError("In der Adresse fehlt der Code (…?code=…).")
    return code


def wait_for_redirect(port: int, path: str, cancel=None, timeout: float = WAIT_LOGIN, host: str = "127.0.0.1") -> str:
    """Kurzzeitiger Server auf 127.0.0.1:port (bei „localhost“ zusätzlich [::1], weil Browser localhost oft als IPv6
    auflösen); liefert die vollständige Rückleitungs-Adresse."""
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if urllib.parse.urlparse(self.path).path.rstrip("/") != path.rstrip("/"):
                self.send_response(404)
                self.end_headers()
                return
            got["url"] = f"http://{host}:{port}{self.path}"
            ok = "code=" in self.path
            page = DONE_PAGE.format(title="Anmeldung abgeschlossen" if ok else "Anmeldung nicht abgeschlossen",
                                    text=html.escape("Du kannst dieses Fenster schliessen und zu TagStudio zurückkehren."))
            data = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    import select
    import socket

    class V6(http.server.HTTPServer):
        address_family = socket.AF_INET6

    try:
        servers = [http.server.HTTPServer(("127.0.0.1", int(port)), H)]
    except OSError as ex:
        raise OAuthError(f"Port {port} ist belegt – anderen Port eintragen oder „Adresse einfügen“ wählen.") from ex
    if host == "localhost" and socket.has_ipv6:
        try:
            servers.append(V6(("::1", int(port)), H))
        except OSError:
            pass                                          # ohne IPv6 genügt 127.0.0.1
    t0 = time.time()
    try:
        while "url" not in got:
            if cancel:
                cancel()
            if time.time() - t0 > timeout:
                raise OAuthError("Keine Anmeldung innerhalb von 3 Minuten – bitte nochmals versuchen.")
            ready, _w, _x = select.select(servers, [], [], 0.5)
            for s in ready:
                s.handle_request()
    finally:
        for s in servers:
            s.server_close()
    return got["url"]


def open_browser(url: str) -> bool:
    try:
        import webbrowser
        return bool(webbrowser.open(url))
    except Exception:  # noqa: BLE001
        return False


class App:
    """OAuth-Zugang eines Dienstes. cfg: authorize, token, scopes, header ("Bearer" | "OAuth"), secret (bool: Client-
    Secret nötig), name. Zugangsdaten und Token in den Schlüsseln des Plugins: client_id, client_secret, redirect,
    token (JSON)."""

    def __init__(self, ctx, cfg: dict):
        self.ctx, self.cfg = ctx, cfg
        self.keys = sk.load_keys(ctx)

    # ---- Zugangsdaten
    @property
    def client_id(self) -> str:
        return self.keys.get("client_id", "")

    @property
    def redirect(self) -> str:
        return self.keys.get("redirect") or self.cfg.get("redirect", "http://127.0.0.1:8765/callback")

    def configured(self) -> bool:
        return bool(self.client_id and (self.keys.get("client_secret") or not self.cfg.get("secret")))

    @property
    def token(self) -> dict:
        try:
            t = json.loads(self.keys.get("token") or "{}")
        except ValueError:
            t = {}
        return t if isinstance(t, dict) else {}

    def logged_in(self) -> bool:
        return bool(self.token.get("access_token"))

    def _save(self, **kv):
        self.keys.update(kv)
        sk.save_keys(self.ctx, self.keys)

    def save_credentials(self, opts: dict):
        """Aktion „Zugang …“: leere Felder = unverändert; Redirect-Adresse immer übernehmen; clear löscht alles."""
        if opts.get("clear"):
            self.keys = {}
        else:
            for k in ("client_id", "client_secret"):
                if (opts.get(k) or "").strip():
                    self.keys[k] = opts[k].strip()
            if (opts.get("redirect") or "").strip():
                r = opts["redirect"].strip()
                if not r.startswith("http://127.0.0.1:") and not r.startswith("http://localhost:"):
                    raise OAuthError("Die Rückleitungs-Adresse muss mit http://127.0.0.1:<Port>/ beginnen.")
                self.keys["redirect"] = r
        sk.save_keys(self.ctx, self.keys)

    def logout(self):
        self.keys.pop("token", None)
        self.keys.pop("pending", None)
        sk.save_keys(self.ctx, self.keys)

    # ---- Anmeldung
    def auth_url(self) -> str:
        verifier, challenge = pkce()
        state = secrets.token_urlsafe(16)
        self._save(pending=json.dumps({"verifier": verifier, "state": state, "at": time.time()}))
        params = {"client_id": self.client_id, "response_type": "code", "redirect_uri": self.redirect,
                  "code_challenge_method": "S256", "code_challenge": challenge, "state": state}
        if self.cfg.get("scopes"):
            params["scope"] = " ".join(self.cfg["scopes"])
        params.update(self.cfg.get("auth_params") or {})          # z. B. Google: access_type=offline (#319)
        return self.cfg["authorize"] + "?" + urllib.parse.urlencode(params)

    def _pending(self) -> dict:
        try:
            p = json.loads(self.keys.get("pending") or "{}")
        except ValueError:
            p = {}
        if not p.get("verifier") or time.time() - float(p.get("at") or 0) > 900:
            raise OAuthError("Keine laufende Anmeldung – zuerst „Anmelden …“ ohne eingefügte Adresse ausführen.")
        return p

    def finish(self, redirected_url: str) -> dict:
        p = self._pending()
        code = parse_redirect(redirected_url, p["state"])
        data = {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect,
                "client_id": self.client_id, "code_verifier": p["verifier"]}
        if self.keys.get("client_secret"):
            data["client_secret"] = self.keys["client_secret"]
        st, tok = http_post(self.cfg["token"], data)
        if st >= 400 or not tok.get("access_token"):
            raise OAuthError(f"{self.cfg['name']}: Anmeldung fehlgeschlagen ({tok.get('error_description') or tok.get('error') or f'HTTP {st}'}).")
        self.keys.pop("pending", None)
        self._store(tok)
        return self.token

    def login_browser(self) -> dict:
        """Anmeldeseite öffnen und auf die Rückleitung warten (blockiert bis zur Anmeldung oder Abbruch)."""
        u = urllib.parse.urlparse(self.redirect)
        url = self.auth_url()
        if not open_browser(url):
            self.ctx.log(f"Browser liess sich nicht öffnen – diese Adresse im Browser öffnen: {url}")
        return self.finish(wait_for_redirect(u.port or 80, u.path or "/", getattr(self.ctx, "check_cancel", None),
                                             host=u.hostname or "127.0.0.1"))

    def _store(self, tok: dict):
        old = self.token
        t = {"access_token": str(tok["access_token"]),
             "refresh_token": str(tok.get("refresh_token") or old.get("refresh_token") or ""),
             "expires_at": time.time() + int(tok.get("expires_in") or 3600), "scope": tok.get("scope", old.get("scope", ""))}
        self._save(token=json.dumps(t))

    def refresh(self) -> bool:
        t = self.token
        if not t.get("refresh_token"):
            return False
        data = {"grant_type": "refresh_token", "refresh_token": t["refresh_token"], "client_id": self.client_id}
        if self.keys.get("client_secret"):
            data["client_secret"] = self.keys["client_secret"]
        st, tok = http_post(self.cfg["token"], data)
        if st >= 400 or not tok.get("access_token"):
            return False
        self._store(tok)
        return True

    def access_token(self) -> str:
        t = self.token
        if not t.get("access_token"):
            raise OAuthError(f"{self.cfg['name']}: nicht angemeldet (Plugin › „Anmelden …“).")
        if float(t.get("expires_at") or 0) - 60 < time.time() and not self.refresh():
            raise OAuthError(f"{self.cfg['name']}: Anmeldung abgelaufen – bitte neu anmelden.")
        return self.token["access_token"]

    def headers(self) -> dict:
        return {"Authorization": f"{self.cfg.get('header', 'Bearer')} {self.access_token()}"}

    def get(self, url: str, cl=None):
        """GET mit Token (JSON); bei 401 einmal erneuern. cl: servicekit-Client (Drosselung, 429)."""
        cl = cl or sk.client(self.ctx)
        try:
            return cl.json(url, self.headers())
        except om.HttpError as ex:
            if ex.status != 401 or not self.refresh():
                raise
            return cl.json(url, self.headers())

    def secrets(self) -> list:
        t = self.token
        return [x for x in (t.get("access_token"), t.get("refresh_token"), self.keys.get("client_secret")) if x]
