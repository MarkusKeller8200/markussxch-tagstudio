"""#401: Zugangsdaten nie an einen anderen Host mitschicken, wenn ein Dienst umleitet."""
import http.server
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import onlinematch as om  # noqa: E402


class _Srv:
    """Kleiner Server: /redirect?to=<url> → 302, sonst 200 und merkt sich die Kopfzeilen."""

    def __init__(self, host="127.0.0.1"):
        seen = self.seen = []

        class H(http.server.BaseHTTPRequestHandler):
            def _go(self):
                if self.path.startswith("/redirect?to="):
                    self.send_response(302)
                    self.send_header("Location", self.path.split("=", 1)[1])
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                seen.append({k.lower(): v for k, v in self.headers.items()})
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

            do_GET = _go
            do_PUT = _go

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer((host, 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class RedirectAuthTest(unittest.TestCase):
    def setUp(self):
        self.a, self.b = _Srv(), _Srv()

    def tearDown(self):
        self.a.close()
        self.b.close()

    def test_same_origin(self):
        self.assertTrue(om.same_origin("https://Graph.microsoft.com/v1.0/x", "https://graph.microsoft.com/y"))
        self.assertFalse(om.same_origin("https://graph.microsoft.com/x", "https://x.files.1drv.com/y"))
        self.assertFalse(om.same_origin("https://a.example/x", "http://a.example/x"))       # Schema-Wechsel
        self.assertFalse(om.same_origin("http://127.0.0.1:1/x", "http://127.0.0.1:2/x"))     # anderer Port

    def test_other_host_gets_no_token(self):
        target = f"http://127.0.0.1:{self.b.port}/datei"      # anderer Port = andere Herkunft (wie anderer Host)
        url = f"http://127.0.0.1:{self.a.port}/redirect?to={target}"
        st, _h, body = om.http_get(url, {"Authorization": "Bearer GEHEIM", "Cookie": "s=1", "X-Api-Key": "K",
                                         "User-Agent": "test"})
        self.assertEqual((st, body), (200, b"ok"))
        h = self.b.seen[-1]
        self.assertNotIn("authorization", h)
        self.assertNotIn("cookie", h)
        self.assertNotIn("x-api-key", h)
        self.assertEqual(h.get("user-agent"), "test")       # unkritische Kopfzeilen bleiben

    def test_same_host_keeps_token(self):
        url = f"http://127.0.0.1:{self.a.port}/redirect?to=http://127.0.0.1:{self.a.port}/datei"
        st, _h, _b = om.http_get(url, {"Authorization": "Bearer GEHEIM"})
        self.assertEqual(st, 200)
        self.assertEqual(self.a.seen[-1].get("authorization"), "Bearer GEHEIM")

    def test_request_also_protected(self):
        url = f"http://127.0.0.1:{self.a.port}/redirect?to=http://127.0.0.1:{self.b.port}/datei"
        st, _h, _b = om.http_request("GET", url, {"Authorization": "Bearer GEHEIM"})
        self.assertEqual(st, 200)
        self.assertNotIn("authorization", self.b.seen[-1])


if __name__ == "__main__":
    unittest.main()
