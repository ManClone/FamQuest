# FamQuest – Mehrfamilienarchitektur: Datenbank pro Familie

Status: **beschlossene Zielarchitektur, noch nicht implementiert**. Dieser Draft-PR enthält ältere experimentelle `users.family_id`-Änderungen für ein Shared-Table-Modell. Diese dürfen **nicht** als produktive Mehrfamilienlösung ausgerollt werden. Bestehende QNAP-Installation bleibt unverändert.

## Ziel

Ein FamQuest-Backend, ein MCP-Endpunkt, ein PostgreSQL-16-Server mit mehreren logisch getrennten Datenbanken:

- `famquest_auth`: zentrale Benutzerkonten, Passwort-Hashes, Superadmin, Familienregister, DB-Zuordnung, Einladungen, Sessions, OAuth-Clients/-Grants/-Tokens und Audit-Log.
- `famquest_grasser`: ausschließlich private Fachdaten der Familie Grasser (Mitglieder, Aufgaben, XP, Belohnungen, Taschengeld, Bankzuordnungen, Einstellungen).
- `famquest_sertl`: ausschließlich private Fachdaten der Familie Sertl; erst nach vollständigen Tests anlegen.
- Weitere Familien erhalten jeweils eine eigene Datenbank und eigene Datenbankrolle mit minimalen Rechten.

Benutzer-/Familienzuordnung ist ausschließlich in der Auth-Datenbank maßgeblich. Der Familien-DB-Name kommt aus einer serverseitig kontrollierten Registry, **niemals** aus Request-Headern, URL-Parametern oder vom Client gelieferten IDs. DB-Namen sind technische IDs und werden nicht aus frei eingegebenen Familiennamen konstruiert.

## Sicherheitsgrenzen

1. Die Authentifizierung liefert eine validierte Benutzer-ID und Familienzugehörigkeit; der Superadmin ist nicht automatisch Mitglied einer Familie und kann keine privaten Familiendaten lesen.
2. Die API wählt pro Request nach erfolgreicher Authentifizierung die passende Family-DB-Session. Kein globales `get_family(db)` über alle Mandanten. Hintergrundjobs erhalten einen expliziten, serverseitig validierten Tenant-Kontext.
3. Jede Familiendatenbank besitzt eine eigene PostgreSQL-Loginrolle mit Rechten **nur** auf diese Datenbank; kein gemeinsamer App-Superuser. Provisionierung/Migration erfolgt über einen getrennten privilegierten Prozess, dessen Credentials nicht im normalen Request-Pfad verfügbar sind.
4. DB-Verbindungen und Pools sind nach Familie getrennt und begrenzt; keine dynamischen Connection-Strings aus Client-Daten. Verbindungen beim Offboarding schließen.
5. Uploads/Avatare/Exports werden je Familie in getrennten Verzeichnissen mit serverseitig geprüften Pfaden gespeichert. Kein gemeinsamer ungeschützter Dateizugriff.
6. Die Familiendatenbanken speichern keine Login-Passwörter oder OAuth-Refresh-Tokens. Für Fachdaten benötigte Benutzerreferenzen sind externe IDs; keine Cross-Database-Foreign-Keys voraussetzen.
7. FamQuest stellt OAuth 2.0 Authorization Code + PKCE für die ChatGPT-MCP-Verbindung selbst bereit (kein Auth0). Tokens sind kurzlebig, widerrufbar und an Benutzer, Familie, Audience, Client und Berechtigungen gebunden. Der globale Legacy-MCP-Service-Token mit `X-FamQuest-Parent-ID` muss **vor** Freigabe einer zweiten Familie deaktiviert werden.
8. Elternfreigaben bleiben auch bei MCP-Schreiboperationen verpflichtend. Superadmin-Aktionen und Tenant-Provisionierung erhalten Audit-Einträge.

## Umsetzungsschritte

### 1. Bestandsaufnahme und Architektur-Refactoring

- Inventar aller Modelle, Alembic-Migrationen, API-Routen, Hintergrundjobs, Uploads, MCP-Aktionen und DB-Abhängigkeiten.
- Bestehendes `User`/`AuthSession`/`Family`-Modell in Auth-Registry und Fachdaten aufteilen. Das bisherige `family_id`-Experiment im Draft-PR nicht einfach weiterausbauen.
- Zwei getrennte SQLAlchemy-Engines/Session-Factories (Auth + Family) definieren; für Family-Engines tenantbezogenen Pool-Lifecycle vorsehen.
- Alembic-Historien für Auth-DB und Family-DB separat versionieren; niemals automatisch alle bestehenden Revisionen auf einer leeren Auth-DB ausführen.

