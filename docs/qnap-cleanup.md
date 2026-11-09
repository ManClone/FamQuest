# Eine dauerhafte Anwendung: famquest-live

Verbindliches Ziel: genau eine FamQuest-Anwendung `famquest-live` in Container
Station. Die bestehende Anwendung wird bearbeitet, nicht daneben neu erstellt.
Die produktive Ausführung übernimmt der Betreiber. Auf dem NAS wurde durch die
Cloud-Sitzung nichts geändert.

## Aktuelle Dateien

- `docker-compose.qnap-live-final.yml`: vollständige neue Zielkonfiguration.
- `scripts/qnap-live-auto-backup.sh`: zugehöriger neuer Sicherungsjob.
- `scripts/qnap-container-inventory.sh`: rein lesende Bestandsaufnahme.

Die früheren Dateien `docker-compose.qnap-live-update.yml` (nur Image-Update)
und `docker-compose.qnap-consolidated.yml` (Umbenennung nach `famquest`) sind
überholte Alternativen und für diesen Ablauf nicht anzuwenden.

Die finale Vorlage enthält fünf normale Dienste: `live-db`, `live-app`,
`live-gateway`, `live-mcp`, `cloudflared`. `backup` ist ein sechster Dienst im
Profil `backup`, den der Sicherungsjob nur während der Sicherung als temporären
Container derselben Compose-Anwendung startet und anschließend entfernt.
Beim normalen App-Start wird er nicht aktiviert. Zusätzlich führt sein Start
ohne das vom koordinierten Job gesetzte Freigabeflag nur zu einer SKIP-Meldung;
es wird keine unkoordinierte Sicherung erstellt.

Der Tunnel bleibt mit derselben Identität eingerichtet und verwendet die
vorhandene `.env`. Sein Gateway-Zielname `famquest-live-gateway` bleibt als Alias
im Frontnetz erhalten. Der Tunnel hängt an Front- und Egress-Netz; Gateway und
MCP bleiben intern erreichbar. Die finale Anwendung verwendet nur ihre eigenen
Netzwerke `famquest-live_data`, `famquest-live_front`, `famquest-live_egress`.
Sie benötigt das alte `famquest_default` nicht mehr. Das ist erst nach dem
gezielten Tunnelwechsel und erfolgreicher öffentlicher Prüfung wirksam.

## Daten und Dateien erhalten

| Bestehende Ablage | Verwendung |
| --- | --- |
| `famquest-release-v2-db` | aktuelle PostgreSQL-Daten, einschließlich zentraler und Familien-DB |
| `famquest-release-v2-runtime-uploads` | aktuelle Uploads |
| `famquest-live-config-v1` | private Runtime- und Gateway-Konfiguration |
| `/share/Container/famquest-live/backups` | private Sicherungen |
| `/share/Container/famquest-central-stage/postgres.env` | DB-Zugang des bestehenden DB-/Backupdienstes |
| `/share/Container/famquest/.env` | vorhandene Tunnelidentität |

Die drei Volumes sind in der Vorlage ausdrücklich extern. Es werden keine
Datenbanken kopiert oder neue Live-Datenvolumes erzeugt. Historische Namen von
Volumes und Ordnern können bestehen bleiben, obwohl nur eine Anwendung in
Container Station verbleibt. Die beiden alten Konfigurationsordner dürfen
wegen der weiterhin benötigten Dateien nicht pauschal gelöscht werden.

## App-Image

Die Vorlage verwendet das geprüfte lokale Image
`famquest:sternchen-review-20261109-aclfix` mit `pull_policy: never`.
Der Suffix bezeichnet die zusätzlich erforderliche QNAP-ACL-Korrektur.
Archiv und Prüfsumme wurden in der Cloud vorbereitet:

- `/workspace/.famquest/famquest-sternchen-review-20261109.tar.gz`
- `/workspace/.famquest/famquest-sternchen-review-20261109.tar.gz.sha256`

Nach Übertragung die Prüfsumme des Archivs prüfen (die Prüfsummendatei enthält
den Cloud-Dateipfad; zum lokalen Prüfen nur den Dateinamen anpassen), per
`docker load` importieren und die Image-ID vergleichen:

```
sha256:7f946f7de8623e3e2dd71272928592ccb96ef5f659a4924917a3e3b22362c78a
```

