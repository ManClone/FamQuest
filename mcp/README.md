# FamQuest MCP – erster Prototyp

**Status:** Nur Quest-Entwürfe. Kein Zugriff auf FamQuest-API, Elternkonten, Bankkonten oder Taschengeld.

## Lokal starten

```bash
cd mcp
cp .env.example .env
# In .env einen eigenen langen Zufallstoken setzen, z. B. mit: openssl rand -hex 32
docker compose up -d --build
```

Die lokale `.env` benötigt zwei **verschiedene**, zufällig erzeugte Geheimnisse (`FAMQUEST_MCP_TOKEN` und `FAMQUEST_PARENT_TOKEN`), jeweils mindestens 32 Zeichen. Beispiel zur Erzeugung: `openssl rand -hex 32` zweimal ausführen. Die Elternansicht liegt unter `/parent` und nutzt HTTP Basic Auth (Benutzer `parent`, Passwort: `FAMQUEST_PARENT_TOKEN`). Sie darf nur über HTTPS oder innerhalb eines vertrauenswürdigen lokalen Netzes verwendet werden. Ein freigegebener Entwurf wird **noch nicht** in FamQuest veröffentlicht.\n\nStreamable-HTTP-Endpunkt im Container: `http://famquest-mcp:8000/mcp`.
Auf dem Docker-Host ausschließlich `127.0.0.1:8091` gebunden. Für QNAP Container Station muss der Zugriff über ein internes Docker-Netzwerk bzw. passende lokale Portweiterleitung eingerichtet werden.

## MCP-Werkzeuge
- `propose_quest`: erstellt einen Entwurf mit XP, optionalem Euro-Cent-Bonus und Wiederholung.
- `list_quest_proposals`: zeigt bis zu 100 Entwürfe.

Entwürfe werden in einem persistenten SQLite-Docker-Volume gespeichert. **Es gibt noch keine Elternfreigabe oder Veröffentlichung in FamQuest.**

## Sicherheit
Der MCP-Endpunkt verlangt einen **Bearer-Token** (mindestens 32 Zeichen), der in der lokalen, nicht einzucheckenden `mcp/.env` steht. Alle HTTP-/WebSocket-Anfragen ohne gültigen Token werden abgewiesen. Das ist eine einfache erste Zugangssperre, **noch keine OAuth- oder rollenbasierte ChatGPT-Authentifizierung**. Nicht öffentlich bereitstellen und keinen Cloudflare-Tunnel verbinden, bevor ein geeigneter Auth-Gateway samt Tests eingerichtet ist. Nächster Schritt: Freigabeworkflow, Rollen, Integration in FamQuest und Ende-zu-Ende-Tests.

Lokal: `cd mcp && python -m unittest discover -s tests` (nach Installation der Python-Abhängigkeiten). Die Tests wurden im GitHub-Schreibvorgang nicht ausgeführt.

Der bestehende FamQuest-Quellcode und seine AGPL-Lizenz bleiben unverändert.
