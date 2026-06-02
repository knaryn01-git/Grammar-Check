// ---------------------------------------------------------------------------
// Grammar & Writing Enhancer — frontend
// ---------------------------------------------------------------------------
const editor      = document.getElementById("editor");
const highlights  = document.getElementById("highlights");
const checkBtn    = document.getElementById("checkBtn");
const clearBtn    = document.getElementById("clearBtn");
const autoCheck   = document.getElementById("autoCheck");
const pickyCb     = document.getElementById("picky");
const langSel     = document.getElementById("language");
const statusEl    = document.getElementById("status");
const grammarList = document.getElementById("grammarList");
const styleList   = document.getElementById("styleList");
const grammarCount= document.getElementById("grammarCount");
const styleCount  = document.getElementById("styleCount");

const mWords = document.getElementById("m-words");
const mSent  = document.getElementById("m-sent");
const mAvg   = document.getElementById("m-avg");
const mEase  = document.getElementById("m-ease");
const mGrade = document.getElementById("m-grade");
const mLevel = document.getElementById("m-level");

const rephrasePanel   = document.getElementById("rephrasePanel");
const rephraseBtn     = document.getElementById("rephraseBtn");
const rephraseResults = document.getElementById("rephraseResults");
const styleBtns       = document.querySelectorAll(".style-btn");

const synonymPopup = document.getElementById("synonymPopup");
const popupWord    = document.getElementById("popupWord");
const popupBody    = document.getElementById("popupBody");
const popupClose   = document.getElementById("popupClose");

let state = { grammar: [], style: [], lastText: "", inFlight: null };
let activeStyles = new Set(["standard"]);

// ---------- Tabs ----------
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    const which = t.dataset.tab;
    grammarList.classList.toggle("hidden", which !== "grammar");
    styleList.classList.toggle("hidden", which !== "style");
    rephrasePanel.classList.toggle("hidden", which !== "rephrase");
  });
});

// ---------- Editor / highlight overlay sync ----------
function syncScroll() {
  highlights.scrollTop  = editor.scrollTop;
  highlights.scrollLeft = editor.scrollLeft;
}
editor.addEventListener("scroll", syncScroll);

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function severityFor(m) {
  if (m._kind === "style") return "style";
  const issue = (m.issueType || "").toLowerCase();
  if (issue === "misspelling" || issue === "grammar") return "err";
  return "warn";
}

function renderHighlights(text, items) {
  // Build a single non-overlapping list of marks, sorted by offset
  const ranges = items
    .map((m, i) => ({
      start: m.offset,
      end: m.offset + m.length,
      cls: severityFor(m),
      idx: i,
    }))
    .filter((r) => r.end > r.start && r.start >= 0 && r.end <= text.length)
    .sort((a, b) => a.start - b.start || b.end - a.end);

  // Skip ranges that overlap with an earlier one (keep the first)
  const accepted = [];
  let cursor = -1;
  for (const r of ranges) {
    if (r.start >= cursor) {
      accepted.push(r);
      cursor = r.end;
    }
  }

  let html = "";
  let pos = 0;
  for (const r of accepted) {
    html += escapeHtml(text.slice(pos, r.start));
    html += `<mark class="${r.cls}">${escapeHtml(text.slice(r.start, r.end))}</mark>`;
    pos = r.end;
  }
  html += escapeHtml(text.slice(pos));
  // Trailing newline padding so the last line aligns
  highlights.innerHTML = html + "\n";
}

// ---------- Apply replacement ----------
function applyReplacement(offset, length, value) {
  const text = editor.value;
  editor.value = text.slice(0, offset) + value + text.slice(offset + length);
  editor.focus();
  editor.selectionStart = editor.selectionEnd = offset + value.length;
  scheduleCheck(50);
}

// ---------- Suggestion card ----------
function renderSuggestionList(target, items, opts) {
  target.innerHTML = "";
  if (!items.length) {
    target.innerHTML = `<div class="empty"><span class="ok-icon">✓</span>${opts.emptyMsg}</div>`;
    return;
  }
  for (const m of items) {
    const sev = severityFor(m);
    const card = document.createElement("div");
    card.className = `suggestion ${sev}`;
    const orig = editor.value.slice(m.offset, m.offset + m.length);

    const repls = (m.replacements || []).map(
      (r) => `<span class="repl" data-r="${escapeHtml(r)}">${escapeHtml(r)}</span>`
    ).join("");

    card.innerHTML = `
      <div class="cat">${escapeHtml(m.category || m.type || "issue")}</div>
      <div class="msg">${escapeHtml(m.message || "")}</div>
      ${orig ? `<div class="orig">${escapeHtml(orig)}</div>` : ""}
      ${repls ? `<div class="repls">${repls}</div>` : ""}
    `;

    card.addEventListener("click", (e) => {
      const target = e.target.closest(".repl");
      if (target) {
        applyReplacement(m.offset, m.length, target.dataset.r);
        return;
      }
      // Click anywhere else: jump editor selection to the issue
      editor.focus();
      editor.setSelectionRange(m.offset, m.offset + m.length);
    });
    target.appendChild(card);
  }
}

