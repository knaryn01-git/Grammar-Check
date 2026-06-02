# Grammar & Writing Enhancer

A small, **locally-hosted** web app for grammar checking and writing
enhancement of any English sentence or paragraph.

## What it uses (all open source)

| Layer | Tool | License |
| --- | --- | --- |
| Grammar / spelling | [LanguageTool](https://github.com/languagetool-org/languagetool) (via free public API by default) | LGPL-2.1 |
| Style heuristics | Inspired by [`write-good`](https://github.com/btford/write-good) — implemented locally in Python | MIT |
| Readability | Flesch Reading Ease & Flesch–Kincaid Grade Level | Public domain |
| Backend | Flask | BSD-3 |

## Run it

```powershell
# from this folder:
.\run.bat
```

The first run creates a virtualenv and installs `flask` + `requests`.
Then open <http://127.0.0.1:5000> in your browser.

To run without the helper script:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Features

- **Live grammar & spell-check** as you type (debounced).
- **Replacement chips** — click a suggestion to apply it instantly.
- **Style/writing suggestions**: wordy phrases, weasel words, passive voice,
  weak adverbs, overly long sentences.
- **Readability metrics**: word/sentence counts, Flesch reading-ease score,
  Flesch–Kincaid grade level, average words per sentence.
- **Picky mode** toggle for stricter LanguageTool rules.
- **English variants** — US / UK / India / AU / CA.

## Going fully offline (optional)

The default uses LanguageTool's free public API (≈20 req/min, 20 000 chars
per request). For unlimited, offline use, run LanguageTool locally:

1. Install Java 17+.
2. Download the LanguageTool stand-alone server:
   <https://languagetool.org/download/LanguageTool-stable.zip>
3. Unzip and start it:

   ```powershell
   java -cp languagetool-server.jar org.languagetool.server.HTTPServer --port 8081
   ```

4. Point the app at it:

   ```powershell
   $env:LT_API_URL = "http://localhost:8081/v2/check"
   python app.py
   ```

## Files

- `app.py` — Flask backend (`/api/check` grammar, `/api/enhance` style).
- `static/index.html`, `static/style.css`, `static/app.js` — UI.
- `requirements.txt` — Python deps.
- `run.bat` — one-click launcher (Windows).
