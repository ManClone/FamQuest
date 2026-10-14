# FamQuest – Sicherheits- und Abnahmetests

Stand: 2026-10-14. Diese Checkliste ist ein Testplan, **kein Nachweis bestandener Tests**.

## Konten und Rollen
- [ ] Frische Installation: erstes Administratorkonto ohne PIN anlegen.
- [ ] Administrator legt zweites Elternkonto und Tims Kinderkonto an.
- [ ] Beide Elternkonten können Aufgaben und Belohnungen verwalten.
- [ ] Kinderkonto erhält bei GET /api/auth/accounts und POST /api/auth/accounts keinen Zugriff (403).
- [ ] Unangemeldete Zugriffe auf beide Endpunkte werden verweigert.
- [ ] Gleiche E-Mail erneut anlegen ergibt 409; ungültige Rolle ergibt 422.
- [ ] Anmeldung, Abmeldung und Sitzungsablauf mit allen drei Konten prüfen.

## Demo-Modus
- [ ] Bei DEMO_MODE aktiv: GET und POST /api/auth/accounts ergeben 403 demo.disabled.
- [ ] Bei DEMO_MODE deaktiviert: berechtigtes Elternkonto darf Konten lesen und anlegen.
- [ ] Demo-Reset und Seed-Ablauf bleiben funktionsfähig.

## Geld und XP
- [ ] Grundtaschengeld bleibt unabhängig von Konsequenzen unverändert.
- [ ] Euro-Konsequenzen reduzieren höchstens den Wochenbonus; keine Übertragung in nächste Woche.
- [ ] XP-Abzug höchstens bis zum verfügbaren Guthaben; Level-XP bleiben erhalten.
- [ ] Stornierung erstattet exakt den tatsächlich abgezogenen Betrag; wiederholte Stornierung ist idempotent.
- [ ] Wochenwechsel Montag/Sonntag, Zeitzone und stornierte Konsequenzen prüfen.

## Migration, CI und QNAP
- [ ] Alembic: genau eine aktuelle Migrationsspitze und Upgrade von leerer Datenbank.
- [ ] Backend-Tests, Lint, Frontend-Build und Docker-Build erfolgreich.
- [ ] Drei Logins und Freigabeablauf in Testumgebung durchspielen.
- [ ] Erst nach bestandenen Tests QNAP-Backup und bewusste Freigabe für Neuinstallation.
- [ ] MCP erst nach rollenbasierten API-Tests freischalten; Approvals nur auf ausdrückliche Elternbestätigung.
- [ ] Abendliche Approval-Erinnerung bleibt bis zur Freigabe deaktiviert.
