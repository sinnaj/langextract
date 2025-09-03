/**
 * Comments System UI Integration
 * Handles comment display, creation, editing, and management for the web interface
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
          const errorData = await response.json();
          throw new Error(errorData.error || `Failed to update comment: ${response.statusText}`);
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
          const errorData = await response.json();
          throw new Error(errorData.error || `Failed to delete comment: ${response.statusText}`);
        }
        return await response.json();
      } catch (error) {
        console.error('Error deleting comment:', error);
        throw error;
      }
    }

    static async replyToComment(commentId, replyData) {
      try {
        const response = await fetch(`/api/comments/${commentId}/reply`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(replyData),
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || `Failed to create reply: ${response.statusText}`);
        }
        return await response.json();
      } catch (error) {
        console.error('Error creating reply:', error);
        throw error;
      }
    }
  }

  // Comments UI Manager
  class CommentsUI {
    constructor() {
      this.currentFilePath = null;
      this.comments = [];
      this.currentUser = this.getCurrentUser();
      this.init();
    }

    init() {
      // Initialize comments UI for all preview panels
      this.initializeCommentsPanels();
      this.createCommentModal();
    }

    getCurrentUser() {
      // Get user from localStorage or prompt for it
      let user = localStorage.getItem('langextract_user');
      if (!user) {
        user = prompt('Enter your name for comments:') || 'Anonymous';
        localStorage.setItem('langextract_user', user);
      }
      return user;
    }

    initializeCommentsPanels() {
      // Add comments panels to each preview panel
      const previewPanels = document.querySelectorAll('.preview-panel');
      previewPanels.forEach((panel, index) => {
        this.addCommentsPanel(panel, index);
      });
    }

    addCommentsPanel(previewPanel, panelIndex) {
      const previewDiv = previewPanel.querySelector('.preview');
      if (!previewDiv) return;

      // Create comments toggle button
      const headerDiv = previewPanel.querySelector('.flex.items-center.justify-between');
      if (headerDiv) {
        const commentsToggle = document.createElement('button');
        commentsToggle.className = 'comments-toggle hover:text-gray-700 dark:hover:text-gray-300 px-2 py-1 rounded transition-colors duration-200';
        commentsToggle.title = 'Toggle comments panel';
        commentsToggle.innerHTML = '💬';
        commentsToggle.dataset.panel = panelIndex;
        
        // Add comments count badge
        const commentsBadge = document.createElement('span');
        commentsBadge.className = 'comments-count bg-blue-500 text-white text-xs px-1.5 py-0.5 rounded-full ml-1 hidden';
        commentsBadge.dataset.panel = panelIndex;
        
        commentsToggle.appendChild(commentsBadge);
        
        // Find the actions container (where other buttons are)
        const actionsContainer = headerDiv.querySelector('div.flex.items-center.space-x-2');
        if (actionsContainer) {
          // Insert before the preview stats
          const previewStats = actionsContainer.querySelector('.preview-stats');
          if (previewStats) {
            actionsContainer.insertBefore(commentsToggle, previewStats);
          } else {
            actionsContainer.appendChild(commentsToggle);
          }
        } else {
          // Fallback: just append to header
          headerDiv.appendChild(commentsToggle);
        }

        // Add click handler
        commentsToggle.addEventListener('click', () => {
          this.toggleCommentsPanel(panelIndex);
        });
      }

      // Create comments panel (initially hidden)
      const commentsPanel = document.createElement('div');
      commentsPanel.className = 'comments-panel hidden bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 p-4 max-h-96 overflow-y-auto';
      commentsPanel.dataset.panel = panelIndex;

      // Create comments header
      const commentsHeader = document.createElement('div');
      commentsHeader.className = 'flex items-center justify-between mb-4';
      commentsHeader.innerHTML = `
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Comments</h3>
        <button class="add-comment-btn bg-blue-600 hover:bg-blue-700 text-white text-xs px-2 py-1 rounded" data-panel="${panelIndex}">
          + Add Comment
        </button>
      `;

      // Create comments list
      const commentsList = document.createElement('div');
      commentsList.className = 'comments-list space-y-3';
      commentsList.dataset.panel = panelIndex;

      commentsPanel.appendChild(commentsHeader);
      commentsPanel.appendChild(commentsList);

      // Insert comments panel after preview div - find parent container
      const previewContainer = previewDiv.parentNode;
      if (previewContainer) {
        previewContainer.appendChild(commentsPanel);
      }

      // Add click handler for add comment button
      const addCommentBtn = commentsHeader.querySelector('.add-comment-btn');
      addCommentBtn.addEventListener('click', () => {
        this.showCommentModal(panelIndex);
      });
    }

    toggleCommentsPanel(panelIndex) {
      const commentsPanel = document.querySelector(`.comments-panel[data-panel="${panelIndex}"]`);
      if (!commentsPanel) return;

      if (commentsPanel.classList.contains('hidden')) {
        commentsPanel.classList.remove('hidden');
        // Load comments for current file if not already loaded
        this.loadCommentsForPanel(panelIndex);
      } else {
        commentsPanel.classList.add('hidden');
      }
    }

    async loadCommentsForPanel(panelIndex) {
      // Get current file path for this panel
      const filePath = this.getCurrentFilePathForPanel(panelIndex);
      if (!filePath) {
        console.log(`No file path for panel ${panelIndex}`);
        return;
      }

      try {
        const comments = await CommentsAPI.getComments(filePath);
        this.displayComments(panelIndex, comments);
        this.updateCommentsCount(panelIndex, comments.length);
      } catch (error) {
        console.error('Failed to load comments:', error);
        this.showError(panelIndex, 'Failed to load comments');
      }
    }

    getCurrentFilePathForPanel(panelIndex) {
      // This would need to integrate with the existing file path tracking
      // For now, we'll use a simple approach to get the current file
      // TODO: Integrate with the existing selectedFilePaths array
      if (window.selectedFilePaths && window.selectedFilePaths[panelIndex]) {
        return window.selectedFilePaths[panelIndex];
      }
      return null;
    }

    displayComments(panelIndex, comments) {
      const commentsList = document.querySelector(`.comments-list[data-panel="${panelIndex}"]`);
      if (!commentsList) return;

      if (comments.length === 0) {
        commentsList.innerHTML = '<p class="text-sm text-gray-500 dark:text-gray-400 italic">No comments yet</p>';
        return;
      }

      // Separate root comments and replies
      const rootComments = comments.filter(c => !c.parent_comment_id);
      const replies = comments.filter(c => c.parent_comment_id);

      // Create comment HTML
      let html = '';
      rootComments.forEach(comment => {
        html += this.renderComment(comment, panelIndex);
        
        // Add replies
        const commentReplies = replies.filter(r => r.parent_comment_id === comment.id);
        commentReplies.forEach(reply => {
          html += this.renderComment(reply, panelIndex, true);
        });
      });

      commentsList.innerHTML = html;

      // Attach event listeners
      this.attachCommentEventListeners(panelIndex);
    }

    renderComment(comment, panelIndex, isReply = false) {
      const createdDate = new Date(comment.created_at * 1000).toLocaleString();
      const indentClass = isReply ? 'ml-4 pl-4 border-l-2 border-gray-300 dark:border-gray-600' : '';
      
      return `
        <div class="comment-item bg-white dark:bg-gray-800 rounded-lg p-3 ${indentClass}" data-comment-id="${comment.id}">
          <div class="comment-header flex items-center justify-between mb-2">
            <div class="flex items-center space-x-2">
              <span class="font-medium text-sm text-gray-900 dark:text-gray-100">${this.escapeHtml(comment.author_name)}</span>
              <span class="text-xs text-gray-500 dark:text-gray-400">${createdDate}</span>
            </div>
            <div class="comment-actions flex space-x-1">
              ${!isReply ? `<button class="reply-btn text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400" data-comment-id="${comment.id}" data-panel="${panelIndex}">Reply</button>` : ''}
              <button class="edit-btn text-xs text-green-600 hover:text-green-800 dark:text-green-400" data-comment-id="${comment.id}" data-panel="${panelIndex}">Edit</button>
              <button class="delete-btn text-xs text-red-600 hover:text-red-800 dark:text-red-400" data-comment-id="${comment.id}" data-panel="${panelIndex}">Delete</button>
            </div>
          </div>
          <div class="comment-body text-sm text-gray-700 dark:text-gray-300">${this.escapeHtml(comment.text_body)}</div>
          ${comment.position_data && Object.keys(comment.position_data).length > 0 ? 
            `<div class="comment-position text-xs text-gray-500 dark:text-gray-400 mt-2">📍 ${this.formatPositionData(comment.position_data)}</div>` : ''
          }
        </div>
      `;
    }

    formatPositionData(positionData) {
      if (typeof positionData === 'string') {
        positionData = JSON.parse(positionData);
      }
      
      const parts = [];
      if (positionData.line) parts.push(`Line ${positionData.line}`);
      if (positionData.column) parts.push(`Col ${positionData.column}`);
      if (positionData.path) parts.push(`Path: ${positionData.path}`);
      if (positionData.position) parts.push(`Pos ${positionData.position}`);
      
      return parts.join(', ') || 'General comment';
    }

    attachCommentEventListeners(panelIndex) {
      const commentsList = document.querySelector(`.comments-list[data-panel="${panelIndex}"]`);
      if (!commentsList) return;

      // Reply buttons
      commentsList.querySelectorAll('.reply-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const commentId = parseInt(e.target.dataset.commentId);
          this.showReplyModal(panelIndex, commentId);
        });
      });

      // Edit buttons
      commentsList.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const commentId = parseInt(e.target.dataset.commentId);
          this.editComment(panelIndex, commentId);
        });
      });

      // Delete buttons
      commentsList.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const commentId = parseInt(e.target.dataset.commentId);
          this.deleteComment(panelIndex, commentId);
        });
      });
    }

    updateCommentsCount(panelIndex, count) {
      const countBadge = document.querySelector(`.comments-count[data-panel="${panelIndex}"]`);
      if (!countBadge) return;

      if (count > 0) {
        countBadge.textContent = count;
        countBadge.classList.remove('hidden');
      } else {
        countBadge.classList.add('hidden');
      }
    }

    createCommentModal() {
      // Create modal HTML
      const modal = document.createElement('div');
      modal.id = 'comment-modal';
      modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 hidden flex items-center justify-center';
      modal.innerHTML = `
        <div class="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md mx-4">
          <div class="flex items-center justify-between mb-4">
            <h3 id="comment-modal-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">Add Comment</h3>
            <button id="comment-modal-close" class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
          <form id="comment-form">
            <div class="mb-4">
              <label for="comment-author" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Author</label>
              <input type="text" id="comment-author" class="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" required>
            </div>
            <div class="mb-4">
              <label for="comment-text" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Comment</label>
              <textarea id="comment-text" rows="4" class="w-full border border-gray-300 dark:border-gray-600 rounded px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" required></textarea>
            </div>
            <div class="flex space-x-3">
              <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded flex-1">Save Comment</button>
              <button type="button" id="comment-modal-cancel" class="bg-gray-300 hover:bg-gray-400 text-gray-700 px-4 py-2 rounded flex-1">Cancel</button>
            </div>
          </form>
        </div>
      `;

      document.body.appendChild(modal);

      // Attach event listeners
      const closeBtn = modal.querySelector('#comment-modal-close');
      const cancelBtn = modal.querySelector('#comment-modal-cancel');
      const form = modal.querySelector('#comment-form');

      closeBtn.addEventListener('click', () => this.hideCommentModal());
      cancelBtn.addEventListener('click', () => this.hideCommentModal());
      form.addEventListener('submit', (e) => this.handleCommentSubmit(e));

      // Close on backdrop click
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          this.hideCommentModal();
        }
      });
    }

    showCommentModal(panelIndex, parentCommentId = null) {
      const modal = document.getElementById('comment-modal');
      const title = document.getElementById('comment-modal-title');
      const authorInput = document.getElementById('comment-author');
      const textArea = document.getElementById('comment-text');

      // Set modal title
      title.textContent = parentCommentId ? 'Reply to Comment' : 'Add Comment';

      // Set author from localStorage
      authorInput.value = this.currentUser;

      // Clear comment text
      textArea.value = '';

      // Store panel and parent comment info
      modal.dataset.panel = panelIndex;
      modal.dataset.parentCommentId = parentCommentId || '';

      modal.classList.remove('hidden');
      textArea.focus();
    }

    showReplyModal(panelIndex, parentCommentId) {
      this.showCommentModal(panelIndex, parentCommentId);
    }

    hideCommentModal() {
      const modal = document.getElementById('comment-modal');
      modal.classList.add('hidden');
    }

    async handleCommentSubmit(e) {
      e.preventDefault();
      
      const modal = document.getElementById('comment-modal');
      const panelIndex = parseInt(modal.dataset.panel);
      const parentCommentId = modal.dataset.parentCommentId || null;
      
      const authorInput = document.getElementById('comment-author');
      const textArea = document.getElementById('comment-text');
      
      const author = authorInput.value.trim();
      const text = textArea.value.trim();
      
      if (!author || !text) {
        alert('Please fill in all fields');
        return;
      }

      // Update localStorage user
      this.currentUser = author;
      localStorage.setItem('langextract_user', author);

      const filePath = this.getCurrentFilePathForPanel(panelIndex);
      if (!filePath) {
        alert('No file selected for comments');
        return;
      }

      try {
        const commentData = {
          file_path: filePath,
          author_name: author,
          text_body: text,
          position_data: {}, // TODO: Implement position capture
        };

        if (parentCommentId) {
          commentData.parent_comment_id = parseInt(parentCommentId);
          await CommentsAPI.replyToComment(parentCommentId, {
            author_name: author,
            text_body: text,
          });
        } else {
          await CommentsAPI.createComment(commentData);
        }

        // Reload comments for the panel
        await this.loadCommentsForPanel(panelIndex);
        
        this.hideCommentModal();
      } catch (error) {
        alert(`Failed to ${parentCommentId ? 'reply to' : 'create'} comment: ${error.message}`);
      }
    }

    async editComment(panelIndex, commentId) {
      const commentElement = document.querySelector(`[data-comment-id="${commentId}"]`);
      if (!commentElement) return;

      const commentBody = commentElement.querySelector('.comment-body');
      const currentText = commentBody.textContent;

      const newText = prompt('Edit comment:', currentText);
      if (newText === null || newText.trim() === '') {
        return;
      }

      try {
        await CommentsAPI.updateComment(commentId, newText.trim());
        await this.loadCommentsForPanel(panelIndex);
      } catch (error) {
        alert(`Failed to update comment: ${error.message}`);
      }
    }

    async deleteComment(panelIndex, commentId) {
      if (!confirm('Are you sure you want to delete this comment and all its replies?')) {
        return;
      }

      try {
        await CommentsAPI.deleteComment(commentId);
        await this.loadCommentsForPanel(panelIndex);
      } catch (error) {
        alert(`Failed to delete comment: ${error.message}`);
      }
    }

    showError(panelIndex, message) {
      const commentsList = document.querySelector(`.comments-list[data-panel="${panelIndex}"]`);
      if (commentsList) {
        commentsList.innerHTML = `<p class="text-sm text-red-500 dark:text-red-400">${this.escapeHtml(message)}</p>`;
      }
    }

    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    // Public method to load comments when file changes
    onFileChanged(panelIndex, filePath) {
      if (window.selectedFilePaths) {
        window.selectedFilePaths[panelIndex] = filePath;
      }
      
      // If comments panel is open, reload comments
      const commentsPanel = document.querySelector(`.comments-panel[data-panel="${panelIndex}"]`);
      if (commentsPanel && !commentsPanel.classList.contains('hidden')) {
        this.loadCommentsForPanel(panelIndex);
      }
    }
  }

  // Initialize comments system when DOM is ready
  document.addEventListener('DOMContentLoaded', () => {
    window.commentsUI = new CommentsUI();
  });

  // Expose CommentsUI class for external access
  window.CommentsUI = CommentsUI;
  window.CommentsAPI = CommentsAPI;

})();