Die Cloud-Browserabnahme, 366 Frontendtests, neun Backendtests und Runtime-
Leserechteprüfung sind dokumentiert in `sternchen-3d-update.md`. Die neue
zentrale App-/OAuth-/MCP-Prüfung auf einer isolierten Kopie steht noch aus.
Die lokale Einfamilienprüfung ist kein Ersatz für diese Betriebsprobe.

## Sicherungsjob

Der alte Job startet den Container des Projekts `famquest-live-manual-backup`.
Der neue Job verwendet das Profil `backup` der dauerhaften Anwendung, pausiert
wie bisher App und MCP, erstellt dieselben Artefakte und startet die Dienste
auch nach einem Sicherungsfehler wieder. Bei einem unterbrochenen Lauf wird
zuerst der eigene Backupcontainer beendet, bevor Schreibzugriffe fortgesetzt
werden. Eine fehlgeschlagene Wiederaufnahme wird als Fehler gemeldet.

Gesichert werden weiterhin globale Rollen, `famquest_auth`,
`famquest_grasser_runtime`, Uploads und die drei bisherigen Runtime-/Gateway-
Dateien. Die Familien-DB ist wie im gelieferten Helfer ausdrücklich benannt;
neu hinzukommende Familien sind damit noch nicht automatisch gesichert.
Prüfsummen und `BACKUP-COMPLETE` werden erst am Ende erzeugt. Ein erfolgreicher
Dump-/Archivtest ist keine vollständige Wiederherstellungsprobe.

Der neue Job benötigt `docker compose` auf dem NAS und dieselbe finale YAML
als Datei `/share/Container/famquest-live/compose.yml`. Die Datei muss den
Inhalten in Container Station entsprechen. Alternativ wird der Pfad über
`FAMQUEST_COMPOSE_FILE` festgelegt. Skript und YAML ohne Zugangswerte ablegen;
die referenzierten privaten Dateien bleiben auf dem NAS.

Die bestehende Sperre `.famquest-live-auto-backup-lock` wird beibehalten. Alten
und neuen Zeitplanerjob niemals parallel aktivieren. Der Zeitplan bleibt bei
der vorhandenen Uhrzeit des NAS; es wird keine neue Uhrzeit erfunden.

## Geplanter Betreiberablauf

1. Mit dem bisherigen Job eine aktuelle vollständige Sicherung ausführen und
   bestätigen. Beide bisherigen Compose-Konfigurationen sowie den alten
   Zeitplanerjob privat sichern. Aktuelles Produktionsimage mit Digest-Präfix
   `d4073b03` als Rückweg behalten.
2. Kandidatenimage auf dem NAS importieren, Image-ID prüfen und die isolierte
   zentrale Betriebsprobe abschließen. Keine zweite Datenbank auf dem
   produktiven Volume starten.
3. Finale YAML als `/share/Container/famquest-live/compose.yml` ablegen und den
   neuen Job daneben als `qnap-live-auto-backup.sh`. Den alten Sicherungszeitplan
   für das Wartungsfenster deaktivieren.
4. Ausschließlich den alten Tunnelcontainer `famquest-cloudflared-1` stoppen.
   Die alte Anwendung `famquest` vorerst für den Rückweg erhalten. Niemals beide
   Tunnel während dieses gezielten Wechsels unbeabsichtigt parallel starten.
5. Bestehende Anwendung `famquest-live` in Container Station bearbeiten und die
   YAML vollständig durch die finale Vorlage ersetzen. Daten und Volumes beim
   Aktualisieren erhalten; `backup` nicht als normales Startprofil aktivieren.
   DB nicht duplizieren oder entfernen. Bei fehlenden Dateien/Volumes abbrechen,
   statt leere Ersatzdatenvolumes zu erzeugen.
6. Fünf normale Dienste sowie DB-/App-Health prüfen. Öffentliche Anmeldung,
   Familienzuordnung, vorhandene Uploads, Aufgaben, Sternchen und OAuth/MCP
   prüfen. Der Tunnel muss den Gateway-Alias nun über das interne Frontnetz
   erreichen. Einen gegebenenfalls automatisch erzeugten Backupcontainer nur
   nach Prüfung beenden; ohne Freigabeflag schreibt er keine Sicherung.
7. Den neuen Job erst mit `--check`, dann mit `--run` ausführen. `--check` sichert
   keine Daten. Erst nach einem vollständigen erfolgreichen Lauf den täglichen
   Zeitplan auf den neuen Skriptpfad mit `--run` umstellen. Danach wird die alte
   Anwendung `famquest-live-manual-backup` nicht mehr benötigt.
