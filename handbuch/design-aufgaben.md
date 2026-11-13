# Design-Aufgaben (helles und dunkles Theme)

Gefunden beim Erstellen des Handbuchs „Inventar und Ausleihe“ (13.11.2026, OK-Tools 4.71.0).
Regel: im hellen Theme alles hell, im dunklen alles dunkel, überall gut lesbar.

| # | Seite | Problem | Status |
|---|---|---|---|
| 1 | Inventarartikel → Aktion „Barcodes drucken“ | Dialog blieb im dunklen Theme weiß, Formatnamen hellgrau auf Weiß kaum lesbar. | erledigt – Theme-Farben; die Etikettenvorschau bleibt bewusst weiß (wie gedruckt) |
| 2 | Ausleihe-Detail → Verbrauchsmaterial | Eingabefelder im dunklen Theme weiß; rote „fehlt“-Texte dunkelrot auf Dunkel. | erledigt |
| 3 | Ausleihe-Detail → Geräteliste | Reservierte (noch nicht ausgegebene) Geräte trugen das Etikett „Zurückgegeben“. „Out“ war als „Nicht verfügbar“ übersetzt. | erledigt – „Reserviert“ / „Ausgegeben“ / „Zurückgegeben“ |
| 4 | Ausleihprozess → Schnell | Platzhalter im Scanfeld „INV-…“, obwohl die Nummern mit „OK-“ beginnen. | erledigt – „Inventarnummer scannen oder eingeben…“ |
| 5 | Standorte (Liste) | Spaltenkopf „Full path“ nicht übersetzt. | erledigt – „Standort“ |
| 6 | Handbuch → Hinweise | Formular-Layout (Beschriftung neben schmalem Feld). | erledigt |

Nur lokal (keine Aufgabe): In der lokalen Testumgebung fehlte die Logo-Datei unter `media/`;
auf den Servern ist sie vorhanden.
