# Betreiberverwaltung: Familien sperren und wieder freigeben

Die zentrale Testanwendung besitzt unter `/operator` eine getrennte Betreiberanmeldung.
Sie zeigt Familiennamen, Status und Anzahl verknüpfter Konten. Sie öffnet keine Familien-DB
und zeigt keine Aufgaben oder Bilder. Aktive Familien können mit Begründung, exakt eingegebenem
Familiennamen und ausdrücklicher Bestätigung gesperrt bzw. wieder freigegeben werden.
Familien können in ausdrücklich vorbereiteten leeren Datenbankplätzen angelegt werden
(siehe [Familie anlegen](family-creation.md)). Familien löschen ist weiterhin nicht möglich.
Der bisherige Elternbereich innerhalb einer Familie bleibt getrennt bestehen.

## Rechte und Anmeldung

- Ein eigener zentraler `Identity`-Datensatz mit `is_superadmin=true`, ohne Familienmitgliedschaft.
- Eltern-/Kinderkonten werden ausdrücklich abgewiesen. Vorhandene Konten werden nicht hochgestuft.
- Eigener Cookie `__Host-famquest_operator`, Secure, HttpOnly, SameSite Strict; eine Stunde Laufzeit.
- Zufällige Sitzungswerte werden nur gehasht gespeichert. Jede Anfrage prüft erneut die Betreiberrolle.
- Familiencookies und MCP-Bearer gewähren keinen Betreiberzugriff; der Betreiber-Cookie gewährt keinen Familienzugriff.
- Ausdrückliche Abmeldung mit CSRF-Nachweis; Anmeldeversuche begrenzt. Antworten werden nicht zwischengespeichert.
- Die Oberfläche setzt Familiennamen als Text ein und verwendet eine Content Security Policy ohne Inline-Skripte.

## Bestehende zentrale Testinstanz aktualisieren

### Bereits vorhandene Betreiberübersicht (Auth-Stand `f20261101_operator`)

Für die Statusaktionen ist die neue additive Auth-Migration `g20261101_status` nötig.
Sie legt nur `tenant_status_events` samt Index an. Vor Ausführung frische Benutzer-DB-Sicherung
und Compose-Kopie erstellen, Sicherung prüfen und Freigabe einholen; keine Familie migrieren.
Mit dem neuen geprüften Image, bestehender `runtime.env` und internem Staging-Datennetz einmalig:

```text
python -m app.operator_setup --apply-reviewed-status-migration
```

Der Helfer akzeptiert nur `f20261101_operator` oder den bereits angewendeten Zielstand.
Danach die beiden App-Image-Verweise im bestehenden Staging-Compose aktualisieren,
Netzwerke und Volumes behalten, Gateway und App gemeinsam neu starten. Der vorhandene
Betreiberzugang bleibt erhalten; keinen neuen Betreiber und keine neuen Passwortdateien anlegen.

### Älterer Stand ohne Betreiberübersicht

**Kein bloßes Image-Update:** Die zentrale Benutzer-DB benötigt die additive Migration
`f20261101_operator` nach `e20261031_actors`. Sie legt ausschließlich `operator_sessions`
mit einem Index an. Familien-Datenbanken und bestehende Identitäten werden nicht geändert.
Die normale Startprüfung führt diese Migration nicht selbst aus.

Die folgenden Schritte sind ein geplanter Bedienablauf, keine bereits ausgeführte NAS-Änderung.
Vor Datenbankänderung Sicherung der zentralen Benutzer-DB und der aktuellen Compose-Konfiguration
erstellen und prüfen. Erst nach Freigabe ausführen. Daten-Volumes beibehalten.

1. Mit dem geprüften neuen App-Image einen einmaligen Container im **bestehenden internen
   Staging-Datennetz** starten. Er nutzt die bestehende `runtime.env`, keine Root-Zugangsdaten.
   Den normalen App-Einstieg überschreiben durch:

   ```text
   python -m app.operator_setup --apply-reviewed-auth-migration
   ```

   Die Hilfe akzeptiert nur den bekannten alten bzw. bereits migrierten Stand. Bei fremdem
   Stand bricht sie ab. Sie migriert weder Familien noch zukünftige unbekannte Versionen.
