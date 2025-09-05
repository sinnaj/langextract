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
    this.cacheHits = 0;
    this.cacheRequests = 0;
    this._lastSearchQuery = '';
    this.uberMode = false; // UBERMODE state
    this.currentJsonData = null; // Store parsed JSON for UBERMODE
    this.currentFilter = null; // Current statistics filter (null = show all, string = show only that type)
    this.updateJsonDisplayTimeout = null; // For debouncing JSON updates
    this.currentRenderOperation = null; // Track ongoing render operations
    this.performanceStats = { // Track rendering performance
      renderCount: 0,
      totalRenderTime: 0,
      lastRenderTime: 0
    };
    
    this.init();
  }
  
  init() {
    this.element.style.position = 'relative';
    this.element.style.overflow = 'auto';
    
    // Use bound method for better memory management
    this.element.addEventListener('click', this.handleClick);
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
      this.cacheRequests++;
      
      if (this.cache.has(cacheKey)) {
        this.cacheHits++;
        const cached = this.cache.get(cacheKey);
        this.renderContent(cached.content, cached.contentType, cached.meta);
        console.log(`Cache hit for ${filePath} (hit rate: ${(this.cacheHits/this.cacheRequests*100).toFixed(1)}%)`);
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
      
      // Detect file type for better UBERMODE feedback
      const filePath = this.currentFile?.filePath || 'unknown';
      const isChunkEvaluations = filePath.includes('chunk_evaluations.json');
      const isCombinedExtractions = filePath.includes('combined_extractions.json');
      
      console.log('JSON parsed successfully, data available for UBERMODE:', !!obj);
      console.log('Current UBERMODE state:', this.uberMode);
      console.log('File being loaded:', filePath);
      console.log('File type detection:', { isChunkEvaluations, isCombinedExtractions });

      // Check if UBERMODE is enabled and if this panel should show tree visualization
      const shouldShowTreeView = this.shouldShowTreeVisualization();
      console.log('UBERMODE check:', {
        uberMode: this.uberMode,
        shouldShowTreeView: shouldShowTreeView,
        hasJsonData: !!obj,
        currentJsonData: !!this.currentJsonData,
        dataStructure: {
          hasExtractions: !!(obj?.extractions),
          extractionCount: obj?.extractions?.length || 0,
          hasSections: !!(obj?.sections),
          sectionCount: obj?.sections?.length || 0
        }
      });
      
      if (this.uberMode && shouldShowTreeView) {
        console.log('UBERMODE is enabled and this panel should show tree view');
        console.log('Data structure:', {
          hasExtractions: !!(obj?.extractions),
          extractionCount: obj?.extractions?.length || 0,
          hasSections: !!(obj?.sections),
          sectionCount: obj?.sections?.length || 0
        });
        try {
          console.log('Calling renderUberMode...');
          this.renderUberMode(obj, meta);
          return;
        } catch (error) {
          console.error('Error in renderUberMode:', error);
          console.error('Stack trace:', error.stack);
        }
      } else if (this.uberMode && !shouldShowTreeView) {
        console.log('UBERMODE is enabled but this panel should not show tree view');
      } else if (!this.uberMode) {
        console.log('UBERMODE is not enabled');
      }

      // Determine rendering strategy based on JSON size and complexity
      const jsonString = JSON.stringify(obj);
      const jsonSize = jsonString.length;
      const jsonDepth = this.calculateJsonDepth(obj);
      const itemCount = this.countJsonItems(obj);

      console.log(`JSON analysis: size=${this.formatBytes(jsonSize)}, depth=${jsonDepth}, items=${itemCount}`);

      // Strategy 1: Very large JSON files - use specialized large JSON renderer
      if (jsonSize > 2000000 || itemCount > 10000) {
        console.log('Using large JSON renderer for performance');
        this.renderLargeJsonObject(obj, meta, { jsonSize, jsonDepth, itemCount });
        return;
      }

      // Strategy 2: Medium to large JSON - use JSONFormatter with optimizations
      if (typeof JSONFormatter !== 'undefined' && jsonSize <= 2000000) {
        this.renderEnhancedJsonObject(obj, meta);
        return;
      }

      // Strategy 3: Fallback for very large files or when JSONFormatter unavailable
      if (jsonSize > 500000) {
        console.log('JSON too large, falling back to text rendering');
        this.renderTextContent(content, meta, 'json');
      } else {
        this.renderEnhancedJson(jsonString, meta);
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
          // Limit depth for performance in JSONL rendering
          const maxDepth = line.length > 10000 ? 1 : 2;
          const formatter = new JSONFormatter(obj, maxDepth, { 
            theme: 'dark',
            hoverPreviewEnabled: line.length < 5000,
            animateOpen: false,
            animateClose: false
          });
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
        
        // Determine appropriate depth based on JSON size and complexity
        const jsonSize = jsonString.length;
        const jsonDepth = this.calculateJsonDepth(obj);
        
        let maxDepth;
        if (jsonSize > 500000) { // >500KB
          maxDepth = 1; // Very shallow for large files
        } else if (jsonSize > 100000) { // >100KB
          maxDepth = 2; // Moderate depth
        } else if (jsonDepth > 5) {
          maxDepth = 3; // Limit deep nesting
        } else {
          maxDepth = Math.min(jsonDepth, 4); // Reasonable default
        }
        
        const formatter = new JSONFormatter(obj, maxDepth, {
          theme: 'dark', // theme hint; CSS controls final look
          hoverPreviewEnabled: true,
          hoverPreviewArrayCount: 10,
          hoverPreviewFieldCount: 5,
          animateOpen: false, // Disable animations for performance
          animateClose: false
        });
        
        const container = document.createElement('div');
        container.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-lg p-2 overflow-auto';
        
        // Use requestAnimationFrame for non-blocking DOM update
        requestAnimationFrame(() => {
          container.appendChild(formatter.render());
          this.element.appendChild(container);
        });
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
    const startTime = performance.now();
    
    // Use JSONFormatter directly on parsed object with enhanced controls
    try {
      // Determine JSON complexity and size for performance optimization
      const jsonString = JSON.stringify(obj);
      const jsonSize = jsonString.length;
      const jsonDepth = this.calculateJsonDepth(obj);
      const itemCount = this.countJsonItems(obj);
      
      console.log(`Rendering JSON: ${this.formatBytes(jsonSize)}, depth=${jsonDepth}, items=${itemCount}`);
      
      // Performance-based rendering strategy
      if (jsonSize > 2000000 || itemCount > 10000) { // >2MB or >10k items
        this.renderLargeJsonObject(obj, meta, { jsonSize, jsonDepth, itemCount });
        return;
      }
      
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
      const needsHorizontalScroll = !wordWrap || jsonDepth > 2;
      
      if (needsHorizontalScroll) {
        contentWrapper.style.overflowX = 'auto';
        contentWrapper.style.whiteSpace = 'nowrap';
      } else {
        contentWrapper.style.overflowX = 'hidden';
        contentWrapper.style.whiteSpace = 'pre-wrap';
      }
      
      // Create line numbers container if enabled (only for smaller JSON)
      let lineNumbersContainer = null;
      if (showLineNumbers && jsonSize < 500000) { // Skip line numbers for large JSON
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
      
      // Determine appropriate depth and options based on JSON complexity
      let maxDepth = options.maxDepth;
      if (!maxDepth) {
        if (jsonSize > 500000) maxDepth = 1;
        else if (jsonSize > 100000 || itemCount > 1000) maxDepth = 2;
        else if (jsonDepth > 5) maxDepth = 3;
        else maxDepth = Math.min(jsonDepth, 4);
      }
      
      // Create JSONFormatter with performance-optimized settings
      const formatter = new JSONFormatter(obj, maxDepth, {
        hoverPreviewEnabled: jsonSize < 100000, // Disable hover for large JSON
        hoverPreviewArrayCount: jsonSize < 100000 ? 50 : 5,
        hoverPreviewFieldCount: jsonSize < 100000 ? 5 : 3,
        animateOpen: jsonSize < 50000, // Disable animations for large JSON
        animateClose: jsonSize < 50000,
        theme: 'default'
      });
      
      // Use requestAnimationFrame for non-blocking rendering
      requestAnimationFrame(() => {
        const formatterElement = formatter.render();
        formatterElement.style.padding = '12px';
        formatterElement.style.minHeight = '100%';
        
        contentWrapper.appendChild(formatterElement);
        container.appendChild(contentWrapper);
        
        // Generate line numbers if enabled and not too large
        if (showLineNumbers && lineNumbersContainer && jsonSize < 100000) {
          requestAnimationFrame(() => {
            this.generateJsonLineNumbers(obj, lineNumbersContainer);
          });
        }
        
        mainContainer.appendChild(container);
        this.element.appendChild(mainContainer);
        
        // Store references for control updates
        this.jsonContainer = container;
        this.jsonContentWrapper = contentWrapper;
        this.jsonLineNumbersContainer = lineNumbersContainer;
        
        // Track performance
        const endTime = performance.now();
        const renderTime = endTime - startTime;
        this.performanceStats.renderCount++;
        this.performanceStats.totalRenderTime += renderTime;
        this.performanceStats.lastRenderTime = renderTime;
        
        console.log(`JSON rendered in ${renderTime.toFixed(2)}ms (avg: ${(this.performanceStats.totalRenderTime / this.performanceStats.renderCount).toFixed(2)}ms)`);
      });
      
    } catch (e) {
      console.error('JSONFormatter failed:', e);
      // Fallback: pretty print with enhanced controls
      const pretty = JSON.stringify(obj, null, 2);
      this.renderEnhancedJsonWithControls(pretty, meta);
    } finally {
      // Ensure performance tracking even on fallback
      if (this.performanceStats.lastRenderTime === 0) {
        const endTime = performance.now();
        const renderTime = endTime - startTime;
        this.performanceStats.renderCount++;
        this.performanceStats.totalRenderTime += renderTime;
        this.performanceStats.lastRenderTime = renderTime;
      }
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
    if (typeof obj !== 'object' || obj === null || currentDepth > 10) { // Limit recursion depth
      return currentDepth;
    }
    
    let maxDepth = currentDepth;
    const keys = Object.keys(obj);
    
    // Limit checking for performance on very large objects
    const keysToCheck = keys.length > 100 ? keys.slice(0, 100) : keys;
    
    for (const key of keysToCheck) {
      const value = obj[key];
      if (typeof value === 'object' && value !== null) {
        const depth = this.calculateJsonDepth(value, currentDepth + 1);
        maxDepth = Math.max(maxDepth, depth);
      }
    }
    
    return maxDepth;
  }

  // Count JSON items (keys + array elements) for performance estimation
  countJsonItems(obj, maxCount = 20000) {
    let count = 0;
    
    const countRecursive = (item) => {
      if (count >= maxCount) return; // Stop counting if we hit the limit
      
      if (Array.isArray(item)) {
        count += item.length;
        for (const element of item.slice(0, 10)) { // Sample first 10 elements
          if (typeof element === 'object' && element !== null) {
            countRecursive(element);
          }
        }
      } else if (typeof item === 'object' && item !== null) {
        const keys = Object.keys(item);
        count += keys.length;
        for (const key of keys.slice(0, 50)) { // Sample first 50 keys
          countRecursive(item[key]);
        }
      }
    };
    
    countRecursive(obj);
    return count;
  }

  // Render very large JSON with virtual scrolling and progressive loading
  renderLargeJsonObject(obj, meta, stats = {}) {
    this.element.innerHTML = '';
    
    // Create warning and info container
    const infoContainer = document.createElement('div');
    infoContainer.className = 'bg-orange-50 dark:bg-orange-900 border border-orange-200 dark:border-orange-700 rounded-lg p-4 mb-4';
    
    const { jsonSize, jsonDepth, itemCount } = stats;
    infoContainer.innerHTML = `
      <div class="flex items-start space-x-3">
        <div class="flex-shrink-0">
          <svg class="h-5 w-5 text-orange-400" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
        </div>
        <div class="flex-1">
          <h3 class="text-sm font-medium text-orange-800 dark:text-orange-200">Large JSON File</h3>
          <div class="mt-2 text-sm text-orange-700 dark:text-orange-300">
            <p>This JSON file is very large (${this.formatBytes(jsonSize)}, ~${itemCount.toLocaleString()} items, depth ${jsonDepth})</p>
            <p>Using optimized rendering with limited depth to maintain performance.</p>
          </div>
          <div class="mt-3 flex space-x-2">
            <button id="render-shallow" class="text-xs bg-orange-600 hover:bg-orange-700 text-white px-3 py-1 rounded">
              Render (Depth 1)
            </button>
            <button id="render-medium" class="text-xs bg-orange-600 hover:bg-orange-700 text-white px-3 py-1 rounded">
              Render (Depth 2)
            </button>
            <button id="render-text" class="text-xs bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded">
              View as Text
            </button>
          </div>
        </div>
      </div>
    `;
    
    this.element.appendChild(infoContainer);
    
    // Add event listeners for rendering options
    const shallowBtn = infoContainer.querySelector('#render-shallow');
    const mediumBtn = infoContainer.querySelector('#render-medium');
    const textBtn = infoContainer.querySelector('#render-text');
    
    shallowBtn?.addEventListener('click', () => {
      this.renderJsonWithDepth(obj, 1, infoContainer);
    });
    
    mediumBtn?.addEventListener('click', () => {
      this.renderJsonWithDepth(obj, 2, infoContainer);
    });
    
    textBtn?.addEventListener('click', () => {
      this.renderJsonAsText(obj, infoContainer);
    });
    
    // Auto-render with minimal depth by default
    setTimeout(() => {
      this.renderJsonWithDepth(obj, 1, infoContainer);
    }, 100);
  }

  // Render JSON with specific depth limit and better error handling
  renderJsonWithDepth(obj, maxDepth, infoContainer) {
    // Cancel any ongoing render
    if (this.currentRenderOperation) {
      this.currentRenderOperation.cancelled = true;
    }
    
    // Create operation tracker
    const renderOperation = { cancelled: false };
    this.currentRenderOperation = renderOperation;
    
    // Show loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'text-center py-8 text-gray-500';
    loadingDiv.innerHTML = `
      <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900 dark:border-white mx-auto mb-2"></div>
      <div class="text-sm">Rendering JSON (depth ${maxDepth})...</div>
    `;
    
    // Remove any existing JSON container
    const existingJson = this.element.querySelector('.json-viewer');
    if (existingJson) existingJson.remove();
    
    this.element.appendChild(loadingDiv);
    
    // Use timeout to allow UI to update
    setTimeout(() => {
      // Check if operation was cancelled
      if (renderOperation.cancelled) {
        loadingDiv.remove();
        return;
      }
      
      try {
        const formatter = new JSONFormatter(obj, maxDepth, {
          hoverPreviewEnabled: false, // Disable for performance
          hoverPreviewArrayCount: 3,
          hoverPreviewFieldCount: 3,
          animateOpen: false,
          animateClose: false,
          theme: 'default'
        });
        
        const container = document.createElement('div');
        container.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 p-3 overflow-auto max-h-96';
        
        // Check again if cancelled before expensive DOM operation
        if (renderOperation.cancelled) {
          loadingDiv.remove();
          return;
        }
        
        const formatterElement = formatter.render();
        container.appendChild(formatterElement);
        
        // Remove loading indicator and add JSON
        loadingDiv.remove();
        this.element.appendChild(container);
        
        // Clear operation tracker
        if (this.currentRenderOperation === renderOperation) {
          this.currentRenderOperation = null;
        }
        
      } catch (e) {
        console.error('Failed to render JSON:', e);
        if (!renderOperation.cancelled) {
          loadingDiv.innerHTML = `
            <div class="text-red-600">Failed to render JSON: ${e.message}</div>
            <button onclick="this.parentElement.parentElement.querySelector('#render-text').click()" 
                    class="mt-2 text-xs bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded">
              View as Text Instead
            </button>
          `;
        }
      }
    }, 10);
  }

  // Render JSON as plain text with syntax highlighting
  renderJsonAsText(obj, infoContainer) {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'text-center py-8 text-gray-500';
    loadingDiv.innerHTML = `
      <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900 dark:border-white mx-auto mb-2"></div>
      <div class="text-sm">Rendering as text...</div>
    `;
    
    // Remove any existing JSON container
    const existingJson = this.element.querySelector('.json-viewer');
    if (existingJson) existingJson.remove();
    
    this.element.appendChild(loadingDiv);
    
    // Use timeout for non-blocking rendering
    setTimeout(() => {
      try {
        const pretty = JSON.stringify(obj, null, 2);
        
        const container = document.createElement('div');
        container.className = 'json-viewer relative bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600 overflow-auto max-h-96';
        
        const pre = document.createElement('pre');
        pre.className = 'font-mono text-sm leading-relaxed m-0 p-3';
        pre.style.whiteSpace = 'pre-wrap'; // Allow word wrapping for long lines
        
        const code = document.createElement('code');
        code.className = 'language-json';
        code.textContent = pretty;
        
        pre.appendChild(code);
        container.appendChild(pre);
        
        // Remove loading and add content
        loadingDiv.remove();
        this.element.appendChild(container);
        
        // Apply syntax highlighting after a short delay
        if (typeof hljs !== 'undefined') {
          setTimeout(() => {
            try { 
              hljs.highlightElement(code); 
            } catch(e) {
              console.warn('Syntax highlighting failed:', e);
            }
          }, 100);
        }
        
      } catch (e) {
        console.error('Failed to render JSON as text:', e);
        loadingDiv.innerHTML = `<div class="text-red-600">Failed to render JSON: ${e.message}</div>`;
      }
    }, 10);
  }

  // Generate line numbers for JSON (optimized for performance)
  generateJsonLineNumbers(obj, container) {
    // Use requestAnimationFrame for non-blocking line number generation
    requestAnimationFrame(() => {
      try {
        const pretty = JSON.stringify(obj, null, 2);
        const lines = pretty.split('\n');
        const maxLength = lines.length.toString().length;
        
        // Clear existing line numbers
        container.innerHTML = '';
        
        // Create a document fragment for better performance
        const fragment = document.createDocumentFragment();
        
        // Limit line numbers for very large JSON (performance)
        const maxLinesToShow = Math.min(lines.length, 2000);
        
        for (let i = 1; i <= maxLinesToShow; i++) {
          const lineNumber = document.createElement('div');
          lineNumber.className = 'line-number';
          lineNumber.textContent = i.toString().padStart(maxLength, ' ');
          lineNumber.style.height = '20px';
          fragment.appendChild(lineNumber);
        }
        
        // If we truncated, show an indicator
        if (lines.length > maxLinesToShow) {
          const indicator = document.createElement('div');
          indicator.className = 'line-number text-gray-400';
          indicator.textContent = '...';
          indicator.style.height = '20px';
          fragment.appendChild(indicator);
        }
        
        container.appendChild(fragment);
      } catch (e) {
        console.warn('Failed to generate line numbers:', e);
      }
    });
  }

  // Debounced update for JSON display changes
  updateJsonDisplay() {
    if (!this.currentJsonData) return;
    
    // Cancel any pending update
    if (this.updateJsonDisplayTimeout) {
      clearTimeout(this.updateJsonDisplayTimeout);
    }
    
    // Debounce updates to prevent rapid re-rendering
    this.updateJsonDisplayTimeout = setTimeout(() => {
      const container = this.element.querySelector('.enhanced-json-container');
      if (container) {
        // Remove existing JSON display
        this.element.removeChild(container);
        
        // Re-render with updated preferences
        requestAnimationFrame(() => {
          this.renderEnhancedJsonObject(this.currentJsonData, { size: 0, truncated: false });
        });
      }
    }, 100); // 100ms debounce
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
  
  // Add memory management and cleanup
  cleanup() {
    // Cancel any pending timeouts
    if (this.updateJsonDisplayTimeout) {
      clearTimeout(this.updateJsonDisplayTimeout);
      this.updateJsonDisplayTimeout = null;
    }
    
    // Clear cache to free memory
    this.cache.clear();
    
    // Remove event listeners
    this.element.removeEventListener('click', this.handleClick);
    
    // Clear element content
    this.element.innerHTML = '';
    
    console.log('PreviewOptimizer cleaned up');
  }

  // Add click handler for better event management
  handleClick = (e) => {
    const filterCard = e.target.closest('.stats-filter-card');
    if (filterCard) {
      const filterType = filterCard.dataset.filterType;
      this.applyStatisticsFilter(filterType === 'total' ? null : filterType);
    }
  };

  // Get performance statistics
  getPerformanceStats() {
    const avgRenderTime = this.performanceStats.renderCount > 0 
      ? this.performanceStats.totalRenderTime / this.performanceStats.renderCount 
      : 0;
    
    return {
      ...this.performanceStats,
      averageRenderTime: avgRenderTime,
      cacheSize: this.cache.size,
      cacheHitRate: this.cacheHits / Math.max(this.cacheRequests, 1) || 0
    };
  }

  // Clear performance stats
  resetPerformanceStats() {
    this.performanceStats = {
      renderCount: 0,
      totalRenderTime: 0,
      lastRenderTime: 0
    };
    this.cacheHits = 0;
    this.cacheRequests = 0;
    console.log('Performance stats reset');
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
    console.log('renderUberMode called with:', {
      jsonData: !!jsonData,
      meta: meta,
      dataKeys: Object.keys(jsonData || {}),
      extractionCount: jsonData?.extractions?.length || 0
    });
    
    // Detect file type and validate for UBERMODE
    const filePath = this.currentFile?.filePath || 'unknown';
    const isChunkEvaluations = filePath.includes('chunk_evaluations.json');
    const isCombinedExtractions = filePath.includes('combined_extractions.json');
    
    console.log('UBERMODE file validation:', { 
      filePath, 
      isChunkEvaluations, 
      isCombinedExtractions,
      hasExtractions: !!(jsonData?.extractions),
      hasChunkEvaluations: !!(jsonData?.chunk_evaluations)
    });
    
    // Clear previous content
    this.element.innerHTML = '';
    
    // Show warning if wrong file type is loaded
    if (isChunkEvaluations && !jsonData?.extractions) {
      console.warn('UBERMODE: chunk_evaluations.json loaded instead of combined_extractions.json');
      this.element.innerHTML = `
        <div class="bg-amber-50 border border-amber-200 rounded p-4">
          <h3 class="text-amber-800 font-semibold flex items-center">
            <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
            </svg>
            Wrong File for UBERMODE
          </h3>
          <p class="text-amber-700 mt-2">You have loaded <strong>chunk_evaluations.json</strong> which contains evaluation data, not extraction data.</p>
          <p class="text-amber-600 mt-1">For UBERMODE tree view, please select <strong>combined_extractions.json</strong> instead.</p>
          <div class="mt-3 p-2 bg-white border border-amber-200 rounded text-sm">
            <strong>What you need:</strong> combined_extractions.json contains the hierarchical extraction data with sections and entities that UBERMODE can display as a tree.
          </div>
        </div>
      `;
      return;
    }
    
    try {
      // Update stats
      console.log('Updating UBERMODE stats...');
      this.updateUberModeStats(jsonData);
      
      // Create UBERMODE container
      const container = document.createElement('div');
      container.className = 'ubermode-container space-y-4';
      
      // Render tree visualization
      console.log('Creating tree visualization...');
      const treeContainer = this.createTreeVisualization(jsonData);
      container.appendChild(treeContainer);
      
      this.element.appendChild(container);
      console.log('renderUberMode completed successfully');
    } catch (error) {
      console.error('Error in renderUberMode:', error);
      console.error('Stack trace:', error.stack);
      
      // Show error message to user
      this.element.innerHTML = `
        <div class="bg-red-50 border border-red-200 rounded p-4">
          <h3 class="text-red-800 font-semibold">UBERMODE Error</h3>
          <p class="text-red-600 mt-2">Failed to render tree view: ${error.message}</p>
          <p class="text-sm text-red-500 mt-1">Check browser console for details.</p>
        </div>
      `;
    }
  }

  updateUberModeStats(jsonData) {
    console.log('Updating UBERMODE stats...');
    const stats = this.analyzeJsonData(jsonData);
    
    // Dynamically update the statistics container based on actual data
    this.updateStatsContainer(stats);
  }

  analyzeJsonData(data) {
    console.log('Analyzing JSON data for stats...');
    console.log('Raw input data for analysis:', data);
    const stats = {
      totalItems: 0,
      types: new Map(),
      quality: '—'
    };
    
    // Normalize the data format to handle both old and new structures
    const normalizedData = this.normalizeJsonDataForUberMode(data);
    console.log('Normalized data for analysis:', {
      hasExtractions: !!(normalizedData?.extractions),
      extractionCount: normalizedData?.extractions?.length || 0,
      hasSections: !!(normalizedData?.sections),
      sectionCount: normalizedData?.sections?.length || 0,
      sampleExtraction: normalizedData?.extractions?.[0] || null,
      extractionSample: normalizedData?.extractions?.slice(0, 3) || []
    });
    
    // Handle extraction format - count by extraction_class
    if (normalizedData && normalizedData.extractions && Array.isArray(normalizedData.extractions)) {
      console.log(`Processing ${normalizedData.extractions.length} extractions for stats...`);
      normalizedData.extractions.forEach((extraction, index) => {
        stats.totalItems++;
        
        // Count extraction types dynamically
        const extractionClass = extraction.extraction_class;
        if (extractionClass) {
          const currentCount = stats.types.get(extractionClass) || 0;
          stats.types.set(extractionClass, currentCount + 1);
        } else {
          console.warn(`Extraction ${index} missing extraction_class:`, extraction);
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
      console.log('Analysis complete:', {
        totalItems: stats.totalItems,
        types: Object.fromEntries(stats.types),
        quality: stats.quality
      });
    } else {
      console.warn('No extractions found in normalized data');
    }
    
    return stats;
  }

  updateStatsContainer(stats) {
    console.log('Updating stats container with stats:', stats);
    // Find the stats content container within this element's scope
    const statsContent = document.querySelector('.stats-content');
    // const statsContent = this.element.querySelector('.stats-content');
    console.log('this.element:', this.element);
    console.log('Stats content container:', statsContent);
    if (!statsContent) return;

    // Find the grid containers
    const gridContainers = statsContent.querySelectorAll('.grid');
    if (gridContainers.length < 2) return;
    console.log('Grid containers found:', gridContainers.length);
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
    // Add click event listeners to filter cards
    document.querySelectorAll('.stats-filter-card').forEach(card => {
      card.addEventListener('click', (e) => {
        const filterType = card.dataset.filterType;
        this.applyStatisticsFilter(filterType === 'total' ? null : filterType);
      });
    });

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
    console.log('createTreeVisualization called with data:', {
      hasData: !!data,
      dataKeys: Object.keys(data || {}),
      extractionCount: data?.extractions?.length || 0
    });
    
    const container = document.createElement('div');
    container.className = 'tree-visualization bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4';
    
    const title = document.createElement('h3');
    title.className = 'text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200';
    title.textContent = '🌳 Document Structure';
    container.appendChild(title);
    
    const tree = document.createElement('div');
    tree.className = 'tree-content space-y-1';
    
    try {
      // Build document tree from extraction data
      console.log('Building document tree...');
      const documentTree = this.buildDocumentTree(data);
      console.log('Document tree built, rendering...', {
        rootNodeCount: documentTree?.length || 0,
        rootNodes: documentTree?.map(n => `${n.id} (${n.children?.length || 0} children)`) || []
      });
      
      this.renderDocumentTree(tree, documentTree);
      console.log('Tree rendering completed');
    } catch (error) {
      console.error('Error in tree visualization:', error);
      console.error('Stack trace:', error.stack);
      
      tree.innerHTML = `
        <div class="text-red-600 p-4">
          <p>Error building tree: ${error.message}</p>
          <p class="text-sm mt-2">Check browser console for details.</p>
        </div>
      `;
    }
    
    container.appendChild(tree);
    return container;
  }

  // Helper method to normalize JSON data format for UBERMODE
  normalizeJsonDataForUberMode(data) {
    // Handle the new combined_extractions.json format with nested structure
    if (data && data.extractions && Array.isArray(data.extractions)) {
      // Already in the expected format { extractions: [...] }
      return data;
    }
    
    // Handle legacy format or other structures - return as-is if no extractions found
    return data;
  }

  buildDocumentTree(data) {
    const startTime = performance.now();
    console.log('Building document tree...');
    console.log('Raw input data:', data);
    
    const nodes = new Map();
    const rootNodes = [];
    
    // Normalize the data format to handle both old and new structures
    const normalizedData = this.normalizeJsonDataForUberMode(data);
    console.log('Normalized data for tree building:', {
      hasExtractions: !!(normalizedData?.extractions),
      extractionCount: normalizedData?.extractions?.length || 0,
      hasSections: !!(normalizedData?.sections),
      sectionCount: normalizedData?.sections?.length || 0,
      sampleExtraction: normalizedData?.extractions?.[0] || null
    });
    
    // Handle extraction format
    if (normalizedData && normalizedData.extractions && Array.isArray(normalizedData.extractions)) {
      console.log('Processing extractions for tree building...');
      // First, add actual section nodes from the sections array if available
      if (normalizedData.sections && Array.isArray(normalizedData.sections)) {
        normalizedData.sections.forEach(section => {
          if (section.section_id) {
            const nodeData = {
              id: section.section_id,
              title: section.section_name || section.section_title || section.extraction_text || section.section_id,
              type: 'SECTION',
              parentId: section.parent_section || null,
              parentType: 'SECTION',
              summary: section.section_summary || '',
              extractionText: section.extraction_text || '',
              children: [],
              isExpanded: true, // Sections start expanded
              level: 0,
              attributes: section,
              extraction: { extraction_class: 'SECTION', attributes: section, extraction_text: section.extraction_text }
            };
            nodes.set(section.section_id, nodeData);
            console.log(`Added section node: ${section.section_id} -> title: "${nodeData.title}"`);
          }
        });
      }
      
      // Filter relevant extraction types - excluding LEGAL_DOCUMENT as requested
      const excludedTypes = ['LEGAL_DOCUMENT', 'Legal_Document', 'Legal_Documents', 'CHUNK_METADATA']; // Exclude as requested
      let relevant = normalizedData.extractions.filter(ext => 
        !excludedTypes.includes(ext.extraction_class)
      );
      
      // Apply statistics filter if one is active
      const currentFilter = window.globalStatisticsFilter;
      if (currentFilter) {
        console.log(`Filtering extractions by type: ${currentFilter}`);
        
        // Get all extractions that match the filter
        const filteredExtractions = normalizedData.extractions.filter(ext => 
          ext.extraction_class === currentFilter
        );
        
        // If we're filtering, we need to also include parent nodes to maintain hierarchy
        const requiredNodeIds = new Set();
        
        // Add filtered nodes and collect their parent chain
        filteredExtractions.forEach(ext => {
          const nodeId = this.getNodeId(ext);
          if (nodeId) {
            requiredNodeIds.add(nodeId);
            
            // Add parent chain
            let parentId = this.getParentId(ext);
            while (parentId) {
              requiredNodeIds.add(parentId);
              // Find parent extraction to continue the chain
              const parentExt = normalizedData.extractions.find(e => this.getNodeId(e) === parentId);
              parentId = parentExt ? this.getParentId(parentExt) : null;
            }
          }
        });
        
        // Filter relevant extractions to only include required nodes
        relevant = relevant.filter(ext => {
          const nodeId = this.getNodeId(ext);
          return nodeId && requiredNodeIds.has(nodeId);
        });
        
        console.log(`Filtered from ${normalizedData.extractions.length} total to ${relevant.length} relevant nodes for filter: ${currentFilter}`);
      }
      
      console.log(`Building tree from ${relevant.length} relevant extractions out of ${normalizedData.extractions.length} total`);
      
      // Performance safeguard for very large documents
      const totalNodes = (normalizedData.sections?.length || 0) + relevant.length;
      const MAX_TREE_NODES = 5000; // Reasonable limit for browser performance
      
      console.log(`Total nodes to process: ${totalNodes} (${normalizedData.sections?.length || 0} sections + ${relevant.length} extractions)`);
      
      if (totalNodes > MAX_TREE_NODES) {
        console.warn(`Large document detected: ${totalNodes} total nodes. This may affect performance.`);
        console.warn(`Consider using the statistics filter to reduce the scope.`);
        
        // For very large documents, limit to sections and a sample of extractions
        if (totalNodes > MAX_TREE_NODES * 2) {
          console.warn(`Document too large (${totalNodes} nodes). Limiting to first ${MAX_TREE_NODES} extractions.`);
          relevant = relevant.slice(0, MAX_TREE_NODES - (normalizedData.sections?.length || 0));
          console.log(`Limited to ${relevant.length} extractions for performance`);
        }
      }
      
      // First pass: create all nodes (following section_tree_visualizer.py pattern)
      relevant.forEach(extraction => {
        const nodeId = this.getNodeId(extraction);
        if (!nodeId) {
          console.warn('Skipping extraction without ID:', extraction);
          return;
        }
        
        const attrs = extraction.attributes || {};
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
      
      // Create synthetic root nodes only if needed and sections array is not available
      if (!normalizedData.sections || normalizedData.sections.length === 0) {
        this.createSyntheticRoots(nodes);
      }
      
      // Create synthetic parent nodes for missing parents before building relationships
      const missingParents = new Set();
      nodes.forEach(node => {
        if (node.parentId && !nodes.has(node.parentId)) {
          missingParents.add(node.parentId);
        }
      });
      
      // Create synthetic nodes for missing parents
      missingParents.forEach(parentId => {
        const syntheticNode = {
          id: parentId,
          title: `[Dropped Section] ${parentId}`,
          type: 'SECTION',
          parentId: null, // Make synthetic nodes root-level
          parentType: 'SECTION',
          summary: 'This section was dropped during processing but is referenced by child sections.',
          extractionText: '',
          children: [],
          isExpanded: true,
          level: 0,
          attributes: { section_id: parentId, section_name: `[Dropped Section] ${parentId}`, synthetic: true },
          extraction: { extraction_class: 'SECTION', attributes: { synthetic: true }, extraction_text: '' }
        };
        nodes.set(parentId, syntheticNode);
        rootNodes.push(syntheticNode); // Add synthetic parents to root nodes
        console.log(`Created synthetic parent node: ${parentId}`);
      });

      // Second pass: build parent-child relationships
      let orphanCount = 0;
      nodes.forEach(node => {
        if (node.parentId && nodes.has(node.parentId)) {
          const parent = nodes.get(node.parentId);
          parent.children.push(node);
          node.level = parent.level + 1;
          console.log(`Linked ${node.id} as child of ${parent.id} (level ${node.level})`);
        } else if (!node.attributes?.synthetic) { // Don't double-add synthetic nodes
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
    } else {
      console.warn('No valid extraction data found for tree building');
      console.warn('Normalized data check failed:', {
        hasNormalizedData: !!normalizedData,
        hasExtractions: !!(normalizedData?.extractions),
        isExtractionsArray: Array.isArray(normalizedData?.extractions),
        extractionCount: normalizedData?.extractions?.length || 0
      });
    }
    
    const endTime = performance.now();
    console.log(`Tree building completed in ${(endTime - startTime).toFixed(2)}ms`);
    console.log('Returning root nodes:', rootNodes.length);
    
    return rootNodes;
  }

  // Helper method to extract ID from extraction data
  getNodeId(extraction) {
    const attrs = extraction.attributes || {};
    
    // First try to get ID from attributes
    if (attrs.id) {
      return attrs.id;
    }
    
    // Try to parse ID from extraction_text (Python dict format)
    if (extraction.extraction_text) {
      try {
        // Handle Python dictionary format with single quotes
        const pythonDictStr = extraction.extraction_text;
        
        // Look for 'id': 'value' pattern in the string
        const idMatch = pythonDictStr.match(/'id':\s*'([^']+)'/);
        if (idMatch) {
          return idMatch[1];
        }
        
        // Alternative patterns
        const idMatch2 = pythonDictStr.match(/"id":\s*"([^"]+)"/);
        if (idMatch2) {
          return idMatch2[1];
        }
      } catch (error) {
        console.warn('Error parsing extraction_text for ID:', error);
      }
    }
    
    // Fall back to section_parent_id or extraction_index for unique ID
    return attrs.section_parent_id || extraction.section_parent_id || `extraction_${extraction.extraction_index || Math.random()}`;
  }

  // Helper method to determine parent ID following section_tree_visualizer.py patterns
  getParentId(extraction) {
    const attrs = extraction.attributes || {};
    const type = extraction.extraction_class;
    
    // First try to get parent from attributes
    let parentId = attrs.parent_section_id || attrs.parent_id;
    
    // If not found, try to parse from extraction_text
    if (!parentId && extraction.extraction_text) {
      try {
        const pythonDictStr = extraction.extraction_text;
        const parentMatch = pythonDictStr.match(/'parent_section_id':\s*'([^']+)'/);
        if (parentMatch) {
          parentId = parentMatch[1];
        }
      } catch (error) {
        console.warn('Error parsing extraction_text for parent ID:', error);
      }
    }
    
    // Fall back to section_parent_id
    if (!parentId) {
      parentId = extraction.section_parent_id;
    }
    
    return parentId;
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
          title: 'CTE - Código Técnico de la Edificación',
          type: 'SECTION', // Change from LEGAL_DOCUMENT to SECTION
          parentId: null,
          parentType: null,
          summary: 'Código Técnico de la Edificación - Documento Básico de Seguridad en caso de Incendio',
          extractionText: cteRootId,
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
          type: 'SECTION', // Change from LEGAL_DOCUMENT to SECTION to avoid confusion
          parentId: null,
          parentType: null,
          summary: `Root section: ${rootId}`,
          extractionText: rootId,
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
    // Remove "Document Root" as requested
    if (rootId.includes('CTE')) {
      return 'CTE - Código Técnico de la Edificación';
    } else if (rootId.includes('DB')) {
      return `Documento Básico - ${rootId}`;
    } else if (rootId.includes('SI')) {
      return `Seguridad en caso de Incendio - ${rootId}`;
    } else if (rootId.startsWith('section_')) {
      // Extract section number and create a more meaningful title
      const sectionNum = rootId.replace('section_', '');
      return `Section ${sectionNum}`;
    } else {
      return rootId; // Just use the ID itself instead of "Document Root"
    }
  }

  getNodeTitle(extraction) {
    const attrs = extraction.attributes || {};
    const type = extraction.extraction_class;
    
    // For sections, try to get from section metadata first
    if (type === 'SECTION') {
      // Check if we have section metadata
      if (extraction.section_metadata) {
        return extraction.section_metadata.section_name || extraction.section_metadata.section_title || 'Untitled Section';
      }
      // Use section_name if available, otherwise fall back to section_title or extraction text
      return attrs.section_name || attrs.section_title || extraction.extraction_text || 'Untitled Section';
    } 
    
    // For NORM extractions, try to parse the norm statement from extraction_text
    else if (type === 'NORM') {
      // Try to parse norm statement from extraction_text Python dict format
      if (extraction.extraction_text) {
        try {
          const pythonDictStr = extraction.extraction_text;
          
          // Look for norm_statement in the extraction_text
          const normMatch = pythonDictStr.match(/'norm_statement':\s*'([^']+)'/);
          if (normMatch) {
            const statement = normMatch[1];
            return statement.length > 80 ? statement.substring(0, 80) + '...' : statement;
          }
          
          // Alternative patterns
          const normMatch2 = pythonDictStr.match(/"norm_statement":\s*"([^"]+)"/);
          if (normMatch2) {
            const statement = normMatch2[1];
            return statement.length > 80 ? statement.substring(0, 80) + '...' : statement;
          }
        } catch (error) {
          console.warn('Error parsing extraction_text for norm statement:', error);
        }
      }
      
      // Fall back to attributes or raw extraction text
      const statement = attrs.norm_statement || attrs.statement_text || extraction.extraction_text || '';
      return statement.length > 80 ? statement.substring(0, 80) + '...' : statement;
    } 
    
    // For other types, use extraction class as title with extraction text truncated
    else {
      const text = extraction.extraction_text || '';
      const displayText = text.length > 50 ? text.substring(0, 50) + '...' : text;
      return `${type}: ${displayText}` || type;
    }
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
    } else if (type === 'PROCEDURE' || type === 'Procedure') {
      const stepNum = attrs.step_number || attrs.paragraph_number || 'N/A';
      const procType = attrs.procedure_type || 'Procedure';
      return `Step ${stepNum} - ${procType}`;
    } else if (type === 'LEGAL_DOCUMENT') {
      // For root sections, just return the type name instead of formatted document info
      if (!attrs.doc_type && !attrs.jurisdiction) {
        return 'Legal Document';
      }
      // Match the format: "{doc_type} - {jurisdiction}"
      const docType = attrs.doc_type || 'Legal Document';
      const jurisdiction = attrs.jurisdiction || 'Unknown jurisdiction';
      return `${docType} - ${jurisdiction}`;
    }
    return '';
  }

  renderDocumentTree(container, nodes) {
    const startTime = performance.now();
    console.log(`Rendering tree with ${nodes.length} root nodes...`);
    
    nodes.forEach(node => {
      this.renderDocumentNode(container, node, 0);
    });
    
    const endTime = performance.now();
    console.log(`Tree rendering completed in ${(endTime - startTime).toFixed(2)}ms`);
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
    
    // Always make nodes expandable (for children or details)
    const hasChildren = node.children.length > 0;
    const hasDetails = this.hasNodeDetails(node);
    
    if (hasChildren || hasDetails) {
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
    
    // Remove ID display - just show title and type
    const titleSpan = document.createElement('span');
    titleSpan.className = 'node-title text-gray-800 dark:text-gray-200 text-sm flex-grow';
    titleSpan.textContent = node.title;
    titleSpan.title = node.title; // Show full title on hover
    titleSpan.style.wordBreak = 'break-word'; // Allow text wrapping
    
    const typeSpan = document.createElement('span');
    typeSpan.className = `node-type text-xs px-2 py-1 rounded-full flex-shrink-0 font-medium ${this.getTypeClass(node.type)}`;
    typeSpan.textContent = node.type;
    
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
    
    // Create details container (for expandable details)
    const detailsContainer = document.createElement('div');
    detailsContainer.className = 'tree-details transition-all duration-300 ease-in-out overflow-hidden';
    
    // Render details if the node has them
    if (this.hasNodeDetails(node)) {
      this.renderNodeDetails(detailsContainer, node, level);
      
      // Set initial visibility
      if (node.isExpanded) {
        detailsContainer.style.display = 'block';
        detailsContainer.style.maxHeight = 'none';
        detailsContainer.style.opacity = '1';
      } else {
        detailsContainer.style.display = 'none';
        detailsContainer.style.maxHeight = '0px';
        detailsContainer.style.opacity = '0';
      }
      
      nodeElement.appendChild(detailsContainer);
    }
    
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
      
      // Single click - toggle expand/collapse for nodes with children or details
      const hasChildren = node.children.length > 0;
      const hasDetails = this.hasNodeDetails(node);
      
      if (hasChildren || hasDetails) {
        e.preventDefault();
        e.stopPropagation();
        console.log(`Toggling node: ${node.id}, has ${node.children.length} children, has details: ${hasDetails}, currently expanded: ${node.isExpanded}`);
        
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
        
        // Toggle details visibility if they exist
        if (hasDetails) {
          if (node.isExpanded) {
            // Expanding details
            detailsContainer.style.display = 'block';
            detailsContainer.style.transition = 'max-height 0.3s ease-out, opacity 0.3s ease-out';
            // Force a reflow
            detailsContainer.offsetHeight;
            detailsContainer.style.maxHeight = detailsContainer.scrollHeight + 'px';
            detailsContainer.style.opacity = '1';
            
            // Remove max-height after animation for dynamic content
            setTimeout(() => {
              if (node.isExpanded) {
                detailsContainer.style.maxHeight = 'none';
              }
            }, 300);
          } else {
            // Collapsing details
            detailsContainer.style.maxHeight = detailsContainer.scrollHeight + 'px';
            detailsContainer.style.transition = 'max-height 0.3s ease-in, opacity 0.3s ease-in';
            // Force a reflow
            detailsContainer.offsetHeight;
            detailsContainer.style.maxHeight = '0px';
            detailsContainer.style.opacity = '0';
            
            // Hide after animation completes
            setTimeout(() => {
              if (!node.isExpanded) { // Check if still collapsed
                detailsContainer.style.display = 'none';
              }
            }, 300);
          }
        }
        
        // Toggle children visibility if they exist
        if (hasChildren) {
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
    
    // Navigate by finding the extraction with directed search using node context
    this.scrollToJsonNode(previewElement, node);
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

  scrollToJsonNode(previewElement, nodeOrId) {
    const nodeId = typeof nodeOrId === 'string' ? nodeOrId : (nodeOrId && nodeOrId.id) || '';
    const nodeInfo = typeof nodeOrId === 'object' && nodeOrId ? nodeOrId : null;
    console.log(`Attempting to scroll to node ID: ${nodeId} in JSON panel: `, previewElement);
    
    // IMPORTANT: Use intelligent expansion strategy to find the target node
    // First try to find the target with minimal expansion, then expand only necessary paths
    const targetElement = this.findTargetNodeWithIntelligentExpansion(previewElement, nodeId, nodeInfo);
    if (targetElement) {
      this.scrollToFoundElement(targetElement, nodeId);
      return;
    }
    
    // Fallback: if intelligent expansion failed, try text-based search
    this.fallbackTextSearch(previewElement, nodeId);
  }

  // Intelligent expansion strategy: find target with minimal expansion
  findTargetNodeWithIntelligentExpansion(previewElement, nodeId, nodeInfo) {
    console.log(`Using intelligent expansion to find node: ${nodeId}`);
    
    // Step 1: Try to find target without any expansion first
    let targetElement = this.searchForTargetElement(previewElement, nodeId, nodeInfo);
    if (targetElement) {
      console.log(`Found target node ${nodeId} without expansion`);
      return targetElement;
    }

    // Step 2: If not found, try progressive expansion with path analysis
    return this.expandPathToTarget(previewElement, nodeId, nodeInfo);
  }

  // Progressive expansion that only expands the path to the target
  expandPathToTarget(previewElement, nodeId, nodeInfo) {
    console.log(`Starting path-based expansion for node: ${nodeId}`);
    
    const maxAttempts = 8;
    let attempt = 0;
    
    while (attempt < maxAttempts) {
      // Try to find potential parent containers that might contain our target
      const candidateContainers = this.findCandidateContainers(previewElement, nodeId, nodeInfo);
      
      if (candidateContainers.length === 0) {
        console.log(`No candidate containers found on attempt ${attempt + 1}`);
        break;
      }
      
      // Expand the most promising containers (upward chain + one level down)
      let expandedAny = false;
      for (const container of candidateContainers) {
        if (this.expandContainerPath(container)) {
          expandedAny = true;
        }
      }
      
      // If we expanded something, try to find the target again
      if (expandedAny) {
        const targetElement = this.searchForTargetElement(previewElement, nodeId, nodeInfo);
        if (targetElement) {
          console.log(`Found target node ${nodeId} after ${attempt + 1} expansion attempts`);
          return targetElement;
        }
      }
      
      attempt++;
    }
    
    console.warn(`Could not find node ${nodeId} after ${attempt} intelligent expansion attempts`);
    return null;
  }

  // Find containers that might contain the target node
  findCandidateContainers(previewElement, nodeId, nodeInfo) {
    const candidates = [];
    
    // Look for containers that contain text related to our target
    const searchTerms = [nodeId];
    if (nodeInfo && nodeInfo.type) {
      searchTerms.push(nodeInfo.type);
    }
    if (nodeInfo && nodeInfo.extraction) {
      const parentId = nodeInfo.extraction.parent_id || nodeInfo.extraction.parent;
      if (parentId) {
        searchTerms.push(parentId);
      }
    }
    
    // Find collapsed containers that might contain relevant text
    const collapsedSelectors = [
      '.json-formatter-closed',
      '.json-formatter-collapsed', 
      '.collapsed',
      'details:not([open])'
    ].join(',');
    
    const collapsedContainers = previewElement.querySelectorAll(collapsedSelectors);
    
    collapsedContainers.forEach(container => {
      // Check if this container might contain our target based on visible text
      const visibleText = this.getVisibleText(container);
      const hasRelevantText = searchTerms.some(term => visibleText.includes(term));
      
      if (hasRelevantText) {
        candidates.push({
          element: container,
          relevanceScore: this.calculateRelevanceScore(visibleText, searchTerms),
          depth: this.getElementDepth(container, previewElement)
        });
      }
    });
    
    // Sort candidates by relevance score and depth (prioritize higher relevance and shallower depth)
    candidates.sort((a, b) => {
      if (a.relevanceScore !== b.relevanceScore) {
        return b.relevanceScore - a.relevanceScore;
      }
      return a.depth - b.depth;
    });
    
    // Return top candidates
    return candidates.slice(0, 5).map(c => c.element);
  }

  // Get visible text from a container (text that's immediately visible, not in collapsed children)
  getVisibleText(container) {
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (node) => {
          // Only accept text nodes that are not inside collapsed containers
          let current = node.parentElement;
          while (current && current !== container) {
            if (current.classList && (
              current.classList.contains('json-formatter-closed') ||
              current.classList.contains('json-formatter-collapsed') ||
              current.classList.contains('collapsed')
            )) {
              return NodeFilter.FILTER_REJECT;
            }
            if (current.tagName && current.tagName.toLowerCase() === 'details' && !current.open) {
              return NodeFilter.FILTER_REJECT;
            }
            current = current.parentElement;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );
    
    let text = '';
    let node;
    while ((node = walker.nextNode())) {
      text += node.textContent + ' ';
      // Limit text collection for performance
      if (text.length > 1000) break;
    }
    
    return text.trim();
  }

  // Calculate relevance score for a container
  calculateRelevanceScore(text, searchTerms) {
    let score = 0;
    searchTerms.forEach(term => {
      if (text.includes(term)) {
        score += term.length; // Longer terms get higher scores
      }
    });
    return score;
  }

  // Get depth of element relative to preview container
  getElementDepth(element, root) {
    let depth = 0;
    let current = element;
    while (current && current !== root) {
      depth++;
      current = current.parentElement;
    }
    return depth;
  }

  // Expand a container path (the container itself + one level down)
  expandContainerPath(container) {
    console.log(`Expanding container path:`, container);
    
    const togglerSelectors = [
      '.json-formatter-toggler',
      '.json-formatter-toggle',
      '.json-formatter-opener',
      '.json-formatter-arrow'
    ].join(',');
    
    let expanded = false;
    
    // First, expand the container itself if it's collapsed
    if (this.isCollapsed(container)) {
      if (this.expandElement(container, togglerSelectors)) {
        expanded = true;
        console.log(`Expanded container itself`);
      }
    }
    
    // Then, expand immediate children one level down
    const immediateChildren = this.getImmediateCollapsedChildren(container);
    immediateChildren.forEach(child => {
      if (this.expandElement(child, togglerSelectors)) {
        expanded = true;
        console.log(`Expanded immediate child`);
      }
    });
    
    return expanded;
  }

  // Check if an element is collapsed
  isCollapsed(element) {
    if (element.tagName && element.tagName.toLowerCase() === 'details') {
      return !element.open;
    }
    
    return element.classList && (
      element.classList.contains('json-formatter-closed') ||
      element.classList.contains('json-formatter-collapsed') ||
      element.classList.contains('collapsed')
    );
  }

  // Expand a single element
  expandElement(element, togglerSelectors) {
    if (element.tagName && element.tagName.toLowerCase() === 'details') {
      if (!element.open) {
        element.open = true;
        return true;
      }
      return false;
    }
    
    const toggler = element.querySelector(togglerSelectors);
    if (toggler) {
      try {
        toggler.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        return true;
      } catch (e) {
        console.warn('Failed to expand element:', e);
        return false;
      }
    }
    
    return false;
  }

  // Get immediate collapsed children of a container
  getImmediateCollapsedChildren(container) {
    const children = [];
    const childElements = container.children;
    
    for (let child of childElements) {
      if (this.isCollapsed(child)) {
        children.push(child);
      }
      
      // Also check one more level down for JSONFormatter rows
      const grandChildren = child.querySelectorAll('.json-formatter-row');
      for (let grandChild of grandChildren) {
        if (this.isCollapsed(grandChild) && grandChild.parentElement === child) {
          children.push(grandChild);
        }
      }
    }
    
    return children.slice(0, 10); // Limit to prevent excessive expansion
  }

  // Search for target element in the DOM
  searchForTargetElement(previewElement, nodeId, nodeInfo) {
    // Try structured search first (JSONFormatter DOM)
    let targetElement = this.tryStructuredSearch(previewElement, nodeId, nodeInfo);
    if (targetElement) {
      return targetElement;
    }
    
    // Try scored element search
    targetElement = this.tryScoredElementSearch(previewElement, nodeId, nodeInfo);
    if (targetElement) {
      return targetElement;
    }
    
    // Try simple text-based search as last resort
    return this.trySimpleTextSearch(previewElement, nodeId);
  }

  // Try structured search for JSONFormatter elements
  tryStructuredSearch(previewElement, nodeId, nodeInfo) {
    const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim();
    
    // Prefer rows with key "id" matching the target
    const rows = previewElement.querySelectorAll('.json-formatter-row');
    for (const row of rows) {
      const keyEl = row.querySelector('.json-formatter-key');
      if (!keyEl) continue;
      
      const keyText = normalize(keyEl.textContent);
      if (!/\b"?id"?\b/i.test(keyText)) continue;
      
      const valueEl = row.querySelector('.json-formatter-string, .json-formatter-number, .json-formatter-value');
      const valText = normalize(valueEl && valueEl.textContent);
      
      // Value may include quotes; compare loosely
      const unquoted = (valText || '').replace(/^"|"$/g, '');
      if (unquoted !== nodeId) continue;
      
      // Found a matching id row - find the container that represents the full object
      return this.findObjectContainer(row, nodeInfo);
    }
    
    return null;
  }

  // Find the object container that holds a matching row
  findObjectContainer(row, nodeInfo) {
    let candidate = row;
    
    // Walk up to find a container representing the object
    for (let i = 0; i < 6 && candidate && candidate !== document; i++) {
      if (this.isGoodContainer(candidate, nodeInfo)) {
        return candidate;
      }
      candidate = candidate.parentElement;
    }
    
    // Fallback to the row itself
    return row;
  }

  // Check if container contains expected object structure
  isGoodContainer(element, nodeInfo) {
    const txt = (element.textContent || '').replace(/\s+/g, ' ').trim();
    let isGood = true;
    
    if (nodeInfo && nodeInfo.type) {
      isGood = isGood && txt.includes('extraction_class') && txt.includes(nodeInfo.type);
    }
    
    // If we have parent info, prefer containers that include it
    const parentId = nodeInfo && nodeInfo.extraction && (
      nodeInfo.extraction.parent_id || 
      nodeInfo.extraction.parent || 
      (nodeInfo.extraction.attributes && (
        nodeInfo.extraction.attributes.parent_id || 
        nodeInfo.extraction.attributes.parent
      ))
    );
    
    if (parentId) {
      isGood = isGood && txt.includes(parentId);
    }
    
    return isGood;
  }

  // Try scored element search
  tryScoredElementSearch(previewElement, nodeId, nodeInfo) {
    const normalize = (s) => (s || '').replace(/\s+/g, ' ').trim();
    const all = previewElement.querySelectorAll('*');
    let best = null;
    let bestScore = -1;
    
    const parentId = nodeInfo && nodeInfo.extraction && (
      nodeInfo.extraction.parent_id || 
      nodeInfo.extraction.parent || 
      (nodeInfo.extraction.attributes && (
        nodeInfo.extraction.attributes.parent_id || 
        nodeInfo.extraction.attributes.parent
      ))
    );
    
    for (const el of all) {
      const txt = normalize(el.textContent || '');
      if (!txt) continue;
      
      let score = 0;
      if (txt.includes(`"id": "${nodeId}"`) || txt.includes(`"id":"${nodeId}"`)) score += 4;
      if (txt.includes(nodeId)) score += 2;
      if (nodeInfo && nodeInfo.type && txt.includes(nodeInfo.type)) score += 1;
      if (parentId && txt.includes(parentId)) score += 1;
      
      if (score <= 0) continue;
      
      // Prefer smaller containers and deeper matches
      const tieBreak = 1 / Math.max(1, txt.length) + (1000 - (el.children ? el.children.length : 0)) * 1e-6;
      const total = score + tieBreak;
      
      if (total > bestScore) {
        bestScore = total;
        best = el;
      }
    }
    
    return best;
  }

  // Try simple text search
  trySimpleTextSearch(previewElement, nodeId) {
    const allElements = previewElement.querySelectorAll('*');
    let targetElement = null;
    
    for (const element of allElements) {
      const elementText = element.textContent || '';
      if (elementText.includes(`"id": "${nodeId}"`) ||
          elementText.includes(`"id":"${nodeId}"`) ||
          elementText.includes(nodeId)) {
        if (!targetElement || element.children.length < targetElement.children.length) {
          targetElement = element;
        }
      }
    }
    
    return targetElement;
  }

  // Scroll to found element with proper expansion
  scrollToFoundElement(targetElement, nodeId) {
    console.log(`Found target element for node ${nodeId}, scrolling into view`);
    
    // Ensure ancestors are expanded so the element remains visible
    this.ensureAncestorsExpanded(targetElement);
    
    // Scroll into view
    const isVisible = targetElement.offsetParent !== null && targetElement.offsetHeight > 0;
    if (!isVisible && targetElement.parentElement) {
      targetElement.parentElement.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
    
    targetElement.scrollIntoView({
      behavior: 'smooth',
      block: 'center'
    });
    
    // Add temporary highlighting
    this.highlightElement(targetElement);
    
    console.log(`Successfully scrolled to and highlighted node ${nodeId} in JSON panel`);
  }

  // Ensure ancestors of an element are expanded
  ensureAncestorsExpanded(element) {
    const togglerSelectors = [
      '.json-formatter-toggler',
      '.json-formatter-toggle',
      '.json-formatter-opener',
      '.json-formatter-arrow'
    ].join(',');
    
    let current = element;
    while (current && current !== document) {
      // Open <details>
      if (current.tagName && current.tagName.toLowerCase() === 'details' && !current.open) {
        current.open = true;
      }
      
      // Expand JSONFormatter collapsed containers
      if (current.classList && (
        current.classList.contains('json-formatter-closed') ||
        current.classList.contains('json-formatter-collapsed') ||
        current.classList.contains('collapsed')
      )) {
        const toggler = current.querySelector(togglerSelectors);
        if (toggler) {
          try {
            toggler.dispatchEvent(new MouseEvent('click', { bubbles: true }));
          } catch (e) {
            console.warn('Failed to expand ancestor:', e);
          }
        }
      }
      
      current = current.parentElement;
    }
  }

  // Highlight an element temporarily
  highlightElement(element) {
    const originalBg = element.style.backgroundColor;
    const originalBorder = element.style.border;
    const originalTransition = element.style.transition;
    
    element.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
    element.style.border = '2px solid rgba(59, 130, 246, 0.5)';
    element.style.transition = 'all 0.3s ease-in-out';
    
    setTimeout(() => {
      element.style.backgroundColor = originalBg;
      element.style.border = originalBorder;
      element.style.transition = originalTransition;
    }, 2000);
  }

  // Fallback text search method
  fallbackTextSearch(previewElement, nodeId) {
    console.log(`Falling back to text search for node: ${nodeId}`);
    
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
      console.warn(`Could not find node ID ${nodeId} in JSON content using any method`);
      return;
    }
    
    // Calculate approximate scroll position
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

  // Legacy method: kept for backward compatibility but no longer used for scrolling
  // The intelligent expansion approach is now used instead
  expandAllJsonFormatterNodes(previewElement) {
    console.log('Legacy expandAllJsonFormatterNodes called - consider using intelligent expansion instead');
    
    const togglerSelectors = [
      '.json-formatter-toggler',
      '.json-formatter-toggle', 
      '.json-formatter-opener',
      '.json-formatter-arrow'
    ].join(',');
    
    let expandedCount = 0;
    const maxExpansions = 200; // Safety limit
    
    // Multiple passes to handle nested collapsed nodes
    for (let pass = 0; pass < 5; pass++) {
      // Open all <details> elements
      const details = previewElement.querySelectorAll('details:not([open])');
      details.forEach(detail => {
        if (expandedCount < maxExpansions) {
          detail.open = true;
          expandedCount++;
        }
      });
      
      // Find and click all collapsed JSONFormatter containers
      const closedContainers = previewElement.querySelectorAll(
        '.json-formatter-closed, .json-formatter-collapsed, .collapsed'
      );
      
      let expandedInThisPass = 0;
      closedContainers.forEach(container => {
        if (expandedCount >= maxExpansions) return;
        
        const toggler = container.querySelector(togglerSelectors);
        if (toggler) {
          try {
            toggler.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            expandedCount++;
            expandedInThisPass++;
          } catch (e) {
            console.warn('Failed to click toggler:', e);
          }
        }
      });
      
      // Also check for togglers that might be collapsed based on aria-expanded
      const possibleTogglers = previewElement.querySelectorAll(togglerSelectors);
      possibleTogglers.forEach(toggler => {
        if (expandedCount >= maxExpansions) return;
        
        const expanded = (toggler.getAttribute('aria-expanded') || '').toLowerCase();
        if (expanded === 'false' || expanded === '') {
          try {
            toggler.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            expandedCount++;
            expandedInThisPass++;
          } catch (e) {
            console.warn('Failed to click toggler with aria-expanded:', e);
          }
        }
      });
      
      console.log(`Pass ${pass + 1}: Expanded ${expandedInThisPass} nodes (total: ${expandedCount})`);
      
      // If we didn't expand anything in this pass, we're done
      if (expandedInThisPass === 0) {
        break;
      }
      
      // Small delay to allow DOM updates
      if (expandedInThisPass > 0 && pass < 4) {
        // Use synchronous delay to keep the function call simple
        const start = Date.now();
        while (Date.now() - start < 50) {
          // Wait 50ms for DOM updates
        }
      }
    }
    
    console.log(`Legacy expansion complete: ${expandedCount} nodes expanded`);
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

  // Check if a node has details that can be expanded
  hasNodeDetails(node) {
    if (!node || !node.extraction) return false;
    
    const type = node.type;
    const attrs = node.extraction.attributes || {};
    
    if (type === 'SECTION') {
      return attrs.parent_section || attrs.section_level || attrs.section_summary;
    } else if (type === 'NORM') {
      return attrs.norm_statement || attrs.applies_if || attrs.exempt_if;
    } else if (type === 'TABLE') {
      return attrs.table_description || attrs.table_content;
    } else if (type === 'LEGAL_DOCUMENT') {
      return attrs.doc_type || attrs.jurisdiction || attrs.document_summary;
    }
    
    // For other types, check if there are any meaningful attributes
    return Object.keys(attrs).length > 1; // More than just 'id'
  }

  // Render detailed information for a node
  renderNodeDetails(container, node, level) {
    const detailsContent = document.createElement('div');
    detailsContent.className = 'tree-node-details bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-600 p-3 ml-8 mt-2';
    
    const type = node.type;
    const extraction = node.extraction;
    const attrs = extraction ? extraction.attributes || {} : {};
    
    // Create details based on node type
    if (type === 'SECTION') {
      this.renderSectionDetails(detailsContent, attrs);
    } else if (type === 'NORM') {
      this.renderNormDetails(detailsContent, attrs, extraction);
    } else if (type === 'TABLE') {
      this.renderTableDetails(detailsContent, attrs);
    } else if (type === 'LEGAL_DOCUMENT') {
      this.renderLegalDocumentDetails(detailsContent, attrs);
    } else {
      this.renderGenericDetails(detailsContent, attrs);
    }
    
    container.appendChild(detailsContent);
  }

  renderSectionDetails(container, attrs) {
    const details = [
      { label: 'Parent Section', value: attrs.parent_section || 'None' },
      { label: 'Section Level', value: attrs.section_level || 'N/A' },
      { label: 'Section Summary', value: attrs.section_summary || 'No summary available' }
    ];
    
    this.renderDetailsList(container, details);
  }

  renderNormDetails(container, attrs, extraction) {
    const details = [
      { label: 'Norm Statement', value: attrs.norm_statement || extraction?.extraction_text || 'No statement available' },
      { label: 'Applies If', value: attrs.applies_if || 'Not specified' },
      { label: 'Satisfied If', value: attrs.satisfied_if || 'Not specified' },
      { label: 'Exempt If', value: attrs.exempt_if || 'Not specified' },
      { label: 'Obligation Type', value: attrs.obligation_type || 'Not specified' },
      { label: 'Paragraph Number', value: attrs.paragraph_number || 'N/A' }
    ];
    
    this.renderDetailsList(container, details);
  }

  renderTableDetails(container, attrs) {
    const details = [
      { label: 'Table Description', value: attrs.table_description || 'No description available' },
      { label: 'Table Content', value: attrs.table_content || 'No content available' }
    ];
    
    this.renderDetailsList(container, details);
  }

  renderLegalDocumentDetails(container, attrs) {
    const details = [
      { label: 'Document Type', value: attrs.doc_type || 'Unknown' },
      { label: 'Jurisdiction', value: attrs.jurisdiction || 'Unknown' },
      { label: 'Document Summary', value: attrs.document_summary || 'No summary available' }
    ];
    
    this.renderDetailsList(container, details);
  }

  renderGenericDetails(container, attrs) {
    // For other types, show all available attributes except 'id'
    const details = [];
    Object.keys(attrs).forEach(key => {
      if (key !== 'id' && attrs[key] !== null && attrs[key] !== undefined) {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const value = typeof attrs[key] === 'object' ? JSON.stringify(attrs[key]) : String(attrs[key]);
        details.push({ label, value });
      }
    });
    
    if (details.length > 0) {
      this.renderDetailsList(container, details);
    } else {
      container.innerHTML = '<div class="text-xs text-gray-500 dark:text-gray-400">No additional details available</div>';
    }
  }

  renderDetailsList(container, details) {
    details.forEach(detail => {
      if (detail.value && detail.value !== 'N/A' && detail.value !== 'Not specified') {
        const detailItem = document.createElement('div');
        detailItem.className = 'detail-item mb-2 last:mb-0';
        
        const label = document.createElement('div');
        label.className = 'detail-label text-xs font-medium text-gray-700 dark:text-gray-300 mb-1';
        label.textContent = detail.label + ':';
        
        const value = document.createElement('div');
        value.className = 'detail-value text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap break-words';
        value.textContent = detail.value;
        value.style.wordBreak = 'break-word';
        
        detailItem.appendChild(label);
        detailItem.appendChild(value);
        container.appendChild(detailItem);
      }
    });
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
    const normalizedData = this.normalizeJsonDataForUberMode(data);
    if (!normalizedData || !normalizedData.extractions) {
      console.log('No extraction data available for filtering');
      return;
    }

    // Get the container where the tree is rendered
    const treeContainer = this.element.querySelector('.document-tree-container, .tree-view-container, .ubermode-container');
    if (!treeContainer) {
      console.log('No tree container found, falling back to full re-render');
      // Fallback to full re-render
      this.element.innerHTML = '';
      this.renderUberMode(normalizedData, { size: 0, truncated: false });
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
      this.renderHierarchicalTree(treeElement, normalizedData);
    } else {
      // Filter active - show flat list of matching items
      this.renderFlatFilteredTree(treeElement, normalizedData, filterType);
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
    
    // Normalize data format first
    const normalizedData = this.normalizeJsonDataForUberMode(data);
    
    // Get all extractions that match the filter
    const filteredExtractions = normalizedData.extractions.filter(ext => 
      ext.extraction_class === filterType
    );

    console.log(`Found ${filteredExtractions.length} items matching filter: ${filterType}`);

    // Group by parent-child relationships within the same type
    const flatItems = this.buildFlatFilteredItems(filteredExtractions, normalizedData, filterType);
    
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
    
    // Format display text based on extraction type - remove IDs
    if (extraction.extraction_class === 'SECTION') {
      // Use section_name if available, otherwise section_title
      displayText = attrs.section_name || attrs.section_title || extraction.extraction_text || 'Untitled Section';
    } else if (extraction.extraction_class === 'NORM') {
      displayText = attrs.norm_statement?.substring(0, 100) || extraction.extraction_text?.substring(0, 100) || 'Norm';
      if ((attrs.norm_statement?.length || extraction.extraction_text?.length || 0) > 100) {
        displayText += '...';
      }
    } else if (extraction.extraction_class === 'TABLE') {
      displayText = attrs.table_title || extraction.extraction_text?.substring(0, 100) || 'Table';
      if ((extraction.extraction_text?.length || 0) > 100) {
        displayText += '...';
      }
    } else if (extraction.extraction_class === 'LEGAL_DOCUMENT') {
      displayText = extraction.extraction_text || attrs.doc_title || attrs.title || 'Legal Document';
    } else {
      displayText = extraction.extraction_text?.substring(0, 100) || extraction.extraction_class || 'Unknown';
      if ((extraction.extraction_text?.length || 0) > 100) {
        displayText += '...';
      }
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
      this.navigateToNode(item.id, extraction);
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
    const normalizedData = this.normalizeJsonDataForUberMode(data);
    if (!normalizedData || !normalizedData.extractions) {
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
      this.renderCompleteJsonView(jsonContainer, normalizedData);
    } else {
      // Filter active - show only matching extractions
      this.renderFlatJsonFilter(jsonContainer, normalizedData, filterType);
    }
  }

  // Render complete JSON view (original logic) with enhanced controls
  renderCompleteJsonView(container, data) {
    console.log('Rendering complete JSON view with controls');
    
    // Clear the entire element to prevent duplication
    this.element.innerHTML = '';
    
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
    
    // Render JSON content with performance optimizations
    if (typeof JSONFormatter !== 'undefined') {
      // Determine appropriate settings based on data size
      const dataSize = JSON.stringify(filteredData).length;
      const maxDepth = dataSize > 100000 ? 2 : 3;
      
      const formatter = new JSONFormatter(filteredData, maxDepth, {
        hoverPreviewEnabled: dataSize < 50000,
        hoverPreviewArrayCount: dataSize < 50000 ? 50 : 10,
        hoverPreviewFieldCount: dataSize < 50000 ? 5 : 3,
        animateOpen: dataSize < 20000,
        animateClose: dataSize < 20000
      });
      
      // Use requestAnimationFrame for non-blocking rendering
      requestAnimationFrame(() => {
        const formatterElement = formatter.render();
        formatterElement.style.padding = '12px';
        contentWrapper.appendChild(formatterElement);
      });
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