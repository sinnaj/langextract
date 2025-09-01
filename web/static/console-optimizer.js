/**
 * Console Performance Optimizer
 * Handles large console outputs efficiently using virtual scrolling and buffering
 */
class ConsoleOptimizer {
  constructor(element, options = {}) {
    this.element = element;
    this.options = {
      maxLines: options.maxLines || 10000,
      chunkSize: options.chunkSize || 100,
      debounceMs: options.debounceMs || 16, // ~60fps
      autoScroll: options.autoScroll !== false,
      ...options
    };
    
    this.lines = [];
    this.displayStartIndex = 0;
    this.displayEndIndex = 0;
    this.isAutoScrolling = true;
    this.scrollTimeout = null;
    this.updateTimeout = null;
    this.lineHeight = null;
    
    this.init();
  }
  
  init() {
    // Set up the container structure
    this.element.innerHTML = '';
    this.element.style.position = 'relative';
    this.element.style.overflow = 'auto';
    
    // Create virtual container
    this.virtualContainer = document.createElement('div');
    this.virtualContainer.style.position = 'absolute';
    this.virtualContainer.style.top = '0';
    this.virtualContainer.style.left = '0';
    this.virtualContainer.style.right = '0';
    this.element.appendChild(this.virtualContainer);
    
    // Create viewport
    this.viewport = document.createElement('div');
    this.viewport.style.position = 'relative';
    this.viewport.style.fontFamily = 'monospace';
    this.viewport.style.fontSize = '14px';
    this.viewport.style.lineHeight = '1.4';
    this.viewport.style.whiteSpace = 'pre-wrap';
    this.virtualContainer.appendChild(this.viewport);
    
    // Measure line height
    this.measureLineHeight();
    
    // Set up event listeners
    this.element.addEventListener('scroll', this.handleScroll.bind(this));
    
    // Initial render
    this.updateDisplay();
  }
  
  measureLineHeight() {
    const testLine = document.createElement('div');
    testLine.textContent = 'Test line';
    testLine.style.fontFamily = this.viewport.style.fontFamily;
    testLine.style.fontSize = this.viewport.style.fontSize;
    testLine.style.lineHeight = this.viewport.style.lineHeight;
    testLine.style.position = 'absolute';
    testLine.style.visibility = 'hidden';
    document.body.appendChild(testLine);
    
    this.lineHeight = testLine.offsetHeight;
    document.body.removeChild(testLine);
    
    if (this.lineHeight <= 0) {
      this.lineHeight = 20; // fallback
    }
  }
  
  handleScroll() {
    // Check if user has scrolled away from bottom
    const scrollTop = this.element.scrollTop;
    const scrollHeight = this.element.scrollHeight;
    const clientHeight = this.element.clientHeight;
    
    this.isAutoScrolling = (scrollTop + clientHeight >= scrollHeight - 10);
    
    // Debounced display update
    if (this.scrollTimeout) {
      clearTimeout(this.scrollTimeout);
    }
    this.scrollTimeout = setTimeout(() => {
      this.updateDisplay();
    }, this.options.debounceMs);
  }
  
  appendLine(line) {
    this.lines.push(line);
    
    // Trim buffer if needed
    if (this.lines.length > this.options.maxLines) {
      const excess = this.lines.length - this.options.maxLines;
      this.lines.splice(0, excess);
    }
    
    // Schedule display update
    this.scheduleUpdate();
  }
  
  appendLines(lines) {
    this.lines.push(...lines);
    
    // Trim buffer if needed
    if (this.lines.length > this.options.maxLines) {
      const excess = this.lines.length - this.options.maxLines;
      this.lines.splice(0, excess);
    }
    
    this.scheduleUpdate();
  }
  
  scheduleUpdate() {
    if (this.updateTimeout) {
      clearTimeout(this.updateTimeout);
    }
    this.updateTimeout = setTimeout(() => {
      this.updateDisplay();
      if (this.isAutoScrolling) {
        this.scrollToBottom();
      }
    }, this.options.debounceMs);
  }
  
  updateDisplay() {
    if (this.lines.length === 0) {
      this.viewport.innerHTML = '';
      this.virtualContainer.style.height = '0px';
      return;
    }
    
    const containerHeight = this.element.clientHeight;
    const scrollTop = this.element.scrollTop;
    
    // Calculate visible range with buffer
    const visibleLines = Math.ceil(containerHeight / this.lineHeight);
    const bufferLines = Math.ceil(visibleLines * 0.5); // 50% buffer
    
    this.displayStartIndex = Math.max(0, 
      Math.floor(scrollTop / this.lineHeight) - bufferLines
    );
    this.displayEndIndex = Math.min(this.lines.length,
      this.displayStartIndex + visibleLines + (bufferLines * 2)
    );
    
    // Update virtual container height
    this.virtualContainer.style.height = `${this.lines.length * this.lineHeight}px`;
    
    // Render visible lines
    this.renderLines();
  }
  
  renderLines() {
    const fragment = document.createDocumentFragment();
    
    // Clear viewport
    this.viewport.innerHTML = '';
    
    // Position viewport
    this.viewport.style.transform = `translateY(${this.displayStartIndex * this.lineHeight}px)`;
    
    // Render visible lines
    for (let i = this.displayStartIndex; i < this.displayEndIndex; i++) {
      const lineDiv = document.createElement('div');
      lineDiv.textContent = this.lines[i];
      lineDiv.style.height = `${this.lineHeight}px`;
      fragment.appendChild(lineDiv);
    }
    
    this.viewport.appendChild(fragment);
  }
  
  scrollToBottom() {
    this.element.scrollTop = this.element.scrollHeight;
  }
  
  clear() {
    this.lines = [];
    this.updateDisplay();
  }
  
  setMaxLines(maxLines) {
    this.options.maxLines = maxLines;
    
    // Trim if needed
    if (this.lines.length > maxLines) {
      const excess = this.lines.length - maxLines;
      this.lines.splice(0, excess);
      this.updateDisplay();
    }
  }
  
  getStats() {
    return {
      totalLines: this.lines.length,
      displayedLines: this.displayEndIndex - this.displayStartIndex,
      maxLines: this.options.maxLines,
      isAutoScrolling: this.isAutoScrolling,
      lineHeight: this.lineHeight
    };
  }
  
  search(query) {
    if (!query) return [];
    
    const results = [];
    const lowerQuery = query.toLowerCase();
    
    this.lines.forEach((line, index) => {
      if (line.toLowerCase().includes(lowerQuery)) {
        results.push({
          lineIndex: index,
          line: line,
          preview: line.length > 100 ? line.substring(0, 100) + '...' : line
        });
      }
    });
    
    return results;
  }
  
  scrollToLine(lineIndex) {
    if (lineIndex < 0 || lineIndex >= this.lines.length) return;
    
    const targetScrollTop = lineIndex * this.lineHeight;
    this.element.scrollTop = targetScrollTop;
    this.isAutoScrolling = false;
  }
}