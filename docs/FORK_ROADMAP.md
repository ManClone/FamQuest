# FamQuest – Zielbild und Umsetzungsregeln

Stand: 13.10.2026. Diese Produktentscheidungen gelten für die Weiterentwicklung des privaten Forks auf `develop`. Die bestehende allgemeine Spezifikation beschreibt teilweise noch frühere Dashboard-Funktionen; bei Konflikten gelten für diesen Fork die folgenden Entscheidungen.

## Produktfokus

FamQuest ist eine schlanke, selbst gehostete Familien-App für Kinder und Eltern. Kernfunktionen:

1. **Quests/Aufgaben**: kindgerecht anlegen, zuweisen, erledigen und bei Bedarf von Eltern bestätigen.
2. **Punkte und Belohnungen**: spielerischer Fortschritt; Punkte sind nicht automatisch Euro.
3. **Festes Grundtaschengeld**: ein unabhängiger, bedingungsloser Anspruch.
4. **Bonus-Euros**: zusätzliche, ausdrücklich dafür vorgesehene Quest-Belohnungen.
5. **Optional Bank-/Zahlungsübersicht**: Guthaben, Auszahlungen und Abgleich nachvollziehbar dokumentieren.

Nicht wieder einbauen: Kalenderansicht, Kalenderintegration (auch nicht über Home Assistant), Essensplanung, Einkaufsliste, Wetterverwaltung oder Terminsymbole. Die Oberfläche soll übersichtlich bleiben.

## Verbindliche Geldregeln

- Grundtaschengeld ist **nicht an Quests, Punkte, Verhalten oder Elternfreigaben geknüpft**.
- Grundtaschengeld darf **niemals durch Sanktionen, Punktabzüge oder Bonusstornierungen gekürzt werden**.
- Quest-Bonus ist ein **separater Geldbereich**. Nur dieser darf nach transparenten Regeln korrigiert oder sanktioniert werden.
- Punktestand, Grundtaschengeldanspruch, Bonusanspruch und tatsächlich ausgezahltes Geld sind getrennte Größen.
- Geldbuchungen sind nachvollziehbar: Betrag, Währung, Zeitpunkt, Typ, Begründung und ggf. Bezug zu einer Quest oder Auszahlung.
- Eine Korrektur sollte als neue Gegenbuchung statt als stilles Überschreiben historischer Geldbewegungen erfolgen.
- Keine automatische Auszahlung oder Überweisung ohne gesonderte Freigabe und passende Anbindung.

## Umsetzung in Etappen

### 1. Bestandsaufnahme und Datenmodell

- Bestehende Modelle, API-Routen, Migrationen, Elternfreigaben und UI für Aufgaben, Punkte und Belohnungen erfassen.
- Vorhandene Euro-/Taschengeldfunktionen identifizieren; keine zweite parallele Geldlogik anlegen.
- Separate Buchungsarten für Grundtaschengeld, Quest-Bonus, Bonuskorrektur und Auszahlung definieren.
- Doppelte Gutschriften bei wiederholten API-Aufrufen und Bestätigungen verhindern.

### 2. Geschäftslogik und Tests

- Fälliges Grundtaschengeld unabhängig von Quest-Ergebnissen gutschreiben.
- Bonus-Euros nur für explizit berechtigte Quests vergeben, ggf. nach Elternfreigabe.
- Bonusstorno darf ausschließlich Bonusbuchungen betreffen.
- Tests für Unveränderlichkeit des Grundtaschengeldes, Wiederholungsversuche, negative Salden, Elternberechtigung und Zahlungsabgleich hinzufügen.

### 3. Schlanke Oberfläche

- Kind: verfügbare Quests, Fortschritt, Punkte, erreichbare Belohnungen.
- Eltern: Quest-Verwaltung, Bonusregeln, Grundtaschengeld und ggf. Zahlungen.
- Geld klar beschriften: „Grundtaschengeld“, „Bonus“ und „Ausgezahlt“ statt eines unklaren Gesamtsaldos.
- Keine zusätzliche Kalenderseite oder funktionsfremde Navigation.

## Entwicklungs- und Freigabeprozess

- Änderungen ausschließlich auf `develop`, niemals direkt auf `main`.
- Kein QNAP-Deployment ohne ausdrückliche Freigabe.
- Kleine, überprüfbare Commits; bestehende Funktionalität nicht für grüne Tests entfernen.
- Frontend-/Backend-Tests und Build in GitHub Actions müssen erfolgreich sein.
- Vor einer größeren Datenmigration oder Änderung der Geldregeln: konkrete Auswirkungen und offene Entscheidungen abstimmen.

## Vor Implementierung noch zu entscheiden

- Betrag und Intervall des festen Taschengelds pro Kind.
- Ob und wann Bonus-Euros nach Elternfreigabe verfügbar werden.
- Wie Bankkontostände erfasst werden: manuell oder über eine gesonderte Anbindung.
- Welche Bonuskorrekturen Eltern durchführen dürfen und wie sie dem Kind angezeigt werden.

Diese offenen Punkte dürfen nicht durch willkürliche Standardbeträge oder automatische Zahlungen vorweggenommen werden.
