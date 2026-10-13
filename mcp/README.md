# FamQuest MCP – erster Prototyp

**Status:** Nur Quest-Entwürfe. Kein Zugriff auf FamQuest-API, Elternkonten, Bankkonten oder Taschengeld.

## Lokal starten

```bash
cd mcp
docker compose up -d --build
```

Streamable-HTTP-Endpunkt im Container: `http://famquest-mcp:8000/mcp`.
Auf dem Docker-Host ausschließlich `127.0.0.1:8091` gebunden. Für QNAP Container Station muss der Zugriff über ein internes Docker-Netzwerk bzw. passende lokale Portweiterleitung eingerichtet werden.

## MCP-Werkzeuge
- `propose_quest`: erstellt einen Entwurf mit XP, optionalem Euro-Cent-Bonus und Wiederholung.
- `list_quest_proposals`: zeigt bis zu 100 Entwürfe.

Entwürfe werden in einem persistenten SQLite-Docker-Volume gespeichert. **Es gibt noch keine Elternfreigabe oder Veröffentlichung in FamQuest.**

## Sicherheit
Der Prototyp enthält bewusst noch **keine eigene Authentifizierung**. Nicht öffentlich bereitstellen, keinen Cloudflare-Tunnel verbinden und nicht direkt als öffentlich erreichbaren ChatGPT-Connector konfigurieren. Nächster Schritt: OAuth-/Gateway-Authentifizierung, Autorisierung, Freigabeworkflow, Tests und erst dann sichere Verbindung zur FamQuest-API.

Der bestehende FamQuest-Quellcode und seine AGPL-Lizenz bleiben unverändert.
