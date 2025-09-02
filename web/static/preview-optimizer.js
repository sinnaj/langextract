/**
 * Preview Performance Optimizer  
 * Handles large file previews efficiently with progressive loading and virtualization
 */
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
    
    this.init();
  }
  
  init() {
    this.element.style.position = 'relative';
    this.element.style.overflow = 'auto';
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
      const pretty = JSON.stringify(obj, null, 2);

      // Check if UBERMODE is enabled
      if (this.uberMode) {
        this.renderUberMode(obj, meta);
        return;
      }

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

  renderEnhancedJsonObject(obj, meta) {
    // Use JSONFormatter directly on parsed object
    try {
  const formatter = new JSONFormatter(obj, Number.POSITIVE_INFINITY, { theme: 'dark' });
      const container = document.createElement('div');
      container.className = 'json-viewer bg-gray-50 dark:bg-gray-900 rounded-lg p-2 overflow-auto';
      container.appendChild(formatter.render());
      this.element.appendChild(container);
    } catch (e) {
      // Fallback: pretty print
      const pretty = JSON.stringify(obj, null, 2);
      this.renderEnhancedJson(pretty, meta);
    }
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
  toggleUberMode() {
    this.uberMode = !this.uberMode;
    
    // Update stats visibility
    this.updateStatsVisibility();
    
    // Re-render current content if available
    if (this.currentJsonData) {
      if (this.uberMode) {
        this.renderUberMode(this.currentJsonData, { size: 0, truncated: false });
      } else {
        // Re-render with normal JSON view
        const pretty = JSON.stringify(this.currentJsonData, null, 2);
        if (typeof JSONFormatter !== 'undefined') {
          this.renderEnhancedJsonObject(this.currentJsonData, { size: 0, truncated: false });
        } else {
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
    
    // Update stat values in the DOM
    const updateStat = (className, value) => {
      const el = document.querySelector(`.${className}`);
      if (el) {
        el.textContent = value;
      }
    };
    
    updateStat('stats-total-items', this.formatNumber(stats.totalItems));
    updateStat('stats-norms', this.formatNumber(stats.norms));
    updateStat('stats-tags', this.formatNumber(stats.tags));
    updateStat('stats-parameters', this.formatNumber(stats.parameters));
    updateStat('stats-questions', this.formatNumber(stats.questions));
    updateStat('stats-locations', this.formatNumber(stats.locations));
    updateStat('stats-quality', stats.quality || '—');
  }

  analyzeJsonData(data) {
    const stats = {
      totalItems: 0,
      norms: 0,
      tags: 0,
      parameters: 0,
      questions: 0,
      locations: 0,
      quality: '—'
    };
    
    // Handle extraction format
    if (data && data.extractions && Array.isArray(data.extractions)) {
      data.extractions.forEach(extraction => {
        if (extraction.norms) stats.norms += Array.isArray(extraction.norms) ? extraction.norms.length : 0;
        if (extraction.tags) stats.tags += Array.isArray(extraction.tags) ? extraction.tags.length : 0;
        if (extraction.parameters) stats.parameters += Array.isArray(extraction.parameters) ? extraction.parameters.length : 0;
        if (extraction.questions) stats.questions += Array.isArray(extraction.questions) ? extraction.questions.length : 0;
        if (extraction.locations) stats.locations += Array.isArray(extraction.locations) ? extraction.locations.length : 0;
        
        // Quality indicators
        if (extraction.quality) {
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
      
      stats.totalItems = stats.norms + stats.tags + stats.parameters + stats.questions + stats.locations;
    }
    
    // Handle direct collections format
    if (data && data.collections) {
      const collections = data.collections;
      Object.keys(collections).forEach(key => {
        const collection = collections[key];
        if (Array.isArray(collection)) {
          switch (key) {
            case 'norms': stats.norms = collection.length; break;
            case 'tags': stats.tags = collection.length; break;
            case 'parameters': stats.parameters = collection.length; break;
            case 'questions': stats.questions = collection.length; break;
            case 'locations': stats.locations = collection.length; break;
          }
        }
      });
      stats.totalItems = stats.norms + stats.tags + stats.parameters + stats.questions + stats.locations;
    }
    
    return stats;
  }

  createTreeVisualization(data) {
    const container = document.createElement('div');
    container.className = 'tree-visualization bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4';
    
    const title = document.createElement('h3');
    title.className = 'text-lg font-semibold mb-4 text-gray-800 dark:text-gray-200';
    title.textContent = '🌳 Document Structure';
    container.appendChild(title);
    
    const tree = document.createElement('div');
    tree.className = 'tree-content space-y-2';
    
    this.renderTreeNode(tree, data, '', 0);
    
    container.appendChild(tree);
    return container;
  }

  renderTreeNode(container, data, key, level) {
    if (level > 5) return; // Prevent excessive nesting
    
    const indent = level * 20;
    const node = document.createElement('div');
    node.className = `tree-node flex items-start space-x-2 py-1 px-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded transition-colors`;
    node.style.marginLeft = `${indent}px`;
    
    // Create expand/collapse indicator
    const indicator = document.createElement('span');
    indicator.className = 'tree-indicator text-gray-400 cursor-pointer select-none w-4 text-center';
    
    // Node content
    const content = document.createElement('div');
    content.className = 'tree-content flex-1';
    
    if (Array.isArray(data)) {
      // Array node
      indicator.textContent = level === 0 ? '' : '▼';
      content.innerHTML = `
        <span class="node-key font-medium text-blue-600 dark:text-blue-400">${key || 'Array'}</span>
        <span class="node-type text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 px-2 py-1 rounded-full ml-2">${data.length} items</span>
      `;
      
      // Add sample items
      if (level < 3) {
        data.slice(0, 5).forEach((item, index) => {
          this.renderTreeNode(container, item, `[${index}]`, level + 1);
        });
        
        if (data.length > 5) {
          const more = document.createElement('div');
          more.className = 'text-gray-500 text-sm';
          more.style.marginLeft = `${(level + 1) * 20 + 20}px`;
          more.textContent = `... and ${data.length - 5} more items`;
          container.appendChild(more);
        }
      }
      
    } else if (data && typeof data === 'object') {
      // Object node
      const keys = Object.keys(data);
      indicator.textContent = level === 0 ? '' : '▼';
      
      // Determine object type and color
      let objectType = 'Object';
      let typeClass = 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300';
      
      if (data.statement_text) {
        objectType = 'Norm';
        typeClass = 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200';
      } else if (data.tag_path) {
        objectType = 'Tag';
        typeClass = 'bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200';
      } else if (data.parameter_name) {
        objectType = 'Parameter';
        typeClass = 'bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-200';
      } else if (data.question_text) {
        objectType = 'Question';
        typeClass = 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200';
      }
      
      content.innerHTML = `
        <span class="node-key font-medium text-gray-800 dark:text-gray-200">${key || objectType}</span>
        <span class="node-type text-xs ${typeClass} px-2 py-1 rounded-full ml-2">${objectType}</span>
        ${keys.length > 0 ? `<span class="node-count text-xs text-gray-500 ml-2">${keys.length} fields</span>` : ''}
      `;
      
      // Add summary if available
      if (data.statement_text) {
        const summary = document.createElement('div');
        summary.className = 'text-sm text-gray-600 dark:text-gray-400 mt-1 truncate';
        summary.textContent = data.statement_text.substring(0, 100) + (data.statement_text.length > 100 ? '...' : '');
        content.appendChild(summary);
      }
      
      // Render important fields
      if (level < 3) {
        const importantFields = ['id', 'statement_text', 'tag_path', 'parameter_name', 'question_text', 'location_name'];
        keys.forEach(k => {
          if (importantFields.includes(k) || keys.length <= 5) {
            this.renderTreeNode(container, data[k], k, level + 1);
          }
        });
        
        if (keys.length > 5) {
          const more = document.createElement('div');
          more.className = 'text-gray-500 text-sm';
          more.style.marginLeft = `${(level + 1) * 20 + 20}px`;
          more.textContent = `... and ${keys.length - 5} more fields`;
          container.appendChild(more);
        }
      }
      
    } else {
      // Primitive value
      indicator.textContent = '';
      const valueText = String(data).substring(0, 100);
      const truncated = String(data).length > 100;
      content.innerHTML = `
        <span class="node-key font-medium text-gray-600 dark:text-gray-400">${key}:</span>
        <span class="node-value text-gray-800 dark:text-gray-200 ml-2">${this.escapeHtml(valueText)}${truncated ? '...' : ''}</span>
      `;
    }
    
    node.appendChild(indicator);
    node.appendChild(content);
    container.appendChild(node);
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
}