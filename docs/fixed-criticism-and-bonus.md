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

## Docker-Testimage

Der Predeployment-Workflow prüft jetzt genau den Head des eigenen Entwurfs und
veröffentlicht nach erfolgreichen Backend-, Frontend-, Docker- und MCP-Jobs
separate Testimages mit vollständiger Commit-Kennung. Es gibt keine Veröffentlichung
unter `latest` aus diesem Testweg. Pull Requests fremder Repositories können diesen
Veröffentlichungsschritt nicht ausführen. Eine fertige Testimage-Veröffentlichung
ersetzt nicht die separate Migrations-/Restore-Probe vor produktivem Update.
