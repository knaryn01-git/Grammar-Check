"""
Grammar & Writing Enhancer
--------------------------
Local Flask app that:
  1. Proxies grammar/spelling checks to the public LanguageTool API
     (open source: https://languagetool.org/  |  https://github.com/languagetool-org/languagetool)
  2. Runs an additional local "writing enhancement" pass with style heuristics
     inspired by the open-source 'write-good' project
     (https://github.com/btford/write-good - MIT) and Hemingway-style metrics.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""
from __future__ import annotations

import os
import re
from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
# Default: the free public LanguageTool API.
# To use a self-hosted LanguageTool server, set LT_API_URL, e.g.:
#   set LT_API_URL=http://localhost:8081/v2/check
LT_API_URL = os.environ.get("LT_API_URL", "https://api.languagetool.org/v2/check")
LT_TIMEOUT = float(os.environ.get("LT_TIMEOUT", "15"))
DEFAULT_LANG = os.environ.get("LT_LANGUAGE", "en-US")

# Hard cap to stay within LanguageTool's free-tier per-request limit (20 000 chars).
MAX_TEXT_LEN = 18_000

# MyMemory free translation API (open, no key, ~5000 words/day per IP).
# Used for back-translation paraphrasing.
MM_API_URL = "https://api.mymemory.translated.net/get"
MM_TIMEOUT = float(os.environ.get("MM_TIMEOUT", "12"))

# Datamuse free open API for synonyms / related words.
DM_API_URL = "https://api.datamuse.com/words"
DM_TIMEOUT = float(os.environ.get("DM_TIMEOUT", "6"))

# Cap rephrase input — keeps things snappy on the free API.
MAX_REPHRASE_LEN = 1500

app = Flask(__name__, static_folder="static", static_url_path="")


# ----------------------------------------------------------------------------
# Grammar / spelling — LanguageTool proxy
# ----------------------------------------------------------------------------
@app.post("/api/check")
def api_check() -> Any:
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    language = payload.get("language") or DEFAULT_LANG
    picky = bool(payload.get("picky", True))

    if not text:
        return jsonify({"matches": [], "stats": _stats(text)})

    if len(text) > MAX_TEXT_LEN:
        return jsonify({"error": f"Text too long ({len(text)} chars). Limit is {MAX_TEXT_LEN}."}), 413

    data = {
        "text": text,
        "language": language,
        "enabledOnly": "false",
    }
    if picky:
        data["level"] = "picky"

    try:
        resp = requests.post(
            LT_API_URL,
            data=data,
            timeout=LT_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"LanguageTool request failed: {exc}"}), 502

    lt = resp.json()
    matches = [_simplify_match(m) for m in lt.get("matches", [])]
    return jsonify({
        "matches": matches,
        "stats": _stats(text),
        "language": lt.get("language", {}).get("name", language),
    })


def _simplify_match(m: dict) -> dict:
    return {
        "message": m.get("message"),
        "shortMessage": m.get("shortMessage") or m.get("rule", {}).get("category", {}).get("name", ""),
        "offset": m.get("offset", 0),
        "length": m.get("length", 0),
        "replacements": [r["value"] for r in m.get("replacements", [])[:6]],
        "ruleId": m.get("rule", {}).get("id"),
        "category": m.get("rule", {}).get("category", {}).get("name"),
        "issueType": m.get("rule", {}).get("issueType", "misspelling"),
    }


# ----------------------------------------------------------------------------
# Local writing enhancement — style heuristics
# ----------------------------------------------------------------------------
WEASEL_WORDS = {
    "many", "various", "very", "fairly", "several", "extremely", "exceedingly",
    "quite", "remarkably", "few", "surprisingly", "mostly", "largely", "huge",
    "tiny", "excellent", "interestingly", "really", "actually", "basically",
    "literally", "just", "perhaps", "maybe", "somewhat", "kind of", "sort of",
}

WORDY_PHRASES = {
    "a large number of": "many",
    "a majority of": "most",
    "a number of": "several",
    "at this point in time": "now",
    "due to the fact that": "because",
    "in order to": "to",
    "in spite of the fact that": "although",
    "in the event that": "if",
    "in the process of": "(omit)",
    "it is important to note that": "(omit)",
    "the fact that": "that",
    "with regard to": "about",
    "with the exception of": "except",
    "for the purpose of": "for",
    "on a regular basis": "regularly",
    "in close proximity to": "near",
    "make a decision": "decide",
    "give consideration to": "consider",
    "has the ability to": "can",
    "is able to": "can",
}

PASSIVE_INDICATORS = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being|got|gotten)\s+(?:\w+ly\s+)?(\w+ed|known|done|made|said|seen|gone|taken|given|written|shown|held|kept|brought|thought|told|left)\b",
    re.IGNORECASE,
)

ADVERB_LY = re.compile(r"\b([A-Za-z]{4,}ly)\b")

# Adverbs that don't count (common safe -ly words)
ADVERB_WHITELIST = {
    "early", "only", "family", "reply", "supply", "apply", "imply", "comply",
    "rely", "july", "italy", "holy", "ugly", "silly", "jelly", "ally",
    "assembly", "anomaly", "monopoly",
}

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


@app.post("/api/enhance")
def api_enhance() -> Any:
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"suggestions": [], "metrics": _metrics("")})

    suggestions: list[dict] = []
    lower = text.lower()

    # Wordy phrases
    for phrase, replacement in WORDY_PHRASES.items():
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", lower):
            suggestions.append({
                "type": "wordy",
                "offset": m.start(),
                "length": len(phrase),
                "message": f"Wordy phrase — consider \u201C{replacement}\u201D.",
                "replacements": [] if replacement == "(omit)" else [replacement],
            })

    # Weasel / filler words
    for word in WEASEL_WORDS:
        for m in re.finditer(rf"\b{re.escape(word)}\b", lower):
            suggestions.append({
                "type": "weasel",
                "offset": m.start(),
                "length": len(word),
                "message": f"\u201C{word}\u201D is vague filler — consider removing or replacing.",
                "replacements": [],
            })

    # Passive voice
    for m in PASSIVE_INDICATORS.finditer(text):
        suggestions.append({
            "type": "passive",
            "offset": m.start(),
            "length": m.end() - m.start(),
            "message": "Passive voice — rewrite in active voice for clarity.",
            "replacements": [],
        })

    # -ly adverbs
    for m in ADVERB_LY.finditer(text):
        word = m.group(1).lower()
        if word in ADVERB_WHITELIST:
            continue
        suggestions.append({
            "type": "adverb",
            "offset": m.start(),
            "length": len(m.group(1)),
            "message": f"Adverb \u201C{m.group(1)}\u201D — strong verbs often work better.",
            "replacements": [],
        })

    # Long sentences
    pos = 0
    for sentence in SENTENCE_SPLIT.split(text):
        words = sentence.split()
        if len(words) >= 25:
            suggestions.append({
                "type": "long-sentence",
                "offset": pos,
                "length": len(sentence),
                "message": f"Long sentence ({len(words)} words) — consider splitting.",
                "replacements": [],
            })
        pos += len(sentence) + 1

    # Sort + dedupe overlapping suggestions of the same type
    suggestions.sort(key=lambda s: (s["offset"], s["length"]))

    return jsonify({"suggestions": suggestions, "metrics": _metrics(text)})


# ----------------------------------------------------------------------------
# Readability metrics
# ----------------------------------------------------------------------------
def _stats(text: str) -> dict:
    words = re.findall(r"\b[\w']+\b", text)
    sentences = [s for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()]
    return {
        "chars": len(text),
        "words": len(words),
        "sentences": len(sentences),
    }


def _metrics(text: str) -> dict:
    base = _stats(text)
    words = re.findall(r"\b[\w']+\b", text)
    sentences = [s for s in SENTENCE_SPLIT.split(text.strip()) if s.strip()]
    syllables = sum(_count_syllables(w) for w in words)

    if not words or not sentences:
        base.update({
            "syllables": syllables,
            "avgWordsPerSentence": 0,
            "fleschReadingEase": 0,
            "fleschKincaidGrade": 0,
            "readingLevel": "—",
        })
        return base

    w = len(words)
    s = len(sentences)
    avg_w_per_s = w / s
    avg_syl_per_w = syllables / w

    flesch = 206.835 - 1.015 * avg_w_per_s - 84.6 * avg_syl_per_w
    fk_grade = 0.39 * avg_w_per_s + 11.8 * avg_syl_per_w - 15.59

    if flesch >= 90:
        level = "Very easy (5th grade)"
    elif flesch >= 80:
        level = "Easy (6th grade)"
    elif flesch >= 70:
        level = "Fairly easy (7th grade)"
    elif flesch >= 60:
        level = "Plain English (8th–9th)"
    elif flesch >= 50:
        level = "Fairly difficult (10th–12th)"
    elif flesch >= 30:
        level = "Difficult (college)"
    else:
        level = "Very difficult (college grad)"

    base.update({
        "syllables": syllables,
        "avgWordsPerSentence": round(avg_w_per_s, 1),
        "fleschReadingEase": round(flesch, 1),
        "fleschKincaidGrade": round(fk_grade, 1),
        "readingLevel": level,
    })
    return base


_VOWELS = "aeiouy"


def _count_syllables(word: str) -> int:
    word = word.lower()
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in _VOWELS
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


# ----------------------------------------------------------------------------
# Rephraser — back-translation + style post-processing
# ----------------------------------------------------------------------------
# Each "style" is a pivot language (or chain) plus optional post-processing.
# Different pivots give meaningfully different rewordings.
REPHRASE_STYLES = {
    "standard": {"pivots": ["fr"],            "post": None,        "label": "Standard"},
    "fluent":   {"pivots": ["de"],            "post": None,        "label": "Fluent"},
    "formal":   {"pivots": ["it"],            "post": "formal",    "label": "Formal"},
    "simple":   {"pivots": ["es"],            "post": "simple",    "label": "Simple"},
    "creative": {"pivots": ["pt", "nl"],      "post": None,        "label": "Creative"},
}

# Contractions to expand for the "formal" style.
FORMAL_EXPANSIONS = {
    r"\bcan't\b": "cannot", r"\bwon't\b": "will not", r"\bshan't\b": "shall not",
    r"\bdon't\b": "do not", r"\bdoesn't\b": "does not", r"\bdidn't\b": "did not",
    r"\bisn't\b": "is not", r"\baren't\b": "are not", r"\bwasn't\b": "was not",
    r"\bweren't\b": "were not", r"\bhasn't\b": "has not", r"\bhaven't\b": "have not",
    r"\bhadn't\b": "had not", r"\bwouldn't\b": "would not", r"\bshouldn't\b": "should not",
    r"\bcouldn't\b": "could not", r"\bmightn't\b": "might not", r"\bmustn't\b": "must not",
    r"\bi'm\b": "I am", r"\byou're\b": "you are", r"\bwe're\b": "we are",
    r"\bthey're\b": "they are", r"\bhe's\b": "he is", r"\bshe's\b": "she is",
    r"\bit's\b": "it is", r"\bthat's\b": "that is", r"\bwhat's\b": "what is",
    r"\bi'll\b": "I will", r"\byou'll\b": "you will", r"\bwe'll\b": "we will",
    r"\bthey'll\b": "they will", r"\bi'd\b": "I would", r"\byou'd\b": "you would",
    r"\bi've\b": "I have", r"\byou've\b": "you have", r"\bwe've\b": "we have",
    r"\bthey've\b": "they have", r"\bgonna\b": "going to", r"\bwanna\b": "want to",
    r"\bkinda\b": "kind of", r"\bsorta\b": "sort of",
}

# Simple-style swaps: replace long words with shorter equivalents.
SIMPLE_SWAPS = {
    r"\butilize\b": "use", r"\butilized\b": "used", r"\butilization\b": "use",
    r"\bcommence\b": "start", r"\bcommenced\b": "started",
    r"\bterminate\b": "end", r"\bterminated\b": "ended",
    r"\bendeavor\b": "try", r"\bassist\b": "help", r"\bassistance\b": "help",
    r"\bdemonstrate\b": "show", r"\bsubsequently\b": "later",
    r"\bnevertheless\b": "still", r"\btherefore\b": "so",
    r"\baccordingly\b": "so", r"\bregarding\b": "about",
    r"\bnumerous\b": "many", r"\bsufficient\b": "enough",
    r"\bobtain\b": "get", r"\bpurchase\b": "buy",
    r"\bfacilitate\b": "help", r"\bimplement\b": "do",
    r"\bapproximately\b": "about", r"\bconsequently\b": "so",
}


def _translate(text: str, source: str, target: str) -> str:
    """Single MyMemory translation hop. Returns translated text or raises."""
    params = {"q": text, "langpair": f"{source}|{target}"}
    r = requests.get(MM_API_URL, params=params, timeout=MM_TIMEOUT,
                     headers={"Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    rd = data.get("responseData") or {}
    out = (rd.get("translatedText") or "").strip()
    if not out:
        raise RuntimeError(data.get("responseDetails") or "Empty translation response")
    # MyMemory sometimes returns an error message in the translated field
    if out.upper().startswith("MYMEMORY WARNING") or out.upper().startswith("QUERY LENGTH"):
        raise RuntimeError(out)
    return out


def _back_translate(text: str, pivots: list[str]) -> str:
    """Translate en -> pivot[0] -> pivot[1] -> ... -> en."""
    current = text
    source = "en"
    for p in pivots:
        current = _translate(current, source, p)
        source = p
    return _translate(current, source, "en")


def _apply_style(text: str, style: str | None) -> str:
    if style == "formal":
        for pat, rep in FORMAL_EXPANSIONS.items():
            text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    elif style == "simple":
        for pat, rep in SIMPLE_SWAPS.items():
            text = re.sub(pat, rep, text, flags=re.IGNORECASE)
    # Tidy spacing/punctuation
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


@app.post("/api/rephrase")
def api_rephrase() -> Any:
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    requested = payload.get("styles") or list(REPHRASE_STYLES.keys())

    if not text:
        return jsonify({"results": []})
    if len(text) > MAX_REPHRASE_LEN:
        return jsonify({
            "error": f"Text too long for rephrasing ({len(text)} chars). Limit is {MAX_REPHRASE_LEN}."
        }), 413

    results = []
    for style in requested:
        cfg = REPHRASE_STYLES.get(style)
        if not cfg:
            continue
        try:
            rewritten = _back_translate(text, cfg["pivots"])
            rewritten = _apply_style(rewritten, cfg["post"])
            results.append({
                "style": style,
                "label": cfg["label"],
                "text": rewritten,
                "unchanged": rewritten.strip().lower() == text.strip().lower(),
            })
        except Exception as exc:  # noqa: BLE001 — surface any backend issue gracefully
            results.append({
                "style": style,
                "label": cfg["label"],
                "text": "",
                "error": str(exc),
            })
    return jsonify({"results": results})


# ----------------------------------------------------------------------------
# Synonyms — Datamuse open API
# ----------------------------------------------------------------------------
@app.get("/api/synonyms")
def api_synonyms() -> Any:
    word = (request.args.get("word") or "").strip().lower()
    if not word or not re.fullmatch(r"[a-z][a-z'-]{0,30}", word):
        return jsonify({"word": word, "synonyms": [], "related": []})

    out = {"word": word, "synonyms": [], "related": []}
    try:
        # Direct synonyms
        r = requests.get(DM_API_URL, params={"rel_syn": word, "max": 12},
                         timeout=DM_TIMEOUT)
        r.raise_for_status()
        out["synonyms"] = [w["word"] for w in r.json()]

        # Means-like (fallback / broader)
        if len(out["synonyms"]) < 6:
            r2 = requests.get(DM_API_URL,
                              params={"ml": word, "max": 12, "md": "p"},
                              timeout=DM_TIMEOUT)
            r2.raise_for_status()
            seen = set(out["synonyms"])
            for w in r2.json():
                if w["word"] != word and w["word"] not in seen:
                    out["related"].append(w["word"])
                    seen.add(w["word"])
                    if len(out["related"]) >= 8:
                        break
    except requests.RequestException as exc:
        out["error"] = f"Synonym lookup failed: {exc}"
    return jsonify(out)


# ----------------------------------------------------------------------------
# Static UI
# ----------------------------------------------------------------------------
@app.get("/")
def index() -> Any:
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"\n  Grammar & Writing Enhancer running at  http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=False)
