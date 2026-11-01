# Feste Kritikstufen und geschützte Wochenabrechnung

Die Elternansicht ersetzt freie Sternabzüge bei Kindern durch Gespräch bzw.
Wiedergutmachung ohne Abzug, leicht mit einem Stern, schwer mit zwei Sternen und
sehr schwer mit drei Sternen. Sterne sind ausgebbare Spielpunkte; Level-XP und
bereits erreichte Level bleiben getrennt. Bei geringerem Sternestand wird nur der
vorhandene Betrag abgezogen; eine Korrektur erstattet nur den tatsächlich gebuchten
Abzug. Die alten internen `xp_penalty`-Spalten bleiben für die Historie erhalten.

Geld wird niemals automatisch aus einer Kritik abgeleitet. Eltern müssen den
optionalen festen Abzug ausdrücklich auswählen, den Grund angeben und die konkrete
Vorschau bestätigen: schwer höchstens 50 Cent, sehr schwer höchstens 100 Cent.
Die Umsetzung bietet je Stufe entweder keinen Geldabzug oder genau diesen Betrag.
Der aktuelle, noch offene Bonus derselben Woche muss danach positiv bleiben.
Grundtaschengeld und Bankguthaben werden nicht belastet. Die API prüft den zuletzt
angezeigten Bonus erneut und verweigert veraltete Bestätigungen, unzulässige
Beträge und vergangene oder zukünftige Kritikwochen. Wiederholungen derselben
Anfrage werden nicht doppelt gebucht; abweichende Inhalte mit gleichem Schlüssel
werden abgelehnt.

Die Vorschau beruht auf echten Buchungen dieser Familien-Datenbank. Der alte
Simulations-Endpunkt mit frei übergebenen Eurobeträgen ist im integrierten Server
nicht mehr eingebunden. Negative manuelle Kinder-Punktebuchungen können dort die
Kritikstufen nicht umgehen. MCP darf diese Geld-/Kritikentscheidungen nicht
ausführen.

Eine gesonderte Elternbestätigung kann die Wochenabrechnung unveränderlich
abschließen. Sie speichert Grundtaschengeld, verdiente Boni und Abzüge als
Momentaufnahme und prüft zuvor nochmals die bestätigte Gesamtsumme.
Beispiel: 500 Cent Grundtaschengeld + 350 Cent Bonus − 50 Cent ausdrücklich
bestätigter Abzug = 800 Cent. Wiederholter Abschluss erzeugt keinen zweiten Posten.
Spätere Geldsanktionen oder deren Rücknahme verändern den Abschluss nicht.
Nachträgliche Aufgaben-/Nachweiskorrekturen werden als Prüfbedarf angezeigt,
ohne Rückforderung, automatische Auszahlung oder stilles Verwerfen von Nachweisen.

Die Historie zeigt Entscheidungen und begründete, ausdrücklich bestätigte
Rücknahmen. Neue Entscheidungen sind mit ihrer konkreten Sternbuchung verbunden;
zurückgenommene Kritik erzeugt keine weiter aktive Abzugsreaktion im Kinderprofil.
Alte Einträge erhalten keine erfundene Kritikstufe.

Die additive Family-Migration `n20261031criticism` erweitert nur Auditdaten und
Abschlussnachweise. Sie ändert keine bestehenden Punkte-, Geld- oder Bankbuchungen.
Schema-Constraints sichern neue feste Stufen zusätzlich ab. Wie bei den anderen
familienlokalen Buchungen löscht eine ausdrücklich ausgeführte Profil-Löschung
auch die dazugehörigen Nachweise; der Wochenabschluss ist keine separate
Langzeitarchivierung gelöschter Profile.

Dieser Bereich ist eine Abrechnungshilfe, keine Bankanbindung. Er löst keine
Überweisung aus, behauptet keine automatische Zahlungserkennung und ergänzt
keinen frei wählbaren Wochen-Sonderbonus. Bankabruf, Auszahlungstag-/Erinnerungs-
Automatik und nachträglicher Bankabgleich bleiben gesonderte Ausbauschritte.

