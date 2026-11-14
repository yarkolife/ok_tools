# Design-Aufgaben (helles und dunkles Theme)

Gefunden beim Erstellen der Handbuch-Kapitel „Inventar und Ausleihe“ (13.11.2026, OK-Tools 4.71.0,
Nr. 1–6) und „Einstellungen für Administratoren“ (14.11.2026, OK-Tools 4.73.0, Nr. 7–11).
Regel: im hellen Theme alles hell, im dunklen alles dunkel, überall gut lesbar.

| # | Seite | Problem | Status |
|---|---|---|---|
| 1 | Inventarartikel → Aktion „Barcodes drucken“ | Dialog blieb im dunklen Theme weiß, Formatnamen hellgrau auf Weiß kaum lesbar. | erledigt – Theme-Farben; die Etikettenvorschau bleibt bewusst weiß (wie gedruckt) |
| 2 | Ausleihe-Detail → Verbrauchsmaterial | Eingabefelder im dunklen Theme weiß; rote „fehlt“-Texte dunkelrot auf Dunkel. | erledigt |
| 3 | Ausleihe-Detail → Geräteliste | Reservierte (noch nicht ausgegebene) Geräte trugen das Etikett „Zurückgegeben“. „Out“ war als „Nicht verfügbar“ übersetzt. | erledigt – „Reserviert“ / „Ausgegeben“ / „Zurückgegeben“ |
| 4 | Ausleihprozess → Schnell | Platzhalter im Scanfeld „INV-…“, obwohl die Nummern mit „OK-“ beginnen. | erledigt – „Inventarnummer scannen oder eingeben…“ |
| 5 | Standorte (Liste) | Spaltenkopf „Full path“ nicht übersetzt. | erledigt – „Standort“ |
| 6 | Handbuch → Hinweise | Formular-Layout (Beschriftung neben schmalem Feld). | erledigt |
| 7 | Benachrichtigungseinstellungen | Seite außerhalb des Designs: Tabelle ohne Gestaltung, zentrierter Fettdruck, Einleitung englisch. | erledigt (14.11.2026, 4.73.0) – Karten pro Modul wie „Meine Abonnements“, feste Speichern-Leiste |
| 8 | Konfigurationsformulare | Passwort von Nextcloud, API-Schlüssel von Playout, Anchor, Reel-Renderer und Kanal-Tokens im Klartext im Formular. | erledigt – Passwortfelder, gespeicherter Wert wird nie angezeigt |
| 9 | Konfigurationsformulare | Englische Beschriftungen: „Export robustness“ und seine Felder, „Same-State Channel Exceptions“, „Upload Server Path“, „Approval workflow“, „Freistellung city“, Arbeitszeiten-Hinweis, Transcode-Preset, Reel-Timeout. | erledigt – übersetzt |
| 10 | Werkzeuge-/Austausch-Konfiguration | Seitentitel „Tools Configuration“ bzw. „Exchange Config - <URL>“ statt des deutschen Namens. | erledigt |
| 11 | Alle Formulare | Lange Feldnamen („…Genehmigungsbenachrichtigungen“) liefen über die Beschriftungsspalte ins Feld. | erledigt – Silbentrennung in Beschriftungen |

Nur lokal (keine Aufgabe): In der lokalen Testumgebung fehlte die Logo-Datei unter `media/`;
auf den Servern ist sie vorhanden.
