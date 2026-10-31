# FamQuest: Abschlussprüfung vom 31.10.2026

## Ergebnis

Der bestehende Einfamilienbetrieb ist erreichbar und gesund. Die neue
Mehrfamilienversion ist **noch nicht deploybar**. Weder Datenmigration noch
Aktivierung von Sertl/Henning oder Änderungen an Produktivkonten wurden ausgeführt.

## Verifizierter Ausgangsstand

- Repository: https://github.com/ManClone/FamQuest
- `main`: `0d44fc52e63401a08e1634e6209c82d113da5731`.
- `develop`: `2c91da56c556bb7eac4e8f098ff3a361bc186620`.
- Offener Draft-PR #34: `feature/multifamily-foundation`,
  `c1017e30e1f62ef6d1904b2b91073ca565dd1411`.
- main-Workflows: Predeployment 40709807987 und Security 40709808007 erfolgreich.
- main-Docker-Veröffentlichung 40710178691 erfolgreich. Workflow veröffentlicht
  `ghcr.io/manclone/famquest:latest` und den vollständigen SHA-Tag.
  Das tatsächlich laufende QNAP-Image und dessen Digest wurden nicht ermittelt.
- Draft-Predeployment 41193378743 erfolgreich; Security 41193378636 scheitert
  an Ruff in `tests/test_oauth_codes.py`.
- Lesender QNAP-Healthcheck an Port 11900: `status=ok`, `database=ok`.

## Änderungen in dieser Arbeitskopie

- Ruff-Formatfehler behoben.
- Issue #31: Wiederholungsaktion samt Tageszähler und Speichersperre auch in
  der Familienübersicht. Rücknahme bleibt eine getrennte Aktion.
- MCP-Authorization-Codes verweigern Kinder, ungültige Rollen und Superadmins.
  Gesperrte Codes werden beim Austausch aus der Datenbank neu geladen.
- Neue Auth-DB-Revision `c20261031_tokens`: OAuth-Grants und ausschließlich
  gehashte Access-/Refresh-Tokens; keine Änderung der Familien-Alembic-Historie.
- Access-Tokens laufen nach 10 Minuten ab, Refresh-Tokens nach 30 Tagen.
  Client, Familie und MCP-Audience werden geprüft. Mitgliedschaft, Familienstatus,
  Elternrolle und Client-Freigabe werden erneut geprüft.
- Refresh-Rotation sperrt den gemeinsamen Grant; Wiederverwendung widerruft
  auch Nachfolger-Tokens. Der Widerruf wird trotz Fehlerrückgabe gespeichert.
- Auth-Migrations-, Token-Lifecycle- und PostgreSQL-Parallelitätstests ergänzt.
  Die Token-Funktionen sind noch nicht als öffentliche Endpunkte eingebunden.

## Verbleibende Release-Blocker

| Bereich | Noch erforderlich |
| --- | --- |
| Zentrale Anmeldung | Browser-Sessions, Login/Logout, Passwortwechsel, Kontoverwaltung und Einladungen vollständig auf `famquest_auth` umstellen; lokale User-Referenzen ohne lokale Login-Geheimnisse erhalten. |
| API-Isolation | Authentifizierten Tenant vor jeder Family-Session bestimmen; sämtliche API-Pfade, Hintergrundjobs, Uploads und Exporte auf getrennte Datenbanken/Verzeichnisse umstellen. Legacy-Zugriff darf keine zweite Familie erreichen. |
| MCP | HTTP-Authorization/Consent/Token/Revocation-Endpunkte und Metadaten integrieren; Token an serverseitigen Tenant-Kontext binden; globalen Service-Token und Parent-ID-Header vor Mehrfamilienbetrieb ablösen; Elternbestätigungen erhalten. |
| Provisionierung | Auth-DB und Family-DBs mit getrennten minimalen Rollen migrieren; Sertl/Henning erst danach aktivieren und Elternkonten sicher einladen. |
| Bestandsmigration | Wiederherstellbare Testkopie erstellen; IDs, Zuordnungen, XP, Bonus, Belohnungen und Uploads vorher/nachher vergleichen; Wiederherstellungsprobe durchführen. |
| Bonusregeln | Aktuelle API erlaubt frei wählbare Cent-/XP-Abzüge und Datumswerte. Issue #25 fordert feste Kritikstufen, geschützten Restbonus und unveränderliche abgeschlossene Wochen. Vor einer Freigabe dieses Geldbereichs abgleichen und mit Tests absichern. |
| Abzeichen/Drache | Offene Issues #29/#30 gegen bereits vorhandenen Level-/Drachencode abnehmen; vorhandener Code allein ist kein Abschlussnachweis. |
| QNAP | Tatsächliches Image/Digest, DB-Migrationsstand und Compose-Konfiguration ermitteln; Backup und Restore prüfen; anschließend konkreten Cutover zur Freigabe vorlegen. |

Es gibt keinen Nachweis, dass die bisherigen Einfamilien-Endpunkte bereits
zwischen zwei gleichzeitig angemeldeten Familien isolieren. Die vorhandenen
Router-/Registry-Unit-Tests ersetzen diesen End-to-End-Nachweis nicht.

## Prüfungen dieser Änderung

- 53 isolierte Backendtests bestanden, inklusive Auth-Migration auf SQLite.
- Ruff-Lint und Formatprüfung bestanden.
- Lokale Typprüfung und Produktionsbuild bestanden.
- 46 Tests der betroffenen Familien-/Haushaltsansichten bestanden.
- PostgreSQL-Parallelität und vollständiger Backendlauf benötigen den CI-Lauf;
  lokal steht kein PostgreSQL-/Docker-Testdienst zur Verfügung.
- Lokale Frontend-Pakete wurden mit pnpm installiert; dabei wurden innerhalb der
  Versionsbereiche neuere Pakete gewählt. Verbindlicher Reproduktionsnachweis
  bleibt CI mit `npm ci` und dem unveränderten `package-lock.json`.

## Fortsetzung

Der Nutzer hat den Upload dieser Änderungen auf den bestehenden GitHub-Draft
und den Start der vollständigen CI-Prüfungen ausdrücklich freigegeben.
Die CI-Ergebnisse dieses Updates stehen noch aus. Kein Merge nach main,
keine Image-Veröffentlichung und kein produktiver Cutover als Teil dieses Uploads.
