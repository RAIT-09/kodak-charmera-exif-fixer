# Review und Optimierungsplan

> Historisches Review vor den anschließenden Änderungen. Inzwischen wurden unter
> anderem Überschreib-Rückfragen, temporäre Verarbeitung und Ausgabeprüfung,
> namensunabhängige Kartenerkennung, rekursiver Scan, Kamera-Tags und eine
> kompakte CLI-Fortschrittsanzeige ergänzt. Die Tests liegen unter `tests/`.
> Die folgenden Befunde und Prüfstandsangaben beschreiben den damaligen Stand,
> nicht durchgehend den aktuellen Code; weitere Planungspunkte bleiben offen.

Stand: 6. September 2026. Gegenstand ist der lokale Repository-Stand, ohne Änderungen am Anwendungscode und ohne Verarbeitung persönlicher Kameradateien.

## Einschätzung

Die Trennung von Kernlogik, Werkzeug-Adaptern und Oberfläche ist eine brauchbare Grundlage. Ein kompletter Neubau ist nicht erforderlich. Vor einem regelmäßigen Import sollten jedoch Überschreibschutz, Fehlerbehandlung und die überprüfbare Korrektur von Metadaten umgesetzt werden.

Für das konkrete Charmera-Problem ist entscheidend: Der aktuelle Code repariert bei Fotos lediglich ein bestimmtes Datumsformat und abweichende, bereits vorhandene EXIF-Abmessungen. Eine falsch eingestellte Kamerauhr, fehlende Datumswerte oder eine Zeitverschiebung korrigiert er nicht. Ob die Implementierung zu den tatsächlichen Defekten dieser Kamera passt, muss noch anhand unveränderter Beispieldateien geprüft werden.

## Befunde nach Priorität

### P1: Vorhandene Videos können überschrieben werden

Stellen: `core/file_copier.py:25`, `core/video_converter.py:22`, `adapters/ffmpeg_cli.py:33`.

Der Kopierer prüft nur den AVI-Zielnamen. Nach erfolgreicher Konvertierung wird die AVI-Kopie standardmäßig gelöscht. Beim nächsten Import ist dieser Name wieder frei, obwohl die MP4 noch vorhanden ist. Der Konverter verwendet denselben MP4-Namen und FFmpeg erhält `-y`. Dadurch wird die vorhandene MP4 überschrieben; auch verschiedene Videos mit gleichem Änderungszeitpunkt sind betroffen. Die Zielkollision wurde mit temporären Dateien und einem simulierten FFmpeg-Adapter reproduziert.

Abhilfe: Alle endgültigen Zielnamen vorab kollisionsfrei reservieren, vorhandene Ausgaben niemals implizit überschreiben und wiederholte Importe über Inhaltsprüfsummen erkennen. Bei parallelen Prozessen reicht eine bloße `exists()`-Prüfung nicht aus.

### P1: Videokonvertierung kann dauerhaft hängen

Stelle: `adapters/ffmpeg_cli.py:46`.

Der Adapter liest stdout kontinuierlich, stderr jedoch erst nach Prozessende und nur bei Fehlern. Bei genügend Diagnoseausgabe kann die stderr-Pipe volllaufen: FFmpeg wartet auf einen Leser, während die Anwendung auf weiteren Fortschritt wartet. Es fehlen Timeout und geordnetes Beenden des Kindprozesses.

Abhilfe: Beide Streams gleichzeitig abarbeiten oder stderr in eine temporäre Logdatei umleiten; begrenzte Diagnoseausgabe, Abbruchsignal und zuverlässiges Aufräumen ergänzen. Befund aus Codeprüfung, kein realer Langzeit-Konvertierungstest.

### P2: Ein einzelner Lesefehler verhindert den gesamten Import

Stelle: `core/scanner.py:32`.

Dateistatistik und EXIF-Lesen laufen ohne Fehlerbehandlung pro Datei. Bereits ein beschädigtes JPEG oder eine während des Scans entfernte Datei verhindert die Vorschau aller sonst lesbaren Dateien. Mit einem EXIF-Adapter reproduziert, der für eine Datei eine Exception auslöst.

Abhilfe: Lesefehler pro Datei als Scan-Ergebnis sammeln; lesbare Dateien weiterhin anbieten. Fehlende Werkzeuge separat vor dem Scan melden.

### P2: Medien in DCIM-Unterordnern werden übersehen

Stelle: `core/scanner.py:23`.

Der Scanner verwendet `list_files()` ohne Rekursion; der Dateisystemadapter hat standardmäßig `recursive=False`. Eine Datei unter `DCIM/100MEDIA/photo.jpg` ergibt deshalb null Treffer. Mit temporärer Verzeichnisstruktur reproduziert.

