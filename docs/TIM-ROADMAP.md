# FamQuest – Familienerweiterungen (Planung)

Basis: craebby/FamQuest (AGPL-3.0). Änderungen zunächst ausschließlich im Branch `develop`. Upstream-Lizenz und Quellcodehinweise erhalten.

## Priorität 1: MCP für kreative Quests
- Vor Implementierung Datenmodell, vorhandene API, Rollen und Authentifizierung prüfen.
- Separater MCP-Dienst mit minimalen Berechtigungen, authentifiziertem Zugang und Audit-Log.
- Tools: Aufgaben/Quests auflisten, Entwürfe anlegen, Änderungen vorschlagen, Fortschritt lesen.
- Veröffentlichung einer Quest mit Euro-Belohnung erst nach Elternfreigabe; keine unkontrollierten Geldbuchungen.
- Bestehende Quests berücksichtigen, Duplikate vermeiden, altersgerechte Vorschläge auf Deutsch.
- Cloudflare-Tunnel nur nach sicherer Authentifizierung; keine Bankzugangsdaten im MCP.

## Priorität 2: Taschengeld
- Bedingungsloses festes Taschengeld, niemals durch Sanktionen kürzbar.
- Freiwillige Quest-Boni in Euro separat führen, mit Elternfreigabe und nachvollziehbarer Historie.
- Fälligkeit, Zahlungserinnerung und Status: fällig, ausstehend, eingegangen.
- Verdient, aber nicht ausgezahlt strikt von echtem Bankguthaben trennen.

## Priorität 3: Bankanzeige
- Sparkasse und DKB nur lesend; Verfügbarkeit für Kinderkonten gesondert verifizieren.
- Zahlungseingang über konkrete Umsätze statt bloße Kontostandsänderung zuordnen.
- Bankzugangsdaten und Tokens verschlüsselt verwahren; keine Überweisungsfunktion.

## Oberfläche und Betrieb
- Deutsche, schlanke kinderfreundliche Oberfläche für Tim; Elternbereich für Freigaben.
- Keine Kalenderintegration; Einkaufsliste und andere ungenutzte Module zunächst nur aus Navigation ausblenden.
- Docker Compose auf QNAP mit persistenten Daten, Backups und lokalem Test vor Internetfreigabe.
- Upstream-Updates und AGPL-3.0-Pflichten berücksichtigen.

## Noch offen
- FamQuest API-Endpunkte, Authentifizierung und Datenmodell detailliert prüfen.
- Bankanbieter und Rechte für Kinderkonten prüfen.
- Betrag, Rhythmus und Zielkonto für Taschengeld festlegen.
