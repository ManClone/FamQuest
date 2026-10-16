# FamQuest – Zielbild und Umsetzungsregeln

Stand: 13.10.2026. Diese Produktentscheidungen gelten für die Weiterentwicklung des privaten Forks auf `develop`. Die bestehende allgemeine Spezifikation beschreibt teilweise noch frühere Dashboard-Funktionen; bei Konflikten gelten für diesen Fork die folgenden Entscheidungen.

## Produktfokus

FamQuest ist eine schlanke, selbst gehostete Familien-App für Kinder und Eltern. Kernfunktionen:

1. **Quests/Aufgaben**: kindgerecht anlegen, zuweisen, erledigen und bei Bedarf von Eltern bestätigen.
2. **Punkte und Belohnungen**: spielerischer Fortschritt; Punkte sind nicht automatisch Euro.
3. **Festes Taschengeld**: ein unabhängiger, bedingungsloser Anspruch.
4. **Bonus-Euros**: zusätzliche, ausdrücklich dafür vorgesehene Quest-Belohnungen.
5. **Optional Bank-/Zahlungsübersicht**: Guthaben, Auszahlungen und Abgleich nachvollziehbar dokumentieren.

Nicht wieder einbauen: Kalenderansicht, Kalenderintegration (auch nicht über Home Assistant), Essensplanung, Einkaufsliste, Wetterverwaltung oder Terminsymbole. Die Oberfläche soll übersichtlich bleiben.

## Verbindliche Geldregeln

- Taschengeld ist **nicht an Quests, Punkte, Verhalten oder Elternfreigaben geknüpft**.
- Taschengeld darf **niemals durch Sanktionen, Punktabzüge oder Bonusstornierungen gekürzt werden**.
- Quest-Bonus ist ein **separater Geldbereich**. Nur dieser darf nach transparenten Regeln korrigiert oder sanktioniert werden.
- Punktestand, Taschengeldanspruch, Bonusanspruch und tatsächlich ausgezahltes Geld sind getrennte Größen.
- Geldbuchungen sind nachvollziehbar: Betrag, Währung, Zeitpunkt, Typ, Begründung und ggf. Bezug zu einer Quest oder Auszahlung.
- Eine Korrektur sollte als neue Gegenbuchung statt als stilles Überschreiben historischer Geldbewegungen erfolgen.
- Keine automatische Auszahlung oder Überweisung ohne gesonderte Freigabe und passende Anbindung.

## Umsetzung in Etappen

### 1. Bestandsaufnahme und Datenmodell

- Bestehende Modelle, API-Routen, Migrationen, Elternfreigaben und UI für Aufgaben, Punkte und Belohnungen erfassen.
- Vorhandene Euro-/Taschengeldfunktionen identifizieren; keine zweite parallele Geldlogik anlegen.
- Separate Buchungsarten für Taschengeld, Quest-Bonus, Bonuskorrektur und Auszahlung definieren.
- Doppelte Gutschriften bei wiederholten API-Aufrufen und Bestätigungen verhindern.

### 2. Geschäftslogik und Tests

- Fälliges Taschengeld unabhängig von Quest-Ergebnissen gutschreiben.
- Bonus-Euros nur für explizit berechtigte Quests vergeben, ggf. nach Elternfreigabe.
- Bonusstorno darf ausschließlich Bonusbuchungen betreffen.
- Tests für Unveränderlichkeit des Taschengeldes, Wiederholungsversuche, negative Salden, Elternberechtigung und Zahlungsabgleich hinzufügen.

### 3. Schlanke Oberfläche

- Kind: verfügbare Quests, Fortschritt, Punkte, erreichbare Belohnungen.
- Eltern: Quest-Verwaltung, Bonusregeln, Taschengeld und ggf. Zahlungen.
- Geld klar beschriften: „Taschengeld“, „Bonus“ und „Ausgezahlt“ statt eines unklaren Gesamtsaldos.
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


## Technische Bestandsaufnahme (13.10.2026)

Untersucht auf `develop`:

| Bereich | Bestehende Implementierung | Konsequenz |
| --- | --- | --- |
| Euro-Ledger | `backend/app/models.py: MoneyTransaction` mit `member_id`, `amount_cents`, `kind`, `reason`, `completion_id`, `created_at` | Wiederverwenden und gezielt erweitern, kein zweites Ledger |
| Geldbuchung | `backend/app/money.py: book_money`, `money_balance` | Derzeit ein gemeinsamer Saldo über alle Buchungsarten; Taschengeld und Bonus getrennt ausweisen |
| Quest-Bonus | `Task.money_cents`, `TaskCompletion.money_cents`, `TaskIn.money_cents` | Bonusbetrag ist schon als Centwert vorgesehen und bei Erledigung gespeichert |
| Quest-Erledigung | `backend/app/api/today.py` bucht nach unmittelbarer Genehmigung `task_completed` und bei Rücknahme `task_undone` | Gegenbuchungen existieren bereits; auf Idempotenz und Genehmigungswege testen |
| Punkte | `PointTransaction`, `backend/app/points.py`, `backend/app/api/points.py` | Eigenständiges Punktesystem beibehalten |
| Belohnungen | `Reward`, `RewardRedemption`, `backend/app/api/rewards.py` | Bisher punktebasierte Belohnungen nicht mit Euro-Auszahlungen vermischen |
| Taschengeld | In den bisher untersuchten Modellen/API-Routen keine eigenständige Taschengeldverwaltung festgestellt | Vor Implementierung verbleibende API-Routen, Migrationen und Tests prüfen |

### Vor dem ersten Geld-Feature-Commit absichern

1. Sämtliche Genehmigungs-/Ablehnungswege nach `book_money` und `money_cents` durchsuchen; Bonus bei späterer Elternfreigabe genau einmal buchen.
2. Sicherstellen, dass mehrfaches Erledigen, Bestätigen oder Rückgängigmachen keine Doppelbuchung erzeugt.
3. Geldbuchungsarten streng unterscheiden; `money_balance` nicht als vermeintliches Taschengeld anzeigen.
4. Taschengeld separat fällig stellen und mit stabiler Periodenkennung idempotent buchen.
5. Für Auszahlungen und Korrekturen Berechtigungen, negative Salden und Audit-Trail testen.
6. Bestehende Migrationen auf `money_transactions` prüfen, bevor Constraints oder Spalten geändert werden.

**Wichtig:** Diese Bestandsaufnahme ist noch kein Nachweis, dass sämtliche Genehmigungswege und Geldbuchungen vollständig korrekt sind. Sie begründet die nächste gezielte Prüfung, nicht die Freigabe für ein Deployment.