### 2. Migration ohne Datenverlust

- **Vorher** PostgreSQL-Dump, Upload-Backup und verifizierte Wiederherstellungsprobe auf Testumgebung.
- Bestehende produktive `famquest`-Datenbank zunächst unverändert lassen und eine isolierte Testkopie verwenden.
- Auth-Daten (`users`, `sessions`, benötigte Auth-Konfiguration) in `famquest_auth` übernehmen; Fachdaten bleiben in der künftig `famquest_grasser` genannten bzw. entsprechend registrierten Datenbank.
- Bestehende IDs und fachliche Referenzen erhalten; Foreign-Key-Abhängigkeiten beim Split explizit behandeln. Keine pauschalen `DROP TABLE`-Schritte, bevor jede Abhängigkeit migriert und getestet ist.
- Konsistenzprüfungen: Nutzer, Mitglieder, Aufgaben, XP, Bonus, Belohnungen, Bankdaten, Uploads und OAuth-Sessions. Rollback-Plan dokumentieren.
- Produktions-Cutover nur nach expliziter Freigabe; keine Migration im laufenden Betrieb ohne Wartungsfenster.

### 3. Provisionierung und Offboarding

- Superadmin legt Familie an; Provisioner erstellt eigene DB + DB-Rolle, führt Family-Migrationen aus, registriert DB-Zuordnung in `famquest_auth` und lädt Eltern ein. Fehlerfall rollt Teilzustände kontrolliert zurück.
- Offboarding: Familie sperren, Sessions/OAuth-Tokens widerrufen, laufende Jobs stoppen, Pool schließen, optional verschlüsseltes Export-/Backup bereitstellen, DB + DB-Rolle + Uploads entfernen, Registry bereinigen.
- **Wichtig:** Ein `DROP DATABASE` löscht weder externe Backups noch Dateien, Logs oder Kopien. Aufbewahrungs- und Löschfristen gesondert festlegen; Löschung nur nach expliziter Bestätigung.

### 4. Abnahmetests

- Grasser/Sertl gleichzeitig anmelden: keinerlei Cross-Tenant-Zugriff über API, MCP, fremde Objekt-IDs, Upload-Pfade, Hintergrundjobs oder Exporte.
- Falsche/abgelaufene OAuth-Tokens, manipulierte Familienzuordnung, Session-Wechsel, Superadmin-Zugriff und fehlende Elternfreigabe.
- Test der DB-Rollen: Family-A-DB-Credentials können Family-B-DB nicht verbinden/lesen.
- Migration und Wiederherstellung anhand einer **Kopie** des Grasser-Backups; danach erst Deployment.

## Rollout-Sperre

**Keine zweite Familie, keine produktive Datenbanktrennung und kein Merge des Draft-PR**, bevor Auth-/Family-Split, Berechtigungen, Tests und Backup-Restore erfolgreich sind. Keine Änderungen an der produktiven QNAP ohne gesonderte Freigabe.

### Zugangsdaten für isolierte Datenbankverbindungen (noch nicht produktiv aktiv)

Die opt-in Router verwenden keine Legacy-PostgreSQL-Zugangsdaten als Fallback.
Vor dem Start müssen die Rollen mit passenden, getrennten Berechtigungen
existieren und folgende Umgebungsvariablen gesetzt werden:

```env
AUTH_DATABASE_CREDENTIALS={"username":"famquest_auth_app","password":"<separates-langes-geheimnis>"}
FAMILY_DATABASE_CREDENTIALS={"famquest_grasser":{"username":"famquest_grasser_app","password":"<geheimnis-a>"},"famquest_sertl":{"username":"famquest_sertl_app","password":"<geheimnis-b>"},"famquest_henning":{"username":"famquest_henning_app","password":"<geheimnis-c>"}}
```

Die Platzhalter dürfen nicht unverändert übernommen werden. Secrets gehören
nicht ins Git-Repository. Fehlende oder nicht zur Datenbank passende Konten
verhindern den Verbindungsaufbau. Die Rollen-/Rechtevergabe und das sichere
Provisionieren des Auth-Kontos sind noch offen; dieses Konfigurationsbeispiel
ist **keine** Aufforderung, die produktive QNAP bereits umzustellen.
