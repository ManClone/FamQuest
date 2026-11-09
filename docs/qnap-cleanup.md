# QNAP nach der Mehrfamilien-Migration bereinigen

## Aktuelle Empfehlung: `famquest-live` behalten

Die Umbenennung nach `famquest` ist zurückgestellt. Für den nächsten Schritt
`docker-compose.qnap-live-update.yml` verwenden und ausschließlich die bestehende
Container-Station-Anwendung `famquest-live` bearbeiten. Diese Vorlage enthält
die vier bisherigen Dienste mit ihren bisherigen Netzwerken, externen Volumes,
Runtime-/MCP-Korrekturen und dem geprüften lokalen Sternchen-Image. Der vorhandene
Tunnel bleibt zunächst in `famquest`; dadurch wird beim App-Update kein Tunnel
verschoben. Die Zusammenführungsvorlage weiter unten ist ein älterer Entwurf
und soll für diesen Weg nicht angewendet werden.

Der übermittelte tägliche Sicherungsjob sucht `famquest-live` über Compose-Labels
und verwendet den gestoppten Helfer `famquest-live-manual-backup`. Beide bleiben
bei diesem Weg erhalten, daher ist keine Umstellung der Dienstsuche nötig.
`--check` prüft die Dienste und den Lock, erstellt aber kein neues Backup.
Die tatsächliche Sicherung erfolgt weiterhin über `--run` des vorhandenen Jobs.
Die Anwendung `famquest-live-manual-backup` samt Helfer vorerst nicht entfernen.
Für eine spätere Übernahme dieses Helfers wird noch seine Compose-Konfiguration
benötigt; der Zeitplanerjob enthält den eigentlichen Sicherungsbefehl nicht.

Reihenfolge für den Betreiber:

1. Bestehende private Compose-/Betriebskonfiguration sichern und einen aktuellen
   vollständigen Lauf des bestehenden Sicherungsjobs bestätigen.
2. Geprüftes Archiv `famquest-sternchen-review-20261109.tar.gz` auf den QNAP
   übertragen, mit der bereitgestellten Prüfsumme prüfen und per `docker load`
   importieren. Erwartete lokale Image-ID:
   `sha256:7f946f7de8623e3e2dd71272928592ccb96ef5f659a4924917a3e3b22362c78a`.
3. Die weiterhin ausstehende isolierte zentrale App-/OAuth-/MCP-Prüfung mit dem
   Kandidaten durchführen. Die vorhandene Cloud-Abnahme verwendete eine lokale
   Testfamilie und ersetzt diese zentrale Betriebsprobe nicht.
4. Im geplanten Wartungsfenster die vorhandene Anwendung `famquest-live` mit der
   neuen Vorlage aktualisieren. Dabei keine zweite Anwendung mit demselben
   PostgreSQL-Volume starten, kein Volume löschen und keine DB-Migration anstoßen.
   Der zentrale Start führt nur die bestehende lesende Deploymentprüfung aus.
5. Anmeldung, vorhandene Familien, Uploads, Level-6-Baby/Interaktion und MCP
   prüfen. Bestehenden Sicherungsjob erst mit `--check`, dann mit `--run` prüfen.
6. Danach Tunnel und Backup-Helfer getrennt und geprüft in die Daueranwendung
   integrieren; erst anschließend die belegten Altanwendungen entfernen.

Es wurde weiterhin nichts auf dem NAS aktualisiert. Die Stage-Datei
`/share/Container/famquest-central-stage/postgres.env`, der bisherige Tunnel und
das Netzwerk `famquest_default` bleiben benötigt. Der endgültige Umfang ist
fünf laufende Dienste plus gegebenenfalls ein gestoppter Backup-Helfer in einer
Container-Station-Anwendung.

Ziel ist eine Container-Station-Anwendung `famquest` mit App, PostgreSQL,
Gateway, MCP und dem noch zu übernehmenden Cloudflare-Tunnel (fünf Container). Die Zeilen im Container-Station-Bild
sind Anwendungen/Compose-Projekte; die Zahl rechts zählt ihre Container.
Die Dienste zu einem einzelnen Container zusammenzuführen ist für dieses
Aufräumen nicht erforderlich und würde die Betriebsarchitektur verändern.

## Aktuell belegter Stand

Laut Übergabe arbeitet `famquest-live` mit `live-db`, `live-app`, `live-gateway`
und `live-mcp`. Die produktive Umstellung führt der Betreiber selbst aus.
Der Screenshot allein belegt keine entbehrlichen Datenbestände und keine
Unabhängigkeit der Projekte. Insbesondere sind zusätzlich
`famquest-funktionstest` und `famquest-migrated-runtime` als aktiv dargestellt.
Sie dürfen erst nach Prüfung ihrer aktuellen Aufgaben und Verbindungen
abgeschaltet werden. Ein gestopptes Projekt kann weiterhin produktiv verwendete
Volumes oder Bind-Mounts referenzieren.

