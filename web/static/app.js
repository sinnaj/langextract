(() => {
  const $ = (id) => document.getElementById(id);
  const consoleEl = $("console");
  const runIdEl = $("run-id");
  const statsEl = $("stats");
  const inputPanel = $("input-panel");
  const previewContainer = $("preview-container");
  const columnSwitch = $("column-switch");
  const previewPanels = $("preview-panels");
  const form = $("run-form");
  const cancelBtn = $("cancel-run");
  
  // State management
  let selectedFilePaths = [null, null, null]; // Track selected files for each panel
  let currentRunId = null;
  let isInputPanelCollapsed = false;
  let currentColumnCount = 1;
  let previewOptimizers = []; // Array of optimizers for each panel

  // Initialize performance optimizers
  let consoleOptimizer = null;

  // Initialize optimizers when elements are available
  document.addEventListener('DOMContentLoaded', () => {
    if (consoleEl) {
      consoleOptimizer = new ConsoleOptimizer(consoleEl, {
        maxLines: 500,
        autoScroll: true,
        debounceMs: 16
      });
      
      // Update console stats periodically
      setInterval(() => {
        if (consoleOptimizer) {
          const stats = consoleOptimizer.getStats();
          const statsEl = $('console-stats');
          if (statsEl) {
            const wrapIndicator = stats.wordWrap ? '↩️' : '↔️';
            statsEl.textContent = `${stats.totalLines} lines ${wrapIndicator}`;
          }
          // Update word wrap button opacity
          const wordWrapBtn = $('console-word-wrap');
          if (wordWrapBtn) {
            wordWrapBtn.style.opacity = stats.wordWrap ? '1' : '0.5';
          }
        }
      }, 1000);
    }
    
    // Initialize preview optimizers for each panel
    initializePreviewPanels();
    
    // Initialize panel controls
    initializePanelControls();
  });

  // Initialize preview optimizers for each panel
  function initializePreviewPanels() {
    const panels = document.querySelectorAll('.preview-panel');
    panels.forEach((panel, index) => {
      const previewEl = panel.querySelector('.preview');
      if (previewEl) {
        const optimizer = new PreviewOptimizer(previewEl, {
          maxPreviewSize: 1000000, // 1MB
          chunkSize: 100000, // 100KB
          maxInitialLines: 1000
        });
        previewOptimizers[index] = optimizer;
        
        // Make the first optimizer globally available for backward compatibility
        if (index === 0) {
          window.previewOptimizer = optimizer;
        }
      }
    });
  }

  // Initialize panel controls
  function initializePanelControls() {
    // Collapse toggle buttons
    document.querySelectorAll('.collapse-toggle').forEach(btn => {
      btn.addEventListener('click', toggleInputPanel);
    });
    
    // Column switch buttons
    document.querySelectorAll('#column-switch button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const colCount = parseInt(e.target.id.split('-')[1]);
        setColumnCount(colCount);
      });
    });
    
    // Console settings
    const consoleSettingsBtn = $('console-settings');
    if (consoleSettingsBtn) {
      consoleSettingsBtn.addEventListener('click', () => {
        if (consoleOptimizer) {
          const currentMax = consoleOptimizer.options.maxLines;
          const newMax = prompt('Max console lines:', currentMax);
          if (newMax && !isNaN(newMax)) {
            consoleOptimizer.setMaxLines(parseInt(newMax));
          }
        }
      });
    }

    // Word wrap toggle
    const consoleWordWrapBtn = $('console-word-wrap');
    if (consoleWordWrapBtn) {
      consoleWordWrapBtn.addEventListener('click', () => {
        if (consoleOptimizer) {
          consoleOptimizer.toggleWordWrap();
          const stats = consoleOptimizer.getStats();
          consoleWordWrapBtn.style.opacity = stats.wordWrap ? '1' : '0.5';
        }
      });
    }
    
    // Initialize existing functionality for each panel
    initializePanelButtons();
    
    // UBERMODE toggle buttons
    document.querySelectorAll('.ubermode-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const panelIndex = Array.from(document.querySelectorAll('.preview-panel')).indexOf(e.target.closest('.preview-panel'));
        const optimizer = previewOptimizers[panelIndex];
        if (optimizer) {
          const isEnabled = optimizer.toggleUberMode();
          updateUberModeButton(btn, isEnabled);
          
          // Show/hide stats section
          const statsSection = document.querySelector('.ubermode-stats');
          if (statsSection) {
            if (isEnabled) {
              statsSection.classList.remove('hidden');
            } else {
              statsSection.classList.add('hidden');
            }
          }
        }
      });
    });
    
    // Stats collapsible functionality
    document.querySelectorAll('.stats-header').forEach(header => {
      header.addEventListener('click', (e) => {
        const isExpanded = header.getAttribute('data-expanded') === 'true';
        const content = header.nextElementSibling;
        const toggle = header.querySelector('.stats-toggle');
        
        if (isExpanded) {
          content.style.display = 'none';
          toggle.style.transform = 'rotate(-90deg)';
          header.setAttribute('data-expanded', 'false');
        } else {
          content.style.display = 'block';
          toggle.style.transform = 'rotate(0deg)';
          header.setAttribute('data-expanded', 'true');
        }
      });
    });
  }
  
  // Initialize buttons for each panel
  function initializePanelButtons() {
    document.querySelectorAll('.preview-panel').forEach((panel, index) => {
      // Hide certain controls on secondary panels (2 and 3)
      if (index > 0) {
        const collapseBtn = panel.querySelector('.collapse-toggle');
        if (collapseBtn) collapseBtn.classList.add('hidden');
        const loadExistingRunBtnHidden = panel.querySelector('.load-existing-run');
        if (loadExistingRunBtnHidden) loadExistingRunBtnHidden.classList.add('hidden');
        const runSelectorWrap = panel.querySelector('.run-selector');
        if (runSelectorWrap) runSelectorWrap.classList.add('hidden');
      }
      
      // Search functionality
      const searchBtn = panel.querySelector('.preview-search');
      if (searchBtn && !searchBtn.hasAttribute('data-initialized')) {
        searchBtn.setAttribute('data-initialized', 'true');
        searchBtn.addEventListener('click', () => {
          const query = prompt('Search in file:');
          if (query && previewOptimizers[index]) {
            const results = previewOptimizers[index].search(query);
            const count = Array.isArray(results) ? results.length : 0;
            alert(count > 0 ? `Found ${count} matches` : 'No matches found');
          }
        });
      }
      
      // Load existing run functionality
      const loadExistingRunBtn = panel.querySelector('.load-existing-run');
      const runSelectorEl = panel.querySelector('.run-selector');
      const existingRunsSelect = panel.querySelector('.existing-runs');
      
      if (loadExistingRunBtn && runSelectorEl && existingRunsSelect && !loadExistingRunBtn.hasAttribute('data-initialized')) {
        loadExistingRunBtn.setAttribute('data-initialized', 'true');
        loadExistingRunBtn.addEventListener('click', async () => {
          if (runSelectorEl.classList.contains('hidden')) {
            await loadAvailableRuns(existingRunsSelect);
            runSelectorEl.classList.remove('hidden');
          } else {
            runSelectorEl.classList.add('hidden');
          }
        });
        
        existingRunsSelect.addEventListener('change', async () => {
          const selectedRunId = existingRunsSelect.value;
          if (selectedRunId) {
            await loadExistingRunResults(selectedRunId, index);
            // If changed from panel 1, propagate to all other visible panels
            if (index === 0) {
              const panels = document.querySelectorAll('.preview-panel');
              for (let i = 1; i < Math.min(currentColumnCount, panels.length); i++) {
                try { await loadExistingRunResults(selectedRunId, i); } catch (e) { console.error(e); }
              }
            }
          }
        });
      }
    });
  }
  
  // Toggle input panel visibility
  function toggleInputPanel() {
    isInputPanelCollapsed = !isInputPanelCollapsed;
    updateLayout();
  }
  
  // Set column count for preview panels
  function setColumnCount(count) {
    if (count < 1 || count > 3) return;
    currentColumnCount = count;
    updatePreviewPanels();
    updateColumnButtons();
  }
  
  // Update layout based on panel state
  function updateLayout() {
    if (isInputPanelCollapsed) {
      inputPanel.classList.add('hidden');
      previewContainer.className = previewContainer.className.replace(/lg:col-span-\d+/, 'lg:col-span-12');
      columnSwitch.classList.remove('hidden');
    } else {
      inputPanel.classList.remove('hidden');
      previewContainer.className = previewContainer.className.replace(/lg:col-span-\d+/, 'lg:col-span-5');
      columnSwitch.classList.add('hidden');
      currentColumnCount = 1;
      updatePreviewPanels();
      updateColumnButtons();
    }
    
    // Update collapse toggle icons
    document.querySelectorAll('.collapse-toggle').forEach(btn => {
      btn.textContent = isInputPanelCollapsed ? '▶' : '◀';
      btn.title = isInputPanelCollapsed ? 'Show input panel' : 'Hide input panel';
    });
  }
  
  // Update preview panels based on column count
  function updatePreviewPanels() {
    const panels = document.querySelectorAll('.preview-panel');
    const gridClass = currentColumnCount === 1 ? '' : 
                     currentColumnCount === 2 ? 'grid grid-cols-2 gap-4' : 
                     'grid grid-cols-3 gap-2';
    
    previewPanels.className = `space-y-4 ${gridClass}`;
    
    // Track which panels were previously hidden that are now being shown
    const newlyVisiblePanels = [];
    
    panels.forEach((panel, index) => {
      const wasHidden = panel.classList.contains('hidden');
      
      if (index < currentColumnCount) {
        panel.classList.remove('hidden');
        // Adjust height for multiple columns
        const previewEl = panel.querySelector('.preview');
        if (previewEl) {
          if (currentColumnCount > 1) {
            previewEl.className = previewEl.className.replace(/h-\[calc\(100vh-12rem\)\]/, 'h-[calc(100vh-16rem)]');
          } else {
            previewEl.className = previewEl.className.replace(/h-\[calc\(100vh-16rem\)\]/, 'h-[calc(100vh-12rem)]');
          }
        }
        
        // Track newly visible panels for run syncing
        if (wasHidden && index > 0) {
          newlyVisiblePanels.push(index);
        }
      } else {
        panel.classList.add('hidden');
      }
    });
    
    // Initialize additional panels if needed
    while (previewOptimizers.length < currentColumnCount) {
      createAdditionalPanel();
      // The newly created panel is at the end, track it for run syncing
      newlyVisiblePanels.push(previewOptimizers.length - 1);
    }
    
    // Sync current run to newly visible panels
    if (currentRunId && newlyVisiblePanels.length > 0) {
      syncRunToNewPanels(newlyVisiblePanels);
    }
  }
  
  // Sync current run to newly visible panels
  async function syncRunToNewPanels(panelIndices) {
    if (!currentRunId) return;
    
    for (const panelIndex of panelIndices) {
      try {
        await loadExistingRunResults(currentRunId, panelIndex);
      } catch (e) {
        console.error(`Failed to sync run to panel ${panelIndex}:`, e);
      }
    }
  }
  
  // Create additional preview panels
  function createAdditionalPanel() {
    const existingPanel = document.querySelector('.preview-panel');
    const newPanel = existingPanel.cloneNode(true);
    const panelIndex = previewOptimizers.length;
    
    newPanel.setAttribute('data-panel', panelIndex + 1);
    newPanel.querySelector('h2').textContent = `Preview ${panelIndex + 1}`;
    
    // Clear content
    newPanel.querySelector('.preview').innerHTML = '';
    newPanel.querySelector('.file-badges').innerHTML = '';
    newPanel.querySelector('.existing-runs').value = '';
    newPanel.querySelector('.run-selector').classList.add('hidden');
    newPanel.querySelector('.preview-stats').textContent = 'Ready';
    
    previewPanels.appendChild(newPanel);
    
    // Initialize optimizer for new panel
    const previewEl = newPanel.querySelector('.preview');
    const optimizer = new PreviewOptimizer(previewEl, {
      maxPreviewSize: 1000000,
      chunkSize: 100000,
      maxInitialLines: 1000
    });
    previewOptimizers[panelIndex] = optimizer;
    
    // Hide folder select and collapse controls on secondary panels
    const collapseBtn = newPanel.querySelector('.collapse-toggle');
    if (collapseBtn) collapseBtn.classList.add('hidden');
    const loadExistingRunBtn = newPanel.querySelector('.load-existing-run');
    if (loadExistingRunBtn) loadExistingRunBtn.classList.add('hidden');
    const runSelectorWrap = newPanel.querySelector('.run-selector');
    if (runSelectorWrap) runSelectorWrap.classList.add('hidden');

    // Clear any data-initialized flags so event handlers attach for this cloned panel
    newPanel.querySelectorAll('[data-initialized]')
      .forEach(el => el.removeAttribute('data-initialized'));

    // Initialize buttons for the new panel
    initializePanelButtons();
  }
  
  // Update column button states
  function updateColumnButtons() {
    document.querySelectorAll('#column-switch button').forEach(btn => {
      const colCount = parseInt(btn.id.split('-')[1]);
      if (colCount === currentColumnCount) {
        btn.classList.add('bg-blue-500', 'text-white');
        btn.classList.remove('bg-gray-200', 'dark:bg-gray-700');
      } else {
        btn.classList.remove('bg-blue-500', 'text-white');
        btn.classList.add('bg-gray-200', 'dark:bg-gray-700');
      }
    });
  }
  
  // Auto-collapse when run loads
  function autoCollapseOnRunLoad() {
    if (!isInputPanelCollapsed) {
      isInputPanelCollapsed = true;
      updateLayout();
    }
  }

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
    'MAX_CHAR_BUFFER',
    'EXTRACTION_PASSES',
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

  async function loadAvailableRuns(selectElement = null) {
    try {
      const res = await fetch('/runs');
      const runs = await res.json();
      
      // If a specific select element is provided, use it; otherwise update all
      const selects = selectElement ? [selectElement] : document.querySelectorAll('.existing-runs');
      
      selects.forEach(existingRunsSelect => {
        if (existingRunsSelect) {
          existingRunsSelect.innerHTML = '<option value="">Select a previous run...</option>';
          
          for (const run of runs) {
            const opt = document.createElement('option');
            opt.value = run.run_id;
            
            // Format the display text with timestamp
            const date = new Date(run.mtime * 1000).toLocaleString();
            opt.textContent = `${run.run_id} (${date})`;
            
            existingRunsSelect.appendChild(opt);
          }
        }
      });
    } catch (e) {
      console.error('Error loading available runs:', e);
    }
  }

  async function loadExistingRunResults(runId, panelIndex = 0) {
    try {
      // Clear current state for this panel
      selectedFilePaths[panelIndex] = null;
      
      // Only update global state if loading into the first panel
      if (panelIndex === 0) {
        currentRunId = runId;
        runIdEl.textContent = `Loaded Run: ${runId}`;
      }
      
      // Get the correct panel elements
      const panels = document.querySelectorAll('.preview-panel');
      const panel = panels[panelIndex];
      if (!panel) return;
      
      // Update preview stats to show we're loading from existing run
      const previewStatsEl = panel.querySelector('.preview-stats');
      if (previewStatsEl) {
        previewStatsEl.textContent = `Loading ${runId}...`;
      }
      
      // Load files from the existing run
      await loadFiles(runId, panelIndex);
      
      // Update preview stats
      if (previewStatsEl) {
        previewStatsEl.textContent = `Loaded from ${runId}`;
      }
      
      // Auto-collapse left panel when loading existing run (only for main panel)
      if (panelIndex === 0) {
        autoCollapseOnRunLoad();
      }
      
      // Also load and display the run status/stats if available (only for first panel)
      if (panelIndex === 0) {
        try {
          const statusRes = await fetch(`/runs/${runId}/status`);
          if (statusRes.ok) {
            const statusData = await statusRes.json();
            if (statusData.stats) {
              statsEl.textContent = JSON.stringify(statusData.stats, null, 2);
            }
          }
        } catch (e) {
          // Status endpoint might not be available for completed runs, that's OK
          console.log('Run status not available (completed run)');
        }

        // Propagate run selection from panel 1 to all other visible panels
        const panels = document.querySelectorAll('.preview-panel');
        for (let i = 1; i < Math.min(currentColumnCount, panels.length); i++) {
          try { await loadExistingRunResults(runId, i); } catch (e) { console.error(e); }
        }
      }
      
    } catch (e) {
      console.error('Error loading existing run results:', e);
      const previewStatsEl = $('preview-stats');
      if (previewStatsEl) {
        previewStatsEl.textContent = 'Error loading run';
      }
    }
  }

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
    if (consoleOptimizer) {
      consoleOptimizer.appendLine(line);
    } else {
      // Fallback for when optimizer isn't ready
      consoleEl.textContent += line + "\n";
      consoleEl.scrollTop = consoleEl.scrollHeight;
    }
  }

  async function pollStatus(runId) {
    try {
      const res = await fetch(`/runs/${runId}/status`);
      const data = await res.json();
      if (data.stats) {
        statsEl.textContent = JSON.stringify(data.stats, null, 2);
      }
      if (data.status === 'finished' || data.status === 'error' || data.status === 'canceled') {
        await loadFiles(runId, 0); // Load into first panel
        if (cancelBtn) cancelBtn.disabled = true;
        // Auto-collapse when run finishes
        autoCollapseOnRunLoad();
      } else {
        setTimeout(() => pollStatus(runId), 2000);
      }
    } catch (e) {
      console.error('status error', e);
      setTimeout(() => pollStatus(runId), 3000);
    }
  }

  // Fallback function for loading files without optimizer
  async function loadFileOriginal(runId, f, panelIndex = 0) {
    const panels = document.querySelectorAll('.preview-panel');
    const panel = panels[panelIndex];
    if (!panel) return;
    
    const previewEl = panel.querySelector('.preview');
    if (!previewEl) return;
    
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
          panel.querySelectorAll('pre code').forEach((el) => {
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
          panel.querySelectorAll('pre code').forEach((el) => {
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
  }

  async function loadFiles(runId, panelIndex = 0) {
    try {
      const res = await fetch(`/runs/${runId}/files`);
      const files = await res.json();
      
      // Get the correct panel elements
      const panels = document.querySelectorAll('.preview-panel');
      const panel = panels[panelIndex];
      if (!panel) return;
      
      const fileBadgesEl = panel.querySelector('.file-badges');
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
          const isSel = selectedFilePaths[panelIndex] === f.path;
          if (isSel) {
            btn.classList.remove('bg-gray-100','text-gray-800','border-gray-300');
            btn.classList.add('bg-blue-600','text-white','border-blue-600');
          } else {
            btn.classList.add('bg-gray-100','text-gray-800','border-gray-300');
            btn.classList.remove('bg-blue-600','text-white','border-blue-600');
          }
        };
        
        btn.addEventListener('click', async () => {
          selectedFilePaths[panelIndex] = f.path;
          
          // Update all badges selection state for this panel
          if (fileBadgesEl) {
            Array.from(fileBadgesEl.children).forEach((el) => {
              const p = el.dataset.path;
              if (!p) return;
              if (p === selectedFilePaths[panelIndex]) {
                el.classList.remove('bg-gray-100','text-gray-800','border-gray-300','dark:bg-gray-700','dark:text-gray-100','dark:border-gray-600');
                el.classList.add('bg-blue-600','text-white','border-blue-600');
              } else {
                el.classList.add('bg-gray-100','text-gray-800','border-gray-300','dark:bg-gray-700','dark:text-gray-100','dark:border-gray-600');
                el.classList.remove('bg-blue-600','text-white','border-blue-600');
              }
            });
          }
          
          // Use preview optimizer if available
          if (previewOptimizers[panelIndex]) {
            await previewOptimizers[panelIndex].loadFile(runId, f.path, f.size);
            
            // After loading file, sync UBERMODE state properly
            const panel = panels[panelIndex];
            const uberToggle = panel?.querySelector('.ubermode-toggle');
            if (uberToggle) {
              const isButtonEnabled = uberToggle.getAttribute('data-enabled') === 'true';
              const isOptimizerUberMode = previewOptimizers[panelIndex].uberMode;
              
              // Wait for JSON data to be parsed before checking UBERMODE activation
              setTimeout(() => {
                const hasJsonData = previewOptimizers[panelIndex].currentJsonData !== null;
                console.log(`UBERMODE sync: button enabled=${isButtonEnabled}, optimizer mode=${isOptimizerUberMode}, has JSON=${hasJsonData}`);
                
                // Only trigger UBERMODE if button is enabled and JSON data is available
                if (isButtonEnabled && !isOptimizerUberMode && hasJsonData) {
                  console.log('Activating UBERMODE for newly loaded JSON file');
                  previewOptimizers[panelIndex].toggleUberMode();
                  updateUberModeButton(uberToggle, true);
                } else if (!isButtonEnabled && isOptimizerUberMode) {
                  // Button is disabled but optimizer is in UBERMODE - deactivate it
                  console.log('Deactivating UBERMODE - button is disabled');
                  previewOptimizers[panelIndex].toggleUberMode();
                  updateUberModeButton(uberToggle, false);
                }
              }, 100); // Small delay to ensure JSON parsing is complete
            }
          } else {
            // Fallback to original loading method
            await loadFileOriginal(runId, f, panelIndex);
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
      if (!selectedFilePaths[panelIndex] && createdBadges.length) {
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
    
    // Clear console using optimizer if available
    if (consoleOptimizer) {
      consoleOptimizer.clear();
    } else {
      consoleEl.textContent = '';
    }
    
    statsEl.textContent = '';
    
    // Clear all preview panels and their badges
    document.querySelectorAll('.preview-panel').forEach(panel => {
      const fileBadgesEl = panel.querySelector('.file-badges');
      const previewEl = panel.querySelector('.preview');
      if (fileBadgesEl) fileBadgesEl.innerHTML = '';
      if (previewEl) previewEl.textContent = '';
    });

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
  applySavedToInput('MAX_CHAR_BUFFER');
  applySavedToInput('EXTRACTION_PASSES');

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

  // UBERMODE utility functions
  function updateUberModeButton(button, isEnabled) {
    if (isEnabled) {
      button.classList.add('bg-blue-500', 'text-white');
      button.classList.remove('text-gray-500');
      button.setAttribute('data-enabled', 'true');
      button.title = 'Disable UBERMODE';
    } else {
      button.classList.remove('bg-blue-500', 'text-white');
      button.classList.add('text-gray-500');
      button.setAttribute('data-enabled', 'false');
      button.title = 'Enable UBERMODE';
    }
  }
})();
