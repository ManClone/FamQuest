# FamQuest MCP: Elternfreigaben und Erinnerungen

## Verbindliche Anforderungen

- FamQuest ist ueber einen authentifizierten MCP-Endpunkt am bestehenden Gateway/Cloudflare-Tunnel fuer ChatGPT erreichbar.
- Eigene Eltern- und Kinder-Logins bleiben getrennt. MCP-Schreibrechte fuer Approvals nur im autorisierten Elternkontext.
- MCP bietet das Auflisten offener Approvals mit ID, Kind, Aufgabe, Erledigungszeit und Status.
- MCP bietet Freigabe und Ablehnung einzelner Approvals mit nachvollziehbarer Audit-Historie (Elternkonto, Zeit, Entscheidung).
- ChatGPT darf **niemals** eine Approval ohne ausdrueckliche Bestaetigung des Nutzers genehmigen oder ablehnen.
- Sammelfreigaben ebenfalls nur nach expliziter Bestaetigung und mit Auflistung der betroffenen Eintraege.
- Eine taegliche Pruefung am Abend (ca. 19 Uhr, Europe/Berlin) soll nur bei offenen Approvals benachrichtigen.
- Bei nicht erreichbarer oder nicht verbundener MCP-Integration darf keine erfolgreiche Pruefung vorgetaeuscht werden.
- Idempotente API: doppelte Freigaben duerfen keine mehrfachen XP- oder Geldbuchungen ausloesen.
- Taschengeld ist unabhaengig von Freigaben und darf niemals gekuerzt werden.

## Integrationstest vor QNAP-Neuaufsetzung

1. Zwei getrennte Elternkonten und ein Kinderkonto anmelden.
2. Kind markiert kontrollpflichtige Aufgabe als erledigt.
3. ChatGPT listet offene Approvals ohne administrative Kinderrechte.
4. ChatGPT fordert eine ausdrueckliche Elternentscheidung an.
5. Bestaetigung wird genau einmal verbucht, erneuter Aufruf bleibt idempotent.
6. Ablehnung und Audit-Historie pruefen.
7. Abendliche Erinnerung bei offener Freigabe pruefen, keine Meldung bei leerer Liste.
8. Authentifizierungsfehler und MCP-Ausfall sicher behandeln.

Die ChatGPT-Automatisierung wurde bereits angelegt; echte Datenabfragen funktionieren erst nach Anbindung des MCP-Servers.