8. Nach bestätigtem Livebetrieb und neuer Sicherung die verbleibenden
   Test-/Migrationsprojekte zunächst gezielt stoppen und erneut prüfen. Danach
   nur ihre bestätigten Container/Anwendungen entfernen. Volumes, Sicherungen
   und die weiter benötigten Konfigurationsdateien erhalten. Kein globales
   `docker system prune`, `volume prune` oder `compose down -v` verwenden.
9. Neues Inventar prüfen: nur die fünf dauerhaften FamQuest-Container sollen
   laufen; während der Sicherung kommt kurz der eigene Backupcontainer hinzu.

## Belegte Bereinigungsabhängigkeiten

Das Betreiberinventar vom 9. November enthält 21 FamQuest-Projekte und 48
Container; 15 Projekte sind vollständig gestoppt. Gestoppt bedeutet nicht,
dass ihre Datenablagen entbehrlich sind. Der private Rohbericht ist nicht in Git.

Besonders wichtig: `famquest-release-verify-v2-restore-db-1` ist gestoppt, verwendet
aber dasselbe Datenvolume wie die laufende Live-Datenbank. Ihn nicht starten.
Release-Runtime-, Prepare- und Backuphelfer referenzieren ebenfalls Live-Uploads
oder Live-Konfiguration. Bei einer Entfernung ihre Volumes nicht mitlöschen.
`famquest-current-restore`, `famquest-migrated-runtime`, `famquest-central-stage`
und `famquest-funktionstest` enthalten noch laufende Alt-/Testdienste. Ihre
externen Zugriffe und privaten Ablagen müssen vor einer Entfernung zugeordnet
sein. Andere NAS-Anwendungen sind nicht Teil der Bereinigung.

## Rückweg

Bei fehlgeschlagener Umstellung den neuen Zeitplan deaktiviert lassen, den
neuen Tunnel stoppen und die zuvor gesicherte `famquest-live`-YAML mit dem alten
App-Image wiederherstellen. Vor einem Wechsel der DB-Container immer den
bisherigen DB-Prozess geordnet stoppen. Dieselben externen Volumes weiter nutzen.
Anschließend den bisherigen Tunnel in `famquest` und den alten Backupjob wieder
aktivieren. Der alte und der neue Backupjob dürfen nicht gleichzeitig laufen.
Alte Konfigurationen und Container bleiben bis zur erfolgreichen Prüfung erhalten.


## QNAP-ACL-Befund und Reparatur des Kandidaten

Der NAS-Build des ursprünglichen Quellpakets hat POSIX-Zugriffs- und Default-ACLs
auf Backend-Dateien übernommen. Normale Modi waren korrekt (`755`/`644`), aber
der App-Benutzer konnte `app.deployment_check` und `app.multitenant_app` nicht
lesen. Ein fehlendes Modul war hier die Folge der Zugriffsverweigerung.
Die bisherigen statischen Dateiprüfungen erkannten dieses Backendproblem nicht.

Der normale Dockerfile-Build führt jetzt `backend/docker-normalize-permissions.py`
aus: explizite POSIX-ACLs der kopierten App-Dateien entfernen und danach die
Dateimodi setzen. `.venv` und Symlink-Ziele bleiben unberührt. Der Prozess
läuft danach weiterhin als normaler App-Benutzer.

Für das bereits auf dem NAS gebaute Image `famquest:sternchen-review-20261109`
gibt es `Dockerfile.qnap-aclfix`. Es kopiert nur dieses Hilfsskript und repariert
die Berechtigungen im abgeleiteten Image. Mit `-f Dockerfile.qnap-aclfix` das neue
Tag `famquest:sternchen-review-20261109-aclfix` bauen. NAS-Quelldateien,
produktive Container und Datenvolumes werden dabei nicht verändert.

Die zuvor dokumentierte Cloud-Image-ID gehört zum alten Cloud-Artefakt. Ein
NAS-Build bzw. das abgeleitete ACL-Fix-Image hat eine eigene Image-ID; diese nach
dem erfolgreichen lokalen Build erfassen. Vor der Umstellung die zentralen
Modulimporte als App-Benutzer und danach die lesende zentrale Deploymentprüfung
wiederholen. Die NAS-Prüfung und der neue vollständige zentrale Start sind noch
nicht als erfolgreich behauptet.
