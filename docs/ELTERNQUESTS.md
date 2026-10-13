# FamQuest: Elternquests und Belohnungen (Entwurf)

Status: abgestimmtes Konzept, noch nicht implementiert. Branch: develop.

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
