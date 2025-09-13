/**
 * PDF Viewer functionality for highlighting extracted content
 * Integrates with the enhanced_lx_runner positioning data
 */

class PDFViewer {
  constructor() {
    this.pdfDoc = null;
    this.currentPage = 1;
    this.scale = 1.0;
    this.canvas = document.getElementById('pdf-canvas');
    this.ctx = this.canvas?.getContext('2d');
    this.highlightOverlay = document.querySelector('.pdf-highlight-overlay');
    this.currentHighlights = [];
    this.pageData = new Map(); // Store positioning data by page
    
    this.initializeControls();
  }
  
  initializeControls() {
    // PDF navigation controls
    const zoomInBtn = document.querySelector('.pdf-zoom-in');
    const zoomOutBtn = document.querySelector('.pdf-zoom-out');
    const prevPageBtn = document.querySelector('.pdf-prev-page');
    const nextPageBtn = document.querySelector('.pdf-next-page');
    
    if (zoomInBtn) zoomInBtn.addEventListener('click', () => this.zoomIn());
    if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => this.zoomOut());
    if (prevPageBtn) prevPageBtn.addEventListener('click', () => this.previousPage());
    if (nextPageBtn) nextPageBtn.addEventListener('click', () => this.nextPage());
  }
  
  async loadPDF(pdfUrl) {
    if (!pdfjsLib) {
      console.error('PDF.js library not loaded');
      return;
    }
    
    this.showLoading(true);
    
    try {
      this.pdfDoc = await pdfjsLib.getDocument(pdfUrl).promise;
      this.currentPage = 1;
      this.updatePageDisplay();
      await this.renderPage(this.currentPage);
      this.updateStatus('PDF Loaded');
      
      console.log(`PDF loaded with ${this.pdfDoc.numPages} pages`);
    } catch (error) {
      console.error('Error loading PDF:', error);
      this.updateStatus('PDF Load Error');
    } finally {
      this.showLoading(false);
    }
  }
  
  async renderPage(pageNum) {
    if (!this.pdfDoc || !this.canvas || !this.ctx) return;
    
    const page = await this.pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: this.scale });
    
    // Set canvas dimensions
    this.canvas.height = viewport.height;
    this.canvas.width = viewport.width;
    
    // Update overlay dimensions and position to match canvas exactly
    if (this.highlightOverlay) {
      // Make sure the overlay is positioned to match the canvas
      this.updateOverlayPosition();
    }
    
    // Render PDF page
    const renderContext = {
      canvasContext: this.ctx,
      viewport: viewport
    };
    
    await page.render(renderContext).promise;
    
    // Re-apply highlights for this page
    this.redrawHighlights();
  }
  
  zoomIn() {
    this.scale *= 1.2;
    this.updateZoomDisplay();
    this.renderPage(this.currentPage);
  }
  
  zoomOut() {
    this.scale /= 1.2;
    this.updateZoomDisplay();
    this.renderPage(this.currentPage);
  }
  
  nextPage() {
    if (this.pdfDoc && this.currentPage < this.pdfDoc.numPages) {
      this.currentPage++;
      this.updatePageDisplay();
      this.renderPage(this.currentPage);
    }
  }
  
  previousPage() {
    if (this.pdfDoc && this.currentPage > 1) {
      this.currentPage--;
      this.updatePageDisplay();
      this.renderPage(this.currentPage);
    }
  }
  
  updateZoomDisplay() {
    const zoomDisplay = document.querySelector('.pdf-zoom-display');
    if (zoomDisplay) {
      zoomDisplay.textContent = `${Math.round(this.scale * 100)}%`;
    }
  }
  
  /**
   * Update the highlight overlay position and size to match the canvas exactly
   */
  updateOverlayPosition() {
    if (!this.canvas || !this.highlightOverlay) return;
    
    // Get canvas position relative to the viewport
    const canvasRect = this.canvas.getBoundingClientRect();
    const containerRect = this.highlightOverlay.parentElement.getBoundingClientRect();
    
    // Calculate position relative to container
    const offsetLeft = canvasRect.left - containerRect.left;
    const offsetTop = canvasRect.top - containerRect.top;
    
    // Position overlay to match canvas exactly
    this.highlightOverlay.style.left = `${offsetLeft}px`;
    this.highlightOverlay.style.top = `${offsetTop}px`;
    this.highlightOverlay.style.width = `${this.canvas.width}px`;
    this.highlightOverlay.style.height = `${this.canvas.height}px`;
    this.highlightOverlay.style.transform = 'none'; // Remove any existing transforms
    
    console.log(`Overlay positioned at: left=${offsetLeft}px, top=${offsetTop}px, size=${this.canvas.width}x${this.canvas.height}px`);
    console.log(`Canvas rect:`, canvasRect);
    console.log(`Container rect:`, containerRect);
  }
  
  updatePageDisplay() {
    const currentPageEl = document.querySelector('.pdf-current-page');
    const totalPagesEl = document.querySelector('.pdf-total-pages');
    
    if (currentPageEl) currentPageEl.textContent = this.currentPage;
    if (totalPagesEl && this.pdfDoc) {
      totalPagesEl.textContent = this.pdfDoc.numPages;
    }
  }
  
  updateStatus(status) {
    const statusEl = document.querySelector('.pdf-status');
    if (statusEl) statusEl.textContent = status;
  }
  
  showLoading(show) {
    const loadingEl = document.querySelector('.pdf-loading');
    if (loadingEl) {
      if (show) {
        loadingEl.classList.remove('hidden');
      } else {
        loadingEl.classList.add('hidden');
      }
    }
  }
  
  /**
   * Load positioning data from enhanced_lx_runner output
   * @param {Object} positioningData - Data containing bounding boxes and page info
   */
  loadPositioningData(positioningData) {
    this.pageData.clear();
    this.extractionData = new Map(); // Store extraction mapping
    
    if (!positioningData || !positioningData.sections) {
      console.warn('No positioning data or sections provided');
      return;
    }
    
    console.log(`Loading positioning data for ${positioningData.sections.length} sections`);
    
    // Process sections and extract positioning data
    positioningData.sections.forEach((section, sectionIndex) => {
      console.log(`Processing section ${sectionIndex}: ${section.section_id}`);
      
      // Handle section positioning
      if (section.positioning) {
        console.log(`Adding section positioning for ${section.section_id}:`, section.positioning);
        this.addPositionData(section.section_id, section.positioning);
      } else {
        console.log(`No positioning data for section ${section.section_id}`);
      }
      
      // Handle norm positioning within sections
      if (section.norms && section.norms.length > 0) {
        console.log(`Processing ${section.norms.length} norms in section ${section.section_id}`);
        section.norms.forEach((norm, normIndex) => {
          if (norm.positioning) {
            console.log(`Adding norm positioning for ${norm.norm_id}:`, norm.positioning);
            this.addPositionData(norm.norm_id, norm.positioning);
          } else {
            console.log(`No positioning data for norm ${norm.norm_id}`);
          }
        });
      }
    });
    
    console.log(`Positioning data loaded - pages: ${Array.from(this.pageData.keys()).join(', ')}`);
    console.log(`Total elements with positioning: ${Array.from(this.pageData.values()).reduce((sum, arr) => sum + arr.length, 0)}`);
  }
  
  addPositionData(elementId, positioning) {
    if (!positioning || !positioning.page_no) return;
    
    const pageNum = positioning.page_no;
    if (!this.pageData.has(pageNum)) {
      this.pageData.set(pageNum, []);
    }
    
    this.pageData.get(pageNum).push({
      elementId: elementId,
      bbox: positioning.bbox,
      charspan: positioning.charspan
    });
    
    // Store in extraction data map for easy lookup
    if (!this.extractionData) {
      this.extractionData = new Map();
    }
    this.extractionData.set(elementId, positioning);
  }
  
  /**
   * Highlight elements on PDF based on extraction IDs
   * @param {Array|String} elementIds - IDs of elements to highlight
   */
  highlightElements(elementIds) {
    this.clearHighlights();
    
    if (!elementIds) {
      console.log('No elementIds provided to highlightElements');
      return;
    }
    
    // Normalize to array
    if (typeof elementIds === 'string') {
      elementIds = [elementIds];
    }
    
    console.log(`Highlighting elements: ${elementIds.join(', ')}`);
    console.log(`Available pages in pageData: ${Array.from(this.pageData.keys()).join(', ')}`);
    console.log(`Total elements in positioning data: ${Array.from(this.pageData.values()).reduce((sum, arr) => sum + arr.length, 0)}`);
    
    // Debug: show what element IDs are available
    const availableElementIds = [];
    for (const [pageNum, elements] of this.pageData) {
      elements.forEach(el => availableElementIds.push(el.elementId));
    }
    console.log(`Available element IDs: ${availableElementIds.slice(0, 5).join(', ')}${availableElementIds.length > 5 ? '...' : ''} (total: ${availableElementIds.length})`);
    
    let targetPage = null;
    const elementsToHighlight = [];
    
    // Find all elements to highlight across all pages
    for (const [pageNum, elements] of this.pageData) {
      const pageElements = elements.filter(el => 
        elementIds.includes(el.elementId)
      );
      
      if (pageElements.length > 0) {
        if (targetPage === null) {
          targetPage = pageNum; // Use first page found
        }
        elementsToHighlight.push(...pageElements.map(el => ({...el, pageNum})));
      }
    }
    
    console.log(`Found ${elementsToHighlight.length} elements to highlight`);
    
    // Show visual feedback in PDF viewer status
    this.showHighlightStatus(elementIds, elementsToHighlight.length, targetPage);
    
    // Navigate to target page if needed
    if (targetPage !== null && targetPage !== this.currentPage) {
      this.currentPage = targetPage;
      this.updatePageDisplay();
      this.renderPage(this.currentPage).then(() => {
        // Add highlights after page is rendered
        this.addHighlightsForPage(this.currentPage, elementIds);
      });
    } else {
      // Add highlights for current page
      this.addHighlightsForPage(this.currentPage, elementIds);
    }
  }

  // Show visual feedback about highlighting status
  showHighlightStatus(elementIds, foundCount, targetPage) {
    const statusElement = document.querySelector('.pdf-status');
    if (statusElement) {
      const elementText = elementIds.length === 1 ? 'element' : 'elements';
      const foundText = foundCount > 0 ? `Found ${foundCount} positioning data` : 'No positioning data found';
      const pageText = targetPage !== null ? ` on page ${targetPage}` : '';
      
      // Create highlighting indicator
      statusElement.innerHTML = `
        <div class="highlighting-status bg-yellow-100 text-yellow-800 px-3 py-2 rounded-md text-sm flex items-center space-x-2">
          <span class="animate-pulse text-yellow-600">●</span>
          <span>Highlighting ${elementIds.length} ${elementText} - ${foundText}${pageText}</span>
        </div>
      `;
      
      // Clear the status after 3 seconds
      setTimeout(() => {
        if (statusElement && statusElement.querySelector('.highlighting-status')) {
          statusElement.innerHTML = 'No PDF';
        }
      }, 3000);
    }
  }

  addHighlightsForPage(pageNum, elementIds) {
    const pageElements = this.pageData.get(pageNum) || [];
    const elementsToHighlight = pageElements.filter(el => 
      elementIds.includes(el.elementId)
    );
    
    elementsToHighlight.forEach(element => {
      if (element.bbox) {
        this.addHighlight(element.bbox);
        console.log(`Added highlight for ${element.elementId} on page ${pageNum}`);
      }
    });
  }
  
  addHighlight(bbox) {
    if (!bbox || !this.highlightOverlay) return;
    
    // Convert PDF coordinates to canvas coordinates
    const canvasBox = this.convertPDFToCanvasCoords(bbox);
    
    // Create highlight rectangle
    const highlight = document.createElement('div');
    highlight.className = 'pdf-highlight';
    highlight.style.cssText = `
      position: absolute;
      left: ${canvasBox.left}px;
      top: ${canvasBox.top}px;
      width: ${canvasBox.width}px;
      height: ${canvasBox.height}px;
      background-color: rgba(255, 255, 0, 0.3);
      border: 1px solid rgba(255, 255, 0, 0.5);
      pointer-events: none;
      border-radius: 2px;
      z-index: 10;
    `;
    
    this.highlightOverlay.appendChild(highlight);
    this.currentHighlights.push(highlight);
  }
  
  convertPDFToCanvasCoords(bbox) {
    // Convert from PDF coordinate system to canvas coordinates
    // PDF uses BOTTOMLEFT origin, canvas uses TOPLEFT
    // bbox: { l, t, r, b, coord_origin }
    
    if (!this.canvas) return { left: 0, top: 0, width: 0, height: 0 };
    
    const canvasHeight = this.canvas.height;
    const canvasWidth = this.canvas.width;
    
    let left = bbox.l * this.scale;
    let right = bbox.r * this.scale;
    let top, bottom;
    
    if (bbox.coord_origin === 'BOTTOMLEFT') {
      // Convert from bottom-left to top-left origin
      bottom = bbox.b * this.scale;
      top = bbox.t * this.scale;
      // Flip Y coordinate for top-left origin
      top = canvasHeight - top;
      bottom = canvasHeight - bottom;
      // Ensure top < bottom for canvas coordinates
      if (top > bottom) {
        [top, bottom] = [bottom, top];
      }
    } else {
      // Assume top-left origin
      top = bbox.t * this.scale;
      bottom = bbox.b * this.scale;
    }
    
    // Get the canvas wrapper padding to account for centering
    const canvasWrapper = this.canvas.parentElement;
    let offsetLeft = 0;
    let offsetTop = 0;
    
    if (canvasWrapper) {
      const wrapperStyle = window.getComputedStyle(canvasWrapper);
      const wrapperPadding = parseInt(wrapperStyle.paddingLeft) || 0;
      const wrapperRect = canvasWrapper.getBoundingClientRect();
      const canvasRect = this.canvas.getBoundingClientRect();
      
      // Calculate offset due to centering within wrapper
      offsetLeft = canvasRect.left - wrapperRect.left;
      offsetTop = canvasRect.top - wrapperRect.top;
    }
    
    const result = {
      left: Math.min(left, right) + offsetLeft,
      top: Math.min(top, bottom) + offsetTop,
      width: Math.abs(right - left),
      height: Math.abs(bottom - top)
    };
    
    console.log(`PDF coord conversion:`, {
      bbox,
      canvasSize: `${canvasWidth}x${canvasHeight}`,
      scale: this.scale,
      offset: `${offsetLeft}px,${offsetTop}px`,
      result
    });
    
    return result;
  }
  
  /**
   * Get the canvas offset relative to the PDF viewer container
   * to account for wrapper padding and centering when positioning highlights
   */
  getCanvasOffset() {
    if (!this.canvas || !this.highlightOverlay) {
      return { left: 0, top: 0 };
    }
    
    // Get the canvas position relative to the container
    const canvasRect = this.canvas.getBoundingClientRect();
    const containerRect = this.highlightOverlay.parentElement.getBoundingClientRect();
    
    // Calculate the offset
    const offsetLeft = canvasRect.left - containerRect.left;
    const offsetTop = canvasRect.top - containerRect.top;
    
    console.log(`Canvas offset calculated: left=${offsetLeft}px, top=${offsetTop}px`);
    
    return {
      left: offsetLeft,
      top: offsetTop
    };
  }

  clearHighlights() {
    this.currentHighlights.forEach(highlight => {
      if (highlight.parentNode) {
        highlight.parentNode.removeChild(highlight);
      }
    });
    this.currentHighlights = [];
  }
  
  redrawHighlights() {
    // Store current highlight element IDs
    const highlightedIds = [];
    // This would need to be tracked when highlights are added
    // For now, just clear and let the tree selection re-highlight
    this.clearHighlights();
  }
}