Aufgabenboni sind jetzt im Aufgaben-/Routineneditor als optionale Euro-Eingabe
bedienbar. Bestehende Werte werden beim Ändern einer Aufgabe erhalten. Die Eingabe
rechnet Dezimalwerte ohne Gleitkomma-Rundung in ganze Cent um. Grundtaschengeld hat
eine getrennte Elterneinstellung; deren Änderung verändert keine bereits gebuchte
Woche. Aufgaben mit Bonus-Nachweisen werden deaktiviert statt durch Löschen der
Definition ihrer Verdienstnachweise beraubt.

MCP darf weder neue Euro-Boni festlegen noch bereits vergütete Aufgabendefinitionen
ändern oder löschen. Das schließt indirekte Änderungen über Wiederholbarkeit,
Freigabepflicht und Zeitpläne ein. Die gemeinsamen Speicherroutinen sichern auch
verschachtelte Routinenschritte ab; im MCP-Eingabeschema ist das Geldfeld entfernt.
Normale Aufgaben ohne Euro-Bonus bleiben über MCP bearbeitbar. Bereits konfigurierte
Boni können Teil gelesener Aufgabendaten und ausdrücklich bestätigter gültiger
Erledigungen sein; das ist keine Freigabe zur Geld- oder Bankverwaltung.

