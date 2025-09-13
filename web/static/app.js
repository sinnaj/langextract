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

  // Expose state variables globally for preview optimizer navigation
  window.selectedFilePaths = selectedFilePaths;
  window.currentColumnCount = currentColumnCount;
  window.previewOptimizers = previewOptimizers;
  window.currentRunId = currentRunId; // Expose current run ID for comments system

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
          
          // Refresh all other JSON panels to update their tree/JSON view based on new configuration
          refreshAllJsonPanels(panelIndex);
          
          // Initialize comments if UBERMODE is enabled and we have a file
          const currentFilePath = selectedFilePaths[panelIndex];
          if (isEnabled && window.treeCommentsUI && currentFilePath) {
            console.log('Initializing comments after UBERMODE toggle for:', currentFilePath);
            
            // Use requestAnimationFrame to ensure tree is rendered
            requestAnimationFrame(async () => {
              try {
                await window.treeCommentsUI.initializeForFile(currentFilePath, currentRunId);
                console.log('Comments initialized after UBERMODE toggle for:', currentFilePath);
              } catch (error) {
                console.error('Error initializing comments after UBERMODE toggle:', error);
              }
            });
          }
          
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
    
    // Stats collapsible functionality - Updated to handle all panels using event delegation
    document.addEventListener('click', (e) => {
      if (e.target.closest('.stats-header')) {
        const header = e.target.closest('.stats-header');
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
      }
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
    window.currentColumnCount = currentColumnCount; // Update global reference
    updatePreviewPanels();
    updateColumnButtons();
  }
  
  // Update layout based on panel state
  function updateLayout() {
    if (isInputPanelCollapsed) {
      inputPanel.classList.add('hidden');
      previewContainer.className = previewContainer.className.replace(/lg:col-span-\d+/, 'lg:col-span-12');
      columnSwitch.classList.remove('hidden');
      
      // Always show 2 panels when input is collapsed (requirement #2)
      if (currentColumnCount === 1) {
        currentColumnCount = 2;
        window.currentColumnCount = currentColumnCount;
      }
      updatePreviewPanels();
      updateColumnButtons();
    } else {
      inputPanel.classList.remove('hidden');
      previewContainer.className = previewContainer.className.replace(/lg:col-span-\d+/, 'lg:col-span-5');
      columnSwitch.classList.add('hidden');
      currentColumnCount = 1;
      window.currentColumnCount = currentColumnCount; // Update global reference
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
        
        // For the second panel, make it a PDF viewer when input is collapsed (requirement #3)
        if (index === 1 && isInputPanelCollapsed) {
          panel.setAttribute('data-panel-type', 'pdf');
          // Update panel title if needed
          const titleEl = panel.querySelector('h2');
          if (titleEl && !titleEl.textContent.includes('PDF')) {
            titleEl.textContent = 'PDF Viewer';
          }
        } else {
          panel.setAttribute('data-panel-type', 'preview');
        }
        
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
    
    // Initialize PDF viewer for panel 2 if it's visible (regardless of input panel state)
    if (currentColumnCount >= 2 && currentRunId) {
      initializePDFViewer(currentRunId);
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
    
    // Initialize PDF viewer if we have a run and are now in multi-column mode
    if (currentRunId && currentColumnCount >= 2) {
      // Small delay to ensure panel layout has updated
      setTimeout(() => {
        initializePDFViewer(currentRunId);
      }, 100);
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
        window.currentRunId = runId; // Update global reference
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
        
        // Initialize PDF viewer if we have a run ID and are in multi-column mode
        if (runId && currentColumnCount >= 2) {
          initializePDFViewer(runId);
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
          window.selectedFilePaths = selectedFilePaths; // Update global reference
          
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
            
            // Initialize comments for tree-based files
            // Wait a moment for DOM to be fully updated, then initialize comments
            if (window.treeCommentsUI && f.path) {
              console.log('Initializing comments for file:', f.path);
              
              // Use requestAnimationFrame to ensure DOM is updated
              requestAnimationFrame(async () => {
                try {
                  await window.treeCommentsUI.initializeForFile(f.path, runId);
                  console.log('Comments initialized successfully for:', f.path);
                } catch (error) {
                  console.error('Error initializing comments:', error);
                }
              });
            } else {
              console.log('TreeCommentsUI not available or no file path:', {
                treeCommentsUI: !!window.treeCommentsUI,
                filePath: f.path
              });
            }
            
            // After loading file, sync UBERMODE state properly
            const panel = panels[panelIndex];
            const uberToggle = panel?.querySelector('.ubermode-toggle');
            if (uberToggle) {
              const isButtonEnabled = uberToggle.getAttribute('data-enabled') === 'true';
              const isOptimizerUberMode = previewOptimizers[panelIndex].uberMode;
              
              // Wait for JSON data to be parsed before checking UBERMODE activation
              // Use a more robust approach for large files
              const waitForJsonData = (attempt = 1, maxAttempts = 20) => {
                const hasJsonData = previewOptimizers[panelIndex].currentJsonData !== null;
                const filePath = f.path || 'unknown';
                const isCombinedExtractions = filePath.toLowerCase().includes('combined_extractions.json');
                
                console.log(`UBERMODE sync attempt ${attempt} for file ${filePath}: button enabled=${isButtonEnabled}, optimizer mode=${isOptimizerUberMode}, has JSON=${hasJsonData}, is combined_extractions=${isCombinedExtractions}`);
                
                if (!hasJsonData && attempt < maxAttempts) {
                  // JSON not ready yet, wait longer and retry
                  const delay = Math.min(100 * attempt, 1000); // Progressive delay up to 1 second
                  console.log(`JSON not parsed yet, retrying in ${delay}ms (attempt ${attempt}/${maxAttempts})`);
                  setTimeout(() => waitForJsonData(attempt + 1, maxAttempts), delay);
                  return;
                }
                
                if (!hasJsonData) {
                  console.warn(`JSON data not available after ${maxAttempts} attempts, skipping UBERMODE sync`);
                  return;
                }
                
                // Auto-enable UBERMODE button for combined_extractions.json files
                if (isCombinedExtractions && hasJsonData && !isButtonEnabled) {
                  console.log('Auto-enabling UBERMODE button for combined_extractions.json');
                  updateUberModeButton(uberToggle, true);
                }
                
                // Refresh the button state check after potential auto-enable
                const isButtonEnabledAfter = uberToggle.getAttribute('data-enabled') === 'true';
                
                // Only trigger UBERMODE if button is enabled and JSON data is available
                if (isButtonEnabledAfter && !isOptimizerUberMode && hasJsonData) {
                  console.log('Activating UBERMODE for newly loaded JSON file');
                  previewOptimizers[panelIndex].toggleUberMode();
                  updateUberModeButton(uberToggle, true);
                } else if (!isButtonEnabledAfter && isOptimizerUberMode) {
                  // Button is disabled but optimizer is in UBERMODE - deactivate it
                  console.log('Deactivating UBERMODE - button is disabled');
                  previewOptimizers[panelIndex].toggleUberMode();
                  updateUberModeButton(uberToggle, false);
                }
              };
              
              // Start the waiting process
              waitForJsonData();
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
      
      // If nothing selected yet, auto-open the first readable file (preferring combined_extractions.json for UBERMODE)
      if (!selectedFilePaths[panelIndex] && createdBadges.length) {
        console.log(`Auto-selecting file for panel ${panelIndex}. Available files:`, createdBadges.map(b => b.file.path));
        
        const findPreferred = () => {
          // First priority: combined_extractions.json for UBERMODE functionality
          const combinedExtractions = createdBadges.find(({ file }) => 
            file.path.toLowerCase().includes('combined_extractions.json'));
          if (combinedExtractions) {
            console.log('Auto-selecting combined_extractions.json for UBERMODE functionality');
            return combinedExtractions;
          }
          
          // Second priority: other JSON files
          const preferExt = ['.json', '.jsonl', '.ndjson', '.log', '.txt', '.md'];
          for (const ext of preferExt) {
            const found = createdBadges.find(({ file }) => file.path.toLowerCase().endsWith(ext.toLowerCase()));
            if (found) {
              console.log(`Auto-selecting first file with extension ${ext}:`, found.file.path);
              return found;
            }
          }
          console.log('Auto-selecting first available file:', createdBadges[0].file.path);
          return createdBadges[0];
        };
        const target = findPreferred();
        if (target) {
          console.log('Clicking auto-selected file:', target.file.path);
          target.btn.click();
        }
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
  window.currentRunId = runId; // Update global reference
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
  function refreshAllJsonPanels(excludePanelIndex) {
    // Refresh all JSON panels except the one that triggered the toggle
    previewOptimizers.forEach((optimizer, index) => {
      if (index !== excludePanelIndex && optimizer && optimizer.currentJsonData) {
        const filePath = selectedFilePaths[index];
        if (filePath && filePath.toLowerCase().endsWith('.json')) {
          console.log(`Refreshing JSON panel ${index} after UBERMODE toggle`);
          
          // Sync UBERMODE state from the triggering panel
          const triggeringOptimizer = previewOptimizers[excludePanelIndex];
          if (triggeringOptimizer) {
            optimizer.uberMode = triggeringOptimizer.uberMode;
            
            // Re-render with current JSON data
            optimizer.element.innerHTML = '';
            const shouldShowTreeView = optimizer.shouldShowTreeVisualization();
            
            if (optimizer.uberMode && shouldShowTreeView) {
              optimizer.renderUberMode(optimizer.currentJsonData, { size: 0, truncated: false });
            } else {
              // Re-render with normal JSON view
              if (typeof JSONFormatter !== 'undefined') {
                optimizer.renderEnhancedJsonObject(optimizer.currentJsonData, { size: 0, truncated: false });
              } else {
                const pretty = JSON.stringify(optimizer.currentJsonData, null, 2);
                optimizer.renderEnhancedJson(pretty, { size: 0, truncated: false });
              }
            }
          }
        }
      }
    });
  }

  function updateUberModeButton(button, isEnabled) {
    if (isEnabled) {
      button.classList.add('bg-blue-500', 'text-white');
      button.classList.remove('text-gray-500');
      button.setAttribute('data-enabled', 'true');
      button.title = 'Disable Tree View';
    } else {
      button.classList.remove('bg-blue-500', 'text-white');
      button.classList.add('text-gray-500');
      button.setAttribute('data-enabled', 'false');
      button.title = 'Enable Tree View';
    }
  }

  // Tree node selection and PDF highlighting integration
  function setupTreeNodeSelection() {
    // Set up event delegation for tree node clicks
    document.addEventListener('click', handleTreeNodeClick);
  }

  function handleTreeNodeClick(event) {
    const target = event.target;
    
    // Check if click is on a tree node
    const treeNode = target.closest('.json-formatter-row, .tree-node-content, [data-tree-id]');
    if (!treeNode) return;
    
    // Prevent default only if we're handling this as a tree selection
    if (treeNode.querySelector('.json-formatter-key, .tree-item-title')) {
      event.preventDefault();
      event.stopPropagation();
      
      // Clear previous selections
      document.querySelectorAll('.tree-node-selected').forEach(node => {
        node.classList.remove('tree-node-selected');
      });
      
      // Mark current node as selected
      treeNode.classList.add('tree-node-selected');
      
      // Extract element information for PDF highlighting
      const elementInfo = extractElementInfo(treeNode);
      if (elementInfo) {
        console.log('Tree node selected:', elementInfo);
        
        // Check PDF highlighting conditions
        console.log('PDF highlighting conditions:');
        console.log('- window.highlightPDFElements exists:', !!window.highlightPDFElements);
        console.log('- isInputPanelCollapsed:', isInputPanelCollapsed);
        console.log('- currentColumnCount >= 2:', currentColumnCount >= 2);
        console.log('- pdfViewer exists:', !!window.pdfViewer);
        
        // Highlight in PDF (requirement #5)
        if (window.highlightPDFElements && isInputPanelCollapsed && currentColumnCount >= 2) {
          console.log('Attempting to highlight PDF elements:', [elementInfo.id]);
          window.highlightPDFElements([elementInfo.id]);
        } else {
          console.log('PDF highlighting skipped due to conditions not met');
        }
      } else {
        console.log('No element info extracted from tree node');
      }
    }
  }

  function extractElementInfo(treeNode) {
    // Extract element ID and type from the tree node
    let elementId = null;
    let elementType = null;
    
    console.log('Extracting element info from tree node:', treeNode);
    
    // Try to get from data attributes first
    elementId = treeNode.getAttribute('data-tree-id') || 
                treeNode.getAttribute('data-element-id');
    
    console.log('Element ID from data attributes:', elementId);
    
    if (!elementId) {
      // Try to extract from JSON formatter structure
      const keyElement = treeNode.querySelector('.json-formatter-key');
      if (keyElement) {
        const keyText = keyElement.textContent;
        console.log('Found key element with text:', keyText);
        
        // Look for ID patterns in the key or nearby content
        if (keyText.includes('_id') || keyText.includes('id')) {
          // Find the corresponding value
          const valueElement = treeNode.querySelector('.json-formatter-string');
          if (valueElement) {
            elementId = valueElement.textContent.replace(/"/g, '');
            console.log('Found element ID from JSON value:', elementId);
          }
        }
        
        // Determine element type from key patterns
        if (keyText.includes('norm')) {
          elementType = 'NORM';
        } else if (keyText.includes('section')) {
          elementType = 'SECTION';
        } else if (keyText.includes('tag')) {
          elementType = 'TAG';
        } else if (keyText.includes('parameter')) {
          elementType = 'PARAMETER';
        }
        
        console.log('Detected element type:', elementType);
      }
    }
    
    // Alternative: traverse up to find parent container with ID information
    if (!elementId) {
      let parent = treeNode.parentNode;
      while (parent && !elementId) {
        const siblingKeyElements = parent.querySelectorAll('.json-formatter-key');
        for (const keyEl of siblingKeyElements) {
          if (keyEl.textContent.includes('_id')) {
            const valueEl = keyEl.parentNode.querySelector('.json-formatter-string');
            if (valueEl) {
              elementId = valueEl.textContent.replace(/"/g, '');
              break;
            }
          }
        }
        parent = parent.parentNode;
        
        // Don't traverse too far up
        if (parent && parent.classList.contains('preview')) break;
      }
    }
    
    if (elementId) {
      return {
        id: elementId,
        type: elementType || 'UNKNOWN',
        node: treeNode
      };
    }
    
    return null;
  }

  // Initialize tree node selection when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    setupTreeNodeSelection();
  });

  // Extend the existing updatePreviewPanels to include tree selection setup
  const originalCall = updatePreviewPanels;
  window.addEventListener('load', () => {
    // Monitor for changes to tree views and re-setup selection
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
          // Check if JSON formatter or tree content was added
          for (const node of mutation.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE && 
                (node.classList.contains('json-formatter-row') || 
                 node.querySelector && node.querySelector('.json-formatter-row'))) {
              setTimeout(() => setupTreeNodeSelection(), 50);
              break;
            }
          }
        }
      });
    });

    // Toast notification system for PDF click feedback
    function createToastContainer() {
      let container = document.getElementById('toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed top-4 right-4 z-50 space-y-2';
        document.body.appendChild(container);
      }
      return container;
    }

    function showToast(message, type = 'info', duration = 3000) {
      const container = createToastContainer();
      
      const toast = document.createElement('div');
      toast.className = `
        px-4 py-2 rounded-lg shadow-lg text-white font-medium
        transform transition-all duration-300 ease-in-out
        translate-x-full opacity-0
        ${type === 'error' ? 'bg-red-500' : type === 'success' ? 'bg-green-500' : 'bg-blue-500'}
      `;
      toast.textContent = message;
      
      container.appendChild(toast);
      
      // Animate in
      requestAnimationFrame(() => {
        toast.classList.remove('translate-x-full', 'opacity-0');
      });
      
      // Auto remove after duration
      setTimeout(() => {
        toast.classList.add('translate-x-full', 'opacity-0');
        setTimeout(() => {
          if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
          }
        }, 300);
      }, duration);
    }

    function navigateToTreeNode(elementId) {
      console.log('=== TREE NAVIGATION DEBUG ===');
      console.log('Attempting to navigate to tree node:', elementId);
      console.log('Current document title:', document.title);
      console.log('Number of elements in document:', document.querySelectorAll('*').length);
      
      // Debug: Check if we have any preview panels
      const previewPanels = document.querySelectorAll('.preview-panel');
      console.log(`Found ${previewPanels.length} preview panels`);
      previewPanels.forEach((panel, idx) => {
        const previewEl = panel.querySelector('.preview');
        console.log(`Panel ${idx}: class="${panel.className}", id="${panel.id}", has .preview: ${!!previewEl}`);
      });
      
      // Clear ALL previous selections first to prevent multiple selections
      console.log('Clearing all previous selections...');
      const previousSelections = document.querySelectorAll('.tree-node-selected');
      console.log(`Found ${previousSelections.length} previously selected nodes`);
      previousSelections.forEach((node, idx) => {
        console.log(`Clearing selection ${idx}:`, node.tagName, node.className);
        node.classList.remove('tree-node-selected');
      });
      
      // Verify all selections are cleared
      const remainingSelections = document.querySelectorAll('.tree-node-selected');
      if (remainingSelections.length > 0) {
        console.warn(`⚠️ Warning: ${remainingSelections.length} selections still remain after clearing`);
        remainingSelections.forEach(node => node.classList.remove('tree-node-selected'));
      }
      
      // Find the tree node with the given element ID
      const treeNode = findTreeNodeByElementId(elementId);
      
      if (treeNode) {
        console.log('✅ Successfully found tree node for element ID:', elementId);
        console.log('Tree node details:', {
          tagName: treeNode.tagName,
          className: treeNode.className,
          id: treeNode.id,
          hasTreeNodeContent: !!treeNode.querySelector('.tree-node-content'),
          isJsonFormatterRow: treeNode.classList.contains('json-formatter-row'),
          hasDataId: !!(treeNode.dataset.extractionId || treeNode.dataset.nodeId),
          textPreview: treeNode.textContent?.substring(0, 100) + '...'
        });
        
        // Mark as selected BEFORE expansion to ensure it's visible during the process
        treeNode.classList.add('tree-node-selected');
        console.log('✅ Added tree-node-selected class to target node');
        
        // Double-check that only this one node is selected
        const selectedAfter = document.querySelectorAll('.tree-node-selected');
        console.log(`After selection: ${selectedAfter.length} nodes are selected`);
        if (selectedAfter.length > 1) {
          console.warn('⚠️ Warning: Multiple nodes selected after navigation!');
          selectedAfter.forEach((node, idx) => {
            if (node !== treeNode) {
              console.warn(`Removing extra selection ${idx}:`, node);
              node.classList.remove('tree-node-selected');
            }
          });
        }
        
        // Show initial feedback toast
        showToast('🎯 Tree node found - expanding parents...', 'info', 2000);
        
        // Expand parent nodes FIRST, then scroll (addressing user feedback)
        console.log('=== STARTING PARENT EXPANSION ===');
        
        expandParentNodes(treeNode).then(() => {
          console.log('✅ Parent nodes expanded, now scrolling to target...');
          
          // Small delay to ensure DOM updates from expansion have completed
          setTimeout(() => {
            console.log('=== STARTING SCROLL TO TARGET ===');
            scrollTreeNodeIntoView(treeNode);
            
            // Final verification that selection is still correct
            setTimeout(() => {
              const finalSelected = document.querySelectorAll('.tree-node-selected');
              if (finalSelected.length === 1 && finalSelected[0] === treeNode) {
                console.log('✅ Navigation completed successfully');
              } else {
                console.warn('⚠️ Warning: Selection state changed during navigation');
                // Re-apply selection if needed
                document.querySelectorAll('.tree-node-selected').forEach(n => n.classList.remove('tree-node-selected'));
                treeNode.classList.add('tree-node-selected');
              }
            }, 500);
            
          }, 200); // Allow time for DOM updates from parent expansion
          
        }).catch(error => {
          console.warn('⚠️ Error during parent expansion:', error);
          showToast('⚠️ Parent expansion had issues - attempting scroll anyway', 'warning', 2000);
          
          // Still try to scroll even if expansion had issues
          setTimeout(() => {
            console.log('=== ATTEMPTING SCROLL DESPITE EXPANSION ISSUES ===');
            scrollTreeNodeIntoView(treeNode);
          }, 200);
        });
        
        // Return the node for further use if needed
        return treeNode;
        
      } else {
        console.log('❌ Tree node not found for element ID:', elementId);
        console.log('=== TREE NAVIGATION FAILED ===');
        
        // Enhanced debugging for failed searches
        const bodyText = document.body.textContent || '';
        const elementIdInDoc = bodyText.includes(elementId);
        console.log('Debug information:', {
          elementIdInDocument: elementIdInDoc,
          documentHasJsonRows: document.querySelectorAll('.json-formatter-row').length,
          documentHasTreeNodes: document.querySelectorAll('.tree-node').length,
          documentHasDataExtractionIds: document.querySelectorAll('[data-extraction-id]').length,
          documentHasDataNodeIds: document.querySelectorAll('[data-node-id]').length
        });
        
        // Show appropriate error message
        if (elementIdInDoc) {
          const message = `Element ID "${elementId}" found in document but could not locate selectable tree node`;
          showToast(`❌ ${message}`, 'error', 5000);
          console.log('Suggestion: The element may be in text but not in a selectable tree structure');
        } else {
          const message = `Element ID "${elementId}" not found in document`;
          showToast(`❌ ${message}`, 'error', 5000);
        }
        
        return null;
      }
    }

    function findTreeNodeByElementId(elementId) {
      console.log('=== SEARCHING FOR TREE NODE ===');
      console.log('Target element ID:', elementId);
      
      // Search strategies focused on finding the specific tree node, not parent containers
      const searchStrategies = [
        // Strategy 1: Look for exact data attributes on tree nodes
        () => {
          console.log('Strategy 1: Searching for data attributes...');
          const selectors = [
            `[data-extraction-id="${elementId}"]`,
            `[data-node-id="${elementId}"]`, 
            `[data-tree-id="${elementId}"]`,
            `[id="${elementId}"]`
          ];
          
          for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            console.log(`Selector "${selector}" found ${elements.length} elements`);
            
            for (const element of elements) {
              // Prefer elements that look like tree nodes
              if (element.classList.contains('tree-node') || 
                  element.classList.contains('json-formatter-row') ||
                  element.querySelector('.tree-node-content')) {
                console.log('✅ Found tree node with data attribute:', element);
                return element;
              }
            }
            
            // Fallback to first element if none look like tree nodes
            if (elements.length > 0) {
              console.log('Found element with data attribute (fallback):', elements[0]);
              return elements[0];
            }
          }
          
          return null;
        },
        
        // Strategy 2: Look for JSON formatter rows containing the ID as a field value
        () => {
          console.log('Strategy 2: Searching JSON formatter rows...');
          const jsonRows = document.querySelectorAll('.json-formatter-row');
          console.log(`Found ${jsonRows.length} JSON formatter rows to check`);
          
          const candidates = [];
          
          for (const row of jsonRows) {
            // Look for string values that match our element ID
            const stringElements = row.querySelectorAll('.json-formatter-string');
            const keyElement = row.querySelector('.json-formatter-key');
            
            for (const stringEl of stringElements) {
              const value = stringEl.textContent?.replace(/"/g, '').trim();
              if (value === elementId) {
                const keyText = keyElement ? keyElement.textContent?.replace(/"/g, '').trim() : '';
                console.log(`Found matching value in JSON row - key: "${keyText}", value: "${value}"`);
                
                // Check if this looks like an ID field
                const isIdField = (
                  keyText.endsWith('_id') || 
                  keyText.endsWith('Id') || 
                  keyText === 'id' ||
                  keyText.includes('identifier')
                );
                
                if (isIdField) {
                  // Find the parent object row instead of the key-value row
                  let objectRow = row;
                  let searchParent = row.parentElement;
                  let depth = 0;
                  
                  // Look up the DOM tree to find the containing object/array
                  while (searchParent && depth < 5) {
                    if (searchParent.classList.contains('json-formatter-row') &&
                        (searchParent.querySelector('.json-formatter-open') || 
                         searchParent.querySelector('.json-formatter-close'))) {
                      objectRow = searchParent;
                      break;
                    }
                    searchParent = searchParent.parentElement;
                    depth++;
                  }
                  
                  candidates.push({
                    element: objectRow,
                    priority: isIdField ? 10 : 5,
                    keyText: keyText,
                    depth: depth
                  });
                }
              }
            }
          }
          
          if (candidates.length > 0) {
            // Sort by priority, then by depth (prefer shallower/more specific)
            candidates.sort((a, b) => {
              if (a.priority !== b.priority) return b.priority - a.priority;
              return a.depth - b.depth;
            });
            
            console.log('✅ Found JSON formatter candidate:', candidates[0]);
            return candidates[0].element;
          }
          
          return null;
        },
        
        // Strategy 3: Search tree node content for the ID
        () => {
          console.log('Strategy 3: Searching tree node content...');
          const treeNodes = document.querySelectorAll('.tree-node, [data-extraction-id], [data-node-id]');
          console.log(`Found ${treeNodes.length} tree nodes to check`);
          
          for (const node of treeNodes) {
            const nodeContent = node.querySelector('.tree-node-content');
            const textToSearch = nodeContent ? nodeContent.textContent : node.textContent;
            
            if (textToSearch && textToSearch.includes(elementId)) {
              // Check if this contains the ID in an ID-like context
              const hasIdContext = (
                textToSearch.includes(`"${elementId}"`) ||
                textToSearch.includes(`_id": "${elementId}"`) ||
                textToSearch.includes(`id": "${elementId}"`) ||
                new RegExp(`\\b${elementId}\\b`).test(textToSearch)
              );
              
              if (hasIdContext) {
                console.log('✅ Found tree node with ID in content:', node);
                return node;
              }
            }
          }
          
          return null;
        },
        
        // Strategy 4: Text-based search with TreeWalker for precision
        () => {
          console.log('Strategy 4: Text-based TreeWalker search...');
          
          const walker = document.createTreeWalker(
            document.body,
            NodeFilter.SHOW_TEXT,
            {
              acceptNode: function(node) {
                const text = node.textContent;
                return (text && (
                  text.trim() === `"${elementId}"` ||
                  text.trim() === elementId ||
                  text.includes(`"${elementId}"`)
                )) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
              }
            }
          );
          
          const candidates = [];
          let textNode;
          
          while (textNode = walker.nextNode()) {
            let parent = textNode.parentElement;
            let depth = 0;
            
            // Find the most appropriate container
            while (parent && depth < 6) {
              const isGoodCandidate = (
                parent.classList.contains('json-formatter-row') ||
                parent.classList.contains('tree-node') ||
                parent.hasAttribute('data-extraction-id') ||
                parent.hasAttribute('data-node-id') ||
                parent.querySelector('.tree-node-content')
              );
              
              if (isGoodCandidate) {
                candidates.push({ 
                  element: parent, 
                  depth: depth, 
                  textNode: textNode,
                  text: textNode.textContent 
                });
                break;
              }
              
              parent = parent.parentElement;
              depth++;
            }
          }
          
          if (candidates.length > 0) {
            // Prefer candidates with smaller depth (more specific)
            candidates.sort((a, b) => a.depth - b.depth);
            console.log('✅ Found text-based candidate:', candidates[0]);
            return candidates[0].element;
          }
          
          return null;
        },
        
        // Strategy 5: Broad text search fallback
        () => {
          console.log('Strategy 5: Broad text search fallback...');
          const allElements = document.querySelectorAll('*');
          
          for (const element of allElements) {
            if (element.textContent && element.textContent.includes(elementId)) {
              // Make sure this isn't too broad (like body or html)
              const isTooBoard = (
                element.tagName === 'BODY' ||
                element.tagName === 'HTML' ||
                element === document.documentElement
              );
              
              if (!isTooBoard && (
                element.classList.contains('json-formatter-row') ||
                element.classList.contains('tree-node') ||
                element.hasAttribute('data-extraction-id') ||
                element.querySelector('.tree-node-content')
              )) {
                console.log('✅ Found broad search candidate:', element);
                return element;
              }
            }
          }
          
          return null;
        }
      ];
      
      // Try each strategy in order
      for (let i = 0; i < searchStrategies.length; i++) {
        console.log(`--- Trying search strategy ${i + 1} ---`);
        const result = searchStrategies[i]();
        
        if (result) {
          console.log(`✅ Strategy ${i + 1} succeeded!`);
          console.log('Found element details:', {
            tagName: result.tagName,
            className: result.className,
            id: result.id,
            hasDataId: !!(result.dataset.extractionId || result.dataset.nodeId),
            isJsonRow: result.classList.contains('json-formatter-row'),
            hasTreeContent: !!result.querySelector('.tree-node-content'),
            textPreview: result.textContent?.substring(0, 100) + '...'
          });
          
          // Additional validation - ensure this is a reasonable selection target
          const isValidTarget = (
            result.hasAttribute('data-extraction-id') ||
            result.hasAttribute('data-node-id') ||
            result.classList.contains('json-formatter-row') ||
            result.classList.contains('tree-node') ||
            result.querySelector('.tree-node-content')
          );
          
          if (!isValidTarget) {
            console.warn(`Warning: Found element may not be ideal for selection:`, result);
            console.log('Continuing to next strategy...');
            continue; // Try next strategy
          }
          
          return result;
        }
      }
      
      console.log('❌ All search strategies failed for element ID:', elementId);
      
      // Final debug info
      const bodyText = document.body.textContent || '';
      const elementIdExists = bodyText.includes(elementId);
      console.log('Debug info:', {
        elementIdInDocument: elementIdExists,
        documentHasJsonRows: document.querySelectorAll('.json-formatter-row').length > 0,
        documentHasTreeNodes: document.querySelectorAll('.tree-node').length > 0,
        documentHasDataIds: document.querySelectorAll('[data-extraction-id]').length > 0
      });
      
      return null;
    }

    function scrollTreeNodeIntoView(treeNode) {
      console.log('=== SCROLLING TREE NODE INTO VIEW ===');
      console.log('Target node:', treeNode);
      
      // Find the containing preview panel - this is our scrollable container
      const previewPanel = treeNode.closest('.preview');
      if (!previewPanel) {
        console.log('❌ No preview panel found, using fallback scroll');
        treeNode.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'center',
          inline: 'nearest'
        });
        setTimeout(() => {
          showToast('Navigation complete (fallback)!', 'success', 1500);
        }, 500);
        return;
      }
      
      console.log('✅ Found preview panel:', previewPanel);
      console.log('Preview panel scroll properties:', {
        scrollTop: previewPanel.scrollTop,
        scrollHeight: previewPanel.scrollHeight,
        clientHeight: previewPanel.clientHeight
      });
      
      // Get position of target node relative to the preview panel's content
      const nodeRect = treeNode.getBoundingClientRect();
      const panelRect = previewPanel.getBoundingClientRect();
      
      // Calculate the node's position relative to the panel's current scroll position
      const currentScrollTop = previewPanel.scrollTop;
      const nodeTopInPanel = nodeRect.top - panelRect.top + currentScrollTop;
      const nodeBottomInPanel = nodeRect.bottom - panelRect.top + currentScrollTop;
      
      console.log('Position calculations:', {
        nodeRect: { top: nodeRect.top, bottom: nodeRect.bottom, height: nodeRect.height },
        panelRect: { top: panelRect.top, bottom: panelRect.bottom, height: panelRect.height },
        currentScrollTop: currentScrollTop,
        nodeTopInPanel: nodeTopInPanel,
        nodeBottomInPanel: nodeBottomInPanel
      });
      
      // Calculate visible area within the panel
      const visibleTop = currentScrollTop;
      const visibleBottom = currentScrollTop + panelRect.height;
      const buffer = 50; // Pixels from edge to consider "visible"
      
      console.log('Visibility check:', {
        visibleTop: visibleTop,
        visibleBottom: visibleBottom,
        nodeTopInPanel: nodeTopInPanel,
        nodeBottomInPanel: nodeBottomInPanel,
        isVisible: (nodeTopInPanel >= visibleTop + buffer && nodeBottomInPanel <= visibleBottom - buffer)
      });
      
      // Check if node needs scrolling
      const needsScrolling = (
        nodeTopInPanel < visibleTop + buffer || 
        nodeBottomInPanel > visibleBottom - buffer
      );
      
      if (needsScrolling) {
        // Calculate ideal scroll position to center the node
        const panelHeight = panelRect.height;
        const nodeHeight = nodeRect.height;
        
        // Position the node in the upper third of the panel for better visibility
        const targetScrollTop = Math.max(0, nodeTopInPanel - (panelHeight / 3));
        
        console.log('Scrolling required:', {
          from: currentScrollTop,
          to: targetScrollTop,
          distance: Math.abs(targetScrollTop - currentScrollTop)
        });
        
        // Perform the scroll
        previewPanel.scrollTo({
          top: targetScrollTop,
          behavior: 'smooth'
        });
        
        // Add visual feedback
        const scrollIndicator = document.createElement('div');
        scrollIndicator.className = 'scroll-indicator';
        scrollIndicator.style.cssText = `
          position: absolute;
          top: 10px;
          right: 10px;
          background: rgba(59, 130, 246, 0.9);
          color: white;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          z-index: 1000;
          pointer-events: none;
          opacity: 1;
          transition: opacity 0.3s ease;
        `;
        scrollIndicator.textContent = '📍 Scrolling to target...';
        
        const previewContainer = previewPanel.closest('.preview-panel');
        if (previewContainer) {
          previewContainer.style.position = 'relative';
          previewContainer.appendChild(scrollIndicator);
          
          // Remove indicator and show success after scroll animation completes
          setTimeout(() => {
            scrollIndicator.textContent = '✅ Navigation complete!';
            scrollIndicator.style.background = 'rgba(34, 197, 94, 0.9)';
            
            setTimeout(() => {
              scrollIndicator.style.opacity = '0';
              setTimeout(() => {
                if (scrollIndicator.parentNode) {
                  scrollIndicator.parentNode.removeChild(scrollIndicator);
                }
              }, 300);
            }, 1000);
          }, 800); // Match smooth scroll timing
        }
        
        // Verify scroll position after animation
        setTimeout(() => {
          const finalScrollTop = previewPanel.scrollTop;
          console.log('Scroll verification:', {
            target: targetScrollTop,
            actual: finalScrollTop,
            difference: Math.abs(targetScrollTop - finalScrollTop)
          });
          
          if (Math.abs(targetScrollTop - finalScrollTop) > 10) {
            console.warn('Scroll position may not be accurate');
          } else {
            console.log('✅ Scroll completed successfully');
          }
        }, 1000);
        
      } else {
        console.log('✅ Node is already visible, no scrolling needed');
        showToast('✅ Target already visible!', 'success', 1500);
      }
    }

    function expandParentNodes(treeNode) {
      console.log('=== EXPANDING PARENT NODES ===');
      console.log('Starting expansion from node:', treeNode);
      
      // Add expansion indicator to the preview panel
      const previewPanel = treeNode.closest('.preview-panel');
      let expansionIndicator = null;
      
      if (previewPanel) {
        expansionIndicator = document.createElement('div');
        expansionIndicator.className = 'expansion-indicator';
        expansionIndicator.textContent = '🔍 Expanding parent nodes...';
        expansionIndicator.style.cssText = `
          position: absolute;
          top: 10px;
          left: 10px;
          background: rgba(34, 197, 94, 0.9);
          color: white;
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 12px;
          z-index: 1000;
          pointer-events: none;
          opacity: 1;
          transition: opacity 0.3s ease;
          display: flex;
          align-items: center;
        `;
        previewPanel.style.position = 'relative';
        previewPanel.appendChild(expansionIndicator);
      }
      
      // Collect all parent nodes that might need expansion
      const parentsToExpand = [];
      let parent = treeNode.parentNode;
      let depth = 0;
      
      console.log('Searching for collapsible parents...');
      
      while (parent && parent !== document.body && depth < 20) {
        const parentInfo = {
          element: parent,
          depth: depth,
          toggles: [],
          needsExpansion: false
        };
        
        // Check if this parent is currently collapsed
        const isCollapsed = (
          parent.classList.contains('json-formatter-closed') ||
          parent.classList.contains('collapsed') ||
          parent.getAttribute('aria-expanded') === 'false' ||
          (parent.tagName === 'DETAILS' && !parent.hasAttribute('open'))
        );
        
        if (isCollapsed) {
          parentInfo.needsExpansion = true;
          
          // Find appropriate toggles for this parent
          if (parent.tagName === 'DETAILS') {
            const summary = parent.querySelector('summary');
            if (summary) parentInfo.toggles.push(summary);
          } else if (parent.classList.contains('json-formatter-closed')) {
            const toggler = parent.querySelector('.json-formatter-toggler');
            if (toggler) parentInfo.toggles.push(toggler);
          } else {
            // Look for other types of toggles
            const possibleToggles = [
              parent.querySelector('.tree-toggle'),
              parent.querySelector('.tree-node-toggle'),
              parent.querySelector('[data-toggle="collapse"]'),
              parent.querySelector('.collapse-toggle'),
              parent.querySelector('.btn-toggle'),
              parent.querySelector('[aria-expanded="false"]')
            ].filter(toggle => toggle !== null);
            
            parentInfo.toggles.push(...possibleToggles);
            
            // If no specific toggle found, check if parent itself is clickable
            if (parentInfo.toggles.length === 0 && (parent.onclick || parent.getAttribute('role') === 'button')) {
              parentInfo.toggles.push(parent);
            }
          }
        } else {
          // Even if not collapsed, look for toggles that might need to be expanded
          const expandableToggles = [
            parent.querySelector('.json-formatter-toggler'),
            parent.querySelector('.tree-toggle'),
            parent.querySelector('[aria-expanded="false"]')
          ].filter(toggle => toggle !== null);
          
          if (expandableToggles.length > 0) {
            // Check if any of these toggles are in a collapsed state
            const hasCollapsedToggle = expandableToggles.some(toggle => 
              toggle.getAttribute('aria-expanded') === 'false' ||
              toggle.closest('.json-formatter-closed') ||
              toggle.closest('.collapsed')
            );
            
            if (hasCollapsedToggle) {
              parentInfo.needsExpansion = true;
              parentInfo.toggles.push(...expandableToggles);
            }
          }
        }
        
        if (parentInfo.needsExpansion && parentInfo.toggles.length > 0) {
          parentsToExpand.push(parentInfo);
          console.log(`Found collapsible parent at depth ${depth}:`, {
            element: parent,
            tagName: parent.tagName,
            classList: Array.from(parent.classList),
            toggleCount: parentInfo.toggles.length,
            toggles: parentInfo.toggles
          });
        }
        
        parent = parent.parentNode;
        depth++;
      }
      
      console.log(`Found ${parentsToExpand.length} parents that need expansion`);
      
      if (parentsToExpand.length === 0) {
        console.log('No parents need expansion');
        if (expansionIndicator) {
          expansionIndicator.textContent = '✅ No expansion needed';
          setTimeout(() => {
            expansionIndicator.style.opacity = '0';
            setTimeout(() => {
              if (expansionIndicator.parentNode) {
                expansionIndicator.parentNode.removeChild(expansionIndicator);
              }
            }, 300);
          }, 800);
        }
        return Promise.resolve();
      }
      
      // Expand parents from outermost to innermost (reverse order)
      parentsToExpand.reverse();
      
      let expandedCount = 0;
      const expandPromises = [];
      
      for (const parentInfo of parentsToExpand) {
        console.log(`Processing parent at depth ${parentInfo.depth}...`);
        
        // Add visual feedback
        parentInfo.element.classList.add('expanding-parent');
        
        let parentExpanded = false;
        
        for (const toggle of parentInfo.toggles) {
          try {
            console.log('Attempting to expand via toggle:', toggle);
            
            // Update the expansion indicator
            if (expansionIndicator) {
              expansionIndicator.textContent = `🔄 Expanding depth ${parentInfo.depth}...`;
            }
            
            // Create expansion promise
            const expandPromise = new Promise((resolve) => {
              // Try different expansion methods
              if (typeof toggle.click === 'function') {
                toggle.click();
                console.log('✅ Clicked toggle successfully');
              } else if (toggle.dispatchEvent) {
                const clickEvent = new MouseEvent('click', { 
                  bubbles: true, 
                  cancelable: true,
                  view: window
                });
                toggle.dispatchEvent(clickEvent);
                console.log('✅ Dispatched click event');
              } else if (parentInfo.element.tagName === 'DETAILS') {
                parentInfo.element.setAttribute('open', '');
                console.log('✅ Set details open attribute');
              }
              
              // Give time for DOM to update
              setTimeout(() => {
                parentInfo.element.classList.remove('expanding-parent');
                resolve();
              }, 100);
            });
            
            expandPromises.push(expandPromise);
            expandedCount++;
            parentExpanded = true;
            
            // Don't try multiple toggles for the same parent
            break;
            
          } catch (error) {
            console.warn('Error expanding parent node:', error, toggle);
          }
        }
        
        // Remove visual feedback if no expansion was attempted
        if (!parentExpanded) {
          parentInfo.element.classList.remove('expanding-parent');
        }
      }
      
      console.log(`Initiated expansion of ${expandedCount} parent nodes`);
      
      // Return promise that resolves when all expansions complete
      return Promise.all(expandPromises).then(() => {
        console.log(`✅ Successfully expanded ${expandedCount} parent nodes`);
        
        // Update and remove expansion indicator
        if (expansionIndicator && expansionIndicator.parentNode) {
          expansionIndicator.textContent = `✅ Expanded ${expandedCount} parents`;
          setTimeout(() => {
            expansionIndicator.style.opacity = '0';
            setTimeout(() => {
              if (expansionIndicator.parentNode) {
                expansionIndicator.parentNode.removeChild(expansionIndicator);
              }
            }, 300);
          }, 800);
        }
        
        // Clean up any remaining visual feedback
        document.querySelectorAll('.expanding-parent').forEach(el => {
          el.classList.remove('expanding-parent');
        });
        
        // Additional delay to ensure DOM updates complete
        return new Promise(resolve => setTimeout(resolve, 150));
        
      }).catch(error => {
        console.warn('Some parent expansions failed:', error);
        
        // Clean up on error
        if (expansionIndicator && expansionIndicator.parentNode) {
          expansionIndicator.textContent = '⚠️ Expansion had issues';
          setTimeout(() => {
            expansionIndicator.style.opacity = '0';
            setTimeout(() => {
              if (expansionIndicator.parentNode) {
                expansionIndicator.parentNode.removeChild(expansionIndicator);
              }
            }, 300);
          }, 800);
        }
        
        // Remove visual feedback classes
        document.querySelectorAll('.expanding-parent').forEach(el => {
          el.classList.remove('expanding-parent');
        });
        
        // Continue even if expansions failed
        return new Promise(resolve => setTimeout(resolve, 150));
      });
    }

    // Make functions globally available
    window.showToast = showToast;
    window.navigateToTreeNode = navigateToTreeNode;
    window.findTreeNodeByElementId = findTreeNodeByElementId; // For debugging
    
    // Debug function to test tree navigation with enhanced diagnostics
    window.testTreeNavigation = function(elementId) {
      console.log('=== TESTING TREE NAVIGATION ===');
      console.log('Test element ID:', elementId || 'No element ID provided');
      
      // Enhanced diagnostics about the current document
      const diagnostics = {
        totalElements: document.querySelectorAll('*').length,
        previewPanels: document.querySelectorAll('.preview-panel').length,
        previewElements: document.querySelectorAll('.preview').length,
        jsonFormatterRows: document.querySelectorAll('.json-formatter-row').length,
        treeNodes: document.querySelectorAll('.tree-node').length,
        dataExtractionIds: document.querySelectorAll('[data-extraction-id]').length,
        dataNodeIds: document.querySelectorAll('[data-node-id]').length,
        currentlySelected: document.querySelectorAll('.tree-node-selected').length
      };
      
      console.log('Document diagnostics:', diagnostics);
      
      if (!elementId) {
        // Enhanced element ID discovery
        console.log('No element ID provided, searching for candidates...');
        
        // Look for IDs in data attributes first
        const elementsWithDataIds = document.querySelectorAll('[data-extraction-id], [data-node-id]');
        if (elementsWithDataIds.length > 0) {
          const dataIds = Array.from(elementsWithDataIds).map(el => 
            el.dataset.extractionId || el.dataset.nodeId
          ).filter(id => id);
          
          if (dataIds.length > 0) {
            elementId = dataIds[0];
            console.log(`Found ${dataIds.length} data attribute IDs, using first:`, elementId);
            console.log('All data IDs found:', dataIds.slice(0, 5));
          }
        }
        
        // Fallback to text-based ID discovery
        if (!elementId) {
          const bodyText = document.body.textContent || '';
          const idMatches = [
            ...bodyText.matchAll(/[0-9a-f]{16,}/g), // Hex IDs
            ...bodyText.matchAll(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g), // UUIDs
            ...bodyText.matchAll(/"([A-Za-z0-9_-]{8,})"/g) // Quoted strings that might be IDs
          ].map(match => match[1] || match[0]);
          
          if (idMatches.length > 0) {
            // Filter and dedupe
            const uniqueIds = [...new Set(idMatches)].slice(0, 10);
            console.log('Found potential text-based IDs:', uniqueIds);
            elementId = uniqueIds[0];
            console.log('Using first found ID for test:', elementId);
          }
        }
        
        if (!elementId) {
          console.log('❌ No element IDs found in document for testing');
          console.log('Available DOM structure:');
          console.log('- JSON formatter rows:', diagnostics.jsonFormatterRows);
          console.log('- Tree nodes:', diagnostics.treeNodes);  
          console.log('- Data extraction IDs:', diagnostics.dataExtractionIds);
          console.log('- Data node IDs:', diagnostics.dataNodeIds);
          
          // Provide a sample of actual content for debugging
          const sampleElements = document.querySelectorAll('.json-formatter-row, .tree-node, [data-extraction-id]');
          if (sampleElements.length > 0) {
            console.log('Sample elements that could contain IDs:');
            Array.from(sampleElements).slice(0, 3).forEach((el, idx) => {
              console.log(`  ${idx + 1}. ${el.tagName}.${el.className} - Text: "${el.textContent?.substring(0, 50)}..."`);
            });
          }
          
          return;
        }
      }
      
      console.log(`Starting navigation test with element ID: "${elementId}"`);
      showToast(`🧪 Testing navigation to: ${elementId}`, 'info', 2000);
      
      // Run the navigation and provide detailed feedback
      const startTime = Date.now();
      const result = navigateToTreeNode(elementId);
      const endTime = Date.now();
      
      console.log(`Navigation attempt completed in ${endTime - startTime}ms`);
      
      // Verify the result
      setTimeout(() => {
        const selectedElements = document.querySelectorAll('.tree-node-selected');
        const testResult = {
          success: !!result,
          foundElement: !!result,
          elementType: result ? result.tagName : null,
          elementClasses: result ? Array.from(result.classList) : null,
          selectedCount: selectedElements.length,
          testDuration: endTime - startTime
        };
        
        console.log('=== TEST RESULTS ===');
        console.log('Test result:', testResult);
        
        if (testResult.success) {
          showToast(`✅ Test successful! Found and navigated to ${elementId}`, 'success', 3000);
        } else {
          showToast(`❌ Test failed! Could not navigate to ${elementId}`, 'error', 3000);
        }
        
        console.log('=== END TREE NAVIGATION TEST ===');
        
      }, 1000); // Allow time for async operations to complete
    };

    // Observe all preview panels for changes
    document.querySelectorAll('.preview').forEach(previewEl => {
      observer.observe(previewEl, { childList: true, subtree: true });
    });
  });
})();