// Global PDF viewer instance
let pdfViewer = null;

// Initialize PDF viewer when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('pdf-canvas')) {
    pdfViewer = new PDFViewer();
    window.pdfViewer = pdfViewer; // Make globally accessible
  }
});

// Global function for tree view integration
window.highlightPDFElements = function(elementIds) {
  if (pdfViewer && elementIds && elementIds.length > 0) {
    pdfViewer.highlightElements(elementIds);
  }
};

window.initializePDFViewer = function(runId) {
  console.log('initializePDFViewer called with runId:', runId);
  console.log('pdfViewer exists:', !!pdfViewer);
  
  if (!pdfViewer) {
    console.log('PDF viewer not available, waiting for initialization...');
    // Try again after a short delay
    setTimeout(() => {
      if (pdfViewer) {
        console.log('PDF viewer now available, retrying initialization');
        window.initializePDFViewer(runId);
      } else {
        console.error('PDF viewer still not available after delay');
      }
    }, 500);
    return;
  }
  
  if (!runId) {
    console.log('PDF viewer runId not provided for initialization');
    return;
  }
  
  console.log(`Initializing PDF viewer for run: ${runId}`);
  
  // Load PDF file for this run
  const pdfUrl = `/api/runs/${runId}/pdf`;
  const positioningUrl = `/api/runs/${runId}/positioning`;
  
  console.log(`Loading positioning data from: ${positioningUrl}`);
  console.log(`Loading PDF from: ${pdfUrl}`);
  
  // First load positioning data, then PDF
  fetch(positioningUrl)
    .then(response => {
      console.log(`Positioning API response status: ${response.status}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    })
    .then(data => {
      console.log('Positioning data received:', data);
      console.log('Number of sections in positioning data:', data?.sections?.length || 0);
      pdfViewer.loadPositioningData(data);
      console.log('PDF positioning data loaded successfully');
      
      // Try to load PDF after positioning data is loaded
      console.log(`Now loading PDF from: ${pdfUrl}`);
      return pdfViewer.loadPDF(pdfUrl);
    })
    .then(() => {
      console.log('PDF loaded successfully');
    })
    .catch(error => {
      console.error('Failed to initialize PDF viewer:', error);
      console.error('Error details:', {
        runId: runId,
        positioningUrl: positioningUrl,
        pdfUrl: pdfUrl,
        pdfViewerExists: !!pdfViewer
      });
      
      // Even if positioning data fails, try to load PDF
      if (error.message.includes('positioning') || error.message.includes('404')) {
        console.log('Attempting to load PDF without positioning data');
        pdfViewer.loadPDF(pdfUrl).catch(pdfError => {
          console.error('PDF loading also failed:', pdfError);
        });
      }
    });
};