# FamQuest: Elternquests und Belohnungen (Entwurf)

Status: Teilimplementierung auf `develop`; noch nicht produktionsreif. Keine bestätigten CI-Testergebnisse oder QNAP-Bereitstellung.

## Bereits auf `develop` umgesetzt
- Putzplan-Aufgaben haben geschätzte Minuten, Erwachsenen-XP und Zuordnungsmodus (fest, rotierend, flexibel).
- Eltern können diese Angaben bearbeiten; bestehende ältere Clients behalten beim Bearbeiten die Erwachsenen-Einstellungen.
- Wochenvorschlag berücksichtigt feste Aufgaben und Arbeitsbelastung. Eltern können den Vorschlag ändern und verbindlich für die laufende Woche speichern.
- Bestätigte Zuständigkeiten werden im gemeinsamen Putzplan angezeigt; nach Bestätigung wird die Ansicht aktualisiert.
- Eltern können XP für tatsächlich erledigte Hausarbeiten freigeben. Mehrfachfreigaben sind idempotent; Rücknahmen buchen Gegenbuchungen. Für das Rückgängigmachen bereits vergüteter Aufgaben ist eine Elternfreigabe nötig.
- Datenbankmigrationen und Backend-Regressionstests sind angelegt; vollständige CI-Verifikation steht noch aus.

## Noch offen
- Separater Erwachsenen-Belohnungskatalog mit geschützter Einlösung, ggf. Zustimmung der anderen Person und Buchungshistorie.
- Sichere Home-Assistant-/Lumo-Anbindung mit ausdrücklicher Elternbestätigung für generierte Aufgaben.
- Nachweislich grüner CI-Lauf, Testinstallation und erst danach Freigabe zur produktiven Bereitstellung.


## Rollen und Punktesysteme
- Tim sammelt Kinder-XP. Erwachsene sammeln Erwachsenen-XP mit geringerer Vergabe je Routineaufgabe.
- Kein XP-Umtausch zwischen den Rollen. Grundtaschengeld bleibt unabhängig.
- Haushaltsaufgaben zählen auch ohne Punkte als gemeinsame Verantwortung.

## Aufgabenverteilung
- Der Wocheneinkauf ist fest Flo zugeordnet.
- Weitere Aufgaben können fest, rotierend oder flexibel zugeteilt werden.
- Automatische Zuteilung berücksichtigt geschätzte Minuten, erledigte Aufgaben und bereits feste Zuständigkeiten.
- Planung und Organisation (Mental Load) sind als eigene Aufgaben erfassbar.
- Beide Eltern können Aufgaben ändern, verschieben oder tauschen.

## XP-Vorschläge (anpassbar)
- Spülmaschine: 3
- Müll: 3
- Wäsche: 8
- Bad: 15
- Wocheneinkauf (Flo): 15
- Essensplanung: 20
- Große Zusatzaufgabe: 25–40

## Belohnungen
- Separate Erwachsenen-Belohnungen: Massage, Essen, Ausflug, freie Zeit.
- Punkte werden erst bei verbindlicher Einlösung abgebucht.
- Leistungen, die eine andere Person erbringen soll, benötigen deren Zustimmung und Terminabsprache.
- Erwachsene lösen Belohnungen nur über einen geschützten Elternablauf ein.

## Technische Umsetzung
- Vorhandenen Putzplan (api/chores) und bestehendes Punktebuch verwenden.
- Chore-Zuständigkeit, geschätzte Dauer und XP ergänzen; Migration erforderlich.
- Idempotente Punktebuchungen bei Erledigung; Korrekturbuchungen bei Rücknahme oder Wechsel der ausführenden Person.
- Kinderaufgaben (api/tasks) bleiben unverändert.
- Elternfreigabe, Rollenrechte und Buchungshistorie testen.
- Erst auf Testinstanz prüfen, danach QNAP bereitstellen.
