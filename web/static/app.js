(() => {
  const $ = (id) => document.getElementById(id);
  const consoleEl = $("console");
  const runIdEl = $("run-id");
  const statsEl = $("stats");
  const fileBadgesEl = $("file-badges");
  const previewEl = $("preview");
  const form = $("run-form");
  const cancelBtn = $("cancel-run");
  let selectedFilePath = null;
  let currentRunId = null;

  // Escape HTML for safe insertion into <code> blocks
  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- Persistence helpers (localStorage) ---
  const LS_PREFIX = 'le_last_';
  const SAVE_FIELDS = [
    'MODEL_ID',
    'MODEL_TEMPERATURE',
    'MAX_NORMS_PER_5K',
    'INPUT_PROMPTFILE',
    'INPUT_GLOSSARYFILE',
    'INPUT_EXAMPLESFILE',
    'INPUT_SEMANTCSFILE',
    'INPUT_TEACHFILE',
  ];
  const lsKey = (id) => LS_PREFIX + id;
  const saveValue = (id, value) => {
    try { localStorage.setItem(lsKey(id), value ?? ''); } catch {}
  };
  const loadValue = (id) => {
    try { return localStorage.getItem(lsKey(id)); } catch { return null; }
  };
  const applySavedToInput = (id) => {
    const v = loadValue(id);
    if (v !== null && $(id)) $(id).value = v;
  };
  const applySavedToSelect = (id) => {
    const saved = loadValue(id);
    if (!saved) return;
    const sel = $(id);
    if (!sel) return;
    for (const opt of sel.options) {
      if (opt.value === saved) {
        sel.value = saved;
        break;
      }
    }
  };

  async function loadChoices() {
    try {
      const res = await fetch('/choices');
      const data = await res.json();
      const selects = [
        ["INPUT_PROMPTFILE", data.input_promptfiles],
        ["INPUT_GLOSSARYFILE", data.input_glossaryfiles],
        ["INPUT_EXAMPLESFILE", data.input_examplefiles],
        ["INPUT_SEMANTCSFILE", data.input_semanticsfiles],
        ["INPUT_TEACHFILE", data.input_teachfiles],
      ];
      for (const [id, options] of selects) {
        const sel = $(id);
        sel.innerHTML = '';
        const noneOpt = document.createElement('option');
        noneOpt.value = '';
        noneOpt.textContent = 'None';
        sel.appendChild(noneOpt);
        for (const f of options) {
          const opt = document.createElement('option');
          opt.value = f;
          opt.textContent = f;
          sel.appendChild(opt);
        }
        // After populating, re-apply saved selection if any
        applySavedToSelect(id);
      }
      // badges
      const badgesWrap = $("model-badges");
      badgesWrap.innerHTML = '';
      for (const m of (data.pastmodels || [])) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'text-xs bg-gray-200 hover:bg-gray-300 px-2 py-1 rounded dark:bg-gray-700 dark:hover:bg-gray-600 dark:text-gray-100';
        b.textContent = m;
        b.addEventListener('click', () => {
          $("MODEL_ID").value = m;
          saveValue('MODEL_ID', m);
        });
        badgesWrap.appendChild(b);
      }
    } catch (e) {
      console.error('choices error', e);
    }
  }

  function appendConsole(line) {
    consoleEl.textContent += line + "\n";
    consoleEl.scrollTop = consoleEl.scrollHeight;
  }

  async function pollStatus(runId) {
    try {
      const res = await fetch(`/runs/${runId}/status`);
      const data = await res.json();
      if (data.stats) {
        statsEl.textContent = JSON.stringify(data.stats, null, 2);
      }
      if (data.status === 'finished' || data.status === 'error' || data.status === 'canceled') {
        await loadFiles(runId);
        if (cancelBtn) cancelBtn.disabled = true;
      } else {
        setTimeout(() => pollStatus(runId), 2000);
      }
    } catch (e) {
      console.error('status error', e);
      setTimeout(() => pollStatus(runId), 3000);
    }
  }

  async function loadFiles(runId) {
    try {
      const res = await fetch(`/runs/${runId}/files`);
      const files = await res.json();
      if (fileBadgesEl) fileBadgesEl.innerHTML = '';
      const createdBadges = [];
      const makeBadge = (f) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.dataset.path = f.path;
  btn.className = 'text-xs px-2 py-1 rounded-full border bg-gray-100 text-gray-800 border-gray-300 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-100 dark:border-gray-600 dark:hover:bg-gray-600';
        const baseName = f.path.split('/').pop();
        btn.textContent = baseName || f.path;
        const applySelected = () => {
          const isSel = selectedFilePath === f.path;
          if (isSel) {
            btn.classList.remove('bg-gray-100','text-gray-800','border-gray-300');
            btn.classList.add('bg-blue-600','text-white','border-blue-600');
          } else {
            btn.classList.add('bg-gray-100','text-gray-800','border-gray-300');
            btn.classList.remove('bg-blue-600','text-white','border-blue-600');
          }
        };
        btn.addEventListener('click', async () => {
          selectedFilePath = f.path;
          // Update all badges selection state
          if (fileBadgesEl) {
            Array.from(fileBadgesEl.children).forEach((el) => {
              const p = el.dataset.path;
              if (!p) return;
              if (p === selectedFilePath) {
                el.classList.remove('bg-gray-100','text-gray-800','border-gray-300','dark:bg-gray-700','dark:text-gray-100','dark:border-gray-600');
                el.classList.add('bg-blue-600','text-white','border-blue-600');
              } else {
                el.classList.add('bg-gray-100','text-gray-800','border-gray-300','dark:bg-gray-700','dark:text-gray-100','dark:border-gray-600');
                el.classList.remove('bg-blue-600','text-white','border-blue-600');
              }
            });
          }
          const resp = await fetch(`/runs/${runId}/file?path=${encodeURIComponent(f.path)}`);
          const ct = resp.headers.get('content-type') || '';
          if (ct.startsWith('text/') || ct.includes('application/json') || f.path.toLowerCase().endsWith('.md')) {
            const text = await resp.text();
            // Render Markdown
            if (f.path.toLowerCase().endsWith('.md') || ct.includes('text/markdown')) {
              try {
                const rawHtml = marked.parse(text, { mangle: false, headerIds: true });
                const safeHtml = DOMPurify.sanitize(rawHtml);
                previewEl.innerHTML = safeHtml;
                // highlight code blocks
                document.querySelectorAll('#preview pre code').forEach((el) => {
                  try { hljs.highlightElement(el); } catch {}
                });
              } catch {
                previewEl.textContent = text;
              }
            } else if (ct.includes('application/json') || f.path.toLowerCase().endsWith('.json')) {
              // Pretty JSON
              try {
                const obj = JSON.parse(text);
                const pretty = JSON.stringify(obj, null, 2);
                previewEl.innerHTML = `<pre class="whitespace-pre-wrap"><code class="language-json">${escapeHtml(pretty)}</code></pre>`;
                document.querySelectorAll('#preview pre code').forEach((el) => {
                  try { hljs.highlightElement(el); } catch {}
                });
              } catch {
                previewEl.innerHTML = `<pre class="whitespace-pre-wrap"><code>${escapeHtml(text)}</code></pre>`;
              }
            } else {
              // Plain text
              previewEl.innerHTML = `<pre class="whitespace-pre-wrap"><code>${escapeHtml(text)}</code></pre>`;
            }
          } else {
            previewEl.textContent = '[Binary file] Downloading...';
            window.location.href = `/runs/${runId}/file?path=${encodeURIComponent(f.path)}`;
          }
        });
        // Initialize selection state
        applySelected();
        createdBadges.push({ btn, file: f });
        return btn;
      };
      for (const f of files) {
        const badge = makeBadge(f);
        if (fileBadgesEl) fileBadgesEl.appendChild(badge);
      }
      // If nothing selected yet, auto-open the first readable file (preferring json/log/txt)
      if (!selectedFilePath && createdBadges.length) {
        const preferExt = ['.json', '.jsonl', '.ndjson', '.log', '.txt', '.md'];
        const findPreferred = () => {
          for (const ext of preferExt) {
            const found = createdBadges.find(({ file }) => file.path.toLowerCase().endsWith(ext));
            if (found) return found;
          }
          return createdBadges[0];
        };
        const target = findPreferred();
        if (target) target.btn.click();
      }
    } catch (e) {
      console.error('files error', e);
    }
  }

  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    $("form-error").textContent = '';
    consoleEl.textContent = '';
    statsEl.textContent = '';
  if (fileBadgesEl) fileBadgesEl.innerHTML = '';
    previewEl.textContent = '';

    // Save current form values
    for (const fid of SAVE_FIELDS) {
      const el = $(fid);
      if (el) saveValue(fid, el.value);
    }

    const formData = new FormData(form);
    try {
      const res = await fetch('/run', { method: 'POST', body: formData });
      if (!res.ok) {
        const msg = await res.text();
        $("form-error").textContent = msg || 'Failed to start run';
        return;
      }
      const data = await res.json();
  const runId = data.run_id;
  currentRunId = runId;
  runIdEl.textContent = `Run: ${runId}`;
  if (cancelBtn) cancelBtn.disabled = false;

      // SSE
      const sse = new EventSource(`/runs/${runId}/logs`);
      sse.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload.event === 'complete') {
            sse.close();
            pollStatus(runId);
            if (cancelBtn) cancelBtn.disabled = true;
          } else if (payload.line) {
            appendConsole(payload.line);
          }
        } catch {
          appendConsole(evt.data);
        }
      };
      sse.onerror = () => {
        // non-fatal for workshop
      };

      pollStatus(runId);
    } catch (e) {
      $("form-error").textContent = 'Network error starting run';
    }
  });

  // Restore saved inputs before loading choices (for text/number inputs)
  applySavedToInput('MODEL_ID');
  applySavedToInput('MODEL_TEMPERATURE');
  applySavedToInput('MAX_NORMS_PER_5K');

  // Persist on change for all save fields (except file input)
  for (const fid of SAVE_FIELDS) {
    const el = $(fid);
    if (el && fid !== 'input_document') {
      el.addEventListener('change', () => saveValue(fid, el.value));
      el.addEventListener('input', () => saveValue(fid, el.value));
    }
  }

  loadChoices();

  if (cancelBtn) {
    cancelBtn.addEventListener('click', async () => {
      if (!currentRunId) return;
      cancelBtn.disabled = true;
      try {
        await fetch(`/runs/${currentRunId}/cancel`, { method: 'POST' });
      } catch (e) {
        // ignore
      }
    });
  }
})();