Der Sternchen-Integrationsstand ist auf `codex/finalize-multitenant` im Commit
`9548b7d` gepusht. Die isolierte zentrale QNAP-Betriebsprobe bleibt vor dem
Produktivwechsel erforderlich; siehe `sternchen-3d-update.md`.

## Rein lesende Bestandsaufnahme

Auf dem QNAP im aktuellen Repository-Checkout ausführen:

```sh
sh scripts/qnap-container-inventory.sh > famquest-container-inventory.jsonl
```

Bei abweichendem Docker-Pfad `DOCKER_BIN` auf die vorhandene Docker-Binary setzen.
Die aktuelle Datei kann auch separat aus dem gepushten Branch übertragen werden;
ein Austausch des produktiven Quellverzeichnisses ist hierfür nicht nötig.
Das Skript wurde gegen den lokalen Cloud-Docker-Daemon ausgeführt und die
JSON-Zeilen wurden geparst. Eine Ausführung auf dem QNAP steht noch aus.

Das Skript liest alle laufenden und gestoppten Container, ausgewählte Compose-
Zuordnungen, Images, Ports, Netzwerke und Mounts sowie die Volume-/Netzwerkliste.
Auch andere Projekte werden einbezogen, damit gemeinsam verwendete Ablagen und
Netzwerke auffallen. Container-Umgebungswerte, Startbefehle, Zugangsdaten,
Dateiinhalte und Logs werden nicht ausgegeben. Der Bericht enthält private
Pfad- und Netzwerknamen; privat halten und nicht ins Repository committen.
Ein fehlgeschlagener Docker-Aufruf liefert einen Fehler statt einer vermeintlich
vollständigen Liste.

## Reihenfolge nach Auswertung des QNAP-Inventars

1. Für jeden Container den tatsächlichen Compose-Projektnamen, Dienst,
   Image-ID, Daten-Mounts und Verbindungen zu `famquest-live` zuordnen.
   Externe Tunnel, Backup-Zeitplaner und deren Projekt-/Containerreferenzen
   gesondert prüfen; ein Containerinventar belegt keine NAS-Zeitpläne.
2. Vollständige aktuelle Sicherung beider Datenbanken, Uploads und privater
   Live-Konfiguration bestätigen. Das laufende Produktionsimage und die
   Konfiguration des Rückwegs behalten. Backup-Verzeichnisse sind keine
   entbehrlichen Containerreste.
3. Die isolierte zentrale Abnahme des Sternchen-Kandidaten abschließen.
   Der Betreiber führt anschließend den produktiven Wechsel durch.
4. Nach erfolgreichen Prüfungen der Live-Anmeldung, Familienzuordnung,
   Aufgaben, Drachenkarte und MCP die konkret als unabhängig und entbehrlich
   belegten aktiven Altprojekte zuerst stoppen. Livebetrieb erneut prüfen.
5. Nur die bestätigten Altanwendungen/Container entfernen. In Container Station
   keine Option zum gleichzeitigen Löschen von Volumes/Daten verwenden.
   Unzugeordnete Images, Volumes und Ordner bleiben zunächst erhalten.
6. Datenablagen und Images in einem getrennten Schritt nach geprüfter Sicherung
   und Zuordnung bereinigen. Kein globales `docker system prune`, `volume prune`
   oder `compose down -v` für diese Bestandsbereinigung verwenden.

Ergebnis soll nur noch die Anwendung `famquest` in Container Station sein;
private Sicherungen und der dokumentierte Rückweg bleiben außerhalb dieser
Anwendung erhalten. Eine automatische Löschliste aus den sichtbaren Namen wird
nicht erstellt. Nach Eingang des Inventars werden die konkreten Löschkandidaten
und ihre belegten Datenabhängigkeiten hier dokumentiert.

## Ausführung in dieser Cloud-Sitzung

Hier stehen GitHub und der Cloud-Docker-Daemon zur Verfügung, aber kein QNAP-
Remotezugang und keine privaten Betriebsartefakte aus `FamQuest-Dauerbetrieb`.
Es wurde auf dem NAS nichts gestoppt, entfernt oder umgestellt. Die Bestandsaufnahme
und anschließende zentrale Betriebsprobe benötigen Zugriff vom Betreiberrechner
oder einen eingerichteten Remotezugang; keine Zugangswerte im Chat übermitteln.


## Auswertung des Betreiber-Inventars vom 9. November 2026

