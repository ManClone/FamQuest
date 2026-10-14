# FamQuest – Aufgaben, Routinen und Wochenabrechnung (Entwurf)

Status: abgestimmtes Konzept; noch keine produktive Funktion. Umsetzung auf develop, nach Tests via PR nach main.

## Wochenabrechnung, XP und Konsequenzen (aktualisierte Entscheidung)
- Wochenzeitraum: Montag bis Sonntag in der Familienzeitzone. Nur der **verdiente Geldbonus in Euro** wird wöchentlich abgerechnet.
- Jede Konsequenz besitzt **zwei unabhängig konfigurierbare Abzüge**: Geldabzug in Cent vom laufenden Wochenbonus und XP-Abzug vom verfügbaren XP-Guthaben. Startvorlage „Nicht auf Anweisungen gehört“: **0,50 € und 5 XP**, ohne Pflichtnotiz. Werte sind einstellbar, keine automatische Umrechnung von XP in Euro.
- Geld-Auszahlung = **max(0, in dieser Woche verdienter Geldbonus in Cent minus Geldstrafen in Cent)**. Beispiel: 3 € verdient, 4 € Strafen → 0 € Auszahlung. Überschüssige Geldstrafen verfallen zum Wochenwechsel, keine Schulden und kein Übertrag.
- Das **bedingungslose Grundtaschengeld bleibt immer unverändert** und wird separat ausgezahlt.
- **Verfügbare XP** sind ein fortlaufendes, über Wochen ansparbares Guthaben für größere Belohnungen. XP-Strafen reduzieren dieses Guthaben; Belohnungskäufe ebenfalls. Guthaben nicht unter null reduzieren; wirksamen Abzug und eventuell nicht verrechneten Rest transparent ausweisen.
- **Level-/Erfahrungs-XP** sind separat kumuliert. Level bleiben bei Strafabzügen und Belohnungskäufen bestehen. Levelgrenzen werden gesondert festgelegt.
- Konsequenzen nur durch Eltern, mit konfigurierbaren Vorlagen, optionaler Notiz, Urheber, Datum, Zielkind und nachvollziehbarer Stornierung/Gegenbuchung.
- Wochenabschlüsse idempotent, historisch nachvollziehbar; nachträgliche Änderungen ausschließlich über protokollierte Korrekturen.
- **Wichtig für den Code:** Die bereits angelegte `weekly_consequences.py` und Preview-API rechnen derzeit noch mit generischen `bonus_points`; sie sind **nicht** die freigegebene Euro-Abrechnung. Vor produktiver Verwendung auf Cent-Beträge und getrennte XP-Buchungen umstellen, Tests anpassen. Nicht ausrollen.

## Aufgaben und Zeitpunkte
- Eine Aufgabendefinition kann mehrere Zeitfenster pro Tag enthalten: z. B. Zähne putzen morgens und abends; umziehen morgens und nach Sport.
- Jeder Termin ist separat abhakbar. Standard: geringe Routine-XP erst nach vollständiger Tagesroutine; alternative Vergabe je Termin konfigurierbar.
- Wochentage gelten **je Routine unabhängig**. Routinen dürfen denselben Wochentag und Tagesabschnitt teilen; ein Aufgabenabschluss darf nicht versehentlich zwei unterschiedliche Termine erfüllen.
- Wiederholbar jederzeit: mehrfach pro Tag erledigbar, optionales Tageslimit und Elternfreigabe (z. B. Katzenklo). Doppeltippen muss idempotent behandelt werden.
- Einmalige Aufgaben, wiederkehrende Routinen und jederzeitige Quests in einer Aufgabenansicht mit Filtern; keine doppelten Aufgabenanzeigen.
- Nur zugeordnete Aufgaben für Kinder sichtbar; Eltern sehen Familienübersicht. Sichtbarkeit und Schreibrechte **serverseitig** prüfen.
- Eltern können ausstehende Freigaben direkt von der Startseite bearbeiten.
- Eltern-XP und Kinder-XP werden pro Familienmitglied getrennt verbucht; Belohnungen können nach Rolle getrennt angeboten werden.

## Oberfläche und Konten
- Individuelle Logins für beide Eltern und Tim, jeweils mit Familienmitglied verknüpft; Elternfunktionen nicht nur per ausgeblendetem UI schützen.
- Fotos aus der Navigation entfernen; bestehende Bilddaten nicht löschen.
- Mobile Formulare: responsive Layout, keine Spalten mit Buchstaben untereinander.
- Vor Produktivübernahme Migration, Backend-Tests für Wochenabschluss und Berechtigungen, Frontend-Tests für mehrere Tageszeitpunkte und überlappende Wochentage.

## Migrations-/Implementierungsreihenfolge
1. Bestehende Authentifizierung, Geldbonus-/XP-/Level-Ledger, Routinen-API und Tests prüfen; Datenbankmigration planen.
2. Routinen-Wochentage entkoppeln und Mehrfach-Zeitpunkte modellieren.
3. Konsequenztypen, unveränderliche Buchungen, Wochenbilanz und Elternoberfläche.
4. Jederzeit-Aufgaben, rollenbasierte Sichtbarkeit, Freigabeübersicht und vereinfachte Navigation.
5. QNAP-Deployment nach Backup und erfolgreichen CI-Tests; Root-Container-Sicherheitsproblem vor externer Freigabe beheben.

**Wichtig:** Keine automatische Abrechnung auf bestehende Daten anwenden, bevor die Trennung zwischen Geldbonus in Cent, verfügbaren XP und Level-XP getestet ist.
