(() => {
  const $ = (id) => document.getElementById(id);
  const consoleEl = $("console");
  const runIdEl = $("run-id");
  const statsEl = $("stats");
  const fileListEl = $("file-list");
  const previewEl = $("preview");
  const form = $("run-form");

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
      }
      // badges
      const badgesWrap = $("model-badges");
      badgesWrap.innerHTML = '';
      for (const m of (data.pastmodels || [])) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'text-xs bg-gray-200 hover:bg-gray-300 px-2 py-1 rounded';
        b.textContent = m;
        b.addEventListener('click', () => { $("MODEL_ID").value = m; });
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
      if (data.status === 'finished' || data.status === 'error') {
        await loadFiles(runId);
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
      fileListEl.innerHTML = '';
      for (const f of files) {
        const li = document.createElement('li');
        li.className = 'px-3 py-2 hover:bg-gray-50 cursor-pointer';
        li.textContent = `${f.path} (${f.size} B)`;
        li.addEventListener('click', async () => {
          const resp = await fetch(`/runs/${runId}/file?path=${encodeURIComponent(f.path)}`);
          const ct = resp.headers.get('content-type') || '';
          if (ct.startsWith('text/') || ct.includes('application/json')) {
            const text = await resp.text();
            previewEl.textContent = text;
          } else {
            previewEl.textContent = '[Binary file] Downloading...';
            window.location.href = `/runs/${runId}/file?path=${encodeURIComponent(f.path)}`;
          }
        });
        fileListEl.appendChild(li);
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
    fileListEl.innerHTML = '';
    previewEl.textContent = '';

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
      runIdEl.textContent = `Run: ${runId}`;

      // SSE
      const sse = new EventSource(`/runs/${runId}/logs`);
      sse.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          if (payload.event === 'complete') {
            sse.close();
            pollStatus(runId);
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

  loadChoices();
})();
