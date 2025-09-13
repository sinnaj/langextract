(() => {
  // Only initialize if we're in existing run mode
  const urlParams = new URLSearchParams(window.location.search);
  const mode = urlParams.get('mode');
  if (mode !== 'existing') {
    return;
  }

  const $ = (id) => document.getElementById(id);
  
  // State for existing run viewer
  let currentRunId = null;
  let currentFilePath = null;
  let isDevMode = false;
  let isTreeView = true;
  let availableFiles = [];
  
  // Initialize existing run viewer
  document.addEventListener('DOMContentLoaded', async () => {
    console.log('Initializing existing run viewer');
    
    await loadAvailableRuns();
    setupEventListeners();
    
    // Load latest run by default
    await loadLatestRun();
  });
  
  // Load available runs into the dropdown
  async function loadAvailableRuns() {
    try {
      const response = await fetch('/runs');
      const runs = await response.json();
      const select = $('existing-runs-select');
      
      if (!select) return;
      
      // Clear existing options
      select.innerHTML = '<option value="">Select a run...</option>';
      
      // Sort by creation time (most recent first)
      runs.sort((a, b) => b.mtime - a.mtime);
      
      runs.forEach(run => {
        const option = document.createElement('option');
        option.value = run.run_id;
        option.textContent = `${run.run_id} (${new Date(run.mtime * 1000).toLocaleDateString()})`;
        select.appendChild(option);
      });
      
      console.log(`Loaded ${runs.length} available runs`);
    } catch (error) {
      console.error('Error loading available runs:', error);
    }
  }
  
  // Load the latest run by default
  async function loadLatestRun() {
    try {
      const response = await fetch('/runs');
      const runs = await response.json();
      
      if (runs.length > 0) {
        // Sort by creation time (most recent first)
        runs.sort((a, b) => b.mtime - a.mtime);
        const latestRun = runs[0];
        
        // Set the dropdown to the latest run
        const select = $('existing-runs-select');
        if (select) {
          select.value = latestRun.run_id;
        }
        
        // Load the run
        await loadRun(latestRun.run_id);
      }
    } catch (error) {
      console.error('Error loading latest run:', error);
    }
  }
  
  // Load a specific run
  async function loadRun(runId) {
    if (!runId) return;
    
    currentRunId = runId;
    window.currentRunId = runId; // For comments integration
    
    try {
      // Load available files for this run
      const filesResponse = await fetch(`/runs/${runId}/files`);
      availableFiles = await filesResponse.json();
      
      console.log(`Loaded ${availableFiles.length} files for run ${runId}`);
      
      // Update file selector if in dev mode
      updateFileSelector();
      
      // Load the default file (enhanced_extraction_results.json)
      const defaultFile = availableFiles.find(f => 
        f.path.includes('enhanced_extraction_results.json') ||
        f.path.endsWith('enhanced_extraction_results.json')
      );
      
      if (defaultFile) {
        await loadFile(defaultFile.path);
      } else if (availableFiles.length > 0) {
        // Fall back to first available file
        await loadFile(availableFiles[0].path);
      }
      
      // Initialize PDF viewer
      await initializePDFViewer(runId);
      
    } catch (error) {
      console.error('Error loading run:', error);
      updateTreeViewContent('<div class="text-red-500">Error loading run data</div>');
    }
  }
  
  // Load a specific file
  async function loadFile(filePath) {
    if (!currentRunId || !filePath) return;
    
    currentFilePath = filePath;
    
    try {
      const response = await fetch(`/runs/${currentRunId}/file?path=${encodeURIComponent(filePath)}`);
      
      if (!response.ok) {
        throw new Error(`Failed to load file: ${response.statusText}`);
      }
      
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        const data = await response.json();
        await renderFileContent(data, filePath);
      } else {
        const text = await response.text();
        updateTreeViewContent(`<pre>${text}</pre>`);
      }
      
    } catch (error) {
      console.error('Error loading file:', error);
      updateTreeViewContent(`<div class="text-red-500">Error loading file: ${error.message}</div>`);
    }
  }
  
  // Render file content based on view mode
  async function renderFileContent(data, filePath) {
    if (isTreeView && filePath.toLowerCase().endsWith('.json')) {
      await renderTreeView(data);
    } else {
      renderJsonView(data);
    }
  }
  
  // Render tree view using existing preview optimizer
  async function renderTreeView(data) {
    const container = $('tree-view-content');
    if (!container) return;
    
    // Clear existing content
    container.innerHTML = '';
    
    // Create a preview optimizer instance for tree view
    if (typeof PreviewOptimizer !== 'undefined') {
      const optimizer = new PreviewOptimizer(container, {
        maxPreviewSize: 1000000,
        chunkSize: 100000,
        maxInitialLines: 1000
      });
      
      // Enable uber mode for tree visualization
      optimizer.uberMode = true;
      optimizer.currentJsonData = data;
      
      // Render tree view
      if (optimizer.shouldShowTreeVisualization()) {
        optimizer.renderUberMode(data, { size: 0, truncated: false });
        
        // Initialize comments for the tree view
        if (window.treeCommentsUI && currentFilePath) {
          setTimeout(async () => {
            try {
              await window.treeCommentsUI.initializeForFile(currentFilePath, currentRunId);
              console.log('Comments initialized for tree view');
            } catch (error) {
              console.error('Error initializing comments:', error);
            }
          }, 100);
        }
      } else {
        optimizer.renderCompleteJsonView(container, data);
      }
    } else {
      // Fallback to basic JSON display
      renderJsonView(data);
    }
  }
  
  // Render JSON view
  function renderJsonView(data) {
    const container = $('tree-view-content');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (typeof JSONFormatter !== 'undefined') {
      const formatter = new JSONFormatter(data, {
        hoverPreviewEnabled: true,
        theme: 'light'
      });
      container.appendChild(formatter.render());
    } else {
      // Fallback to basic JSON string
      const pre = document.createElement('pre');
      pre.className = 'text-sm overflow-auto';
      pre.textContent = JSON.stringify(data, null, 2);
      container.appendChild(pre);
    }
  }
  
  // Update tree view content
  function updateTreeViewContent(html) {
    const container = $('tree-view-content');
    if (container) {
      container.innerHTML = html;
    }
  }
  
  // Update file selector dropdown
  function updateFileSelector() {
    const select = $('file-selector');
    if (!select) return;
    
    select.innerHTML = '<option value="">Select a file...</option>';
    
    availableFiles.forEach(file => {
      const option = document.createElement('option');
      option.value = file.path;
      option.textContent = file.path;
      
      // Mark current file as selected
      if (file.path === currentFilePath) {
        option.selected = true;
      }
      
      select.appendChild(option);
    });
  }
  
  // Initialize PDF viewer for the run
  async function initializePDFViewer(runId) {
    try {
      // Check if PDF exists for this run
      const response = await fetch(`/api/runs/${runId}/pdf`);
      if (response.ok) {
        // Initialize PDF viewer (this will be handled by existing pdf-viewer.js)
        if (window.initializePDFViewer) {
          window.initializePDFViewer(runId);
        }
      } else {
        // Update PDF status
        const statusEl = document.querySelector('.pdf-status');
        if (statusEl) {
          statusEl.textContent = 'No PDF Available';
        }
      }
    } catch (error) {
      console.warn('PDF not available for this run:', error);
      const statusEl = document.querySelector('.pdf-status');
      if (statusEl) {
        statusEl.textContent = 'PDF Error';
      }
    }
  }
  
  // Setup event listeners
  function setupEventListeners() {
    // Run selector change
    const runSelect = $('existing-runs-select');
    if (runSelect) {
      runSelect.addEventListener('change', async (e) => {
        const runId = e.target.value;
        if (runId) {
          await loadRun(runId);
        }
      });
    }
    
    // Dev mode toggle
    const devToggle = $('dev-mode-toggle');
    if (devToggle) {
      devToggle.addEventListener('click', () => {
        isDevMode = !isDevMode;
        devToggle.setAttribute('data-enabled', isDevMode);
        
        // Update button appearance
        if (isDevMode) {
          devToggle.classList.add('bg-blue-500', 'text-white');
          devToggle.classList.remove('bg-gray-200', 'dark:bg-gray-700');
        } else {
          devToggle.classList.remove('bg-blue-500', 'text-white');
          devToggle.classList.add('bg-gray-200', 'dark:bg-gray-700');
        }
        
        // Show/hide dev controls
        const devControls = $('dev-controls');
        if (devControls) {
          if (isDevMode) {
            devControls.classList.remove('hidden');
            updateFileSelector();
          } else {
            devControls.classList.add('hidden');
          }
        }
      });
    }
    
    // File selector change (dev mode)
    const fileSelect = $('file-selector');
    if (fileSelect) {
      fileSelect.addEventListener('change', async (e) => {
        const filePath = e.target.value;
        if (filePath) {
          await loadFile(filePath);
        }
      });
    }
    
    // View mode toggles (dev mode)
    const treeViewToggle = $('tree-view-toggle');
    const jsonViewToggle = $('json-view-toggle');
    
    if (treeViewToggle && jsonViewToggle) {
      treeViewToggle.addEventListener('click', () => {
        if (!isTreeView) {
          isTreeView = true;
          updateViewToggleButtons();
          if (currentFilePath && currentRunId) {
            loadFile(currentFilePath);
          }
        }
      });
      
      jsonViewToggle.addEventListener('click', () => {
        if (isTreeView) {
          isTreeView = false;
          updateViewToggleButtons();
          if (currentFilePath && currentRunId) {
            loadFile(currentFilePath);
          }
        }
      });
    }
  }
  
  // Update view toggle button states
  function updateViewToggleButtons() {
    const treeViewToggle = $('tree-view-toggle');
    const jsonViewToggle = $('json-view-toggle');
    
    if (treeViewToggle && jsonViewToggle) {
      if (isTreeView) {
        treeViewToggle.className = 'px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600';
        treeViewToggle.setAttribute('data-active', 'true');
        jsonViewToggle.className = 'px-3 py-1 text-xs bg-gray-200 hover:bg-gray-300 rounded dark:bg-gray-700 dark:hover:bg-gray-600';
        jsonViewToggle.setAttribute('data-active', 'false');
      } else {
        jsonViewToggle.className = 'px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600';
        jsonViewToggle.setAttribute('data-active', 'true');
        treeViewToggle.className = 'px-3 py-1 text-xs bg-gray-200 hover:bg-gray-300 rounded dark:bg-gray-700 dark:hover:bg-gray-600';
        treeViewToggle.setAttribute('data-active', 'false');
      }
    }
  }
  
  // Expose functions for external access
  window.existingRunViewer = {
    loadRun,
    loadFile,
    currentRunId: () => currentRunId,
    currentFilePath: () => currentFilePath
  };
  
})();