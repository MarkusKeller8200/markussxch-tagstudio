"""Probeübersetzung für #157 mit Apertus über Hugging Face (läuft nur im Workflow „Probeübersetzung“).

Der Token kommt aus dem Repository-Secret HF_TOKEN (vom Projektverantwortlichen selbst eingetragen) und wird nie
ausgegeben. Ergebnis: tools/i18n_probe/out-<sprache>.json und ein Kommentar in #157. Nur Standardbibliothek.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROUTER = "https://router.huggingface.co/v1/chat/completions"
PUBLICAI = "https://api.publicai.co/v1"          # direkt bei Public AI (eigener Schlüssel, Startguthaben)
UA = "TagStudio-i18n-probe/1.0 (+https://github.com/MarkusKeller8200/markussxch-tagstudio)"
HERE = os.path.dirname(os.path.abspath(__file__))


def ask(prompt: str, model: str, token: str, url: str = ROUTER) -> tuple[str, dict]:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": 0.2, "max_tokens": 8000}).encode()
    for attempt in range(4):
        req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {token}", "User-Agent": UA,
                                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.loads(r.read().decode("utf-8"))
            return d["choices"][0]["message"]["content"], d.get("usage") or {}
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 502, 503) and attempt < 3:
                time.sleep(20 * (attempt + 1))
                continue
            # nur Status und Antworttext des Dienstes – nie den Token
            fail(f"Hugging Face: HTTP {ex.code} {ex.read()[:300].decode('utf-8', 'replace')}")
        except (urllib.error.URLError, OSError, ValueError, KeyError) as ex:
            fail(f"Hugging Face: {type(ex).__name__}: {ex}")
    raise SystemExit("Hugging Face: keine Antwort")


def fail(msg: str):
    """Fehlergrund als GitHub-Anmerkung und Kommentar – der Token steht nie darin."""
    for k in ("HF_TOKEN", "PUBLICAI_TOKEN"):
        msg = msg.replace(os.environ.get(k, "") or "\0", "•••")
    print(f"::error title=Probeübersetzung::{msg.replace(chr(10), ' ')}", flush=True)
    with open(os.path.join(HERE, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(f"**Probeübersetzung fehlgeschlagen:** {msg}")
    raise SystemExit(1)


def parse(text: str):
    """JSON-Liste aus der Antwort holen (Modelle setzen manchmal ```json …``` darum)."""
    s = text.strip()
    if "```" in s:
        s = s.split("```")[1].removeprefix("json").strip()
    i, j = s.find("["), s.rfind("]")
    try:
        return json.loads(s[i:j + 1]) if i >= 0 and j > i else None
    except ValueError:
        return None


def providers(model_id: str, token: str) -> list[str]:
    """Anbieter, die das Modell laut Hugging Face gerade bedienen (öffentliche Modell-Info)."""
    url = f"https://huggingface.co/api/models/{model_id}?expand[]=inferenceProviderMapping"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as ex:
        print(f"::warning title=Probeübersetzung::Anbieterliste für {model_id} nicht lesbar: {type(ex).__name__}", flush=True)
        return []
    m = d.get("inferenceProviderMapping") or {}
    items = m.items() if isinstance(m, dict) else [(x.get("provider"), x) for x in m if isinstance(x, dict)]
    out = [p for p, v in items if p and (not isinstance(v, dict) or v.get("status", "live") == "live")]
    print(f"::notice title=Anbieter {model_id}::{', '.join(out) or 'keine'}", flush=True)
    return out


def pick_model(model: str, token: str) -> str:
    """Gewünschtes Modell; ist der Anbieter nicht verfügbar, einen anderen Anbieter bzw. eine andere Apertus-Version."""
    if ":" in model and model.split(":")[1] != "auto":
        return model
    for mid in [model.split(":")[0], "swiss-ai/Apertus-v1.5-70B", "swiss-ai/Apertus-70B-Instruct-2509", "swiss-ai/Apertus-v1.5-8B",
                "swiss-ai/Apertus-8B-Instruct-2509"]:
        prov = providers(mid, token)
        if prov:
            return f"{mid}:{prov[0]}"
    fail("Kein Anbieter für Apertus erreichbar – in Hugging Face › Settings › Inference Providers prüfen, ob Anbieter eingeschaltet sind.")


def publicai_model(token: str) -> str:
    """Grösstes verfügbares Apertus-Modell bei Public AI (GET /v1/models)."""
    try:
        req = urllib.request.Request(PUBLICAI + "/models", headers={"Authorization": f"Bearer {token}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        fail(f"Public AI: HTTP {ex.code} {ex.read()[:300].decode('utf-8', 'replace')}")
    except (urllib.error.URLError, OSError, ValueError) as ex:
        fail(f"Public AI: {type(ex).__name__}: {ex}")
    ids = [m.get("id", "") for m in d.get("data") or [] if "apertus" in m.get("id", "").lower()]
    print(f"::notice title=Public AI Modelle::{', '.join(ids) or 'kein Apertus'}", flush=True)
    if not ids:
        fail("Public AI bietet kein Apertus-Modell an.")
    size = lambda i: int(next((x[:-1] for x in i.replace("_", "-").split("-") if x.endswith("b") and x[:-1].isdigit()), 0))  # noqa: E731
    return max(ids, key=lambda i: (size(i), "v1.5" in i))


def main():
    pa = os.environ.get("PUBLICAI_TOKEN", "")
    if pa:                                            # bevorzugt: direkt bei Public AI
        token, url = pa, PUBLICAI + "/chat/completions"
        model = publicai_model(pa)
    else:
        token, url = os.environ.get("HF_TOKEN", ""), ROUTER
        if not token:
            fail("Weder PUBLICAI_TOKEN noch HF_TOKEN als Secret hinterlegt (Repository › Settings › Secrets and variables › Actions).")
        model = pick_model(os.environ.get("MODEL") or "swiss-ai/Apertus-v1.5-70B:auto", token)
    report = [f"**Probeübersetzung mit `{model}`** über {'Public AI' if pa else 'Hugging Face'} (Workflow „Probeübersetzung“, #157)", ""]
    for lang in ("en", "gsw"):
        with open(os.path.join(HERE, f"prompt-{lang}.txt"), encoding="utf-8") as fh:
            prompt = fh.read()
        t0 = time.time()
        text, usage = ask(prompt, model, token, url)
        data = parse(text)
        with open(os.path.join(HERE, f"out-{lang}.json"), "w", encoding="utf-8") as fh:
            json.dump({"model": model, "lang": lang, "usage": usage, "raw": text, "items": data}, fh, ensure_ascii=False, indent=1)
        ok = isinstance(data, list)
        report += [f"### {'Englisch' if lang == 'en' else 'Zürichdeutsch'}",
                   f"{len(data) if ok else 0} Einträge, gültiges JSON: {'ja' if ok else 'nein'}, "
                   f"{round(time.time() - t0)} s, Tokens: {usage.get('total_tokens', '?')}", "",
                   "<details><summary>Antwort</summary>", "", "```json",
                   json.dumps(data, ensure_ascii=False, indent=1) if ok else text[:60000], "```", "</details>", ""]
    out = "\n".join(report)
    with open(os.path.join(HERE, "report.md"), "w", encoding="utf-8") as fh:
        fh.write(out)
    print("fertig")


if __name__ == "__main__":
    sys.exit(main())
