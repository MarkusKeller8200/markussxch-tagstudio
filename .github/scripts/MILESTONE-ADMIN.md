# Meilensteine verwalten (GitHub Actions)

Die ChatGPT-GitHub-Integration kann Issues Meilensteinen zuweisen, aber keine Meilensteine selbst erstellen oder schliessen. Der Repo-eigene Workflow [milestone-admin.yml](../workflows/milestone-admin.yml) bietet eine eng begrenzte, überprüfbare Alternative.

**Steuerungs-Issue:** [#190 – Administrationskanal: GitHub-Meilensteine verwalten](https://github.com/MarkusKeller8200/markussxch-tagstudio/issues/190). Nur Kommentare des GitHub-Repository-Eigentümers und nur auf diesem einen Issue dürfen Aktionen auslösen.

**Funktionstest:** Am 14. Oktober 2026 erfolgreich ausgeführt: [Actions-Run 38485688746](https://github.com/MarkusKeller8200/markussxch-tagstudio/actions/runs/38485688746) für `/milestone list`. Auch nach dem Schliessen des Verwaltungs-Issues wurde ein lesender Testbefehl erfolgreich verarbeitet. Schreiboperationen sind bewusst noch nicht an produktiven Meilensteinen getestet worden.

## Erlaubte Befehle

Je Kommentar **genau eine** Zeile eingeben:

```text
/milestone list
/milestone create 4.6.0 – Nächster Entwicklungsschritt
/milestone close 14
/milestone reopen 14
```

Die Antwort wird als Kommentar im Verwaltungs-Issue protokolliert. Aktionen sind idempotent, wo sinnvoll: doppelte Titel werden nicht erneut angelegt, bereits geschlossene Meilensteine nicht nochmals geändert. Der Workflow verwendet ausschliesslich `secrets.GITHUB_TOKEN` mit `issues: write`, keinen Personal Access Token.

## Sicherheitsregeln

- Das Workflow- und Python-Skript prüfen **beide** den Repository-Namen, den Eigentümer und die feste Verwaltungs-Issue-Nummer.
- Befehlsparameter werden ausschliesslich als validierte Daten an die GitHub-REST-API übergeben; niemals als Shellcode.
- Keine Aktion bei Kommentaren anderer Nutzer oder in anderen Issues.
- Bei Änderung des Repository-Eigentümers, der Administrator-Issue-Nummer oder der GitHub-Berechtigungen Workflow und Skript überprüfen.
- Nach Deployment den nicht verändernden Befehl `/milestone list` testen; bei ausbleibender Antwort [GitHub Actions](https://github.com/MarkusKeller8200/markussxch-tagstudio/actions/workflows/milestone-admin.yml) kontrollieren.
