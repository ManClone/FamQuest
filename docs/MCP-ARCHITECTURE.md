# MCP-Architektur für FamQuest

## Bestandsaufnahme (13.10.2026)
Geprüft: backend/app/api/tasks.py, approvals.py, points.py, auth.py, main.py.

Vorhanden:
- GET /api/tasks (ParentSession)
- POST /api/tasks (ParentSession; TaskIn)
- PUT /api/tasks/{task_id} (ParentSession)
- DELETE /api/tasks/{task_id} (ParentSession)
- GET /api/approvals (ParentSession)
- POST /api/approvals/{completion_id} (ParentSession)
- GET/POST /api/members/{member_id}/points (ParentSession)

Authentifizierung: Cookie famquest_session; bei schreibenden Requests X-CSRF-Token. ParentSession setzt entsperrten Elternbereich voraus, PIN-Freigabe läuft nach fünf Minuten ab. Bestehende Sitzung nicht in MCP wiederverwenden.

## Geplantes MCP (separater Docker-Dienst)
1. API-Token mit Hash in Datenbank, minimalen Scopes, Widerruf und Ablaufzeit.
2. Dedizierte Service-Endpunkte für Entwürfe; keine Eltern-Cookie-Simulation.
3. Werkzeuge: list_tasks, list_members, propose_quest, list_quest_proposals, get_progress; publish_quest nur nach expliziter Elternfreigabe.
4. Jede Schreibaktion mit Audit-Log, idempotency_key und Eingabevalidierung.
5. Quests in Deutsch, altersgerecht; bestehende Aufgaben auf Duplikate prüfen.
6. Euro-Beträge zunächst nur als Vorschläge; kein direkter Zugriff auf Bankkonten, Auszahlungen oder unveränderliches Taschengeld.
7. Cloudflare-Tunnel erst nach Test der Authentifizierung und Autorisierung.

## Offene Implementierungsfragen
- TaskIn, Rollen, Datenbankmigrationen und bestehende Tests genauer prüfen.
- Entwurfsmodell und Freigabeworkflow implementieren.
- MCP-Transport (Streamable HTTP) mit ChatGPT-Verbindung testen.
- Tests: unauthenticated, insufficient scope, double-submit, revoked token, parent approval.