Abhilfe: Rekursiv und deterministisch scannen, Metadatendateien ausschließen und den Umgang mit Symlinks explizit festlegen.

### P2: Strukturdefekte allein lösen keine EXIF-Reparatur aus

Stellen: `core/models.py:23`, `core/scanner.py:56`, `core/exif_fixer.py:12`.

EXIF-Warnungen und Strukturdefekte werden nicht im Datenmodell erfasst. Sind Datum und Abmessungen unauffällig, überspringt der Fixer die Verarbeitung vollständig, auch wenn ein Strukturdefekt vorliegt. Umgekehrt wird bei jeder einfachen Tagkorrektur die gesamte Metadatenstruktur neu aufgebaut. Nach dem Schreiben findet keine Kontrolle der tatsächlichen Tags statt.

Abhilfe: Diagnose und Wertkorrekturen getrennt modellieren, Strukturreparatur gezielt auslösen und Metadaten vor/nach dem Schreiben vergleichen. Welche beschädigten Tags tatsächlich wiederherstellbar sind, ist an Originaldateien zu testen; ein vollständiger Erhalt ist bisher nicht nachgewiesen.

### P2: Fehlerhafte Datumswerte werden als Korrektur vorgeschlagen

Stelle: `core/scanner.py:66`.

Die Erkennung zählt lediglich durch Doppelpunkte getrennte Teile. Auch `2026:99:99:25:61:61` wird zu einem vermeintlich korrigierten Datum. Fehlende und bereits formal gültige, aber sachlich falsche Werte bleiben unverändert. Videos übernehmen ungeprüft die Dateimodifikationszeit als Aufnahmezeit; der Dateisystemadapter liefert dabei einen Zeitwert ohne Zeitzone.

Abhilfe: Kalenderwerte streng validieren, Datumquelle und Unsicherheit anzeigen. Eine manuelle Uhrkorrektur und Kamerazeitzone vorsehen; bei unbekannter Aufnahmezeit keine Gewissheit vortäuschen. Video-Zeitmetadaten nach dem Schreiben mit explizit definierter Zeitzonenstrategie prüfen.

### P2: Automatisierung meldet trotz Verarbeitungsfehlern Erfolg

Stellen: `core/pipeline.py:83`, `__main__.py:33`.

Die Pipeline sammelt Fehler, aber `_run_pipeline()` verwirft ihre Ergebnisse. Der CLI-Prozess kann bei fehlgeschlagenen Dateien normal mit Exitcode 0 enden. Auch ein leerer Scan wird nicht als Fehlerstatus weitergereicht.

Abhilfe: Strukturiertes Gesamtergebnis und dokumentierte Exitcodes für Erfolg, Teilfehler und Startfehler. Abbruch durch den Benutzer getrennt behandeln.

### P2: Fehleranzeige der GUI kann weitere UI-Aktualisierungen stoppen

Stelle: `ui/tkinter_app.py:53`.

Der verzögert ausgeführte Lambda-Ausdruck greift auf die Exceptionvariable `e` zu. Diese wird nach dem `except`-Block von Python gelöscht. Wird der Callback danach ausgeführt, entsteht ein `NameError`; `_poll_queue()` fängt nur `queue.Empty` ab und plant dann keinen weiteren Poll ein.

Abhilfe: Fehlertext vorab speichern beziehungsweise an den Callback binden und die Queue-Verarbeitung gegen einzelne Callbackfehler absichern. Statisch geprüft; der aktive Python-Interpreter enthält kein `_tkinter`, daher kein GUI-Laufzeittest.

## Weitere Verbesserungspunkte

- `--dest` wird in der GUI durch deren fest eingebauten Standard und den beim Start ausgelesenen Wert übergangen. Oberfläche aus dem ProcessingPlan initialisieren.
- Ohne erkannte Kamera wird die GUI-Meldung nur eingereiht und anschließend vor Start der Ereignisschleife beendet. Einen sichtbaren Leerzustand mit Quellenauswahl anbieten.
- Quelle ist auf `/Volumes/Untitled/DCIM` festgelegt. `--source` und Ordnerauswahl ermöglichen auch SD-Karten mit anderem Namen sowie bereits kopierte Fotos.
- Fenster schließen beendet den Hintergrundthread ohne kontrollierten Abbruch. Temporäre Ausgaben und Kindprozesse benötigen geregeltes Aufräumen.
- Die Anwendung schreibt direkt in die endgültigen Dateien. Fehlgeschlagene Reparaturen können halbfertige Ergebnisse hinterlassen. AVI-Kopien werden ohne zusätzliche Ausgabeprüfung gelöscht.
- Kein Schutz verhindert, dass ein gewähltes Ziel auf dem Kameravolume liegt. Das widerspricht dem dokumentierten Versprechen, dort nichts zu verändern.
- Wiederholte Fotoimporte erzeugen immer weitere Kopien. Ein Importmanifest sollte Quellprüfsumme, Ziel, Reparaturversion und Ergebnis speichern.
- Der LaunchAgent lädt seine Vorlage über einen Pfad außerhalb des Python-Pakets; die Paketkonfiguration enthält keine entsprechende Ressource. Wheel-Installation einschließlich Launcher testen und die Vorlage als Paketressource ausliefern.
- Mehrere Konfigurationsfelder, etwa `dcim_subdir` und die Dateiendungen, werden vom Scanner nicht verwendet.
- Pro Foto entstehen ein Leseprozess und bei Reparatur zwei Schreibprozesse. Erst nach Korrektheitsabsicherung messen und gegebenenfalls ExifTool-Batches einsetzen.

