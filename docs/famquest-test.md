# Dauerhafte Testanwendung famquest-test

`main` ist der freigegebene Quellstand, `codex/experiments` der Entwicklungszweig.
Docker verwendet gebaute Images, keine Git-Branches. Die Testanwendung bekommt
neue Images durch manuelles Aktualisieren; die Live-Anwendung bleibt unabhängig davon bestehen.

## Vereinbarter Standardablauf

Dauerhaft bestehen nur `famquest-live` und `famquest-test`. Live verwendet
`ghcr.io/manclone/famquest:latest`, Test `ghcr.io/manclone/famquest:test` und
`ghcr.io/manclone/famquest-mcp:test`. Die FamQuest-Dienste verwenden
`pull_policy: always`. Der Betreiber muss für normale Updates nur die bestehende
Anwendung in Container Station neu erstellen/aktualisieren. Docker zieht die
aktuell veröffentlichten Images; kein manuelles Ändern der Imageversion nötig.

Die Test-Pinnung auf eine unveränderliche Version wurde damit auf ausdrücklichen
Wunsch durch den festen Aktualisierungskanal `test` ersetzt. Feste Commit-Tags
bleiben zusätzlich für Rücksprünge und nachvollziehbare Abnahmen verfügbar.
Ein neuer Branch-Push allein ändert keine laufenden Container.

Nach Testabnahme durch den Betreiber: geprüften Stand nach `main` übernehmen,
CI und Veröffentlichung abwarten, dann die bestehende Live-Anwendung
aktualisieren. Diese Vereinbarung steht auch in der rootweiten `AGENTS.md`.

## Images

- main veröffentlicht nach erfolgreichen Prüfungen `:latest` und `:sha-<Commit>`.
- `codex/experiments` veröffentlicht nach erfolgreichen Prüfungen für App und
  MCP jeweils `:test` und `:test-<Commit>`. Dieser Workflow verändert `latest` nicht.
- Bei fehlgeschlagenen Prüfungen bleibt der jeweilige Kanal auf dem zuletzt
  erfolgreich veröffentlichten Stand.
- Am 10. November 2026 wurde `latest` für main `a14c99a` geprüft. Der Betreiber
  hat die Live-Anwendung danach auf die Registry-Referenz umgestellt.

## Erstmalige Vorbereitung

Das Paket wird neu generiert, ohne produktive Dateien oder Daten zu übernehmen.
Es enthält neue private Testzugänge für zwei getrennte Testfamilien. Bestehende
Live-Volumes und die Dateien unter `famquest-central-stage` werden nicht benutzt.
Der Generator verweigert vorhandene Ausgabeordner, HTTP-Ursprünge und unpassende
Image-Referenzen.

Beispiel auf einem Rechner mit Python 3, im Repository:

```sh
python3 scripts/prepare-famquest-test.py \
  --output /NEUER/PRIVATER/PFAD/famquest-test \
  --target-dir /share/Container/famquest-test \
  --origin https://famtest.websiteclone.de \
  --listen-host 192.168.1.2
```

Alternativ denselben Generator im geprüften App-Image über einen neu angelegten
privaten Bind-Mount ausführen. Der Generator benötigt beide Python-Skripte unter
`scripts/`, die Staging-/Test-Compose-Templates und die referenzierten Dokumente
aus diesem Repository. Alle erzeugten Dateien gemeinsam übertragen; private
Zugangswerte nicht in Git speichern.

Auf dem QNAP das Paket unter `/share/Container/famquest-test` ablegen. Container
Station: neue Anwendung **famquest-test**, YAML aus dem erzeugten `compose.yml`.
DB und Uploads erhalten ausschließlich `famquest-test-db-v1` beziehungsweise
`famquest-test-uploads-v1`. Der Initialisierungsdienst endet nach erfolgreichem
Erststart; vier normale Dienste (DB, App, Gateway, MCP) laufen dauerhaft.

Port 11902 ist vom alten Testaufbau bekannt. Die explizite Bindung an
192.168.1.2 erhält diesen LAN-Zugriff für die vorhandene Test-Route. Die Route
für `famtest.websiteclone.de` muss weiterhin diesen Gateway erreichen; vor dem
Start Portbelegung prüfen. Die Live-Route nicht ändern. Lokal ist standardmäßig
nur 127.0.0.1 gebunden. Browserzugriff über HTTPS, weil die zentrale Anmeldung
Secure-Cookies verwendet. Die Testfamilien-Zugänge stehen nur lokal in
`TESTZUGAENGE-PRIVAT.txt`.

## Spätere Updates

1. Entwicklung nach `codex/experiments` pushen und erfolgreiche Prüfungen sowie
   Veröffentlichung der beiden Test-Images abwarten.
2. Bei relevanten Änderungen Testdaten/Uploads sichern.
3. Bestehende Anwendung `famquest-test` in Container Station neu erstellen bzw.
   aktualisieren, ohne ihre Datenvolumes zu löschen. Die beiden `test`-Tags und
   `pull_policy: always` bleiben in der YAML unverändert.
4. Anmeldung, Familienrechte, Aufgaben, Drachenkarte und gegebenenfalls MCP prüfen.
5. Nach Abnahme geprüften Stand nach `main` übernehmen. Veröffentlichung von
   `latest` abwarten und anschließend `famquest-live` gezielt aktualisieren.

Schemaänderungen benötigen zusätzlich eine ausdrücklich geplante Testmigration.
Der Start prüft Schemastände und migriert vorhandene Daten nicht heimlich.
Der Erstinitialisierer ist kein allgemeines Updatewerkzeug. Für Rücksprünge kann
bewusst ein festes `test-<Commit>`-Image gewählt werden; das ist eine Ausnahme
vom normalen Aktualisierungskanal.

## Isolationsregeln

Keine Live-DB, Live-Uploads oder Live-Runtime-Dateien in die Testanwendung mounten.
Keine Produktionskonten kopieren. Gleiche interne Dienstnamen sind zulässig,
weil eigene Netzwerke und ein separater PostgreSQL-Server verwendet werden.
Ein vorhandenes Testvolume wird nicht automatisch ersetzt oder gelöscht.

## Bisherige Validierung

In der Cloud wurden elf Skripttests erfolgreich ausgeführt. Ein vollständig
neuer lokaler Testcluster wurde tatsächlich initialisiert und über das Gateway
geprüft. Die vorhandene Staging-Smokeprüfung bestand zentrale Eltern-/Kinder-
Logins, Datentrennung, PostgreSQL-Rollen, Sitzungswiderruf und Betreiberaktionen.
Zusätzlich bestand ein echter HTTPS-Test mit einer ausschließlich lokalen
Test-CA: OAuth-Registrierung, Anmeldung, Zustimmung, PKCE-Codeaustausch,
MCP-Initialisierung und angemeldetes `tools/list`. Es wurden keine produktiven
Konten oder Daten verwendet. Die Vorbereitung wurde noch nicht auf dem QNAP
installiert; dessen HTTPS-/Tunnelroute ist nach Erstellung separat zu prüfen.