Der übermittelte Bericht enthält 21 FamQuest-Projekte mit 48 Containern.
15 Projekte enthalten ausschließlich gestoppte Container. Dieser Befund ist
kein Nachweis, dass ihre Volumes oder Projekt-Netzwerke entbehrlich sind.
Der private Rohbericht wurde nicht ins Repository übernommen.

### Produktive Abhängigkeiten erhalten

Die vier Container von `famquest-live` laufen. Zusätzlich läuft
`famquest-cloudflared-1` im alten Projekt `famquest`. Das Live-Gateway ist
auch an `famquest_default` angeschlossen und hat dort den Alias
`famquest-live-gateway`. Eine tatsächliche Tunnel-Zielkonfiguration wurde nicht
mitgeliefert; die Übergabe beschreibt den Produktionsweg über Cloudflare zum
Live-Gateway. Daher bleiben der Tunnel und dieses Netzwerk zunächst erhalten.
Das alte Projekt `famquest` darf nicht als Ganzes gelöscht werden.

Folgende Volumes werden tatsächlich von laufenden Live-Containern verwendet:

| Volume | Verwendung |
| --- | --- |
| `famquest-release-v2-db` | Live-PostgreSQL-Daten |
| `famquest-release-v2-runtime-uploads` | Live-Uploads |
| `famquest-live-config-v1` | Live-App- und Gateway-Konfiguration |

Sie bleiben trotz historischer Namen bestehen. Insbesondere referenziert der
gestoppte Datenbankcontainer von `famquest-release-verify-v2` dasselbe Volume
wie die laufende Live-Datenbank. Diesen alten DB-Container nicht starten und
beim Entfernen keine Volumes löschen. Die Projekte `famquest-release-runtime-v2`,
`famquest-release-runtime-prepare`, `famquest-live-manual-backup` und
`famquest-live-config-prepare` referenzieren ebenfalls Live-Volumes.

### Noch aktive Alt-/Testsysteme

Neben `famquest-live` laufen Teile von:

- `famquest`: Tunnel und ursprüngliche Datenbank.
- `famquest-central-stage`: eigene Test-App, Gateway und Datenbank.
- `famquest-current-restore`: Restore-Datenbank.
- `famquest-migrated-runtime`: Migrations-App und Gateway, verbunden mit dem
  Restore-Netzwerk.
- `famquest-funktionstest`: eigene Test-App und Datenbank.

Ihre aktuellen externen Zugriffe, Testdaten, Sicherungs- und Zeitplanreferenzen
sind aus dem Containerinventar allein nicht vollständig ersichtlich.
`famquest-central-stage` vorerst für die ausstehende isolierte zentrale
Update-Abnahme erhalten. Andere NAS-Anwendungen sind außerhalb des Auftrags.

### Konkrete Reihenfolge

1. Den bestehenden Backup-Zeitplaner und die private Live-/Tunnel-Konfiguration
   lesend prüfen. Insbesondere klären, ob der tägliche Job Container der
   Anwendung `famquest-live-manual-backup` wiederverwendet oder neu erzeugt.
2. Zentralen Updatekandidaten isoliert abnehmen, danach produktiven Wechsel
   durch den Betreiber und Live-/MCP-Prüfung abschließen.
3. Cloudflare-Tunnel mit der bestehenden Identität und den vorhandenen Routen
   in `famquest-live` übernehmen. Den bisherigen Alias/Zielpfad zunächst erhalten
   oder die Route ausdrücklich anpassen. Keinen konkurrierenden Tunnelstart
   und keine ungeprüfte Routenänderung mit der Bereinigung verbinden.
4. Nach erfolgreicher Tunnelübernahme die alten Testsysteme gezielt stoppen,
   Livebetrieb prüfen und anschließend nur bestätigte Container/Anwendungen
   entfernen. Volumes, Bind-Mount-Verzeichnisse, Sicherungen und bislang
   benötigte Netzwerke beibehalten.
5. Erst zum Schluss unabhängige ungenutzte Ablagen prüfen und bereinigen.

Der Bericht wurde ausgewertet; es wurde weiterhin nichts auf dem QNAP geändert.
Die nächsten Voraussetzungen sind die private Betriebs-/Backup-Zuordnung und
der nach wie vor fehlende QNAP-Remotezugang dieser Cloud-Sitzung.


## Vorbereitete Zusammenführung unter dem Namen `famquest`

Nach Eingang beider Compose-Konfigurationen liegt die konkrete Vorlage in
`docker-compose.qnap-consolidated.yml`. Sie verwendet die bestehenden Live-Images
(einschließlich OAuth-/MCP-Startkorrekturen), die drei externen Live-Volumes,
die bisherigen Dienstnamen `live-db`, `live-app`, `live-gateway`, `live-mcp`
und zusätzlich `cloudflared`. Sternchens neues Image wird in diesem Schritt
noch nicht eingesetzt. Die Umbenennung und das App-Update bleiben getrennt.