## Umsetzungsplan

### 1. Datenverlust und blockierende Prozesse verhindern

Kollisionsfreie Zielplanung für AVI und MP4, temporäre Arbeitsdateien, Veröffentlichung erst nach erfolgreicher Prüfung, geordneter Prozessabbruch und sichere stderr-Verarbeitung. Unveränderte Originalkopien zunächst behalten; Löschen als ausdrückliche Option anbieten. Quelle und Ziel vor Verarbeitung validieren.

Abnahme: Zwei Videos mit gleichem Zeitstempel überschreiben sich nicht; ein erneuter Import verändert vorhandene Ausgaben nicht. Abbruch, voller Datenträger und Werkzeugfehler hinterlassen keine als fertig ausgewiesene Teildatei. Quellen bleiben bytegleich. Hohe stderr-Ausgabe führt nicht zum Stillstand.

### 2. EXIF-Reparatur fachlich absichern

Kleine Referenzsammlung unveränderter Charmera-JPEGs und AVIs erstellen. Rohmetadaten und Warnungen erfassen. Strenge Datumsvalidierung, explizite Datumsquelle, optionale Uhrkorrektur und Zeitzone implementieren. Strukturreparatur von Tagänderungen trennen und Ergebnisse erneut einlesen. Fehlende Dimensionen aus verifizierten Bilddimensionen ergänzen.

Abnahme: Für jede Referenzdatei sind erwartete Änderungen festgelegt. Korrekte Metadaten bleiben erhalten; JPEG-Bilddaten werden nicht neu komprimiert. Ein zweiter Reparaturdurchlauf ergibt keine weiteren Änderungen. Unbekannte Aufnahmezeiten werden als ungeklärt angezeigt.

### 3. Import im Alltag zuverlässig machen

Freie Quellenauswahl, rekursiver Scan, Fehlerisolierung pro Datei, Abhängigkeitsprüfung, Importmanifest und Exitcodes umsetzen. Manifest erst nach validierter Veröffentlichung aktualisieren; fehlende oder veränderte Zielausgaben beim Wiederanlauf erkennen.

Abnahme: Umbenannte SD-Karte und lokaler Ordner funktionieren. Eine defekte Datei blockiert gesunde Dateien nicht. Wiederholung überspringt verifizierte Importe. Teilfehler sind für CLI-Automatisierung eindeutig erkennbar.

### 4. Oberfläche und Auslieferung abrunden

Vorschau mit alten/neuen Werten und Datumquelle, Dateiauswahl, sichtbare Einzelfehler, sicherer Abbruch und korrekter Übernahme des Zielordners. Paketressourcen und Launcher prüfen. Danach Laufzeiten an einer definierten Medienmenge messen und nur belegte Engpässe optimieren.

Abnahme: Quelle, Ziel und geplante Änderungen sind vor Start sichtbar. Fehler legen die Oberfläche nicht still. Installation aus einem gebauten Wheel funktioniert unabhängig vom Repository-Verzeichnis.

## Prüfstand und Grenzen

- Gesamter Python-Anwendungscode, README, Paketkonfiguration und LaunchAgent-Konfiguration gelesen.
- `python3 -m unittest discover -v`: 0 Tests; `tests/` enthält nur `__init__.py`.
- Temporäre Reproduktionen für MP4-Zielkollision, fehlende Ausgabeprüfung vor AVI-Löschung, nichtrekursiven Scan, Scanabbruch und unzureichende Datumsvalidierung ausgeführt. Externe Adapter dabei simuliert.
- ExifTool, FFmpeg und ffprobe sind lokal vorhanden, wurden in diesem Review aber nicht mit echten Kameradateien validiert.
- GUI-Ausführung wegen fehlendem `_tkinter` im aktiven Python nicht möglich. Keine Aussage über bereits erfolgreich getestete GUI- oder Medienintegration.
- Keine Änderungen am Anwendungscode; dieses Dokument hält Review und Planung fest.