// ---------- Metrics ----------
function renderMetrics(metrics) {
  mWords.textContent = metrics.words ?? 0;
  mSent.textContent  = metrics.sentences ?? 0;
  mAvg.textContent   = metrics.avgWordsPerSentence ?? 0;
  mEase.textContent  = metrics.fleschReadingEase ?? 0;
  mGrade.textContent = metrics.fleschKincaidGrade ?? 0;
  mLevel.textContent = metrics.readingLevel ?? "—";
}

// ---------- Check pipeline ----------
async function runCheck() {
  const text = editor.value;
  state.lastText = text;
  if (!text.trim()) {
    state.grammar = [];
    state.style = [];
    renderHighlights("", []);
    renderSuggestionList(grammarList, [], { emptyMsg: "No text to check." });
    renderSuggestionList(styleList, [],  { emptyMsg: "No text to check." });
    renderMetrics({ words: 0, sentences: 0 });
    grammarCount.textContent = "0";
    styleCount.textContent = "0";
    statusEl.textContent = "";
    return;
  }

  statusEl.textContent = "Checking…";
  statusEl.className = "status";

  const body = JSON.stringify({
    text,
    language: langSel.value,
    picky: pickyCb.checked,
  });
  const opts = { method: "POST", headers: { "Content-Type": "application/json" }, body };

  try {
    const [gRes, sRes] = await Promise.all([
      fetch("/api/check", opts),
      fetch("/api/enhance", opts),
    ]);

    if (!gRes.ok) {
      const err = await gRes.json().catch(() => ({}));
      throw new Error(err.error || `Grammar check failed (${gRes.status})`);
    }
    const gData = await gRes.json();
    const sData = await sRes.json();

    // Tag style items so severityFor() picks the right class
    const styleItems = (sData.suggestions || []).map((s) => ({ ...s, _kind: "style" }));

    state.grammar = gData.matches || [];
    state.style = styleItems;

    renderHighlights(text, [...state.grammar, ...state.style]);
    renderSuggestionList(grammarList, state.grammar, {
      emptyMsg: "No grammar or spelling issues found.",
    });
    renderSuggestionList(styleList, state.style, {
      emptyMsg: "No style suggestions — looks tight!",
    });
    renderMetrics(sData.metrics || gData.stats || {});

    grammarCount.textContent = state.grammar.length;
    styleCount.textContent   = state.style.length;
    statusEl.textContent = `Checked · ${gData.language || langSel.value}`;
    statusEl.className = "status ok";
  } catch (err) {
    statusEl.textContent = err.message || "Check failed.";
    statusEl.className = "status error";
  }
}

// ---------- Debounce ----------
let debounceTimer = null;
function scheduleCheck(delay = 900) {
  if (!autoCheck.checked) return;
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runCheck, delay);
}

editor.addEventListener("input", () => {
  // Re-render highlights immediately based on the last results, adjusted only by truncation
  renderHighlights(editor.value, [...state.grammar, ...state.style].filter(
    (m) => m.offset + m.length <= editor.value.length
  ));
  scheduleCheck();
});

checkBtn.addEventListener("click", () => runCheck());
clearBtn.addEventListener("click", () => {
  editor.value = "";
  runCheck();
});
pickyCb.addEventListener("change", () => editor.value && runCheck());
langSel.addEventListener("change", () => editor.value && runCheck());

// Initial empty state
renderSuggestionList(grammarList, [], { emptyMsg: "Start typing to see grammar suggestions." });
renderSuggestionList(styleList,   [], { emptyMsg: "Start typing to see style suggestions." });
renderMetrics({});

// ---------- Rephrase ----------
styleBtns.forEach((btn) => {
  btn.addEventListener("click", () => {
    const style = btn.dataset.style;
    if (activeStyles.has(style) && activeStyles.size > 1) {
      activeStyles.delete(style);
      btn.classList.remove("active");
    } else {
      activeStyles.add(style);
      btn.classList.add("active");
    }
  });
});