Lob und Kritik verwenden wie die übrigen Erledigungsaktionen kryptografische
128-Bit-Auftragsschlüssel über `getRandomValues`. Dadurch benötigen diese beiden
Formulare nicht die nur im sicheren Kontext verfügbare `randomUUID`-Methode;
siehe [W3C Web Cryptography API](https://w3c.github.io/webcrypto/).

## Docker-Testimage

Der Predeployment-Workflow prüft jetzt genau den Head des eigenen Entwurfs und
veröffentlicht nach erfolgreichen Backend-, Frontend-, Docker- und MCP-Jobs
separate Testimages mit vollständiger Commit-Kennung. Es gibt keine Veröffentlichung
unter `latest` aus diesem Testweg. Pull Requests fremder Repositories können diesen
Veröffentlichungsschritt nicht ausführen. Eine fertige Testimage-Veröffentlichung
ersetzt nicht die separate Migrations-/Restore-Probe vor produktivem Update.


## Eine gemeinsame Liste beim Kind

Unter Familie → Kind bearbeiten zeigt die Buchungsliste Erledigungen und
Gegenbuchungen. Eine korrigierbare Erledigung wird direkt angetippt; erst die
nachfolgende Bestätigung nimmt genau diese Erledigung zurück. Die zusätzlichen
Listen für Kinderaufgaben und Haushaltsaufgaben entfallen in diesem Profil.
Manuelle Gutschriften werden ebenfalls über ihren Eintrag mit Begründung korrigiert.

Der gemeinsame, cursorbasierte Verlauf berücksichtigt auch Erledigungen ohne
Punkte sowie reine Euro-Boni. Positive Aufgaben-Geldbuchungen und zugehörige
Punkte erscheinen zusammen; reine Euro-Gegenbuchungen bleiben nachvollziehbar.
Die Buchungsnachweise selbst werden durch eine Rücknahme nicht gelöscht.

Die additive Migration `o20261101links` ergänzt ausschließlich zwei optionale
Herkunftsspalten im Punktejournal. Neue Gutschriften verweisen damit direkt auf
die konkrete Kinder- oder Haushaltserledigung. Die Referenz bleibt als Nachweis
erhalten, wenn eine Erledigung zurückgenommen wurde. Bestehende Beträge und
Buchungen werden nicht umgeschrieben.

Alte Einträge ohne Herkunftsreferenz erhalten nur dann eine Rücknahmeaktion,
wenn genau eine Buchung und eine passende Erledigung innerhalb desselben
Datenbank-Transaktionszeitpunkts eindeutig zusammengehören. Es wird niemals
allein anhand gleicher Titel, Tage oder Punkte auf eine Erledigung geschlossen.
Nicht eindeutig zuordenbare alte Nachweise bleiben lesbar; die vorhandenen
fachlichen Korrekturansichten können sie weiterhin bearbeiten.


### Sichtbare Rücknahmen und Wiederaktivierung

Ab `p20261101reactivate` bleiben neu zurückgenommene Erledigungen als ein roter,
inaktiver Eintrag in der gemeinsamen Buchungsliste erhalten. Sie zählen nicht zum
Punktestand. Antippen und Bestätigen aktiviert die ursprünglichen Punkte und den
ursprünglichen Aufgabenbonus wieder; geänderte Aufgabendefinitionen ändern diese
Momentaufnahme nicht. Eine inzwischen erneut erledigte normale Aufgabe blockiert
die Wiederaktivierung, damit keine doppelte Gutschrift entsteht. Einzelne echte
Wiederholungs-Erledigungen bleiben unabhängig.

Das gilt auch für manuelle positive Gutschriften. Alle ursprünglichen und
kompensierenden Buchungen bleiben im unveränderten Journal erhalten; der
Familienverlauf fasst sie zu einem Eintrag zusammen. Die additive Migration legt
nur zwei neue Tabellen an und schreibt keine alten Beträge um. Vor diesem Stand
bereits gelöschte Erledigungen besitzen keine vollständige Momentaufnahme und
werden deshalb nicht nachträglich als wiederherstellbar ausgegeben.


### Geldbonus bei Haushaltsaufgaben und Drachenanzeige

Ab `q20261101chorebonus` kann pro Haushaltsaufgabe ein optionaler Kinderbonus in
Euro eingestellt werden. Er gilt zusätzlich zu Sternen, getrennt vom
Grundtaschengeld. Kinder-Erledigungen warten auf Elternfreigabe; eine direkt von
Eltern für ein berechtigtes Kind bestätigte Erledigung wird sofort gebucht.
Erwachsene erhalten keinen Geldbonus. Ohne Personen-Zuordnung wird nichts bezahlt.
Der Betrag bleibt pro Erledigung gespeichert. Änderungen der Aufgabe ändern
frühere oder bereits zur Freigabe eingereichte Beträge nicht.

Rücknahme und Wiederaktivierung wirken auf denselben ursprünglichen Bonus und
erscheinen in der gemeinsamen Buchungsliste. Wiederholte Aufrufe zahlen nicht
doppelt. Haushalts- und Kinderaufgaben besitzen getrennte Journalarten, damit
identische Datenbank-IDs ihre Wochenbeträge nicht vermischen. Abgeschlossene
Wochen bleiben eingefroren und zeigen nachträgliche Korrekturen zur Prüfung an.
Bestätigte bezahlte Erledigungen müssen vor dem Löschen einer Hausarbeit oder
ihres Raums zurückgenommen werden; Deaktivieren bleibt möglich. Der Empfänger
einer bezahlten Erledigung kann nicht stillschweigend geändert werden.

Die additive Migration ergänzt je ein Null-vorbelegtes Cent-Feld in Aufgaben und
Erledigungen. Bestehende Ausführungen bekommen keinen nachträglichen Bonus. MCP
kann diese Geldwerte weder konfigurieren noch Geldfreigaben oder Rücknahmen
ausführen.

Der Drachenbegleiter wird in Kinderansicht, Personenansicht und Familienübersicht
wieder angezeigt. Vorhandene Drachen-Namen und Level bleiben erhalten. Ein noch
unbenannter Drache kann einmalig benannt werden; Kinder dürfen nur ihren eigenen
Drachen benennen. Es handelt sich um die Anzeige mit vorhandenem Drachen-Icon und
bestehendem Levelstand, nicht um eine neue animierte Entwicklungssimulation.


### Haushaltsstatistik mit Zeitraum und getrennten Prozentbezügen

Die Übersicht zeigt Eltern mit Aufgabenanzahl, geschätzten Minuten und Anteil an
der Elternzeit. Kinder zeigen Aufgabenanzahl und Anteil an allen zugeordneten
Erledigungen der Familie, einschließlich der Eltern-Erledigungen. Kinder-Minuten
werden nicht in die Elternzeit eingerechnet. Ein Hinweis erklärt die verschiedenen
Bezugsgrößen. Auch ein einzelnes Elternteil wird mit seinen Werten angezeigt.

Im Kopf stehen 7 Tage, 30 Tage oder 1 Jahr zur Wahl (rollierend 365 Tage, jeweils
heute eingeschlossen). Anzahl und Zeit werden für denselben Zeitraum neu geladen;
nur bestätigte, zugeordnete Erledigungen bis einschließlich heute zählen. Die
Auswahl bleibt auch in einem leeren Zeitraum sichtbar. Die kompakte Familienansicht
behält den Standardzeitraum von 30 Tagen.
