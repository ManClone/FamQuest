# Haushaltsstatistik: Elternzeit und Kinder-Erledigungen

Die Haushaltsübersicht vergleicht Eltern anhand des geschätzten Zeitaufwands der
bestätigten Hausarbeiten in den letzten 30 Familientagen. Der Prozentbalken
verwendet ausschließlich diese Eltern-Minuten. Kinder wie Tim werden separat
mit der Anzahl ihrer bestätigten Erledigungen angezeigt, ohne Zeitvergleich
oder gemeinsame Prozentrechnung mit den Eltern.

Es handelt sich um Zeitvorgaben pro Aufgabe, nicht um gemessene Arbeitszeit.
Neue Erledigungen speichern die zum Erledigungszeitpunkt eingestellten Minuten
als Momentaufnahme. Wiederholungen zählen einzeln; Retries nicht doppelt.
Zuordnung zu einer anderen Person überträgt dieselben ursprünglichen Minuten.
Eine gezielte Rücknahme entfernt genau die Minuten und den Zähler dieser Erledigung.
Wartende Kinderfreigaben, anonyme Erledigungen und Termine außerhalb des
30-Tage-Fensters fließen nicht ein.

Die additive Family-DB-Migration `l20261031choreminutes` legt eine nullable
Minutenspalte an. Vorhandene Erledigungen, XP und Geldbuchungen werden nicht
verändert. Bei alten Erledigungen ohne Momentaufnahme nutzt die Statistik die
heutige Zeitvorgabe der Aufgabe und weist darauf ausdrücklich hin. Die App kann
die früher eingestellte Dauer nicht zuverlässig nachträglich rekonstruieren.

Einmalige To-dos besitzen bisher keine Zeitvorgabe. Sie werden deshalb nicht
mit erfundenen Minuten im Elternvergleich berücksichtigt; ihre vorhandenen
Erledigungszähler bleiben für die Kinderanzeige und API-Kompatibilität erhalten.

Die Familie sieht in der normalen Haushaltsansicht und in der kompakten
Familienübersicht dieselbe Trennung. Ein Rundungstest stellt sicher, dass die
Elternprozente zusammen genau 100 ergeben. Kein produktives Deployment oder
Ausführen dieser Migration wurde mit der Implementierung vorgenommen.
