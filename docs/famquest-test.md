# Dauerhafte Testanwendung famquest-test

`main` ist der freigegebene Quellstand, `codex/experiments` der Entwicklungszweig.
Docker verwendet gebaute Images, keine Git-Branches. Die Testanwendung bekommt
neue Images ausdrücklich; die Live-Anwendung bleibt unabhängig davon bestehen.

## Vereinbarter Standardablauf

Dauerhaft bestehen nur `famquest-live` und `famquest-test`. Entwicklung und
Experimente werden im Entwicklungsbranch vorbereitet, in ein Docker-Image
gebaut und in derselben Testanwendung geprüft. `famquest-test` ist jeweils auf
eine gewählte Version gepinnt; normale Updates bestehen aus Pull und Wechsel
auf diese Version, ohne neue Anwendungen oder Testdatenbanken anzulegen.

Nach Abnahme durch den Betreiber: geprüften Stand nach `main` übernehmen,
CI und Veröffentlichung abwarten, dann `latest` gezielt in der bestehenden
Live-Anwendung aktualisieren. Branch-Pushes verändern keine laufenden NAS-
Anwendungen automatisch. Live bleibt auf `latest`, Test auf einem festen Tag
oder Digest. Diese Vereinbarung steht auch in der rootweiten `AGENTS.md`.

## Images

- Produktion: Die vorhandene main-Pipeline veröffentlicht nach erfolgreicher
  Sicherheitsprüfung `ghcr.io/manclone/famquest:latest` und `:sha-<voller Commit>`.
- Experimente: Die Prüfungen auf `codex/experiments` veröffentlichen nach Erfolg
  `ghcr.io/manclone/famquest:test-<voller Commit>` und entsprechend das MCP-Image.
- Auf dem NAS bevorzugt die Commit-Referenz einsetzen. `latest` bezeichnet nur
  die zuletzt erfolgreich veröffentlichte main-Version, nicht zwingend den
  momentanen Git-Commit. Ein fehlgeschlagener Check aktualisiert kein Image.

Am 10. November 2026 wurde `main` auf `a14c99a` korrigiert (nur Formatierung
einer OAuth-Testassertion). Beide GitHub-Prüfungen bestanden; die Registry-
Veröffentlichung wurde bestätigt. `latest` und `sha-a14c99aa04b8f4c4aa997edb2fca26156c04dc2a`
haben identische Manifeste. Die finale Live-Vorlage verwendet jetzt `latest`
mit `pull_policy: always`. Der tatsächliche NAS-Wechsel wird vom Betreiber
ausgeführt; die Cloud hat den laufenden Container nicht verändert. Ein Push führt kein NAS-Update aus.

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

1. Erfolgreiches Testimage aus GitHub Actions auswählen und auf dem NAS abrufen.
2. Testdaten/Uploads vor relevanten Änderungen sichern.
3. In der Test-YAML nur `x-app-image` durch den neuen `test-<Commit>` ersetzen.
   Dieser eine YAML-Anker wird von App und Initialisierungsdienst verwendet.
   Bei Änderungen am MCP-Dienst zusätzlich `x-mcp-image` aktualisieren.
4. Bestehende Anwendung **famquest-test** aktualisieren. Volumes behalten,
   keine neue Anwendung und keine neuen Testkonten erzeugen.
5. Anmeldung beider Familien, Rechte, Aufgaben, Drachenkarte und gegebenenfalls
   MCP prüfen. Erst danach den Entwicklungsstand nach `main` übernehmen.

Bei reinen App-Änderungen genügt damit normalerweise der Imagewechsel.
Schemaänderungen benötigen eine ausdrücklich geplante Testmigration; der
Start prüft Schemastände und migriert vorhandene Daten nicht heimlich.
Insbesondere der Erstinitialisierer ist kein allgemeines Updatewerkzeug.
`app.staging_smoke` setzt die unveränderten generierten Testdaten voraus und
ist für automatisierte Erstabnahmen geeignet; spätere manuelle Testdaten können
zusätzliche gezielte Prüfungen erfordern.

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
