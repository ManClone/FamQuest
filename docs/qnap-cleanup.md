# QNAP nach der Mehrfamilien-Migration bereinigen

Ziel ist eine Container-Station-Anwendung `famquest-live` mit App, PostgreSQL,
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

Ergebnis soll nur noch die Anwendung `famquest-live` in Container Station sein;
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
