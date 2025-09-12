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
    
    // Update overlay dimensions to match canvas
    if (this.highlightOverlay) {
      this.highlightOverlay.style.width = `${viewport.width}px`;
      this.highlightOverlay.style.height = `${viewport.height}px`;
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
    
    if (!positioningData || !positioningData.sections) return;
    
    // Process sections and extract positioning data
    positioningData.sections.forEach(section => {
      if (section.norms) {
        section.norms.forEach(norm => {
          if (norm.positioning) {
            this.addPositionData(norm.norm_id, norm.positioning);
          }
        });
      }
      
      // Also handle direct positioning data on sections
      if (section.positioning) {
        this.addPositionData(section.section_id, section.positioning);
      }
    });
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
  }
  
  /**
   * Highlight elements on the current page
   * @param {Array} elementIds - IDs of elements to highlight
   */
  highlightElements(elementIds) {
    this.clearHighlights();
    
    const pageElements = this.pageData.get(this.currentPage) || [];
    const elementsToHighlight = pageElements.filter(el => 
      elementIds.includes(el.elementId)
    );
    
    elementsToHighlight.forEach(element => {
      this.addHighlight(element.bbox);
    });
    
    // Navigate to page with highlights if not on current page
    if (elementsToHighlight.length === 0) {
      // Find first page with highlighted elements
      for (const [pageNum, elements] of this.pageData) {
        const hasHighlightedElements = elements.some(el => 
          elementIds.includes(el.elementId)
        );
        if (hasHighlightedElements && pageNum !== this.currentPage) {
          this.currentPage = pageNum;
          this.updatePageDisplay();
          this.renderPage(this.currentPage);
          return;
        }
      }
    }
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
      border: 2px solid rgba(255, 200, 0, 0.8);
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
    
    const canvasHeight = this.canvas ? this.canvas.height : 0;
    
    let left = bbox.l * this.scale;
    let right = bbox.r * this.scale;
    let top, bottom;
    
    if (bbox.coord_origin === 'BOTTOMLEFT') {
      // Convert from bottom-left to top-left origin
      bottom = bbox.b * this.scale;
      top = bbox.t * this.scale;
      // Flip Y coordinate
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
    
    return {
      left: Math.min(left, right),
      top: Math.min(top, bottom),
      width: Math.abs(right - left),
      height: Math.abs(bottom - top)
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
  if (!pdfViewer || !runId) return;
  
  // Load PDF file for this run
  const pdfUrl = `/api/runs/${runId}/pdf`;
  pdfViewer.loadPDF(pdfUrl).then(() => {
    // Load positioning data
    fetch(`/api/runs/${runId}/positioning`)
      .then(response => response.json())
      .then(data => {
        pdfViewer.loadPositioningData(data);
        console.log('PDF positioning data loaded');
      })
      .catch(error => {
        console.error('Failed to load positioning data:', error);
      });
  });
};