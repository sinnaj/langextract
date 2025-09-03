/**
 * Hover-based Comments System for Web File Viewer
 * Provides position-aware commenting with overlay UI and inline editing
 */

(() => {
  'use strict';

  // Comments API client
  class CommentsAPI {
    static async getComments(filePath) {
      try {
        const response = await fetch(`/api/comments?file_path=${encodeURIComponent(filePath)}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch comments: ${response.statusText}`);
        }
        const data = await response.json();
        return data.comments || [];
      } catch (error) {
        console.error('Error fetching comments:', error);
        return [];
      }
    }

    static async createComment(commentData) {
      try {
        const response = await fetch('/api/comments', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(commentData),
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Failed to create comment: ${response.statusText}`);
        }
        return await response.json();
      } catch (error) {
        console.error('Error creating comment:', error);
        throw error;
      }
    }

    static async updateComment(commentId, textBody) {
      try {
        const response = await fetch(`/api/comments/${commentId}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text_body: textBody }),
        });
        if (!response.ok) {
          throw new Error(`Failed to update comment: ${response.statusText}`);
        }
        return await response.json();
      } catch (error) {
        console.error('Error updating comment:', error);
        throw error;
      }
    }

    static async deleteComment(commentId) {
      try {
        const response = await fetch(`/api/comments/${commentId}`, {
          method: 'DELETE',
        });
        if (!response.ok) {
          throw new Error(`Failed to delete comment: ${response.statusText}`);
        }
      } catch (error) {
        console.error('Error deleting comment:', error);
        throw error;
      }
    }
  }

  // Position-aware Comment Manager
  class HoverCommentsUI {
    constructor() {
      this.currentFilePath = null;
      this.comments = [];
      this.currentUser = this.getCurrentUser();
      this.activeOverlay = null;
      this.hoverIndicators = new Map(); // Map panel -> indicators
      this.hoverTimeout = null; // Debounce hover events
      this.activeIndicator = null; // Currently shown indicator
      this.lastHoverTime = 0; // Cooldown tracking
      this.hoverCooldown = 150; // Minimum time between indicator changes (ms)
      this.init();
    }

    init() {
      this.injectStyles();
      this.setupHoverListeners();
    }

    getCurrentUser() {
      let user = localStorage.getItem('langextract_user');
      if (!user) {
        user = this.promptForUserName();
      }
      return user;
    }

    promptForUserName() {
      const user = prompt('Please enter your name for comments:');
      if (!user || user.trim() === '') {
        alert('A name is required to create comments.');
        return this.promptForUserName(); // Recursively prompt until valid name is provided
      }
      const trimmedUser = user.trim();
      localStorage.setItem('langextract_user', trimmedUser);
      return trimmedUser;
    }

    ensureUserName() {
      if (!this.currentUser || this.currentUser.trim() === '') {
        this.currentUser = this.promptForUserName();
      }
      return this.currentUser;
    }

    injectStyles() {
      // Add CSS for hover indicators and overlays
      const style = document.createElement('style');
      style.textContent = `
        .comment-hover-indicator {
          position: absolute;
          left: -25px;
          top: 50%;
          transform: translateY(-50%);
          width: 16px;
          height: 16px;
          background: #3b82f6;
          color: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 10px;
          cursor: pointer;
          opacity: 0;
          transition: opacity 0.3s ease, transform 0.2s ease;
          z-index: 1000;
          will-change: opacity, transform;
        }
        
        .comment-hover-indicator.show {
          opacity: 0.7;
          transform: translateY(-50%) scale(1);
        }
        
        .comment-hover-indicator:hover {
          opacity: 1 !important;
          background: #2563eb;
          transform: translateY(-50%) scale(1.1);
        }
        
        .comment-hover-area {
          position: relative;
        }
        
        .comment-hover-area:hover .comment-hover-indicator {
          /* Remove automatic opacity on hover - we'll control it manually */
        }
        
        .comment-overlay {
          position: absolute;
          background: white;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
          padding: 12px;
          min-width: 300px;
          max-width: 400px;
          z-index: 1001;
          font-size: 14px;
        }
        
        .dark .comment-overlay {
          background: #374151;
          border-color: #4b5563;
          color: white;
        }
        
        .comment-overlay .comment-header {
          display: flex;
          justify-content: between;
          align-items: center;
          margin-bottom: 8px;
          font-size: 12px;
          color: #6b7280;
        }
        
        .dark .comment-overlay .comment-header {
          color: #9ca3af;
        }
        
        .comment-user-info {
          font-size: 12px;
          color: #6b7280;
          border-bottom: 1px solid #e5e7eb;
          padding-bottom: 8px;
          margin-bottom: 8px;
        }
        
        .dark .comment-user-info {
          color: #9ca3af;
          border-color: #4b5563;
        }
        
        .comment-textarea {
          width: 100%;
          min-height: 60px;
          padding: 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          resize: vertical;
          font-size: 13px;
        }
        
        .dark .comment-textarea {
          background: #1f2937;
          border-color: #4b5563;
          color: white;
        }
        
        .comment-actions {
          display: flex;
          gap: 8px;
          margin-top: 8px;
          justify-content: flex-end;
        }
        
        .comment-btn {
          padding: 4px 12px;
          font-size: 12px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          transition: background-color 0.2s ease;
        }
        
        .comment-btn-primary {
          background: #3b82f6;
          color: white;
        }
        
        .comment-btn-primary:hover {
          background: #2563eb;
        }
        
        .comment-btn-secondary {
          background: #e5e7eb;
          color: #374151;
        }
        
        .comment-btn-secondary:hover {
          background: #d1d5db;
        }
        
        .dark .comment-btn-secondary {
          background: #4b5563;
          color: #d1d5db;
        }
        
        .dark .comment-btn-secondary:hover {
          background: #6b7280;
        }
        
        .existing-comment {
          background: #f8fafc;
          padding: 8px;
          border-radius: 4px;
          margin-bottom: 8px;
          border-left: 3px solid #3b82f6;
        }
        
        .dark .existing-comment {
          background: #1f2937;
        }
        
        .comment-author {
          font-weight: 600;
          font-size: 12px;
          color: #374151;
          margin-bottom: 4px;
        }
        
        .dark .comment-author {
          color: #d1d5db;
        }
        
        .comment-text {
          font-size: 13px;
          line-height: 1.4;
          color: #4b5563;
        }
        
        .dark .comment-text {
          color: #9ca3af;
        }
        
        .comment-position {
          font-size: 10px;
          color: #9ca3af;
          margin-top: 4px;
        }
        
        .has-comments .comment-hover-indicator {
          background: #10b981;
          opacity: 1;
        }
        
        .has-comments .comment-hover-indicator.show {
          opacity: 1;
        }
        
        .has-comments .comment-hover-indicator:hover {
          background: #059669;
          transform: translateY(-50%) scale(1.1);
        }
      `;
      document.head.appendChild(style);
    }

    setupHoverListeners() {
      // Set up mutation observer to watch for new preview content
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.type === 'childList') {
            mutation.addedNodes.forEach((node) => {
              if (node.nodeType === Node.ELEMENT_NODE) {
                const previewElements = node.classList?.contains('preview') ? [node] : 
                                       node.querySelectorAll?.('.preview') || [];
                previewElements.forEach(preview => this.setupPreviewHover(preview));
              }
            });
          }
        });
      });
      
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });

      // Setup existing preview elements
      document.querySelectorAll('.preview').forEach(preview => {
        this.setupPreviewHover(preview);
      });

      // Close overlay when clicking outside
      document.addEventListener('click', (e) => {
        if (this.activeOverlay && !this.activeOverlay.contains(e.target) && 
            !e.target.classList.contains('comment-hover-indicator')) {
          this.closeOverlay();
        }
      });
    }

    setupPreviewHover(previewElement) {
      // Clear any existing hover setup
      this.clearPreviewHover(previewElement);
      
      // Get panel index
      const panel = previewElement.closest('.preview-panel');
      const panelIndex = panel ? parseInt(panel.dataset.panel || '0') : 0;

      previewElement.addEventListener('mouseover', (e) => {
        this.handlePreviewHover(e, previewElement, panelIndex);
      });

      previewElement.addEventListener('mouseleave', (e) => {
        this.handlePreviewLeave(e, previewElement, panelIndex);
      });
    }

    clearPreviewHover(previewElement) {
      // Remove existing hover indicators
      const indicators = previewElement.querySelectorAll('.comment-hover-indicator');
      indicators.forEach(indicator => indicator.remove());
      
      // Remove hover area classes
      const hoverAreas = previewElement.querySelectorAll('.comment-hover-area');
      hoverAreas.forEach(area => area.classList.remove('comment-hover-area'));
    }

    handlePreviewHover(e, previewElement, panelIndex) {
      const target = e.target;
      if (!target || target === previewElement) return;

      // Implement cooldown to prevent too many rapid changes
      const now = Date.now();
      if (now - this.lastHoverTime < this.hoverCooldown) {
        return;
      }

      // Clear any existing timeout
      if (this.hoverTimeout) {
        clearTimeout(this.hoverTimeout);
      }

      // Debounce the hover to avoid creating indicators too rapidly
      this.hoverTimeout = setTimeout(() => {
        this.processHoverTarget(target, previewElement, panelIndex);
        this.lastHoverTime = Date.now();
      }, 50); // 50ms debounce
    }

    processHoverTarget(target, previewElement, panelIndex) {
      // Hide any currently active indicator first
      this.hideActiveIndicator();

      // Determine content type and position strategy
      const contentType = this.detectContentType(previewElement);
      const position = this.calculatePosition(target, contentType, previewElement);
      
      if (position) {
        this.showHoverIndicator(target, position, panelIndex);
      }
    }

    handlePreviewLeave(e, previewElement, panelIndex) {
      // Clear any pending hover timeout
      if (this.hoverTimeout) {
        clearTimeout(this.hoverTimeout);
        this.hoverTimeout = null;
      }

      // Hide active indicator with delay to allow interaction
      setTimeout(() => {
        if (!previewElement.matches(':hover') && !this.isOverlayActive()) {
          this.hideActiveIndicator();
        }
      }, 200); // Longer delay for smoother experience
    }

    hideActiveIndicator() {
      if (this.activeIndicator) {
        this.activeIndicator.classList.remove('show');
        // Remove the indicator after transition completes
        setTimeout(() => {
          if (this.activeIndicator && this.activeIndicator.parentElement && 
              !this.activeIndicator.classList.contains('show')) {
            this.activeIndicator.remove();
            this.activeIndicator.parentElement?.classList.remove('comment-hover-area');
            this.activeIndicator = null;
          }
        }, 300); // Match CSS transition duration
      }
    }

    isOverlayActive() {
      return this.activeOverlay && document.body.contains(this.activeOverlay);
    }

    detectContentType(previewElement) {
      // Detect content type from preview element structure
      if (previewElement.querySelector('.json-formatter-row')) return 'json';
      if (previewElement.querySelector('pre code')) return 'code';
      if (previewElement.querySelector('img')) return 'image';
      if (previewElement.querySelector('.markdown-body')) return 'markdown';
      return 'text';
    }

    calculatePosition(element, contentType, previewElement) {
      const rect = element.getBoundingClientRect();
      const previewRect = previewElement.getBoundingClientRect();
      
      switch (contentType) {
        case 'json':
          return this.calculateJSONPosition(element, previewElement);
        case 'code':
          return this.calculateCodePosition(element, previewElement);
        case 'image':
          return this.calculateImagePosition(element, previewElement);
        default:
          return this.calculateTextPosition(element, previewElement);
      }
    }

    calculateJSONPosition(element, previewElement) {
      // For JSON, try to identify the node path and line position
      const jsonRow = element.closest('.json-formatter-row');
      if (!jsonRow) return null;

      const key = jsonRow.querySelector('.json-formatter-key');
      const path = this.buildJSONPath(jsonRow);
      
      return {
        type: 'json_node',
        path: path,
        line: this.getElementLine(element, previewElement),
        display: path ? `JSON: ${path}` : 'JSON node'
      };
    }

    calculateCodePosition(element, previewElement) {
      // For code, calculate line and character position
      const line = this.getElementLine(element, previewElement);
      return {
        type: 'code_line',
        line: line,
        char: 0, // Could be enhanced with character position
        display: `Line ${line}`
      };
    }

    calculateImagePosition(element, previewElement) {
      // For images, use coordinates
      const rect = element.getBoundingClientRect();
      const previewRect = previewElement.getBoundingClientRect();
      
      return {
        type: 'image_coords',
        x: Math.round(rect.left - previewRect.left),
        y: Math.round(rect.top - previewRect.top),
        display: `Coords (${Math.round(rect.left - previewRect.left)}, ${Math.round(rect.top - previewRect.top)})`
      };
    }

    calculateTextPosition(element, previewElement) {
      // For text, try to calculate line position
      const line = this.getElementLine(element, previewElement);
      return {
        type: 'text_line',
        line: line,
        display: `Line ${line || 'N/A'}`
      };
    }

    getElementLine(element, container) {
      // Try to calculate line number based on element position
      const allElements = Array.from(container.querySelectorAll('*'));
      const elementIndex = allElements.indexOf(element);
      
      // This is a rough approximation - could be improved per content type
      return Math.max(1, Math.floor(elementIndex / 3) + 1);
    }

    buildJSONPath(jsonRow) {
      // Build JSON path by traversing up the hierarchy
      const path = [];
      let current = jsonRow;
      
      while (current && current.classList.contains('json-formatter-row')) {
        const key = current.querySelector('.json-formatter-key');
        if (key) {
          path.unshift(key.textContent.replace(/[":]/g, ''));
        }
        current = current.parentElement?.closest('.json-formatter-row');
      }
      
      return path.length > 0 ? path.join('.') : null;
    }

    showHoverIndicator(element, position, panelIndex) {
      // Make element a hover area if it isn't already
      if (!element.classList.contains('comment-hover-area')) {
        element.classList.add('comment-hover-area');
      }

      // Check if this element already has an indicator
      let indicator = element.querySelector('.comment-hover-indicator');
      if (indicator) {
        // Just make sure it's visible and set as active
        indicator.classList.add('show');
        this.activeIndicator = indicator;
        return;
      }

      // Create new hover indicator
      indicator = document.createElement('div');
      indicator.className = 'comment-hover-indicator';
      indicator.innerHTML = '💬';
      indicator.title = `Add comment to ${position.display}`;
      
      // Check if there are existing comments at this position
      const existingComments = this.getCommentsAtPosition(position);
      if (existingComments.length > 0) {
        element.classList.add('has-comments');
        indicator.title = `${existingComments.length} comment(s) at ${position.display}`;
      }

      // Position indicator
      element.style.position = 'relative';
      element.appendChild(indicator);

      // Add click handler
      indicator.addEventListener('click', (e) => {
        e.stopPropagation();
        this.showCommentOverlay(element, position, panelIndex, existingComments);
      });

      // Set as active and show with animation
      this.activeIndicator = indicator;
      // Use requestAnimationFrame to ensure the element is in the DOM before adding the class
      requestAnimationFrame(() => {
        indicator.classList.add('show');
      });
    }

    hideHoverIndicators(panelIndex) {
      // Hide indicators for specific panel or all if panelIndex is undefined
      const selector = panelIndex !== undefined ? 
        `.preview-panel[data-panel="${panelIndex}"] .comment-hover-indicator` : 
        '.comment-hover-indicator';
      
      document.querySelectorAll(selector).forEach(indicator => {
        if (!indicator.closest('.has-comments')) {
          indicator.remove();
          indicator.parentElement?.classList.remove('comment-hover-area');
        }
      });
    }

    getCommentsAtPosition(position) {
      // Filter comments that match this position
      return this.comments.filter(comment => {
        if (!comment.position_data) return false;
        
        try {
          const commentPos = JSON.parse(comment.position_data);
          return this.positionsMatch(position, commentPos);
        } catch {
          return false;
        }
      });
    }

    positionsMatch(pos1, pos2) {
      if (pos1.type !== pos2.type) return false;
      
      switch (pos1.type) {
        case 'json_node':
          return pos1.path === pos2.path;
        case 'code_line':
        case 'text_line':
          return pos1.line === pos2.line;
        case 'image_coords':
          return Math.abs(pos1.x - pos2.x) < 10 && Math.abs(pos1.y - pos2.y) < 10;
        default:
          return false;
      }
    }

    showCommentOverlay(element, position, panelIndex, existingComments = []) {
      // Close any existing overlay
      this.closeOverlay();

      const overlay = document.createElement('div');
      overlay.className = 'comment-overlay';
      
      // Position overlay near the element
      const rect = element.getBoundingClientRect();
      overlay.style.position = 'fixed';
      overlay.style.left = Math.min(rect.right + 10, window.innerWidth - 420) + 'px';
      overlay.style.top = Math.max(rect.top, 10) + 'px';

      // Build overlay content
      let overlayHTML = `
        <div class="comment-header">
          <span>📍 ${position.display}</span>
        </div>
      `;

      // Show existing comments
      if (existingComments.length > 0) {
        overlayHTML += existingComments.map(comment => `
          <div class="existing-comment" data-comment-id="${comment.id}">
            <div class="comment-author">${this.escapeHTML(comment.author)}</div>
            <div class="comment-text">${this.escapeHTML(comment.text_body)}</div>
            <div class="comment-position">${new Date(comment.created_at).toLocaleString()}</div>
            <div class="comment-actions" style="margin-top: 8px;">
              <button class="comment-btn comment-btn-secondary edit-comment-btn" data-comment-id="${comment.id}">Edit</button>
              <button class="comment-btn comment-btn-secondary delete-comment-btn" data-comment-id="${comment.id}">Delete</button>
            </div>
          </div>
        `).join('');
      }

      // Add new comment form
      overlayHTML += `
        <div class="new-comment-form">
          <div class="comment-user-info" style="display: flex; justify-content: between; align-items: center; margin-bottom: 8px; font-size: 12px; color: #6b7280;">
            <span>Commenting as: <strong>${this.escapeHTML(this.currentUser || 'Unknown')}</strong></span>
            <button class="comment-btn comment-btn-secondary change-user-btn" style="padding: 2px 6px; font-size: 11px; margin-left: 8px;">Change</button>
          </div>
          <textarea class="comment-textarea" placeholder="Add a comment..."></textarea>
          <div class="comment-actions">
            <button class="comment-btn comment-btn-secondary cancel-comment-btn">Cancel</button>
            <button class="comment-btn comment-btn-primary save-comment-btn">Save</button>
          </div>
        </div>
      `;

      overlay.innerHTML = overlayHTML;
      document.body.appendChild(overlay);
      this.activeOverlay = overlay;

      // Focus textarea
      const textarea = overlay.querySelector('.comment-textarea');
      textarea?.focus();

      // Add event handlers
      this.setupOverlayHandlers(overlay, position, panelIndex);
    }

    setupOverlayHandlers(overlay, position, panelIndex) {
      // Save comment
      overlay.querySelector('.save-comment-btn')?.addEventListener('click', async () => {
        const textarea = overlay.querySelector('.comment-textarea');
        const text = textarea.value.trim();
        
        if (!text) return;

        try {
          await this.saveComment(text, position, panelIndex);
          this.closeOverlay();
          await this.refreshComments(panelIndex);
        } catch (error) {
          alert('Error saving comment: ' + error.message);
        }
      });

      // Cancel
      overlay.querySelector('.cancel-comment-btn')?.addEventListener('click', () => {
        this.closeOverlay();
      });

      // Change user
      overlay.querySelector('.change-user-btn')?.addEventListener('click', () => {
        const newUser = this.promptForUserName();
        if (newUser) {
          this.currentUser = newUser;
          // Update the display
          const userInfo = overlay.querySelector('.comment-user-info span');
          if (userInfo) {
            userInfo.innerHTML = `Commenting as: <strong>${this.escapeHTML(newUser)}</strong>`;
          }
        }
      });

      // Edit buttons
      overlay.querySelectorAll('.edit-comment-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const commentId = e.target.dataset.commentId;
          this.editComment(commentId, overlay);
        });
      });

      // Delete buttons
      overlay.querySelectorAll('.delete-comment-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
          const commentId = e.target.dataset.commentId;
          if (confirm('Delete this comment?')) {
            try {
              await CommentsAPI.deleteComment(commentId);
              this.closeOverlay();
              await this.refreshComments(panelIndex);
            } catch (error) {
              alert('Error deleting comment: ' + error.message);
            }
          }
        });
      });

      // Enter to save (Ctrl+Enter)
      overlay.querySelector('.comment-textarea')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
          overlay.querySelector('.save-comment-btn')?.click();
        }
      });
    }

    async saveComment(text, position, panelIndex) {
      if (!this.currentFilePath) {
        throw new Error('No file selected');
      }

      // Ensure we have a valid user name before proceeding
      const userName = this.ensureUserName();
      if (!userName) {
        throw new Error('User name is required to create comments');
      }

      const commentData = {
        file_path: this.currentFilePath,
        text_body: text,
        author: userName,
        position_data: JSON.stringify(position)
      };

      await CommentsAPI.createComment(commentData);
    }

    editComment(commentId, overlay) {
      const commentElement = overlay.querySelector(`[data-comment-id="${commentId}"]`);
      const textElement = commentElement.querySelector('.comment-text');
      const currentText = textElement.textContent;

      // Replace with textarea
      const textarea = document.createElement('textarea');
      textarea.className = 'comment-textarea';
      textarea.value = currentText;
      textarea.style.minHeight = '40px';
      
      textElement.replaceWith(textarea);
      textarea.focus();

      // Update actions
      const actions = commentElement.querySelector('.comment-actions');
      actions.innerHTML = `
        <button class="comment-btn comment-btn-secondary cancel-edit-btn">Cancel</button>
        <button class="comment-btn comment-btn-primary save-edit-btn">Save</button>
      `;

      // Cancel edit
      actions.querySelector('.cancel-edit-btn').addEventListener('click', () => {
        textarea.replaceWith(textElement);
        actions.innerHTML = `
          <button class="comment-btn comment-btn-secondary edit-comment-btn" data-comment-id="${commentId}">Edit</button>
          <button class="comment-btn comment-btn-secondary delete-comment-btn" data-comment-id="${commentId}">Delete</button>
        `;
        this.setupOverlayHandlers(overlay, null, null);
      });

      // Save edit
      actions.querySelector('.save-edit-btn').addEventListener('click', async () => {
        const newText = textarea.value.trim();
        if (!newText) return;

        try {
          await CommentsAPI.updateComment(commentId, newText);
          textElement.textContent = newText;
          textarea.replaceWith(textElement);
          actions.innerHTML = `
            <button class="comment-btn comment-btn-secondary edit-comment-btn" data-comment-id="${commentId}">Edit</button>
            <button class="comment-btn comment-btn-secondary delete-comment-btn" data-comment-id="${commentId}">Delete</button>
          `;
          this.setupOverlayHandlers(overlay, null, null);
        } catch (error) {
          alert('Error updating comment: ' + error.message);
        }
      });
    }

    closeOverlay() {
      if (this.activeOverlay) {
        this.activeOverlay.remove();
        this.activeOverlay = null;
      }
    }

    async refreshComments(panelIndex) {
      if (this.currentFilePath) {
        this.comments = await CommentsAPI.getComments(this.currentFilePath);
        // Update hover indicators to show comment states
        this.updateCommentIndicators();
      }
    }

    updateCommentIndicators() {
      // Update all hover indicators to show if they have comments
      document.querySelectorAll('.comment-hover-area').forEach(area => {
        const indicator = area.querySelector('.comment-hover-indicator');
        if (indicator) {
          // Recalculate position and check for comments
          // This is a simplified version - full implementation would recalculate positions
          area.classList.toggle('has-comments', Math.random() < 0.3); // Placeholder
        }
      });
    }

    // Public API for integration with app.js
    onFileChanged(panelIndex, filePath) {
      this.currentFilePath = filePath;
      this.refreshComments(panelIndex);
      
      // Clear existing hover areas in this panel
      const panel = document.querySelector(`.preview-panel[data-panel="${panelIndex}"]`);
      if (panel) {
        const preview = panel.querySelector('.preview');
        if (preview) {
          this.clearPreviewHover(preview);
        }
      }
    }

    escapeHTML(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  }

  // Initialize the hover comments system
  document.addEventListener('DOMContentLoaded', () => {
    window.hoverCommentsUI = new HoverCommentsUI();
    
    // Provide compatibility with existing API
    window.commentsUI = {
      onFileChanged: (panelIndex, filePath) => {
        window.hoverCommentsUI.onFileChanged(panelIndex, filePath);
      }
    };
  });

})();