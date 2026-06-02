# Grammar & Writing Enhancer

A single-file web app for grammar checking, style suggestions, readability
metrics, rephrasing and translation of any English sentence or paragraph.

**Live:** <https://knaryn01-git.github.io/Grammar-Check/standalone.html>

## What it uses (all open source / free)

| Layer | Tool | License |
| --- | --- | --- |
| Grammar / spelling | [LanguageTool](https://github.com/languagetool-org/languagetool) public API | LGPL-2.1 |
| Synonyms / related words | [Datamuse](https://www.datamuse.com/api/) | Free |
| Rephrase / translate | [MyMemory](https://mymemory.translated.net/) | Free tier |
| Style heuristics | Inspired by [`write-good`](https://github.com/btford/write-good) — implemented locally in JS | MIT |
| Readability | Flesch Reading Ease & Flesch–Kincaid Grade Level | Public domain |

## Features

- **Live grammar & spell-check** as you type (debounced).
- **Click-to-fix replacement chips** for every suggestion.
- **Style/writing suggestions**: wordy phrases, weasel words, passive voice,
  weak adverbs, overly long sentences, **repeated words**, **sentence-variety**
  (3+ consecutive sentences starting the same way).
- **Readability metrics**: words, sentences, avg w/s, Flesch reading-ease,
  grade level, **read time**, **longest / shortest sentence**, **unique-word %**,
  **tone** (Casual / Balanced / Formal).
- **Rephrase tab** — back-translation through any pivot language.
- **Translate tab** — 60+ languages via MyMemory.
- **Synonyms** — double-click any word.
- **Picky mode** + English variants (US / UK / India / AU / CA).
- **Engine toggle** — switch between the public LanguageTool API and your
  own local server.

## Use it

Just open the live URL above. Nothing to install — it's a single HTML file
that runs entirely in your browser.

To run a local copy, double-click `standalone.html` (or open it with any
browser using `file://`). All APIs are CORS-enabled, so no server is needed.

## Going fully offline / unlimited (optional)

The public LanguageTool API is rate-limited (~20 req/min). For unlimited
local use:

1. Make sure Java 17+ is installed (`java -version`).
2. Double-click **`start-languagetool.bat`** — it auto-downloads
   LanguageTool 6.4 (~250 MB) on first run and starts the server on
   `http://localhost:8081`.
3. In the app, click the **`Engine: Public`** button to switch it to
   **`Engine: Local`**.

> When the app is loaded over HTTPS (e.g. the GitHub Pages URL), browsers
> block calls to `http://localhost` for security. Use the local
> `standalone.html` (via `file://`) when you want the local engine.

## Files

- `standalone.html` — the entire app (HTML + CSS + JS, no build step).
- `index.html` — root redirect to `standalone.html` for GitHub Pages.
- `start-languagetool.bat` — one-click LanguageTool local-server launcher.