rephraseBtn.addEventListener("click", async () => {
  let text;
  const selStart = editor.selectionStart;
  const selEnd   = editor.selectionEnd;
  if (selEnd > selStart) {
    text = editor.value.slice(selStart, selEnd).trim();
  } else {
    text = editor.value.trim();
  }
  if (!text) {
    rephraseResults.innerHTML = `<div class="empty">Type or select some text first.</div>`;
    return;
  }
  if (text.length > 1500) {
    rephraseResults.innerHTML = `<div class="empty">Text is too long (${text.length} chars). Limit is 1500 for rephrasing.</div>`;
    return;
  }

  rephraseResults.innerHTML = `<div class="spinner">Rephrasing… (uses MyMemory open API)</div>`;
  rephraseBtn.disabled = true;

  try {
    const res = await fetch("/api/rephrase", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, styles: [...activeStyles] }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `Rephrase failed (${res.status})`);

    rephraseResults.innerHTML = "";
    for (const r of data.results) {
      const card = document.createElement("div");
      let cls = "rephrase-card";
      if (r.error) cls += " err";
      else if (r.unchanged) cls += " unchanged";
      card.className = cls;
      card.innerHTML = `
        <div class="style-label">${escapeHtml(r.label)}${r.unchanged ? " · no change" : ""}</div>
        <div class="text">${escapeHtml(r.error ? `⚠ ${r.error}` : r.text)}</div>
        ${r.error ? "" : `
          <div class="actions">
            <button data-act="replace">Replace</button>
            <button data-act="copy">Copy</button>
          </div>`}
      `;
      card.addEventListener("click", (e) => {
        const act = e.target.closest("button")?.dataset.act;
        if (act === "replace") {
          if (selEnd > selStart) {
            editor.setRangeText(r.text, selStart, selEnd, "end");
          } else {
            editor.value = r.text;
          }
          editor.focus();
          scheduleCheck(100);
        } else if (act === "copy") {
          navigator.clipboard.writeText(r.text).catch(() => {});
          e.target.textContent = "Copied!";
          setTimeout(() => (e.target.textContent = "Copy"), 1200);
        }
      });
      rephraseResults.appendChild(card);
    }
  } catch (err) {
    rephraseResults.innerHTML = `<div class="empty">⚠ ${escapeHtml(err.message)}</div>`;
  } finally {
    rephraseBtn.disabled = false;
  }
});

// ---------- Synonyms popup (double-click any word) ----------
function findWordAt(text, pos) {
  if (pos < 0 || pos > text.length) return null;
  const isWordCh = (c) => /[A-Za-z'-]/.test(c || "");
  let s = pos, e = pos;
  if (!isWordCh(text[s]) && s > 0 && isWordCh(text[s - 1])) s--;
  if (!isWordCh(text[s])) return null;
  while (s > 0 && isWordCh(text[s - 1])) s--;
  while (e < text.length && isWordCh(text[e])) e++;
  const word = text.slice(s, e).replace(/^[-']+|[-']+$/g, "");
  if (!word) return null;
  return { word, start: s, end: e };
}

function showPopupNear(x, y) {
  synonymPopup.classList.remove("hidden");
  const r = synonymPopup.getBoundingClientRect();
  const maxX = window.innerWidth - r.width - 10;
  const maxY = window.innerHeight - r.height - 10;
  synonymPopup.style.left = Math.min(x, maxX) + "px";
  synonymPopup.style.top  = Math.min(y + 16, maxY) + "px";
}

async function openSynonyms(word, anchorX, anchorY, range) {
  popupWord.textContent = word;
  popupBody.innerHTML = `<div class="spinner">Looking up…</div>`;
  showPopupNear(anchorX, anchorY);

  try {
    const res = await fetch(`/api/synonyms?word=${encodeURIComponent(word.toLowerCase())}`);
    const data = await res.json();
    const syns = data.synonyms || [];
    const rel  = data.related || [];

    const buildChips = (arr) =>
      arr.map((w) => `<span class="syn-chip" data-r="${escapeHtml(w)}">${escapeHtml(w)}</span>`).join("");

    let html = "";
    if (syns.length) html += `<span class="group-label">Synonyms</span>${buildChips(syns)}`;
    if (rel.length)  html += `<span class="group-label">Related</span>${buildChips(rel)}`;
    if (!syns.length && !rel.length)
      html = `<div class="syn-empty">No synonyms found.</div>`;

    popupBody.innerHTML = html;
    popupBody.querySelectorAll(".syn-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const replacement = chip.dataset.r;
        // Preserve capitalization of original
        const orig = editor.value.slice(range.start, range.end);
        const cased = orig[0] === orig[0].toUpperCase()
          ? replacement[0].toUpperCase() + replacement.slice(1)
          : replacement;
        editor.setRangeText(cased, range.start, range.end, "end");
        synonymPopup.classList.add("hidden");
        editor.focus();
        scheduleCheck(100);
      });
    });
  } catch (err) {
    popupBody.innerHTML = `<div class="syn-empty">⚠ ${escapeHtml(err.message)}</div>`;
  }
}

editor.addEventListener("dblclick", (e) => {
  const pos = editor.selectionStart;
  const hit = findWordAt(editor.value, pos);
  if (!hit) return;
  openSynonyms(hit.word, e.clientX, e.clientY, hit);
});

popupClose.addEventListener("click", () => synonymPopup.classList.add("hidden"));
document.addEventListener("click", (e) => {
  if (!synonymPopup.contains(e.target) && e.target !== editor) {
    synonymPopup.classList.add("hidden");
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") synonymPopup.classList.add("hidden");
});

// Demo text for first-time users
editor.value =
  "This is a example sentence which was wrote to demonstrate how the tool works. " +
  "In order to make a decision about whether or not to use it, you should literally just try it out. " +
  "The cake was eaten by the children very quickly.";
runCheck();
