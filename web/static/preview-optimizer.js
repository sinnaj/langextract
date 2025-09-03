/**
 * Preview Performance Optimizer  
 * Handles large file previews efficiently with progressive loading and virtualization
 */

// Global filter state shared across all PreviewOptimizer instances
window.globalStatisticsFilter = null;

class PreviewOptimizer {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      maxPreviewSize: options.maxPreviewSize || 1000000, // 1MB default
      chunkSize: options.chunkSize || 100000, // 100KB chunks
      maxInitialLines: options.maxInitialLines || 1000,
      lineHeight: options.lineHeight || 20,
      ...options
    };
    
    this.currentFile = null;
    this.isLoading = false;
    this.cache = new Map();
    this._lastSearchQuery = '';
    this.uberMode = false; // UBERMODE state
    this.currentJsonData = null; // Store parsed JSON for UBERMODE
    this.currentFilter = null; // Current statistics filter (null = show all, string = show only that type)
    
    this.init();
  }
  
  init() {
    this.element.style.position = 'relative';
    this.element.style.overflow = 'auto';
    
    // Set up event delegation for filter cards to ensure they always work
    this.element.addEventListener('click', (e) => {
      const filterCard = e.target.closest('.stats-filter-card');
      if (filterCard) {
        const filterType = filterCard.dataset.filterType;
        this.applyStatisticsFilter(filterType === 'total' ? null : filterType);
      }
    });
  }
  
  async loadFile(runId, filePath, fileSize) {
    if (this.isLoading) return;
    
    this.currentFile = { runId, filePath, fileSize };
    this.isLoading = true;
    
    try {
      // Show loading indicator
      this.showLoadingIndicator(filePath, fileSize);
      
      // Check cache first
      const cacheKey = `${runId}:${filePath}`;
      if (this.cache.has(cacheKey)) {
        const cached = this.cache.get(cacheKey);
        this.renderContent(cached.content, cached.contentType, cached.meta);
        return;
      }
      
      // Determine loading strategy based on file size
      if (fileSize > this.options.maxPreviewSize) {
        await this.loadLargeFile(runId, filePath, fileSize);
      } else {
        await this.loadRegularFile(runId, filePath, fileSize);
      }
      
    } catch (error) {
      this.showError(`Error loading file: ${error.message}`);
    } finally {
      this.isLoading = false;
    }
  }
  
  async loadRegularFile(runId, filePath, fileSize) {
    const resp = await fetch(`/runs/${runId}/file?path=${encodeURIComponent(filePath)}`);
    const contentType = resp.headers.get('content-type') || '';
    
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }
    
    const content = await resp.text();
    const meta = {
      size: fileSize,
      truncated: false,
      loadedSize: content.length
    };
    
    // Cache the result
    const cacheKey = `${this.currentFile.runId}:${this.currentFile.filePath}`;
    this.cache.set(cacheKey, { content, contentType, meta });
    
    this.renderContent(content, contentType, meta);
  }
  
  async loadLargeFile(runId, filePath, fileSize) {
    // Use server-side preview truncation for large files
    const maxBytes = Math.min(this.options.maxPreviewSize, fileSize);
    const resp = await fetch(
      `/runs/${runId}/file?path=${encodeURIComponent(filePath)}&preview=1&maxBytes=${maxBytes}`
    );
    
    const contentType = resp.headers.get('content-type') || '';
    const truncated = resp.headers.get('X-Preview-Truncated') === '1';
    const previewSize = parseInt(resp.headers.get('X-Preview-Max-Bytes') || '0');
    
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
    }
    
    const content = await resp.text();
    const meta = {
      size: fileSize,
      truncated: truncated,
      loadedSize: content.length,
      previewSize: previewSize
    };
    
    this.renderContent(content, contentType, meta);
  }
  
  renderContent(content, contentType, meta) {
    // Clear previous content
    this.element.innerHTML = '';
    
    // Add file info header for large/truncated files
    if (meta.truncated || meta.size > this.options.maxPreviewSize) {
      this.addFileInfoHeader(meta);
    }
    
    // Determine content type and render accordingly
    if (this.isJsonContent(contentType)) {
      this.renderJson(content, meta);
    } else if (this.isMarkdownContent(contentType)) {
      this.renderMarkdown(content, meta);  
    } else {
      this.renderText(content, meta);
    }

    // Re-apply search highlights if a search query is active
    if (this._lastSearchQuery) {
      this.applySearchHighlight(this._lastSearchQuery);
    }
  }
  
  addFileInfoHeader(meta) {
    const header = document.createElement('div');
    header.className = 'bg-yellow-50 dark:bg-yellow-900 border border-yellow-200 dark:border-yellow-700 rounded p-2 mb-3 text-sm';
    
    let message = `File size: ${this.formatBytes(meta.size)}`;
    if (meta.truncated) {
      message += ` (showing first ${this.formatBytes(meta.loadedSize)})`;
    }
    
    header.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="text-yellow-800 dark:text-yellow-200">${message}</span>
        ${meta.truncated ? this.createLoadMoreButton() : ''}
      </div>
    `;
    
    this.element.appendChild(header);
  }
  
  createLoadMoreButton() {
    return `
      <button onclick="previewOptimizer.loadFullFile()" 
              class="text-xs bg-yellow-600 hover:bg-yellow-700 text-white px-2 py-1 rounded">
        Load Full File
      </button>
    `;
  }
  
  async loadFullFile() {
    if (!this.currentFile) return;
    
    try {
      this.showLoadingIndicator(this.currentFile.filePath, this.currentFile.fileSize, 'Loading full file...');
      
      // Load without preview flag to get full content
      const resp = await fetch(
        `/runs/${this.currentFile.runId}/file?path=${encodeURIComponent(this.currentFile.filePath)}`
      );
      
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      
      const contentType = resp.headers.get('content-type') || '';
      const content = await resp.text();
      
      // Check if content is too large for efficient rendering
      const lines = content.split('\n');
      if (lines.length > 10000) {
        this.renderLargeContent(content, contentType, lines.length);
      } else {
        const meta = {
          size: this.currentFile.fileSize,
          truncated: false,
          loadedSize: content.length
        };
        this.renderContent(content, contentType, meta);
      }
      
    } catch (error) {
      this.showError(`Error loading full file: ${error.message}`);
    }
  }
  
  renderLargeContent(content, contentType, lineCount) {
    // For very large content, implement virtual scrolling
    this.element.innerHTML = '';
    
    // Add warning
    const warning = document.createElement('div');
    warning.className = 'bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded p-2 mb-3 text-sm';
    warning.innerHTML = `
      <div class="text-red-800 dark:text-red-200">
        Large file (${lineCount.toLocaleString()} lines). Showing first 1000 lines for performance.
        <button onclick="previewOptimizer.enableVirtualScrolling()" 
                class="ml-2 text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-1 rounded">
          Enable Full View
        </button>
      </div>
    `;
    this.element.appendChild(warning);
    
    // Show first 1000 lines
    const lines = content.split('\n');
    const preview = lines.slice(0, 1000).join('\n');
    
    const meta = {
      size: this.currentFile.fileSize,
      truncated: true,
      loadedSize: content.length,
      lineCount: lineCount
    };
    
    this.renderTextContent(preview, meta);
  }
  
  enableVirtualScrolling() {
    // This would implement a virtual scrolling view for very large files
    // For now, show a message about enabling this feature
    const warning = this.element.querySelector('.bg-red-50, .bg-red-900');
    if (warning) {
      warning.innerHTML = `
        <div class="text-red-800 dark:text-red-200">
          Virtual scrolling for large files is being implemented. 
          Consider downloading the file for better performance.
        </div>
      `;
    }
  }
  
  renderJson(content, meta) {
    // Handle JSON Lines formats gracefully
    const lowerPath = (this.currentFile?.filePath || '').toLowerCase();
    const isJsonl = lowerPath.endsWith('.jsonl') || lowerPath.endsWith('.ndjson');
    if (isJsonl) {
      return this.renderJsonl(content, meta);
    }

    try {
      const obj = JSON.parse(content);
      this.currentJsonData = obj; // Store for UBERMODE
      
      console.log('JSON parsed successfully, data available for UBERMODE:', !!obj);
      console.log('Current UBERMODE state:', this.uberMode);

      // Check if UBERMODE is enabled and if this panel should show tree visualization
      const shouldShowTreeView = this.shouldShowTreeVisualization();
      console.log('Should show tree view:', shouldShowTreeView);
      
      if (this.uberMode && shouldShowTreeView) {
        console.log('UBERMODE is enabled and this panel should show tree view');
        this.renderUberMode(obj, meta);
        return;
      }

      const pretty = JSON.stringify(obj, null, 2);

      // Prefer JSONFormatter for structured view if available and content size is reasonable
      if (typeof JSONFormatter !== 'undefined' && pretty.length <= 1000000) { // 1MB
        this.renderEnhancedJsonObject(obj, meta);
        return;
      }

      // Fallback to pretty-printed code if too large or formatter missing
      if (pretty.length > 1000000) {
        this.renderTextContent(content, meta, 'json');
      } else {
        this.renderEnhancedJson(pretty, meta);
      }
    } catch (e) {
      // Invalid JSON, render as text
      this.renderTextContent(content, meta);
    }
  }
  
  renderJsonl(content, meta) {
    const lines = content.split('\n');
    const total = lines.length;
    const maxLines = 200; // avoid DOM explosion
    const shown = Math.min(total, maxLines);

    const container = document.createElement('div');
    container.className = 'jsonl-viewer space-y-2';

    // Info banner
    const info = document.createElement('div');
    info.className = 'text-xs text-gray-500';
    info.textContent = `JSONL preview: showing first ${shown.toLocaleString()} of ${total.toLocaleString()} lines`;
    container.appendChild(info);

    for (let i = 0; i < shown; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const block = document.createElement('div');
      block.className = 'rounded border border-gray-200 dark:border-gray-700 p-2 bg-white dark:bg-gray-800';

      const header = document.createElement('div');
      header.className = 'text-xs text-gray-400 mb-1';
      header.textContent = `Line ${i + 1}`;
      block.appendChild(header);

      try {
        const obj = JSON.parse(line);
        if (typeof JSONFormatter !== 'undefined') {
          const formatter = new JSONFormatter(obj, Number.POSITIVE_INFINITY, { theme: 'dark' });
          block.appendChild(formatter.render());
        } else {
          const pretty = JSON.stringify(obj, null, 2);
          const pre = document.createElement('pre');
          const code = document.createElement('code');
          code.className = 'language-json';
          code.textContent = pretty;
          pre.appendChild(code);
          block.appendChild(pre);
        }
      } catch (e) {
        // Not a JSON line; show raw
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.textContent = line;
        pre.appendChild(code);
        block.appendChild(pre);
      }

      container.appendChild(block);
    }

    this.element.innerHTML = '';
    this.element.appendChild(container);
    this.applySyntaxHighlighting();
  }

  renderEnhancedJson(jsonString, meta) {
    // Prefer JSONFormatter for interactive, collapsible JSON rendering if available
    if (typeof JSONFormatter !== 'undefined') {
      try {
        const obj = JSON.parse(jsonString);
        const formatter = new JSONFormatter(obj, Number.POSITIVE_INFINITY, {
          theme: 'dark' // theme hint; CSS controls final look
        });
        const container = document.createElement('div');
        container.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-lg p-2 overflow-auto';
        container.appendChild(formatter.render());
        this.element.appendChild(container);
        return;
      } catch (e) {
        // Fallback to code block rendering below
      }
    }

    // Fallback: pretty-print with syntax highlighting
    const container = document.createElement('div');
    container.className = 'json-viewer relative bg-gray-50 dark:bg-gray-900 rounded-lg overflow-auto';
    const pre = document.createElement('pre');
    pre.className = 'font-mono text-sm leading-relaxed m-0';
    const code = document.createElement('code');
    code.className = 'language-json';
    code.textContent = jsonString;
    pre.appendChild(code);
    container.appendChild(pre);
    this.element.appendChild(container);
    if (typeof hljs !== 'undefined') {
      setTimeout(() => { try { hljs.highlightElement(code); } catch(e){} }, 50);
    }
  }

  renderEnhancedJsonObject(obj, meta, options = {}) {
    // Use JSONFormatter directly on parsed object with enhanced controls
    try {
      // Create main container with controls
      const mainContainer = document.createElement('div');
      mainContainer.className = 'enhanced-json-container';
      
      // Add JSON control toolbar
      const toolbar = this.createJsonToolbar();
      mainContainer.appendChild(toolbar);
      
      // Create JSON viewer container
      const container = document.createElement('div');
      container.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 relative';
      
      // Add line numbers toggle state
      const showLineNumbers = this.getJsonPreference('lineNumbers', true);
      const wordWrap = this.getJsonPreference('wordWrap', false);
      
      // Create the content wrapper
      const contentWrapper = document.createElement('div');
      contentWrapper.className = `json-content-wrapper ${wordWrap ? 'word-wrap' : 'no-wrap'}`;
      
      // Determine if we need horizontal scroll
      const jsonDepth = this.calculateJsonDepth(obj);
      const needsHorizontalScroll = !wordWrap || jsonDepth > 2;
      
      if (needsHorizontalScroll) {
        contentWrapper.style.overflowX = 'auto';
        contentWrapper.style.whiteSpace = 'nowrap';
      } else {
        contentWrapper.style.overflowX = 'hidden';
        contentWrapper.style.whiteSpace = 'pre-wrap';
      }
      
      // Create line numbers container if enabled
      let lineNumbersContainer = null;
      if (showLineNumbers) {
        lineNumbersContainer = document.createElement('div');
        lineNumbersContainer.className = 'line-numbers-container bg-gray-100 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 font-mono select-none';
        lineNumbersContainer.style.cssText = `
          position: absolute;
          top: 0;
          left: 0;
          width: 60px;
          height: 100%;
          overflow: hidden;
          padding: 12px 8px;
          z-index: 2;
        `;
        container.appendChild(lineNumbersContainer);
        
        // Adjust content padding for line numbers
        contentWrapper.style.paddingLeft = '68px';
      }
      
      // Create JSONFormatter with custom styling
      const formatter = new JSONFormatter(obj, options.maxDepth || 3, {
        hoverPreviewEnabled: true,
        hoverPreviewArrayCount: 100,
        hoverPreviewFieldCount: 5,
        animateOpen: true,
        animateClose: true,
        theme: 'default'
      });
      
      const formatterElement = formatter.render();
      formatterElement.style.padding = '12px';
      formatterElement.style.minHeight = '100%';
      
      contentWrapper.appendChild(formatterElement);
      container.appendChild(contentWrapper);
      
      // Generate line numbers if enabled
      if (showLineNumbers && lineNumbersContainer) {
        this.generateJsonLineNumbers(obj, lineNumbersContainer);
      }
      
      mainContainer.appendChild(container);
      this.element.appendChild(mainContainer);
      
      // Store references for control updates
      this.jsonContainer = container;
      this.jsonContentWrapper = contentWrapper;
      this.jsonLineNumbersContainer = lineNumbersContainer;
      
    } catch (e) {
      console.error('JSONFormatter failed:', e);
      // Fallback: pretty print with enhanced controls
      const pretty = JSON.stringify(obj, null, 2);
      this.renderEnhancedJsonWithControls(pretty, meta);
    }
  }

  // Create JSON control toolbar
  createJsonToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'json-toolbar flex items-center justify-between bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-t-lg px-4 py-2 text-sm';
    
    // Left side controls
    const leftControls = document.createElement('div');
    leftControls.className = 'flex items-center space-x-4';
    
    // Line numbers toggle
    const lineNumbersToggle = this.createToggleButton('line-numbers', 'Line Numbers', this.getJsonPreference('lineNumbers', true));
    lineNumbersToggle.addEventListener('change', (e) => {
      this.setJsonPreference('lineNumbers', e.target.checked);
      this.updateJsonDisplay();
    });
    leftControls.appendChild(lineNumbersToggle);
    
    // Word wrap toggle
    const wordWrapToggle = this.createToggleButton('word-wrap', 'Word Wrap', this.getJsonPreference('wordWrap', false));
    wordWrapToggle.addEventListener('change', (e) => {
      this.setJsonPreference('wordWrap', e.target.checked);
      this.updateJsonDisplay();
    });
    leftControls.appendChild(wordWrapToggle);
    
    // Right side info
    const rightInfo = document.createElement('div');
    rightInfo.className = 'flex items-center space-x-2 text-xs text-gray-500 dark:text-gray-400';
    
    const jsonInfo = document.createElement('span');
    if (this.currentJsonData && this.currentJsonData.extractions) {
      jsonInfo.textContent = `${this.currentJsonData.extractions.length} extractions`;
    } else {
      jsonInfo.textContent = 'JSON Preview';
    }
    rightInfo.appendChild(jsonInfo);
    
    toolbar.appendChild(leftControls);
    toolbar.appendChild(rightInfo);
    
    return toolbar;
  }

  // Create toggle button component
  createToggleButton(id, label, checked) {
    const container = document.createElement('label');
    container.className = 'flex items-center space-x-2 cursor-pointer';
    container.setAttribute('for', `${id}-toggle`);
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = `${id}-toggle`;
    checkbox.checked = checked;
    checkbox.className = 'rounded border-gray-300 text-blue-600 focus:ring-blue-500 focus:ring-2';
    
    const labelText = document.createElement('span');
    labelText.textContent = label;
    labelText.className = 'text-gray-700 dark:text-gray-300 select-none';
    
    container.appendChild(checkbox);
    container.appendChild(labelText);
    
    return container;
  }

  // Calculate maximum depth of JSON object
  calculateJsonDepth(obj, currentDepth = 0) {
    if (typeof obj !== 'object' || obj === null) {
      return currentDepth;
    }
    
    let maxDepth = currentDepth;
    for (const value of Object.values(obj)) {
      if (typeof value === 'object' && value !== null) {
        const depth = this.calculateJsonDepth(value, currentDepth + 1);
        maxDepth = Math.max(maxDepth, depth);
      }
    }
    
    return maxDepth;
  }

  // Generate line numbers for JSON
  generateJsonLineNumbers(obj, container) {
    const pretty = JSON.stringify(obj, null, 2);
    const lines = pretty.split('\n');
    const maxLength = lines.length.toString().length;
    
    container.innerHTML = '';
    for (let i = 1; i <= lines.length; i++) {
      const lineNumber = document.createElement('div');
      lineNumber.className = 'line-number';
      lineNumber.textContent = i.toString().padStart(maxLength, ' ');
      lineNumber.style.height = '20px'; // Match typical line height
      container.appendChild(lineNumber);
    }
  }

  // Update JSON display when preferences change
  updateJsonDisplay() {
    if (!this.currentJsonData) return;
    
    // Find the JSON container and re-render
    const container = this.element.querySelector('.enhanced-json-container');
    if (container) {
      // Remove existing JSON display
      this.element.removeChild(container);
      
      // Re-render with updated preferences
      this.renderEnhancedJsonObject(this.currentJsonData, { size: 0, truncated: false });
    }
  }

  // JSON preference storage helpers
  getJsonPreference(key, defaultValue) {
    try {
      const stored = localStorage.getItem(`langextract_json_${key}`);
      return stored !== null ? JSON.parse(stored) : defaultValue;
    } catch (e) {
      return defaultValue;
    }
  }

  setJsonPreference(key, value) {
    try {
      localStorage.setItem(`langextract_json_${key}`, JSON.stringify(value));
    } catch (e) {
      console.warn('Failed to save JSON preference:', e);
    }
  }

  // Enhanced JSON fallback with controls (for when JSONFormatter is not available)
  renderEnhancedJsonWithControls(pretty, meta) {
    const mainContainer = document.createElement('div');
    mainContainer.className = 'enhanced-json-container';
    
    // Add toolbar
    const toolbar = this.createJsonToolbar();
    mainContainer.appendChild(toolbar);
    
    // Create enhanced JSON viewer
    const container = document.createElement('div');
    container.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 overflow-auto relative';
    
    const showLineNumbers = this.getJsonPreference('lineNumbers', true);
    const wordWrap = this.getJsonPreference('wordWrap', false);
    
    if (showLineNumbers) {
      container.style.paddingLeft = '60px';
      this.addLineNumbers(container, pretty);
    }
    
    const pre = document.createElement('pre');
    pre.className = 'text-sm p-4 m-0';
    pre.style.whiteSpace = wordWrap ? 'pre-wrap' : 'pre';
    pre.style.overflowX = wordWrap ? 'hidden' : 'auto';
    
    const code = document.createElement('code');
    code.className = 'text-gray-900 dark:text-gray-100';
    code.textContent = pretty;
    
    pre.appendChild(code);
    container.appendChild(pre);
    mainContainer.appendChild(container);
    
    this.element.appendChild(mainContainer);
  }

  // Add line numbers to plain text JSON
  addLineNumbers(container, content) {
    const lines = content.split('\n');
    const lineNumbersContainer = document.createElement('div');
    lineNumbersContainer.className = 'line-numbers-container absolute left-0 top-0 bg-gray-100 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 font-mono select-none p-4';
    lineNumbersContainer.style.width = '60px';
    lineNumbersContainer.style.zIndex = '2';
    
    for (let i = 1; i <= lines.length; i++) {
      const lineNumber = document.createElement('div');
      lineNumber.textContent = i.toString();
      lineNumber.style.height = '20px';
      lineNumber.style.textAlign = 'right';
      lineNumber.style.paddingRight = '8px';
      lineNumbersContainer.appendChild(lineNumber);
    }
    
    container.appendChild(lineNumbersContainer);
  }
  
  isExpandableLine(trimmedLine, lines, index) {
    // Check if this line starts an object or array
    if (trimmedLine.endsWith('{') || trimmedLine.endsWith('[')) {
      // Look ahead to see if there's content to collapse
      let bracketCount = 0;
      const isArray = trimmedLine.endsWith('[');
      const openBracket = isArray ? '[' : '{';
      const closeBracket = isArray ? ']' : '}';
      
      for (let i = index; i < lines.length; i++) {
        const line = lines[i];
        for (const char of line) {
          if (char === openBracket) bracketCount++;
          if (char === closeBracket) bracketCount--;
          
          if (bracketCount === 0 && i > index) {
            // Found the closing bracket, this is expandable
            return true;
          }
        }
      }
    }
    return false;
  }
  
  toggleJsonSection(toggleBtn) {
    const isCollapsed = toggleBtn.getAttribute('data-collapsed') === 'true';
    const contentLine = toggleBtn.closest('.json-line');
    const lineNumber = parseInt(contentLine.getAttribute('data-line'));
    
    if (isCollapsed) {
      // Expand
      toggleBtn.innerHTML = '▼';
      toggleBtn.setAttribute('data-collapsed', 'false');
      this.showJsonSection(contentLine, lineNumber);
    } else {
      // Collapse
      toggleBtn.innerHTML = '▶';
      toggleBtn.setAttribute('data-collapsed', 'true');
      this.hideJsonSection(contentLine, lineNumber);
    }
  }
  
  showJsonSection(startLine, startLineNumber) {
    const container = startLine.closest('.json-viewer');
    const allLines = container.querySelectorAll('.json-line');
    
    // Find the matching closing bracket
    const endLineNumber = this.findMatchingClosingLine(startLine, startLineNumber, allLines);
    
    // Show all lines in between
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i];
      const currentLineNum = parseInt(line.getAttribute('data-line'));
      
      if (currentLineNum > startLineNumber && currentLineNum <= endLineNumber) {
        line.style.display = '';
        // Also show corresponding gutter line
        const gutterLines = container.querySelectorAll('.flex-shrink-0 > div');
        if (gutterLines[currentLineNum - 1]) {
          gutterLines[currentLineNum - 1].style.display = '';
        }
      }
    }
  }
  
  hideJsonSection(startLine, startLineNumber) {
    const container = startLine.closest('.json-viewer');
    const allLines = container.querySelectorAll('.json-line');
    
    // Find the matching closing bracket
    const endLineNumber = this.findMatchingClosingLine(startLine, startLineNumber, allLines);
    
    // Hide all lines in between (but not the closing line)
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i];
      const currentLineNum = parseInt(line.getAttribute('data-line'));
      
      if (currentLineNum > startLineNumber && currentLineNum < endLineNumber) {
        line.style.display = 'none';
        // Also hide corresponding gutter line
        const gutterLines = container.querySelectorAll('.flex-shrink-0 > div');
        if (gutterLines[currentLineNum - 1]) {
          gutterLines[currentLineNum - 1].style.display = 'none';
        }
      }
    }
  }
  
  findMatchingClosingLine(startLine, startLineNumber, allLines) {
    const startText = startLine.textContent.trim();
    const isArray = startText.endsWith('[');
    const openBracket = isArray ? '[' : '{';
    const closeBracket = isArray ? ']' : '}';
    
    let bracketCount = 0;
    
    for (let i = 0; i < allLines.length; i++) {
      const line = allLines[i];
      const currentLineNum = parseInt(line.getAttribute('data-line'));
      
      if (currentLineNum >= startLineNumber) {
        const lineText = line.textContent;
        
        for (const char of lineText) {
          if (char === openBracket) bracketCount++;
          if (char === closeBracket) bracketCount--;
          
          if (bracketCount === 0 && currentLineNum > startLineNumber) {
            return currentLineNum;
          }
        }
      }
    }
    
    return startLineNumber; // Fallback if no matching bracket found
  }

  getIndentLevel(line) {
    const match = line.match(/^(\s*)/);
    return match ? Math.floor(match[1].length / 2) : 0; // Assuming 2 spaces per indent
  }
  
  renderMarkdown(content, meta) {
    try {
      if (typeof marked !== 'undefined' && typeof DOMPurify !== 'undefined') {
        const rawHtml = marked.parse(content, { mangle: false, headerIds: true });
        const safeHtml = DOMPurify.sanitize(rawHtml);
        // Prefer GitHub Markdown CSS if present
        const container = document.createElement('div');
        container.className = 'markdown-body prose dark:prose-invert max-w-none';
        container.innerHTML = safeHtml;
        this.element.appendChild(container);
        
        // Apply syntax highlighting to code blocks
        this.applySyntaxHighlighting();
      } else {
        // Fallback to text rendering
        this.renderTextContent(content, meta);
      }
    } catch (e) {
      this.renderTextContent(content, meta);
    }
  }
  
  renderText(content, meta) {
    this.renderTextContent(content, meta);
  }
  
  renderTextContent(content, meta, language = null) {
    const pre = document.createElement('pre');
    pre.className = 'whitespace-pre-wrap font-mono text-sm';
    
    const code = document.createElement('code');
    if (language) {
      code.className = `language-${language}`;
    }
    code.textContent = content;
    
    pre.appendChild(code);
    this.element.appendChild(pre);
    
    // Apply syntax highlighting if available (debounced for performance)
    if (typeof hljs !== 'undefined') {
      setTimeout(() => {
        try {
          hljs.highlightElement(code);
        } catch (e) {
          // Ignore highlighting errors
        }
      }, 100);
    }
  }
  
  applySyntaxHighlighting() {
    if (typeof hljs === 'undefined') return;
    
    const codeBlocks = this.element.querySelectorAll('pre code');
    codeBlocks.forEach((block, index) => {
      // Stagger highlighting to avoid blocking the UI
      setTimeout(() => {
        try {
          hljs.highlightElement(block);
        } catch (e) {
          // Ignore highlighting errors
        }
      }, index * 10);
    });
  }
  
  showLoadingIndicator(filePath, fileSize, message = 'Loading...') {
    this.element.innerHTML = `
      <div class="flex items-center justify-center h-64 text-gray-500">
        <div class="text-center">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 dark:border-white mx-auto mb-2"></div>
          <div class="text-sm">${message}</div>
          <div class="text-xs text-gray-400 mt-1">
            ${filePath} (${this.formatBytes(fileSize)})
          </div>
        </div>
      </div>
    `;
  }
  
  showError(message) {
    this.element.innerHTML = `
      <div class="flex items-center justify-center h-64 text-red-600">
        <div class="text-center">
          <div class="text-lg mb-2">⚠️</div>
          <div class="text-sm">${message}</div>
        </div>
      </div>
    `;
  }
  
  isJsonContent(contentType) {
    return contentType.includes('application/json') || 
           this.currentFile?.filePath?.toLowerCase().endsWith('.json') ||
           this.currentFile?.filePath?.toLowerCase().endsWith('.jsonl');
  }
  
  isMarkdownContent(contentType) {
    return contentType.includes('text/markdown') ||
           this.currentFile?.filePath?.toLowerCase().endsWith('.md');
  }
  
  formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }
  
  clearCache() {
    this.cache.clear();
  }
  
  search(query) {
    if (!query || !this.element.textContent) return [];
    // Clear previous highlights, then apply new
    this.clearSearchHighlight();
    this._lastSearchQuery = query;
    const results = this.applySearchHighlight(query);
    return results;
  }

  clearSearchHighlight() {
    // Remove existing highlights
    const marks = this.element.querySelectorAll('.search-highlight');
    marks.forEach(mark => {
      const parent = mark.parentNode;
      if (!parent) return;
      // Replace the mark with its text content
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      // Merge adjacent text nodes if needed
      parent.normalize && parent.normalize();
    });
  }

  applySearchHighlight(query) {
    const lc = query.toLowerCase();
    const textNodes = this._collectTextNodes(this.element);
    const results = [];
    textNodes.forEach(node => {
      const text = node.nodeValue;
      if (!text) return;
      const idx = text.toLowerCase().indexOf(lc);
      if (idx === -1) return;
      // Split node: before, match, after
      const before = document.createTextNode(text.slice(0, idx));
      const matchText = text.slice(idx, idx + query.length);
      const after = document.createTextNode(text.slice(idx + query.length));
      const mark = document.createElement('span');
      mark.className = 'search-highlight';
      mark.textContent = matchText;
      const parent = node.parentNode;
      if (!parent) return;
      parent.replaceChild(after, node);
      parent.insertBefore(mark, after);
      parent.insertBefore(before, mark);
      results.push({ text: matchText });
    });
    return results;
  }

  _collectTextNodes(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (node) => {
        // Skip highlighting inside scripts and styles
        const p = node.parentNode;
        if (!p || (p.tagName && /^(SCRIPT|STYLE)$/.test(p.tagName))) return NodeFilter.FILTER_REJECT;
        // Skip highlights themselves
        if (p.classList && p.classList.contains('search-highlight')) return NodeFilter.FILTER_REJECT;
        // Only consider reasonably sized nodes
        if (node.nodeValue && node.nodeValue.trim().length > 0) return NodeFilter.FILTER_ACCEPT;
        return NodeFilter.FILTER_REJECT;
      }
    });
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    return nodes;
  }

  // UBERMODE Methods
  shouldShowTreeVisualization() {
    // If UBERMODE is not enabled, never show tree visualization
    if (!this.uberMode) {
      return false;
    }

    // Get current panel configuration
    const selectedFilePaths = window.selectedFilePaths || [null, null, null];
    const currentColumnCount = window.currentColumnCount || 1;
    
    // Find which panel this optimizer instance belongs to
    const currentPanelIndex = this.findCurrentPanelIndex();
    console.log(`Current panel index: ${currentPanelIndex}`);
    
    if (currentPanelIndex === -1) {
      console.warn('Could not determine current panel index');
      return true; // Default to showing tree view if we can't determine
    }
    
    // Find all JSON panel indices
    const jsonPanelIndices = [];
    for (let i = 0; i < Math.min(selectedFilePaths.length, currentColumnCount); i++) {
      const filePath = selectedFilePaths[i];
      if (filePath && filePath.toLowerCase().endsWith('.json')) {
        jsonPanelIndices.push(i);
      }
    }
    
    console.log(`JSON panels found: ${jsonPanelIndices.join(', ')}`);
    console.log(`Current panel ${currentPanelIndex}, leftmost JSON panel: ${jsonPanelIndices[0]}`);
    
    // Show tree visualization only in the leftmost JSON panel
    const shouldShow = jsonPanelIndices.length > 0 && currentPanelIndex === jsonPanelIndices[0];
    console.log(`Should show tree visualization: ${shouldShow} (multiple JSON panels: ${jsonPanelIndices.length > 1})`);
    
    return shouldShow;
  }
  
  findCurrentPanelIndex() {
    // Try to find which panel this optimizer instance belongs to
    // We can do this by comparing the preview element with the panel elements
    const panels = document.querySelectorAll('.preview-panel');
    
    for (let i = 0; i < panels.length; i++) {
      const panel = panels[i];
      const previewElement = panel.querySelector('.preview');
      if (previewElement === this.element) {
        return i;
      }
    }
    
    return -1; // Not found
  }

  toggleUberMode() {
    this.uberMode = !this.uberMode;
    
    // Update stats visibility
    this.updateStatsVisibility();
    
    // Re-render current content if available and it's JSON
    if (this.currentJsonData) {
      // Clear the element first
      this.element.innerHTML = '';
      
      const shouldShowTreeView = this.shouldShowTreeVisualization();
      
      if (this.uberMode && shouldShowTreeView) {
        this.renderUberMode(this.currentJsonData, { size: 0, truncated: false });
      } else {
        // Re-render with normal JSON view
        if (typeof JSONFormatter !== 'undefined') {
          this.renderEnhancedJsonObject(this.currentJsonData, { size: 0, truncated: false });
        } else {
          const pretty = JSON.stringify(this.currentJsonData, null, 2);
          this.renderEnhancedJson(pretty, { size: 0, truncated: false });
        }
      }
    }
    
    return this.uberMode;
  }

  updateStatsVisibility() {
    const statsSection = document.querySelector('.ubermode-stats');
    if (statsSection) {
      if (this.uberMode) {
        statsSection.classList.remove('hidden');
      } else {
        statsSection.classList.add('hidden');
      }
    }
  }

  renderUberMode(jsonData, meta) {
    // Clear previous content
    this.element.innerHTML = '';
    
    // Update stats
    this.updateUberModeStats(jsonData);
    
    // Create UBERMODE container
    const container = document.createElement('div');
    container.className = 'ubermode-container space-y-4';
    
    // Render tree visualization
    const treeContainer = this.createTreeVisualization(jsonData);
    container.appendChild(treeContainer);
    
    this.element.appendChild(container);
  }

  updateUberModeStats(jsonData) {
    const stats = this.analyzeJsonData(jsonData);
    
    // Dynamically update the statistics container based on actual data
    this.updateStatsContainer(stats);
  }

  analyzeJsonData(data) {
    const stats = {
      totalItems: 0,
      types: new Map(),
      quality: '—'
    };
    
    // Handle extraction format - count by extraction_class
    if (data && data.extractions && Array.isArray(data.extractions)) {
      data.extractions.forEach(extraction => {
        stats.totalItems++;
        
        // Count extraction types dynamically
        const extractionClass = extraction.extraction_class;
        if (extractionClass) {
          const currentCount = stats.types.get(extractionClass) || 0;
          stats.types.set(extractionClass, currentCount + 1);
        }
        
        // Quality indicators (check if any extraction has quality info)
        if (extraction.quality && stats.quality === '—') {
          const errors = extraction.quality.errors?.length || 0;
          const warnings = extraction.quality.warnings?.length || 0;
          if (errors > 0) {
            stats.quality = `${errors} errors`;
          } else if (warnings > 0) {
            stats.quality = `${warnings} warnings`;
          } else {
            stats.quality = 'Good';
          }
        }
      });
    }
    
    return stats;
  }

  updateStatsContainer(stats) {
    // Find the stats content container within this element's scope
    const statsContent = this.element.querySelector('.stats-content');
    if (!statsContent) return;

    // Find the grid containers
    const gridContainers = statsContent.querySelectorAll('.grid');
    if (gridContainers.length < 2) return;

    const firstGrid = gridContainers[0];
    const secondGrid = gridContainers[1];

    // Clear existing stats (keep only Total Items in first position)
    const totalItemsActive = window.globalStatisticsFilter === null ? 'border-blue-500 ring-2 ring-blue-200' : '';
    firstGrid.innerHTML = `
      <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 p-3 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 stats-filter-card ${totalItemsActive}" data-filter-type="total">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Items</div>
        <div class="text-lg font-mono font-semibold text-gray-900 dark:text-gray-100">${this.formatNumber(stats.totalItems)}</div>
      </div>
    `;

    // Sort types by count (descending) and create dynamic stats
    const sortedTypes = Array.from(stats.types.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 7); // Limit to 7 types to fit the layout

    // Define colors for different types
    const colors = [
      'text-blue-600 dark:text-blue-400',
      'text-green-600 dark:text-green-400', 
      'text-purple-600 dark:text-purple-400',
      'text-orange-600 dark:text-orange-400',
      'text-teal-600 dark:text-teal-400',
      'text-pink-600 dark:text-pink-400',
      'text-indigo-600 dark:text-indigo-400'
    ];

    // Add type stats to the first grid (up to 3 more items to make 4 total)
    sortedTypes.slice(0, 3).forEach((type, index) => {
      const [typeName, count] = type;
      const colorClass = colors[index];
      const displayName = this.formatTypeName(typeName);
      const isActive = window.globalStatisticsFilter === typeName ? 'border-blue-500 ring-2 ring-blue-200' : '';
      
      firstGrid.innerHTML += `
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 p-3 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 stats-filter-card ${isActive}" data-filter-type="${typeName}">
          <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">${displayName}</div>
          <div class="text-lg font-mono font-semibold ${colorClass}">${this.formatNumber(count)}</div>
        </div>
      `;
    });

    // Add remaining types to the second grid (up to 4 items)
    secondGrid.innerHTML = '';
    sortedTypes.slice(3, 7).forEach((type, index) => {
      const [typeName, count] = type;
      const colorClass = colors[index + 3];
      const displayName = this.formatTypeName(typeName);
      const isActive = window.globalStatisticsFilter === typeName ? 'border-blue-500 ring-2 ring-blue-200' : '';
      
      secondGrid.innerHTML += `
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 p-3 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 stats-filter-card ${isActive}" data-filter-type="${typeName}">
          <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">${displayName}</div>
          <div class="text-lg font-mono font-semibold ${colorClass}">${this.formatNumber(count)}</div>
        </div>
      `;
    });

    // Add Quality indicator if we have room
    if (sortedTypes.length <= 6 && stats.quality !== '—') {
      secondGrid.innerHTML += `
        <div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 p-3">
          <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Quality</div>
          <div class="text-lg font-mono font-semibold text-red-600 dark:text-red-400">${stats.quality}</div>
        </div>
      `;
    }

    // Update grid layout based on number of items
    const firstGridItemCount = 1 + Math.min(3, sortedTypes.length);
    const secondGridItemCount = Math.max(0, sortedTypes.length - 3) + (stats.quality !== '—' && sortedTypes.length <= 6 ? 1 : 0);
    
    // Adjust grid columns
    firstGrid.className = `grid gap-3 mb-3 grid-cols-2 sm:grid-cols-${Math.min(4, firstGridItemCount)}`;
    if (secondGridItemCount > 0) {
      secondGrid.className = `grid gap-3 grid-cols-2 sm:grid-cols-${Math.min(4, secondGridItemCount)}`;
    }

    // Event listeners are handled by event delegation in init() method
  }

  formatTypeName(typeName) {
    // Convert extraction class names to more readable format
    const formatMap = {
      'LEGAL_DOCUMENT': 'Legal Docs',
      'Legal_Document': 'Legal Docs',
      'NORM': 'Norms',
      'Parameter': 'Parameters',
      'Procedure': 'Procedures',
      'SECTION': 'Sections',
      'Tag': 'Tags',
      'TABLE': 'Tables',
      'LOCATION': 'Locations',
      'QUESTION': 'Questions'
    };
    
    return formatMap[typeName] || typeName;
  }

  createTreeVisualization(data) {
    const container = document.createElement('div');
    container.className = 'tree-visualization bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4';
    
    const title = document.createElement('h3');
    title.className = 'text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200';
    title.textContent = '🌳 Document Structure';
    container.appendChild(title);
    
    const tree = document.createElement('div');
    tree.className = 'tree-content space-y-1';
    
    // Build document tree from extraction data
    const documentTree = this.buildDocumentTree(data);
    this.renderDocumentTree(tree, documentTree);
    
    container.appendChild(tree);
    return container;
  }

  buildDocumentTree(data) {
    const nodes = new Map();
    const rootNodes = [];
    
    // Handle extraction format
    if (data && data.extractions && Array.isArray(data.extractions)) {
      // Filter relevant extraction types like section_tree_visualizer.py does
      const relevantTypes = ['SECTION', 'NORM', 'TABLE', 'LEGAL_DOCUMENT'];
      let relevant = data.extractions.filter(ext => 
        relevantTypes.includes(ext.extraction_class)
      );
      
      // Apply statistics filter if one is active
      const currentFilter = window.globalStatisticsFilter;
      if (currentFilter) {
        console.log(`Filtering extractions by type: ${currentFilter}`);
        
        // Get all extractions that match the filter
        const filteredExtractions = data.extractions.filter(ext => 
          ext.extraction_class === currentFilter
        );
        
        // If we're filtering, we need to also include parent nodes to maintain hierarchy
        const requiredNodeIds = new Set();
        
        // Add filtered nodes and collect their parent chain
        filteredExtractions.forEach(ext => {
          const attrs = ext.attributes || {};
          const nodeId = attrs.id;
          if (nodeId) {
            requiredNodeIds.add(nodeId);
            
            // Add parent chain
            let parentId = this.getParentId(ext);
            while (parentId) {
              requiredNodeIds.add(parentId);
              // Find parent extraction to continue the chain
              const parentExt = data.extractions.find(e => e.attributes?.id === parentId);
              parentId = parentExt ? this.getParentId(parentExt) : null;
            }
          }
        });
        
        // Filter relevant extractions to only include required nodes
        relevant = relevant.filter(ext => {
          const nodeId = ext.attributes?.id;
          return nodeId && requiredNodeIds.has(nodeId);
        });
        
        console.log(`Filtered from ${data.extractions.length} total to ${relevant.length} relevant nodes for filter: ${currentFilter}`);
      }
      
      console.log(`Building tree from ${relevant.length} relevant extractions out of ${data.extractions.length} total`);
      
      // First pass: create all nodes (following section_tree_visualizer.py pattern)
      relevant.forEach(extraction => {
        const attrs = extraction.attributes || {};
        const nodeId = attrs.id;
        if (!nodeId) {
          console.warn('Skipping extraction without ID:', extraction);
          return;
        }
        
        const nodeData = {
          id: nodeId,
          title: this.getNodeTitle(extraction),
          type: extraction.extraction_class,
          parentId: this.getParentId(extraction),
          parentType: attrs.parent_type,
          summary: this.getNodeSummary(extraction),
          extractionText: extraction.extraction_text || '',
          children: [],
          isExpanded: false, // Start collapsed for better UX
          level: 0, // Will be set during tree building
          attributes: attrs,
          extraction: extraction // Store the full extraction for reference
        };
        
        nodes.set(nodeId, nodeData);
        console.log(`Created node: ${nodeId} (${nodeData.type}) -> parent: ${nodeData.parentId || 'ROOT'}`);
      });
      
      // Check if we need to create synthetic root nodes (following section_tree_visualizer.py)
      this.createSyntheticRoots(nodes);
      
      // Second pass: build parent-child relationships
      let orphanCount = 0;
      nodes.forEach(node => {
        if (node.parentId && nodes.has(node.parentId)) {
          const parent = nodes.get(node.parentId);
          parent.children.push(node);
          node.level = parent.level + 1;
          console.log(`Linked ${node.id} as child of ${parent.id} (level ${node.level})`);
        } else {
          // Node has no valid parent, make it a root
          rootNodes.push(node);
          node.level = 0;
          if (node.parentId) {
            console.warn(`Node ${node.id} has parent ${node.parentId} but parent not found - making it root`);
            orphanCount++;
          } else {
            console.log(`Node ${node.id} is a root node`);
          }
        }
      });
      
      if (orphanCount > 0) {
        console.warn(`Found ${orphanCount} orphaned nodes that were promoted to root level`);
      }
      
      // Sort children by ID for consistent ordering (following section_tree_visualizer.py)
      nodes.forEach(node => {
        node.children.sort((a, b) => a.id.localeCompare(b.id));
      });
      rootNodes.sort((a, b) => a.id.localeCompare(b.id));
      
      // Auto-expand first level for better initial view
      rootNodes.forEach(root => {
        root.isExpanded = true;
        // Also expand first level of children if they have children
        root.children.forEach(child => {
          if (child.children.length > 0) {
            child.isExpanded = false; // Keep second level collapsed initially
          }
        });
      });
      
      console.log(`Built tree with ${rootNodes.length} root nodes and ${nodes.size} total nodes`);
      console.log('Root nodes:', rootNodes.map(r => `${r.id} (${r.children.length} children)`));
    }
    
    return rootNodes;
  }

  // Helper method to determine parent ID following section_tree_visualizer.py patterns
  getParentId(extraction) {
    const attrs = extraction.attributes || {};
    const type = extraction.extraction_class;
    
    // Follow the same parent ID resolution logic as section_tree_visualizer.py
    if (type === 'NORM') {
      return attrs.parent_section_id || attrs.parent_id;
    } else if (type === 'TABLE') {
      return attrs.parent_section_id || attrs.parent_id;
    } else {
      return attrs.parent_id;
    }
  }

  // Create synthetic root nodes following section_tree_visualizer.py patterns
  createSyntheticRoots(nodes) {
    const cteRootId = 'CTE.DB.SI';
    
    if (!nodes.has(cteRootId)) {
      const hasChildren = Array.from(nodes.values()).some(node => node.parentId === cteRootId);
      if (hasChildren) {
        console.log(`Creating synthetic root node for ${cteRootId}`);
        nodes.set(cteRootId, {
          id: cteRootId,
          title: 'CTE DB-SI - Documento Básico de Seguridad en caso de Incendio',
          type: 'LEGAL_DOCUMENT',
          parentId: null,
          parentType: null,
          summary: 'Código Técnico de la Edificación - Documento Básico de Seguridad en caso de Incendio',
          extractionText: 'Root Document',
          children: [],
          isExpanded: true, // Root should be expanded
          level: 0,
          attributes: { id: cteRootId },
          extraction: null // Synthetic node
        });
      }
    }
    
    // Check for other common patterns that might need synthetic roots
    const potentialRoots = new Set();
    nodes.forEach(node => {
      if (node.parentId && !nodes.has(node.parentId)) {
        potentialRoots.add(node.parentId);
      }
    });
    
    potentialRoots.forEach(rootId => {
      if (rootId !== cteRootId) {
        console.log(`Creating synthetic root node for ${rootId}`);
        nodes.set(rootId, {
          id: rootId,
          title: this.generateSyntheticRootTitle(rootId),
          type: 'LEGAL_DOCUMENT',
          parentId: null,
          parentType: null,
          summary: `Synthetic root document: ${rootId}`,
          extractionText: 'Synthetic Root Document',
          children: [],
          isExpanded: true,
          level: 0,
          attributes: { id: rootId },
          extraction: null
        });
      }
    });
  }

  generateSyntheticRootTitle(rootId) {
    // Generate more meaningful titles for synthetic roots based on ID patterns
    if (rootId.includes('CTE')) {
      return 'CTE - Código Técnico de la Edificación';
    } else if (rootId.includes('DB')) {
      return `Documento Básico - ${rootId}`;
    } else if (rootId.includes('SI')) {
      return `Seguridad en caso de Incendio - ${rootId}`;
    } else {
      return `Document Root - ${rootId}`;
    }
  }

  getNodeTitle(extraction) {
    const attrs = extraction.attributes || {};
    const type = extraction.extraction_class;
    
    // Follow section_tree_visualizer.py patterns for title extraction
    if (type === 'SECTION') {
      return attrs.section_title || extraction.extraction_text || 'Untitled Section';
    } else if (type === 'NORM') {
      const statement = attrs.norm_statement || attrs.statement_text || extraction.extraction_text || '';
      // Truncate long norm statements like section_tree_visualizer.py does
      return statement.length > 100 ? statement.substring(0, 100) + '...' : statement;
    } else if (type === 'TABLE') {
      return attrs.table_title || extraction.extraction_text?.substring(0, 50) || 'Table';
    } else if (type === 'LEGAL_DOCUMENT') {
      return attrs.doc_title || attrs.title || 'Legal Document';
    }
    return extraction.extraction_text || 'Unknown';
  }

  getNodeSummary(extraction) {
    const attrs = extraction.attributes || {};
    const type = extraction.extraction_class;
    
    // Follow section_tree_visualizer.py patterns for summary extraction
    if (type === 'SECTION') {
      return attrs.section_summary || '';
    } else if (type === 'NORM') {
      // Match the format: "Paragraph {number} - {obligation_type}"
      const paragraphNum = attrs.paragraph_number || 'N/A';
      const obligationType = attrs.obligation_type || 'Unknown';
      return `Paragraph ${paragraphNum} - ${obligationType}`;
    } else if (type === 'TABLE') {
      return attrs.table_description || '';
    } else if (type === 'LEGAL_DOCUMENT') {
      // Match the format: "{doc_type} - {jurisdiction}"
      const docType = attrs.doc_type || 'Document';
      const jurisdiction = attrs.jurisdiction || 'Unknown jurisdiction';
      return `${docType} - ${jurisdiction}`;
    }
    return '';
  }

  renderDocumentTree(container, nodes) {
    nodes.forEach(node => {
      this.renderDocumentNode(container, node, 0);
    });
  }

  renderDocumentNode(container, node, level) {
    const indent = level * 20;
    const nodeElement = document.createElement('div');
    nodeElement.className = 'tree-node';
    nodeElement.style.marginLeft = `${indent}px`;
    nodeElement.setAttribute('data-node-id', node.id);
    
    // Create the node content
    const nodeContent = document.createElement('div');
    nodeContent.className = 'tree-node-content flex items-start space-x-2 py-2 px-3 hover:bg-gray-50 dark:hover:bg-gray-800 rounded transition-colors border-l-2 border-transparent hover:border-blue-300 dark:hover:border-blue-600';
    
    // Add highlighting if this node matches the current filter
    const currentFilter = window.globalStatisticsFilter;
    if (currentFilter && node.type === currentFilter) {
      nodeContent.classList.add('bg-yellow-50', 'dark:bg-yellow-900', 'border-yellow-300', 'dark:border-yellow-600');
      nodeContent.classList.remove('border-transparent');
    }
    
    // Expand/collapse indicator - make it more prominent and clickable
    const indicator = document.createElement('span');
    indicator.className = 'tree-indicator text-gray-500 dark:text-gray-400 select-none w-5 h-5 text-center flex-shrink-0 transition-all duration-200 flex items-center justify-center';
    
    if (node.children.length > 0) {
      indicator.textContent = node.isExpanded ? '▼' : '▶';
      indicator.style.cursor = 'pointer';
      indicator.classList.add('clickable', 'hover:text-blue-600', 'dark:hover:text-blue-400', 'hover:bg-blue-50', 'dark:hover:bg-blue-900', 'rounded');
      // Add subtle rotation effect and scaling
      if (!node.isExpanded) {
        indicator.style.transform = 'rotate(-90deg) scale(0.9)';
      } else {
        indicator.style.transform = 'rotate(0deg) scale(1)';
      }
    } else {
      indicator.textContent = '•';
      indicator.style.opacity = '0.3';
      indicator.style.cursor = 'default';
    }
    
    // Node info
    const info = document.createElement('div');
    info.className = 'tree-info flex-1 min-w-0';
    
    const header = document.createElement('div');
    header.className = 'tree-header flex items-center space-x-2 flex-wrap';
    
    const idSpan = document.createElement('span');
    idSpan.className = 'node-id font-semibold text-blue-600 dark:text-blue-400 text-sm';
    idSpan.textContent = node.id;
    
    const titleSpan = document.createElement('span');
    titleSpan.className = 'node-title text-gray-800 dark:text-gray-200 text-sm';
    titleSpan.textContent = node.title;
    titleSpan.title = node.title; // Show full title on hover
    titleSpan.style.wordBreak = 'break-word'; // Allow text wrapping
    
    const typeSpan = document.createElement('span');
    typeSpan.className = `node-type text-xs px-2 py-1 rounded-full flex-shrink-0 font-medium ${this.getTypeClass(node.type)}`;
    typeSpan.textContent = node.type;
    
    header.appendChild(idSpan);
    header.appendChild(titleSpan);
    header.appendChild(typeSpan);
    info.appendChild(header);
    
    // Summary
    if (node.summary) {
      const summary = document.createElement('div');
      summary.className = 'node-summary text-xs text-gray-600 dark:text-gray-400 mt-1';
      summary.textContent = node.summary;
      summary.title = node.summary; // Show full summary on hover
      summary.style.wordBreak = 'break-word';
      info.appendChild(summary);
    }
    
    nodeContent.appendChild(indicator);
    nodeContent.appendChild(info);
    nodeElement.appendChild(nodeContent);
    
    // Create children container
    const childrenContainer = document.createElement('div');
    childrenContainer.className = 'tree-children transition-all duration-300 ease-in-out overflow-hidden';
    
    // Render children
    if (node.children.length > 0) {
      node.children.forEach(child => {
        this.renderDocumentNode(childrenContainer, child, level + 1);
      });
      
      // Set initial visibility with smooth transition
      if (node.isExpanded) {
        childrenContainer.style.display = 'block';
        childrenContainer.style.maxHeight = 'none';
        childrenContainer.style.opacity = '1';
      } else {
        childrenContainer.style.display = 'none';
        childrenContainer.style.maxHeight = '0px';
        childrenContainer.style.opacity = '0';
      }
      
      nodeElement.appendChild(childrenContainer);
    }
    
    // Enhanced click handler with navigation support
    const handleNodeClick = (e) => {
      // Check if this was a double-click for navigation
      if (e.detail === 2) {
        console.log(`Double-click navigation for node: ${node.id}`);
        this.navigateToNode(node);
        return;
      }
      
      // Single click - toggle expand/collapse for nodes with children
      if (node.children.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        console.log(`Toggling node: ${node.id}, has ${node.children.length} children, currently expanded: ${node.isExpanded}`);
        
        // Toggle expanded state
        node.isExpanded = !node.isExpanded;
        
        // Update indicator with smooth animation
        indicator.style.transition = 'transform 0.3s ease-in-out, background-color 0.2s ease-in-out';
        if (node.isExpanded) {
          indicator.textContent = '▼';
          indicator.style.transform = 'rotate(0deg) scale(1)';
          indicator.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
        } else {
          indicator.textContent = '▶';
          indicator.style.transform = 'rotate(-90deg) scale(0.9)';
          indicator.style.backgroundColor = 'transparent';
        }
        
        // Toggle children visibility with smooth animation
        if (node.isExpanded) {
          // Expanding
          childrenContainer.style.display = 'block';
          childrenContainer.style.transition = 'max-height 0.3s ease-out, opacity 0.3s ease-out';
          // Force a reflow
          childrenContainer.offsetHeight;
          childrenContainer.style.maxHeight = childrenContainer.scrollHeight + 'px';
          childrenContainer.style.opacity = '1';
          
          // Remove max-height after animation for dynamic content
          setTimeout(() => {
            if (node.isExpanded) {
              childrenContainer.style.maxHeight = 'none';
            }
          }, 300);
        } else {
          // Collapsing
          childrenContainer.style.maxHeight = childrenContainer.scrollHeight + 'px';
          childrenContainer.style.transition = 'max-height 0.3s ease-in, opacity 0.3s ease-in';
          // Force a reflow
          childrenContainer.offsetHeight;
          childrenContainer.style.maxHeight = '0px';
          childrenContainer.style.opacity = '0';
          
          // Hide after animation completes
          setTimeout(() => {
            if (!node.isExpanded) { // Check if still collapsed
              childrenContainer.style.display = 'none';
            }
          }, 300);
        }
        
        console.log(`Node ${node.id} is now ${node.isExpanded ? 'expanded' : 'collapsed'}`);
        
        // Reset indicator background after a brief moment
        setTimeout(() => {
          if (node.isExpanded) {
            indicator.style.backgroundColor = 'transparent';
          }
        }, 200);
      } else {
        // Leaf node - navigate on single click
        console.log(`Single-click navigation for leaf node: ${node.id}`);
        this.navigateToNode(node);
      }
    };
    
    // Bind click event to both the indicator and the entire node content
    if (node.children.length > 0) {
      indicator.addEventListener('click', handleNodeClick);
      nodeContent.addEventListener('click', handleNodeClick);
      
      // Add visual feedback on hover for clickable nodes
      nodeContent.style.cursor = 'pointer';
      
      const originalBg = nodeContent.style.backgroundColor;
      nodeContent.addEventListener('mouseenter', () => {
        if (!nodeContent.style.backgroundColor || nodeContent.style.backgroundColor === originalBg) {
          nodeContent.style.backgroundColor = 'rgba(59, 130, 246, 0.05)';
          nodeContent.style.borderLeftColor = 'rgba(59, 130, 246, 0.3)';
        }
      });
      
      nodeContent.addEventListener('mouseleave', () => {
        nodeContent.style.backgroundColor = originalBg;
        nodeContent.style.borderLeftColor = 'transparent';
      });
    } else {
      // Leaf nodes are clickable for navigation
      nodeContent.addEventListener('click', handleNodeClick);
      nodeContent.style.cursor = 'pointer';
      
      nodeContent.addEventListener('mouseenter', () => {
        nodeContent.style.backgroundColor = 'rgba(34, 197, 94, 0.05)';
        nodeContent.style.borderLeftColor = 'rgba(34, 197, 94, 0.3)';
      });
      nodeContent.addEventListener('mouseleave', () => {
        nodeContent.style.backgroundColor = '';
        nodeContent.style.borderLeftColor = 'transparent';
      });
    }
    
    container.appendChild(nodeElement);
  }

  // Navigation Methods for Tree Node Clicking
  navigateToNode(node) {
    console.log(`Navigating to node: ${node.id} (${node.type})`);
    
    // Check if we're in multi-column preview mode (2 or 3 columns)
    const columnInfo = this.getColumnInfo();
    if (columnInfo.columnCount < 2) {
      console.log('Not in multi-column mode, skipping navigation');
      this.highlightNodeSelection(node);
      return;
    }
    
    // Find MD and JSON panels (exclude the current tree panel)
    const mdPanelIndex = this.findPanelByFileType('md');
    const jsonPanelIndices = this.findAllPanelsByFileType('json');
    const currentPanelIndex = this.findCurrentPanelIndex();
    
    // Filter out the current panel from JSON panels to avoid navigating to self
    const otherJsonPanelIndices = jsonPanelIndices.filter(index => index !== currentPanelIndex);
    
    if (mdPanelIndex === -1 && otherJsonPanelIndices.length === 0) {
      console.log('No MD or other JSON panels found for navigation');
      this.highlightNodeSelection(node);
      return;
    }
    
    console.log(`Found panels - MD: ${mdPanelIndex}, Other JSON: ${otherJsonPanelIndices.join(', ')}, Current: ${currentPanelIndex}`);
    
    // Navigate to the node in MD panel
    if (mdPanelIndex !== -1) {
      this.navigateToNodeInMdPanel(node, mdPanelIndex);
    }
    
    // Navigate to the node in other JSON panels (use the first other JSON panel)
    if (otherJsonPanelIndices.length > 0) {
      this.navigateToNodeInJsonPanel(node, otherJsonPanelIndices[0]);
    }
    
    // Highlight the selected node
    this.highlightNodeSelection(node);
  }

  getColumnInfo() {
    // Access the global currentColumnCount from app.js
    const currentColumnCount = window.currentColumnCount || 1;
    return {
      is3ColumnMode: currentColumnCount === 3,
      columnCount: currentColumnCount
    };
  }

  findPanelByFileType(fileExtension) {
    // Access global selectedFilePaths from app.js
    const selectedFilePaths = window.selectedFilePaths || [null, null, null];
    
    for (let i = 0; i < selectedFilePaths.length; i++) {
      const filePath = selectedFilePaths[i];
      if (filePath && filePath.toLowerCase().endsWith(`.${fileExtension.toLowerCase()}`)) {
        return i;
      }
    }
    return -1;
  }

  findAllPanelsByFileType(fileExtension) {
    // Access global selectedFilePaths from app.js
    const selectedFilePaths = window.selectedFilePaths || [null, null, null];
    const currentColumnCount = window.currentColumnCount || 1;
    const indices = [];
    
    for (let i = 0; i < Math.min(selectedFilePaths.length, currentColumnCount); i++) {
      const filePath = selectedFilePaths[i];
      if (filePath && filePath.toLowerCase().endsWith(`.${fileExtension.toLowerCase()}`)) {
        indices.push(i);
      }
    }
    return indices;
  }

  navigateToNodeInMdPanel(node, panelIndex) {
    console.log(`Navigating to node ${node.id} in MD panel ${panelIndex}`);
    
    // Get the extraction data from the node
    const extraction = node.extraction;
    if (!extraction || !extraction.char_interval) {
      console.warn('No char_interval data available for MD navigation');
      return;
    }
    
    const startPos = extraction.char_interval.start_pos;
    const endPos = extraction.char_interval.end_pos;
    
    console.log(`Navigating to character positions ${startPos}-${endPos} in MD panel`);
    
    // Get the preview element for the target panel
    const panels = document.querySelectorAll('.preview-panel');
    if (panelIndex >= panels.length) {
      console.warn(`Panel index ${panelIndex} not found`);
      return;
    }
    
    const targetPanel = panels[panelIndex];
    const previewElement = targetPanel.querySelector('.preview');
    if (!previewElement) {
      console.warn('Preview element not found in target panel');
      return;
    }
    
    // Scroll to the character position in the MD content
    this.scrollToCharacterPosition(previewElement, startPos, endPos);
  }

  navigateToNodeInJsonPanel(node, panelIndex) {
    console.log(`Navigating to node ${node.id} in JSON panel ${panelIndex}`);
    
    // Get the preview element for the target panel
    const panels = document.querySelectorAll('.preview-panel');
    if (panelIndex >= panels.length) {
      console.warn(`Panel index ${panelIndex} not found`);
      return;
    }
    
    const targetPanel = panels[panelIndex];
    const previewElement = targetPanel.querySelector('.preview');
    if (!previewElement) {
      console.warn('Preview element not found in target panel');
      return;
    }
    
    // Navigate by finding the extraction with matching ID in the JSON
    this.scrollToJsonNode(previewElement, node.id);
  }

  scrollToCharacterPosition(previewElement, startPos, endPos) {
    // For markdown content, we need to find the text node that contains the character position
    const textContent = previewElement.textContent || '';
    
    if (startPos >= textContent.length) {
      console.warn(`Start position ${startPos} is beyond text length ${textContent.length}`);
      return;
    }
    
    // Create a temporary range to find the position
    const range = document.createRange();
    const selection = window.getSelection();
    
    try {
      // Walk through the DOM tree to find the character position
      const walker = document.createTreeWalker(
        previewElement,
        NodeFilter.SHOW_TEXT,
        null,
        false
      );
      
      let currentPos = 0;
      let targetNode = null;
      let targetOffset = 0;
      
      while (walker.nextNode()) {
        const textNode = walker.currentNode;
        const nodeLength = textNode.textContent.length;
        
        if (currentPos + nodeLength >= startPos) {
          targetNode = textNode;
          targetOffset = startPos - currentPos;
          break;
        }
        
        currentPos += nodeLength;
      }
      
      if (targetNode) {
        // Set the range to highlight the text
        range.setStart(targetNode, targetOffset);
        
        // Try to set end position too
        let endNode = targetNode;
        let endOffset = Math.min(targetOffset + (endPos - startPos), targetNode.textContent.length);
        
        // If the end position extends beyond this node, we need to find the correct end node
        if (endPos > startPos + (targetNode.textContent.length - targetOffset)) {
          let remainingChars = endPos - startPos - (targetNode.textContent.length - targetOffset);
          
          while (walker.nextNode() && remainingChars > 0) {
            const nextTextNode = walker.currentNode;
            if (remainingChars <= nextTextNode.textContent.length) {
              endNode = nextTextNode;
              endOffset = remainingChars;
              break;
            }
            remainingChars -= nextTextNode.textContent.length;
          }
        }
        
        range.setEnd(endNode, endOffset);
        
        // Clear any existing selection and set the new one
        selection.removeAllRanges();
        selection.addRange(range);
        
        // Scroll the selection into view
        const rect = range.getBoundingClientRect();
        if (rect.height > 0) {
          range.startContainer.parentElement?.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'nearest'
          });
        }
        
        console.log(`Scrolled to character position ${startPos}-${endPos} in MD content`);
      } else {
        console.warn('Could not find text node for character position', startPos);
      }
    } catch (error) {
      console.error('Error scrolling to character position:', error);
      // Fallback: just scroll to the top
      previewElement.scrollTop = 0;
    }
  }

  scrollToJsonNode(previewElement, nodeId) {
    console.log(`Attempting to scroll to node ID: ${nodeId} in JSON panel`);
    
    // First try to find elements containing the nodeId in JSONFormatter structure
    let targetElement = null;
    
    // JSONFormatter creates elements with various classes like json-formatter-*
    // Look for any element that contains the nodeId
    const allElements = previewElement.querySelectorAll('*');
    for (const element of allElements) {
      const elementText = element.textContent || '';
      if (elementText.includes(`"id": "${nodeId}"`) || 
          elementText.includes(`"id":"${nodeId}"`) ||
          elementText.includes(nodeId)) {
        
        // Find the most specific element that contains this text
        if (!targetElement || element.children.length < targetElement.children.length) {
          targetElement = element;
        }
      }
    }
    
    if (targetElement) {
      console.log(`Found target element for node ${nodeId}, scrolling into view`);
      
      // Scroll the target element into view
      targetElement.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest'
      });
      
      // Add temporary highlighting to the element
      const originalBg = targetElement.style.backgroundColor;
      const originalBorder = targetElement.style.border;
      const originalTransition = targetElement.style.transition;
      
      targetElement.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
      targetElement.style.border = '2px solid rgba(59, 130, 246, 0.5)';
      targetElement.style.transition = 'all 0.3s ease-in-out';
      
      setTimeout(() => {
        targetElement.style.backgroundColor = originalBg;
        targetElement.style.border = originalBorder;
        targetElement.style.transition = originalTransition;
      }, 2000);
      
      console.log(`Successfully scrolled to and highlighted node ${nodeId} in JSON panel`);
      return;
    }
    
    // Fallback: try text-based search and scroll
    const jsonText = previewElement.textContent || '';
    const searchTerms = [
      `"id": "${nodeId}"`,
      `"id":"${nodeId}"`,
      `id": "${nodeId}"`,
      `id":"${nodeId}"`,
      nodeId
    ];
    
    let position = -1;
    for (const searchTerm of searchTerms) {
      position = jsonText.indexOf(searchTerm);
      if (position !== -1) {
        console.log(`Found node ID ${nodeId} using search term: ${searchTerm} at position ${position}`);
        break;
      }
    }
    
    if (position === -1) {
      console.warn(`Could not find node ID ${nodeId} in JSON content using any search method`);
      return;
    }
    
    // Calculate approximate scroll position based on character position
    const previewElementRect = previewElement.getBoundingClientRect();
    const textLength = jsonText.length;
    const scrollRatio = position / textLength;
    const scrollPosition = scrollRatio * (previewElement.scrollHeight - previewElementRect.height);
    
    previewElement.scrollTo({
      top: Math.max(0, scrollPosition - previewElementRect.height / 2),
      behavior: 'smooth'
    });
    
    console.log(`Scrolled to approximate position for ${nodeId} (character position ${position})`);
  }

  highlightNodeSelection(node) {
    // Remove previous selection highlights
    const previouslySelected = document.querySelectorAll('.tree-node-selected');
    previouslySelected.forEach(el => el.classList.remove('tree-node-selected'));
    
    // Add selection highlight to the current node
    const nodeElement = document.querySelector(`[data-node-id="${node.id}"]`);
    if (nodeElement) {
      nodeElement.classList.add('tree-node-selected');
      
      // Add some temporary visual feedback
      const nodeContent = nodeElement.querySelector('.tree-node-content');
      if (nodeContent) {
        const originalBg = nodeContent.style.backgroundColor;
        nodeContent.style.backgroundColor = 'rgba(34, 197, 94, 0.15)';
        nodeContent.style.borderLeftColor = 'rgba(34, 197, 94, 0.6)';
        
        setTimeout(() => {
          if (!nodeElement.classList.contains('tree-node-selected')) {
            nodeContent.style.backgroundColor = originalBg;
            nodeContent.style.borderLeftColor = 'transparent';
          }
        }, 3000);
      }
      
      console.log(`Highlighted selected node: ${node.id}`);
    }
  }

  getTypeClass(type) {
    const classes = {
      'SECTION': 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200',
      'NORM': 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200',
      'TABLE': 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200',
      'LEGAL_DOCUMENT': 'bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200'
    };
    return classes[type] || 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300';
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  formatNumber(num) {
    if (num === 0 || num === undefined || num === null) return '0';
    return num.toLocaleString();
  }

  // Apply statistics filter across all panels
  applyStatisticsFilter(filterType) {
    console.log(`Applying statistics filter: ${filterType || 'none'}`);
    
    // Update global filter state
    window.globalStatisticsFilter = filterType;
    
    // Apply filters immediately to all panels with JSON data
    this.applyFiltersToAllPanels();
    
    // Update visual state of all filter cards across all panels
    this.updateFilterCardVisualStates(filterType);
  }

  // Apply filters to all panels immediately without re-rendering everything
  applyFiltersToAllPanels() {
    if (window.previewOptimizers) {
      window.previewOptimizers.forEach((optimizer, index) => {
        if (optimizer && optimizer.uberMode && optimizer.currentJsonData) {
          console.log(`Applying filter to panel ${index}: ${window.globalStatisticsFilter}`);
          optimizer.applyCurrentFilter();
        }
      });
    }
  }

  // Update visual states of filter cards
  updateFilterCardVisualStates(filterType) {
    document.querySelectorAll('.stats-filter-card').forEach(card => {
      const cardFilterType = card.dataset.filterType;
      const isActive = (filterType === null && cardFilterType === 'total') || (filterType === cardFilterType);
      
      if (isActive) {
        card.classList.add('border-blue-500', 'ring-2', 'ring-blue-200');
      } else {
        card.classList.remove('border-blue-500', 'ring-2', 'ring-blue-200');
      }
    });
  }

  // Apply the current filter to this panel specifically
  applyCurrentFilter() {
    const currentFilter = window.globalStatisticsFilter;
    console.log(`Applying current filter to panel: ${currentFilter || 'none'}`);
    
    if (!this.currentJsonData || !this.uberMode) {
      return;
    }

    const shouldShowTreeView = this.shouldShowTreeVisualization();
    
    if (shouldShowTreeView) {
      // Render tree view with current filter
      this.renderFilteredTreeView(currentFilter);
    } else {
      // Render JSON view with current filter
      this.renderFilteredJsonView(currentFilter);
    }
  }

  // Render filtered tree view as flat list
  renderFilteredTreeView(filterType) {
    console.log(`Rendering filtered tree view with filter: ${filterType || 'none'}`);
    
    const data = this.currentJsonData;
    if (!data || !data.extractions) {
      console.log('No extraction data available for filtering');
      return;
    }

    // Get the container where the tree is rendered
    const treeContainer = this.element.querySelector('.document-tree-container, .tree-view-container, .ubermode-container');
    if (!treeContainer) {
      console.log('No tree container found, falling back to full re-render');
      // Fallback to full re-render
      this.element.innerHTML = '';
      this.renderUberMode(data, { size: 0, truncated: false });
      return;
    }

    // Find the actual tree element
    const treeElement = treeContainer.querySelector('.tree-content');
    if (!treeElement) {
      console.log('No tree element found');
      return;
    }

    if (!filterType) {
      // No filter - show hierarchical tree
      this.renderHierarchicalTree(treeElement, data);
    } else {
      // Filter active - show flat list of matching items
      this.renderFlatFilteredTree(treeElement, data, filterType);
    }
  }

  // Render hierarchical tree (original logic)
  renderHierarchicalTree(treeElement, data) {
    console.log('Rendering hierarchical tree view');
    
    // Build hierarchical tree
    const documentTree = this.buildDocumentTree(data);
    
    // Clear and re-render
    treeElement.innerHTML = '';
    this.renderDocumentTree(treeElement, documentTree);
  }

  // Render flat list of filtered items
  renderFlatFilteredTree(treeElement, data, filterType) {
    console.log(`Rendering flat filtered tree for type: ${filterType}`);
    
    // Get all extractions that match the filter
    const filteredExtractions = data.extractions.filter(ext => 
      ext.extraction_class === filterType
    );

    console.log(`Found ${filteredExtractions.length} items matching filter: ${filterType}`);

    // Group by parent-child relationships within the same type
    const flatItems = this.buildFlatFilteredItems(filteredExtractions, data, filterType);
    
    // Clear and render flat list
    treeElement.innerHTML = '';
    this.renderFlatList(treeElement, flatItems, filterType);
  }

  // Build flat list items with same-type hierarchies preserved
  buildFlatFilteredItems(filteredExtractions, data, filterType) {
    const items = [];
    const processedIds = new Set();

    // Create lookup map for all extractions
    const extractionMap = new Map();
    data.extractions.forEach(ext => {
      const id = ext.attributes?.id;
      if (id) {
        extractionMap.set(id, ext);
      }
    });

    // Process each filtered extraction
    filteredExtractions.forEach(extraction => {
      const id = extraction.attributes?.id;
      if (!id || processedIds.has(id)) {
        return;
      }

      // Check if this item has a parent of the same type
      const parentId = this.getParentId(extraction);
      const parentExtraction = parentId ? extractionMap.get(parentId) : null;
      const hasParentOfSameType = parentExtraction && parentExtraction.extraction_class === filterType;

      const item = {
        id: id,
        extraction: extraction,
        level: 0, // Will be calculated based on same-type hierarchy
        children: []
      };

      // If no parent of same type, this is a root item
      if (!hasParentOfSameType) {
        // Find all children of same type recursively
        this.findSameTypeChildren(item, extractionMap, filterType, processedIds);
        items.push(item);
      }
      
      processedIds.add(id);
    });

    // Calculate hierarchy levels for same-type relationships
    this.calculateFlatItemLevels(items);

    return items;
  }

  // Find children of the same type recursively
  findSameTypeChildren(parentItem, extractionMap, filterType, processedIds) {
    const parentId = parentItem.id;
    
    // Look for extractions that have this item as parent and are of the same type
    extractionMap.forEach(extraction => {
      const childParentId = this.getParentId(extraction);
      if (childParentId === parentId && 
          extraction.extraction_class === filterType && 
          !processedIds.has(extraction.attributes?.id)) {
        
        const childItem = {
          id: extraction.attributes.id,
          extraction: extraction,
          level: 0, // Will be calculated later
          children: []
        };
        
        processedIds.add(childItem.id);
        parentItem.children.push(childItem);
        
        // Recursively find children of this child
        this.findSameTypeChildren(childItem, extractionMap, filterType, processedIds);
      }
    });
  }

  // Calculate levels for flat items based on same-type hierarchy
  calculateFlatItemLevels(items, currentLevel = 0) {
    items.forEach(item => {
      item.level = currentLevel;
      if (item.children.length > 0) {
        this.calculateFlatItemLevels(item.children, currentLevel + 1);
      }
    });
  }

  // Render the flat list in the tree element
  renderFlatList(treeElement, flatItems, filterType) {
    const container = document.createElement('div');
    container.className = 'flat-filtered-tree';
    
    // Add header
    const header = document.createElement('div');
    header.className = 'flat-list-header px-4 py-2 bg-blue-50 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-sm font-medium border-b border-blue-200 dark:border-blue-700';
    header.textContent = `Filtered view: ${this.formatTypeName(filterType)} (${this.countTotalItems(flatItems)} items)`;
    container.appendChild(header);

    // Render items
    const listContainer = document.createElement('div');
    listContainer.className = 'flat-list-items';
    this.renderFlatItems(listContainer, flatItems);
    container.appendChild(listContainer);

    treeElement.appendChild(container);
  }

  // Render flat items recursively
  renderFlatItems(container, items) {
    items.forEach(item => {
      this.renderFlatItem(container, item);
      if (item.children.length > 0) {
        this.renderFlatItems(container, item.children);
      }
    });
  }

  // Render individual flat item
  renderFlatItem(container, item) {
    const indent = item.level * 20;
    const nodeElement = document.createElement('div');
    nodeElement.className = 'flat-tree-node';
    nodeElement.style.marginLeft = `${indent}px`;
    nodeElement.setAttribute('data-node-id', item.id);

    const nodeContent = document.createElement('div');
    nodeContent.className = 'tree-node-content flex items-start space-x-2 py-2 px-3 hover:bg-gray-50 dark:hover:bg-gray-800 rounded transition-colors border-l-2 border-transparent hover:border-blue-300 dark:hover:border-blue-600';
    
    // Always highlight filtered items
    nodeContent.classList.add('bg-yellow-50', 'dark:bg-yellow-900', 'border-yellow-300', 'dark:border-yellow-600');
    nodeContent.classList.remove('border-transparent');

    // Expand/collapse indicator for items with children
    const indicator = document.createElement('span');
    indicator.className = 'tree-indicator text-gray-500 dark:text-gray-400 select-none w-5 h-5 text-center flex-shrink-0 transition-all duration-200 flex items-center justify-center';
    
    if (item.children.length > 0) {
      indicator.textContent = '▼'; // Always expanded in flat view
      indicator.style.cursor = 'pointer';
    } else {
      indicator.textContent = '•';
      indicator.style.opacity = '0.5';
    }

    // Create node text with navigation capability
    const nodeText = document.createElement('span');
    nodeText.className = 'text-sm text-gray-900 dark:text-gray-100 cursor-pointer flex-grow select-none';
    
    const extraction = item.extraction;
    const attrs = extraction.attributes || {};
    let displayText = '';
    
    // Format display text based on extraction type
    if (attrs.section_title) {
      displayText = `${attrs.id || 'Unknown'} - ${attrs.section_title}`;
    } else if (attrs.norm_statement) {
      displayText = `${attrs.id || 'Unknown'} - ${attrs.norm_statement.substring(0, 100)}${attrs.norm_statement.length > 100 ? '...' : ''}`;
    } else if (extraction.extraction_text) {
      displayText = `${attrs.id || 'Unknown'} - ${extraction.extraction_text.substring(0, 100)}${extraction.extraction_text.length > 100 ? '...' : ''}`;
    } else {
      displayText = `${attrs.id || 'Unknown'} - ${extraction.extraction_class}`;
    }
    
    nodeText.textContent = displayText;

    // Add click handler for navigation
    nodeContent.addEventListener('click', (e) => {
      e.stopPropagation();
      console.log(`Flat list navigation clicked for node: ${item.id}`);
      
      // Add selection highlighting
      container.querySelectorAll('.tree-node-content').forEach(node => {
        node.classList.remove('bg-green-100', 'dark:bg-green-800', 'border-green-300', 'dark:border-green-600');
      });
      nodeContent.classList.add('bg-green-100', 'dark:bg-green-800', 'border-green-300', 'dark:border-green-600');

      // Navigate to this node across panels
      this.navigateToTreeNode(item.id, extraction);
    });

    nodeContent.appendChild(indicator);
    nodeContent.appendChild(nodeText);
    nodeElement.appendChild(nodeContent);
    container.appendChild(nodeElement);
  }

  // Count total items in flat list (including children)
  countTotalItems(items) {
    let count = 0;
    items.forEach(item => {
      count++;
      if (item.children.length > 0) {
        count += this.countTotalItems(item.children);
      }
    });
    return count;
  }

  // Render filtered JSON view
  renderFilteredJsonView(filterType) {
    console.log(`Rendering filtered JSON view with filter: ${filterType || 'none'}`);
    
    const data = this.currentJsonData;
    if (!data || !data.extractions) {
      console.log('No extraction data available for JSON filtering');
      return;
    }

    // Get the JSON container
    const jsonContainer = this.element.querySelector('.json-formatter, .json-viewer, .enhanced-json');
    if (!jsonContainer) {
      console.log('No JSON container found for filtering');
      return;
    }

    if (!filterType) {
      // No filter - show complete JSON
      this.renderCompleteJsonView(jsonContainer, data);
    } else {
      // Filter active - show only matching extractions
      this.renderFlatJsonFilter(jsonContainer, data, filterType);
    }
  }

  // Render complete JSON view (original logic) with enhanced controls
  renderCompleteJsonView(container, data) {
    console.log('Rendering complete JSON view with controls');
    
    // Clear the container
    container.innerHTML = '';
    
    // Use enhanced JSON object renderer
    if (typeof JSONFormatter !== 'undefined') {
      this.renderEnhancedJsonObject(data, { size: 0, truncated: false });
    } else {
      const pretty = JSON.stringify(data, null, 2);
      this.renderEnhancedJsonWithControls(pretty, { size: 0, truncated: false });
    }
  }

  // Render filtered JSON as flat list with enhanced controls
  renderFlatJsonFilter(container, data, filterType) {
    console.log(`Rendering flat JSON filter for type: ${filterType}`);
    
    // Get filtered extractions
    const filteredExtractions = data.extractions.filter(ext => 
      ext.extraction_class === filterType
    );

    console.log(`Found ${filteredExtractions.length} JSON items matching filter: ${filterType}`);

    // Create filtered data object
    const filteredData = {
      document_id: data.document_id,
      extractions: filteredExtractions,
      filter_applied: filterType,
      total_items: filteredExtractions.length,
      original_total: data.extractions.length
    };

    // Clear the main container and render with enhanced controls
    this.element.innerHTML = '';
    
    // Create main container
    const mainContainer = document.createElement('div');
    mainContainer.className = 'enhanced-json-container';
    
    // Create custom toolbar for filtered view
    const toolbar = document.createElement('div');
    toolbar.className = 'json-toolbar flex items-center justify-between bg-blue-100 dark:bg-blue-800 border border-blue-200 dark:border-blue-600 rounded-t-lg px-4 py-2 text-sm';
    
    // Left side - filter info
    const filterInfo = document.createElement('div');
    filterInfo.className = 'flex items-center space-x-4';
    
    const filterLabel = document.createElement('span');
    filterLabel.className = 'font-medium text-blue-800 dark:text-blue-200';
    filterLabel.textContent = `Filtered: ${this.formatTypeName(filterType)}`;
    filterInfo.appendChild(filterLabel);
    
    // Add control toggles
    const lineNumbersToggle = this.createToggleButton('line-numbers', 'Line Numbers', this.getJsonPreference('lineNumbers', true));
    lineNumbersToggle.addEventListener('change', (e) => {
      this.setJsonPreference('lineNumbers', e.target.checked);
      this.applyCurrentFilter(); // Re-render filtered view
    });
    filterInfo.appendChild(lineNumbersToggle);
    
    const wordWrapToggle = this.createToggleButton('word-wrap', 'Word Wrap', this.getJsonPreference('wordWrap', false));
    wordWrapToggle.addEventListener('change', (e) => {
      this.setJsonPreference('wordWrap', e.target.checked);
      this.applyCurrentFilter(); // Re-render filtered view
    });
    filterInfo.appendChild(wordWrapToggle);
    
    // Right side - item count
    const itemCount = document.createElement('div');
    itemCount.className = 'flex items-center space-x-2 text-xs bg-blue-200 dark:bg-blue-700 px-2 py-1 rounded';
    itemCount.innerHTML = `
      <span class="text-blue-800 dark:text-blue-200">
        ${filteredExtractions.length} of ${data.extractions.length} items
      </span>
    `;
    
    toolbar.appendChild(filterInfo);
    toolbar.appendChild(itemCount);
    mainContainer.appendChild(toolbar);
    
    // Create JSON content container
    const jsonContainer = document.createElement('div');
    jsonContainer.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-b-lg border-l border-r border-b border-gray-200 dark:border-gray-600 relative';
    
    // Apply preferences
    const showLineNumbers = this.getJsonPreference('lineNumbers', true);
    const wordWrap = this.getJsonPreference('wordWrap', false);
    
    // Create content wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = `json-content-wrapper ${wordWrap ? 'word-wrap' : 'no-wrap'}`;
    
    // Determine scrolling behavior
    const jsonDepth = this.calculateJsonDepth(filteredData);
    const needsHorizontalScroll = !wordWrap || jsonDepth > 2;
    
    if (needsHorizontalScroll) {
      contentWrapper.style.overflowX = 'auto';
      contentWrapper.style.whiteSpace = 'nowrap';
    } else {
      contentWrapper.style.overflowX = 'hidden';
      contentWrapper.style.whiteSpace = 'pre-wrap';
    }
    
    // Add line numbers if enabled
    if (showLineNumbers) {
      const lineNumbersContainer = document.createElement('div');
      lineNumbersContainer.className = 'line-numbers-container bg-gray-100 dark:bg-gray-800 border-r border-gray-200 dark:border-gray-600 text-xs text-gray-500 dark:text-gray-400 font-mono select-none';
      lineNumbersContainer.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 60px;
        height: 100%;
        overflow: hidden;
        padding: 12px 8px;
        z-index: 2;
      `;
      jsonContainer.appendChild(lineNumbersContainer);
      contentWrapper.style.paddingLeft = '68px';
      
      // Generate line numbers for filtered data
      this.generateJsonLineNumbers(filteredData, lineNumbersContainer);
    }
    
    // Render JSON content
    if (typeof JSONFormatter !== 'undefined') {
      const formatter = new JSONFormatter(filteredData, 3, {
        hoverPreviewEnabled: true,
        hoverPreviewArrayCount: 100,
        hoverPreviewFieldCount: 5,
        animateOpen: true,
        animateClose: true
      });
      const formatterElement = formatter.render();
      formatterElement.style.padding = '12px';
      contentWrapper.appendChild(formatterElement);
    } else {
      // Fallback to pretty-printed JSON
      const pretty = JSON.stringify(filteredData, null, 2);
      const pre = document.createElement('pre');
      pre.className = 'text-sm text-gray-900 dark:text-gray-100 p-4 m-0';
      pre.style.whiteSpace = wordWrap ? 'pre-wrap' : 'pre';
      pre.textContent = pretty;
      contentWrapper.appendChild(pre);
    }
    
    jsonContainer.appendChild(contentWrapper);
    mainContainer.appendChild(jsonContainer);
    this.element.appendChild(mainContainer);
  }
}

// Export to global scope for use by app.js
window.PreviewOptimizer = PreviewOptimizer;