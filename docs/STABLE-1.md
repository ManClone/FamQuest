# Familien-Stable 1: Issues #16–#23

Dieser Release umfasst die Korrekturen #16–#22 und das Level-Fundament #23.
Die Ja/Nein-Abfrage aus PR #15 ist enthalten: Abbrechen macht keine Erledigung
rückgängig. Zugehöriges Lob bleibt unabhängig bestehen.

## Verhalten

- Lob & Kritik: Lob gezielt mit Grund widerrufen; Strafabzüge gezielt zurücknehmen.
  Alle Aktionen sind an das Elternkonto gebunden und behalten die Historie.
- Manuelle positive und negative Sternbuchungen lassen sich über MCP mit ihrer ID
  stornieren. Eine gemeinsame eindeutige Verknüpfung schützt auch bei parallelen
  Aufrufen über die Strafpunkt- und die allgemeine Storno-API vor Doppelerstattungen.
  Aufgaben, Belohnungsbuchungen und bereits verknüpfte Ausgleichsbuchungen dürfen
  nicht als manuelle Originalbuchung nochmals storniert werden.
- Bei späteren betragsgleichen manuellen Gutschriften verlangt die Rücknahme eine
  Prüfung. Eltern können die vorhandene Ausgleichsbuchung ausdrücklich verknüpfen
  (`existing_compensation_id`): dabei wird nichts zusätzlich gebucht. Sind die
  Gutschriften unabhängig, muss das ausdrücklich mit `compensation_reviewed=true`
  bestätigt werden. Gleicher Betrag allein ist kein Beweis für einen Ausgleich.
- Belohnungen und Einlösungen aller Mitglieder sind einsehbar. Einlösen darf nur
  das mit dem Profil verknüpfte Login, auch bei direkten API-Aufrufen. Elternverwaltung
  und elterliche Stornierung einer Einlösung bleiben in den Einstellungen verfügbar.
  Fremde Aufgaben, persönliche Punktehistorien und Fortschrittsdaten bleiben geschützt.
  Ein Profil ohne Login kann angesehen werden; zum Einlösen benötigt es ein Login.
- Bestätigte Haushaltserledigungen erscheinen in einer weißen Karte. Die Liste
  scrollt innerhalb ihrer begrenzten Höhe; Erklärung und Überschrift bleiben sichtbar.

## Level

| Ziellevel | Kumulierte Aufgaben-XP | Gültiges Lob am Meilenstein |
|---|---:|---:|
| 2 | 50 | – |
| 3 | 110 | – |
| 4 | 175 | 1 |
| 5 | 245 | – |
| 6 | 320 | – |
| 7 | 400 | 2 |
| 8 | 485 | – |
| 9 | 575 | – |
| 10 | 670 | 3 |

Lob wird kumuliert gezählt, nicht verbraucht. Nur Level 4/7/10 prüfen eine
Lob-Schwelle. Ein bereits freigeschalteter Meilenstein bleibt erhalten, auch wenn
Lob später zurückgenommen wird; normale Folgelevel erhalten keine neue Lob-Hürde.
XP sammeln weiter, wenn ein Meilenstein auf Lob wartet. Späteres Lob schaltet
bereits erreichte XP-Schwellen in derselben Transaktion nachträglich frei.

Die Anforderungen steigen nach Level 10 mit weiteren Schritten von jeweils 5 XP;
weitere Lob-Meilensteine sind in diesem Release nicht definiert. Bestehende höhere
Level werden geschützt. Sterneausgaben, Kritik und manuelle Korrekturen verändern
Aufgaben-XP nicht. Aufgabenrücknahmen korrigieren Aufgaben-XP, nehmen aber kein
bereits freigeschaltetes Level weg. Freischaltungen werden auch ohne Öffnen der
Fortschrittsansicht gespeichert.

## Datenprüfung #22

`GET /api/maintenance/consistency` ist nur für Eltern freigegeben und auch per MCP
verfügbar. Alternativ im App-Container:

```sh
python -m app.cli consistency-report
```

Der CLI-Bericht verwendet eine konsistente, datenbankseitig schreibgeschützte
Transaktion. Er meldet verdächtige Buchungen mit IDs, mögliche Ausgleiche,
unplausible Storno-Verknüpfungen, aktive Testlobe, ungültige/leere Kinderzuordnungen
und lange überfällige Aufgaben. Unterschiedliche historische Aufgabenwerte und
Belohnungspreise sind Hinweise auf gespeicherte Momentaufnahmen, keine Fehler.
Ausgebbare Sterne und Aufgaben-XP dürfen voneinander abweichen.

Der Bericht ändert keine Daten. Jede spätere Bereinigung benötigt einen Abgleich
der Original- und Ausgleichs-IDs sowie eine ausdrückliche Entscheidung je Eintrag.
Private Bestandsberichte gehören nicht in GitHub. Keine automatische Bereinigung
oder feste IDs einer realen Familie in Migrationen.

## Deployment und Abnahme

1. Exakten Commit mit erfolgreichen Backend-, Frontend-, MCP- und Docker-Prüfungen wählen.
2. Datenbank, Uploads, bestehendes Image, Compose-Konfiguration und MCP-Zustand sichern.
3. App-Image ausdrücklich mit `--target runtime` bauen. App/MCP während der
   konsistenten Sicherung anhalten. Neue Migration: `i20261016stablelevels`.
4. Migration und `/api/health` prüfen; MCP neu starten, damit es das neue API-Schema lädt.
   Connector-Werkzeugliste bei Bedarf aktualisieren.
5. Eltern- und Kinderlogin, Mitgliederauswahl und fremde Einlöseversuche prüfen.
   Bestätigte Erledigungen mobil aufklappen; Rücknahme abbrechen und bestätigen.
   Storno/Lob-Rücknahme ausschließlich mit isolierten Testdaten prüfen.
6. Privaten Konsistenzbericht ausführen und offene Datenfragen einzeln besprechen.

Die Levelmigration ergänzt `highest_level` und schützt den höchsten aus der
bisherigen 100-XP-Kurve rekonstruierbaren Levelstand. Sie ändert keine Sternsalden,
Lobdatensätze, Erledigungen oder historischen Preise. Nach einer Migration ist
ein Rollback nur mit passendem Datenbankbackup und Image möglich.

Abzeichen, Drache und weitere Phasen aus #24 sowie das Geld-/Bankmodul #25 sind
nicht Bestandteil dieses Releases.
