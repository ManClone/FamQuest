# FamQuest – Aufgaben, Routinen und Wochenabrechnung (Entwurf)

Status: abgestimmtes Konzept; noch keine produktive Funktion. Umsetzung auf develop, nach Tests via PR nach main.

## Wochenabrechnung und Konsequenzen
- Wochenzeitraum: Montag 00:00 bis Sonntag 23:59 in der Familienzeitzone.
- Eltern können eigene Konsequenztypen verwalten. Startvorlage: **Nicht auf Anweisungen gehört**, **5 Strafpunkte**, keine Standardnotiz.
- Nur Eltern dürfen Konsequenzen buchen, korrigieren und stornieren; Ereignisse sind nachvollziehbar (Person, Zeitpunkt, Woche, Typ, Punkte, optionale Begründung, Urheber).
- Strafpunkte beeinflussen ausschließlich den **wöchentlichen Bonusbereich**. Weder das bedingungslose Grundtaschengeld noch bereits verdiente XP, erreichte Level oder vergangene Abrechnungen werden reduziert.
- Wochenbonus = max(0, in der Woche verdiente abrechenbare Bonuspunkte - Strafpunkte). Kein negativer Übertrag. Vergangene Wochen bleiben nachvollziehbar.
- XP für Level und Bonuspunkte für die Wochenabrechnung sind **getrennte Größen**; nicht dieselbe Buchung zweimal als XP-Abzug verwenden.
- Ein Abschluss wird idempotent und revisionssicher gespeichert; Korrekturen nach Abschluss als nachvollziehbare Gegenbuchung, keine stille Mutation.
- Eine Konsequenz wird **nicht automatisch** als Euro-Abzug behandelt. Geldboni separat und ausdrücklich konfigurieren.

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
1. Bestehende Authentifizierung, XP-/Bonus-Ledger, Routinen-API und Tests prüfen; Datenbankmigration planen.
2. Routinen-Wochentage entkoppeln und Mehrfach-Zeitpunkte modellieren.
3. Konsequenztypen, unveränderliche Buchungen, Wochenbilanz und Elternoberfläche.
4. Jederzeit-Aufgaben, rollenbasierte Sichtbarkeit, Freigabeübersicht und vereinfachte Navigation.
5. QNAP-Deployment nach Backup und erfolgreichen CI-Tests; Root-Container-Sicherheitsproblem vor externer Freigabe beheben.

**Wichtig:** Keine automatische Abrechnung auf bestehende Daten anwenden, bevor die Trennung zwischen lebenslangen XP und abrechenbaren Wochenbonuspunkten getestet ist.
