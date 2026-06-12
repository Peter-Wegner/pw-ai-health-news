# Health-AI-News-Agent

Ein kleiner Python-Agent, der wöchentlich Health-AI-Meldungen aus RSS-Feeds sammelt,
nach nachvollziehbaren Regeln bewertet, Duplikate entfernt und einen
Markdown-Überblick sowie ein PDF erzeugt. Er benötigt nur die
Python-Standardbibliothek.

## Ausführen

```bash
cd /Users/peterw/.openclaw/workspace/health_ai_news_agent
python3 agent.py
```

Die Berichte landen als `output/YYYY-MM-DD.md` und `output/YYYY-MM-DD.pdf`.
Bereits ausgegebene URLs werden in
`state/seen.json` gespeichert und bei späteren Läufen übersprungen.

Nützliche Optionen:

```bash
python3 agent.py --dry-run --days 7 --max-items 20
python3 agent.py --config /pfad/zu/config.json --output-dir /pfad/zu/output
```

Quellen, Schlagwörter, Gewichte und Mindestscore stehen in `config.json`. Die
vorbelegten Google-News-RSS-Suchen decken englisch- und deutschsprachige
Meldungen ab.

## Wöchentliche Pipeline

Der vollständige Sonntagslauf sammelt die Meldungen der letzten sieben Tage,
erzeugt Markdown und PDF, erstellt einen Git-Commit und pusht zu `origin`:

```bash
python3 weekly.py
```

Ein lokaler Testlauf ohne Git-Push:

```bash
python3 weekly.py --no-publish
```

## Tests

```bash
python3 -m unittest -v
```