Der Tunnel bleibt im externen Netzwerk `famquest_default`; der Gateway-Alias
`famquest-live-gateway` bleibt erhalten. Die bisherigen vollständigen Live-DNS-
Namen werden auf den neuen internen Netzwerken zusätzlich als Aliasse erhalten,
damit private Runtime-/Nginx-Dateien diese weiterhin auflösen können.
Die bestehende Tunnelidentität wird über die vorhandene `.env` eingebunden.
Weder diese Datei noch das Runtime-Konfigurationsvolume gehören in Git.

Erhalten bleiben müssen auch diese bestehenden Dateien und Ordner:

- `/share/Container/famquest-central-stage/postgres.env`: weiter als `env_file`
  der Live-Datenbank verwendet; ein Löschen des alten Stage-Ordners wäre deshalb
  trotz später entbehrlicher Stage-Container falsch.
- `/share/Container/famquest/.env`: enthält die bestehende Tunnelkonfiguration.
- Live-Konfigurationsvolume, Live-Uploads und vollständige Backupverzeichnisse.

### Noch vor der Umstellung klären

Der tägliche Sicherungsjob wurde noch nicht übermittelt. Er kann auf
`famquest-live-live-db-1`, andere Containernamen, `famquest-live_data` oder die
alte Compose-Datei verweisen. Nach dem Projektwechsel heißen die Container zum
Beispiel `famquest-live-db-1`; das interne Datennetz heißt `famquest_data`.
DNS-Aliasse reparieren keine Docker-CLI-Namensreferenzen oder Netzwerkzuordnungen.
Daher den bestehenden Job zuerst prüfen, seine Anpassung vorbereiten und vor
Abschluss der Umstellung einen vollständigen Sicherungslauf nachweisen.

### Geplanter Ablauf durch den Betreiber, noch nicht ausführen

1. Bestehende Compose-Konfigurationen privat exportieren, aktuellen vollständigen
   Sicherungslauf bestätigen und Backupjob-Anpassung vorbereiten. Die Vorlage
   wurde lokal mit Compose geprüft; NAS-Dateien und geheimnisabhängiger Start
   wurden damit nicht geprüft.
2. Wartungsfenster: alte Anwendung `famquest` stoppen (einschließlich Tunnel und
   alter DB); anschließend `famquest-live` vollständig und geordnet stoppen.
   Neue und alte Live-Datenbank dürfen nie gleichzeitig auf dasselbe Volume
   zugreifen. Die vier alten Live-Container müssen tatsächlich gestoppt sein.
3. In Container Station die vorhandene Anwendung `famquest` bearbeiten und ihre
   YAML durch `docker-compose.qnap-consolidated.yml` ersetzen. Keine weitere
   Anwendung neben dem Livebetrieb starten und keine Daten/Volumes löschen.
   Die bisherigen Legacy-Dienste `db`, `app`, `mcp` sind in der neuen Vorlage
   nicht enthalten; falls Container Station sie als Altcontainer stehen lässt,
   bleiben sie gestoppt, bis sie separat entfernt werden. Ein fehlgeschlagenes
   Anlegen der neuen Dienste ist kein Grund, neue leere Volumes zu erzeugen.
4. Fünf neue Dienste prüfen: DB und App gesund, Gateway/MCP/Tunnel laufend;
   öffentliche Anmeldung, alle vorhandenen Familien und Uploads, Aufgaben sowie
   OAuth/MCP prüfen. Den angepassten täglichen Backupjob vollständig ausführen.
5. Erst nach erfolgreicher Prüfung alte Anwendungen gezielt entfernen, ohne
   Datenvolumes, Bind-Mount-Verzeichnisse oder das externe Tunnelnetz zu löschen.
   Alte Restore- und Stage-Systeme erst nach ihrer gesonderten Zuordnung abbauen.

Rückweg vor dem nächsten App-Update: alle fünf neuen Dienste von `famquest`
geordnet stoppen; alte `famquest-live`-Konfiguration mit denselben externen
Volumes wieder starten, danach nur den bisherigen Tunnel aus der gesicherten
alten `famquest`-Konfiguration starten (alte App/MCP/DB dabei nicht mitstarten).
Auch beim Rückweg darf es nur einen PostgreSQL-Prozess auf dem Live-Volume und
nur den beabsichtigten Tunnelbetrieb geben. Die alten Container/Konfigurationen
bleiben bis zum Abschluss der Prüfungen erhalten.

Die Vorlage ist ein geprüfter Konfigurationsentwurf, kein Nachweis einer
bereits erfolgten NAS-Umstellung. Die produktive Ausführung bleibt beim Betreiber.
