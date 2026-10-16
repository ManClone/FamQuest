<p align="center"><img src="docs/logo.png" alt="FamQuest" width="300"></p>

# FamQuest — Aufgaben, Haushalt und Belohnungen für die Familie

[English](README.md) · **Deutsch**

FamQuest ist eine selbst gehostete Familien-App für Kinder und Eltern. Kinder erledigen
Aufgaben, sammeln Sterne, erhalten Lob-Herzen und schalten Level frei. Eltern verwalten
Aufgaben, bestätigen Erledigungen und behalten den Haushalt im Blick. Alle können die
Belohnungen der Familie ansehen; einlösen kann jede Person nur ihre eigenen.

Dies ist **ManClones Weiterentwicklung von [craebby/FamQuest](https://github.com/craebby/FamQuest)**.
Im Mittelpunkt stehen Aufgaben im Alltag, die Beteiligung am Haushalt und nachvollziehbare
Belohnungen — am Handy, Tablet und gemeinsamen Display. Das ursprüngliche Dashboard mit
Kalender, Wetter, Essensplanung und Einkauf ist nicht der Schwerpunkt der aktuellen Oberfläche.

## Aktueller Stand: Stable 1 Final

[Stabiler Quellstand](https://github.com/ManClone/FamQuest/tree/stable-1-final) ·
[Releaseumfang und Abnahme](docs/STABLE-1.md) ·
[Offene Issues](https://github.com/ManClone/FamQuest/issues)

Stable 1 Final enthält die Issues #16–#23 und die kompakte Belohnungsansicht:

- **Konten und Rollen:** getrennte Zugänge für Kinder und Eltern; Familienprofile können
  eigene Logins erhalten. Kinder sehen ihre eigenen Aufgaben und privaten Fortschrittsdaten.
- **Aufgaben und Routinen:** wiederkehrende Aufgaben, freiwillige Extras und bei Bedarf
  Bestätigung durch die Eltern.
- **Haushalt:** Putzplan mit Räumen, Abständen und einmaligen Aufgaben; freigegebene
  Aufgaben können Kinder übernehmen. Eltern bestätigen die Kindererledigungen.
- **Sterne und Belohnungen:** nachvollziehbare Punktebuchungen, Belohnungen für Kinder
  und Erwachsene, Einlösen nur im eigenen Profil und begründete Stornos ohne doppelte Erstattung.
- **Lob und Fortschritt:** Lob-Herzen, Aufgaben-XP und dauerhaft freigeschaltete Level.
  Ausgebbare Sterne und Aufgaben-XP sind getrennte Werte.
- **Kompakte Handyansicht:** zwei Belohnungskacheln pro Reihe; Sterne und bei Kindern
  Lob-Herzen stehen unter dem Namen direkt im Profilbutton.
- **Korrekturen mit Verlauf:** Rückfrage vor dem Rückgängigmachen einer Erledigung;
  zugehöriges Lob bleibt unabhängig. Ein nur lesender Konsistenzbericht hilft bei der Datenprüfung.
- **Optionaler MCP-Dienst:** authentifizierte Werkzeuge für unterstützte Familienabläufe,
  mit ausdrücklicher Elternentscheidung bei Kinderfreigaben. Siehe [Einrichtung und Grenzen](mcp/README.md).

Die Oberfläche ist auf Deutsch und Englisch verfügbar. Die Daten liegen in der eigenen
PostgreSQL-Datenbank und im eigenen Upload-Speicher. Eine Installation gehört einer Familie.

**Zurückgestellt:** Bankanbindung und Geldmodul (#25) sowie spätere Abenteuerfunktionen (#24)
gehören nicht zu diesem Stable-Release. Sterne sind keine Euros. Es gibt keine automatische Überweisung.

## Installation auf einem Docker-Host

Benötigt werden Git, Docker und das Compose-Plugin. Das Image baut Frontend und Backend;
Node.js und Python müssen auf dem Host nicht installiert sein.

```sh
git clone https://github.com/ManClone/FamQuest.git
cd FamQuest
git checkout stable-1-final
cp .env.example .env
```

In `.env` ein starkes, eigenes `POSTGRES_PASSWORD` setzen. Danach starten:

```sh
docker compose up -d --build
docker compose ps
```

`http://<host>:8080` öffnen; der Port lässt sich über `APP_PORT` ändern. Die Ersteinrichtung
abschließen und anschließend unter **Einstellungen → Familie** die Profile und optionalen
Logins verwalten. Berechtigungen sind kontobasiert; die ursprüngliche Anleitung mit gemeinsamer
Eltern-PIN beschreibt diesen Fork nicht. Datenbankmigrationen laufen beim Start automatisch.
Alle Konfigurationsvariablen stehen in [`.env.example`](.env.example).

Bei einer bestehenden NAS-Installation deren Konfiguration, Datenbank- und Upload-Pfade
beibehalten. Siehe [QNAP-Hinweise](docs/qnap-deployment.md). Änderungen auf GitHub installieren
sich nicht automatisch auf der NAS. Beim Image-Bau immer das Ziel `runtime` verwenden.

## Updates und Sicherungen

`main` enthält die veröffentlichten Änderungen; `develop` dient der Weiterentwicklung.
Der Tag `stable-1-final` markiert den geprüften stabilen Anwendungsstand.

Vor Updates Datenbank, Uploads, Umgebungs-/Compose-Konfiguration, bisheriges Image und bei
Verwendung den MCP-Zustand sichern. Private Sicherungen gehören nicht ins Git-Repository.
Das [Backup-Skript](scripts/backup.sh) passend zur eigenen Installation verwenden.
Nach dem Update Containerzustand und `/api/health` prüfen. Nach einer Migration benötigt
ein Rollback ein zusammenpassendes Datenbankbackup und Image.

Der Konsistenzbericht liest ausschließlich Daten und bereinigt keine Buchungen automatisch:

```sh
docker compose exec -T app python -m app.cli consistency-report
```

Den Bericht privat aufbewahren: Er kann Familiendaten und Buchungsdetails enthalten.

## Entwicklung und Dokumentation

Frontend mit React, TypeScript und Tailwind CSS; Backend mit FastAPI, SQLAlchemy und
PostgreSQL; Migrationen mit Alembic; Betrieb mit Docker. GitHub Actions prüft Frontend,
Backend, MCP-Dienst und Container-Builds.

- [Zielbild und Regeln dieses Forks](docs/FORK_ROADMAP.md)
- [Stable-Verhalten, Level und Abnahme](docs/STABLE-1.md)
- [Familienbetrieb und Konten](docs/LIVE-TEST.md)
- [Ursprüngliche Spezifikation](docs/SPEC.md)
- [Historische Anleitung des Ursprungsprojekts](docs/legacy/README.de.md), einschließlich
  der früheren Dashboard-Integrationen und technischer Details; sie ist keine aktuelle Produktbeschreibung.

## Herkunft und Lizenz

Grundlage ist FamQuest von **Craebby**, Copyright © 2026 Craebby, hier weiterentwickelt
von **ManClone**. Lizenz: [GNU AGPL-3.0-or-later](LICENSE). Herkunft und Lizenz bleiben
erhalten. Die eingebundenen [Fluent Emoji](https://github.com/microsoft/fluentui-emoji)
stammen von Microsoft und stehen unter der MIT-Lizenz.