2. Zusätzlich die oben beschriebene Status-Migration auf `g20261101_status` anwenden.
   Danach im Staging-Compose beide App-Image-Verweise auf den geprüften neuen Digest ändern,
   bestehende Netzwerke, Host-Header und Volumes behalten; Gateway und App zusammen neu starten.
   Die Initialisierung prüft den existierenden Stand und überschreibt keine Testkonten.
3. Im laufenden neuen Test-App-Container mit interaktivem Terminal einen **neuen, unabhängigen**
   Betreiberzugang einrichten:

   ```text
   python -m app.operator_setup --email DEINE-SEPARATE-BETREIBER-ADRESSE
   ```

   Die tatsächliche E-Mail einsetzen. Das Kennwort zweimal verdeckt eingeben (16–128 Zeichen).
   Nicht dasselbe Kennwort wie bei Eltern/Kinderzugängen verwenden. Vorhandene Identitäten
   werden verweigert, nicht umgewidmet. Der Vorgang ist einmalig und läuft nie automatisch.
4. `https://famtest.websiteclone.de/operator` öffnen und mit diesem Betreiberzugang anmelden.
   Der vorhandene Cloudflare-Host leitet auch diesen Pfad an denselben Gateway; keine neue
   öffentliche Route oder Portfreigabe erforderlich.

Für eine **neue leere** Testinstanz berücksichtigt der Staging-Bootstrap die Migration bereits.
Auch dort wird kein Betreiber automatisch eingerichtet.

## Abnahme

- Betreiber sieht beide Familien und Status, kann aktualisieren und sich abmelden.
- Eltern-/Kinderkennwörter funktionieren im Betreiberlogin nicht.
- Betreiberlogin macht keine Familienverwaltung oder Familiendaten zugänglich.
- Nach Abmeldung oder Ablauf ist erneute Anmeldung nötig.
- Mobile Ansicht ohne horizontalen Überlauf; lange Namen dürfen umbrechen.

## Verhalten der Statusaktionen

- Sperre, Widerruf der Browser-Sitzungen und MCP-Freigaben sowie Protokolleintrag werden
  in einer zentralen Transaktion gespeichert. Ausstehende OAuth-Codes werden ebenfalls entwertet.
- Neue Anmeldungen und neue OAuth-Codes/Grants nehmen dieselbe Familien-Zeilensperre.
  Gleichzeitige Anmeldeversuche können deshalb nicht nachträglich eine gültige Sitzung
  hinter einer abgeschlossenen Sperre anlegen. Bereits laufende Fachvorgänge werden nicht abgebrochen.
- Wiederfreigabe erfordert erneut Begründung und Bestätigung. Sie stellt keine alten
  Sitzungen oder MCP-Freigaben wieder her: neu anmelden bzw. MCP erneut autorisieren.
- Ein Request-Schlüssel macht identische Wiederholungen idempotent. Widersprüchliche
  Wiederholungen oder veraltete Ausgangsstände werden abgewiesen. Ein alter Auftrag kann eine
  inzwischen wieder freigegebene Familie nicht erneut sperren.
- Der Statusverlauf ist nur lesbar, nachladbar und enthält Betreiber, Zeitpunkt, Begründung,
  Familiennamen zur Zeit der Änderung und alten/neuen Status. Kein Lösch-/Änderungsendpunkt.
- Familien in Einrichtung oder mit unbekanntem Status können hier nicht aktiviert werden.
- Sind alle Familien gesperrt, darf die App mit einem unabhängigen Betreiberzugang neu starten,
  ohne gesperrte Familien-DBs zu öffnen. So bleibt Wiederfreigabe möglich. Eine leere bzw.
  unvollständige Registrierung ohne solchen Betreiber wird weiterhin abgewiesen.

Noch offen bleiben weitere Betreiberaktionen wie Familienlöschung, zusätzliche Kapazität und Provisionierung echter
Familien und die produktive Wiederherstellungs-/Migrationsabnahme. Dieser Stand erteilt keine
Freigabe zur Produktionsumstellung.
