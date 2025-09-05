/**
 * Simplified Tree-based Comments System for Web File Viewer
 * Provides tree item-based commenting with simple UI interactions
 */

(() => {
  'use strict';

  // Comments API client
  class CommentsAPI {
    static async getComments(filePath, treeItem = null) {
      try {
        let url = `/api/comments?file_path=${encodeURIComponent(filePath)}`;
        if (treeItem) {
          url += `&tree_item=${encodeURIComponent(treeItem)}`;
        }
        const response = await fetch(url);
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
          throw new Error(errorData.error || `Failed to reply to comment: ${response.statusText}`);
        }
        return await response.json();
      } catch (error) {
        console.error('Error replying to comment:', error);
        throw error;
      }
    }
  }

  // Simplified Tree Comments UI Manager
  class TreeCommentsUI {
    constructor() {
      this.currentFilePath = null;
      this.currentUser = this.getCurrentUser();
      this.activePanel = null;
      this.commentsData = new Map(); // treeItem -> comments
      this.init();
    }

    init() {
      this.injectStyles();
      console.log('TreeCommentsUI initialized');
    }

    getCurrentUser() {
      let user = localStorage.getItem('langextract_user');
      if (!user) {
        user = this.promptForUserName();
      }
      return user;
    }

    promptForUserName() {
      const name = prompt('Please enter your name for commenting:');
      if (name && name.trim()) {
        localStorage.setItem('langextract_user', name.trim());
        return name.trim();
      }
      return 'Anonymous';
    }

    ensureUserName() {
      if (!this.currentUser || this.currentUser === 'Anonymous') {
        this.currentUser = this.promptForUserName();
      }
      return this.currentUser;
    }

    injectStyles() {
      // Add CSS for comment indicators and panels
      const style = document.createElement('style');
      style.textContent = `
        .tree-comment-indicator {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          margin-left: 8px;
          border-radius: 50%;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.2s ease;
          vertical-align: middle;
        }
        
        .tree-comment-indicator.no-comments {
          background: #3b82f6;
          color: white;
        }
        
        .tree-comment-indicator.has-comments {
          background: #22c55e;
          color: white;
        }
        
        .tree-comment-indicator:hover {
          transform: scale(1.1);
        }
        
        .tree-comment-count {
          font-size: 10px;
          font-weight: bold;
        }
        
        .comment-panel {
          position: fixed;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          background: white;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
          z-index: 1000;
          max-width: 600px;
          width: 90vw;
          max-height: 80vh;
          overflow-y: auto;
          padding: 0;
        }
        
        .dark .comment-panel {
          background: #1f2937;
          border-color: #374151;
          color: #f9fafb;
        }
        
        .comment-panel-header {
          padding: 16px;
          border-bottom: 1px solid #e5e7eb;
          background: #f9fafb;
          display: flex;
          justify-content: between;
          align-items: center;
        }
        
        .dark .comment-panel-header {
          background: #111827;
          border-bottom-color: #374151;
        }
        
        .comment-panel-title {
          font-weight: 600;
          font-size: 16px;
          flex: 1;
        }
        
        .comment-panel-close {
          background: none;
          border: none;
          font-size: 18px;
          cursor: pointer;
          padding: 4px;
          color: #6b7280;
        }
        
        .comment-panel-close:hover {
          color: #374151;
        }
        
        .comment-panel-body {
          padding: 16px;
        }
        
        .comment-item {
          margin-bottom: 16px;
          padding: 12px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          background: #f9fafb;
        }
        
        .dark .comment-item {
          background: #111827;
          border-color: #374151;
        }
        
        .comment-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
          font-size: 12px;
          color: #6b7280;
        }
        
        .comment-author {
          font-weight: 600;
          color: #374151;
        }
        
        .dark .comment-author {
          color: #f9fafb;
        }
        
        .comment-text {
          margin-bottom: 8px;
          line-height: 1.5;
        }
        
        .comment-actions {
          display: flex;
          gap: 8px;
          font-size: 12px;
        }
        
        .comment-btn {
          background: none;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          padding: 4px 8px;
          cursor: pointer;
          font-size: 12px;
          transition: all 0.2s ease;
        }
        
        .comment-btn:hover {
          background: #f3f4f6;
        }
        
        .comment-btn-primary {
          background: #3b82f6;
          color: white;
          border-color: #3b82f6;
        }
        
        .comment-btn-primary:hover {
          background: #2563eb;
        }
        
        .comment-btn-danger {
          background: #ef4444;
          color: white;
          border-color: #ef4444;
        }
        
        .comment-btn-danger:hover {
          background: #dc2626;
        }
        
        .comment-reply {
          margin-left: 20px;
          margin-top: 8px;
          padding-left: 12px;
          border-left: 2px solid #e5e7eb;
        }
        
        .comment-form {
          margin-top: 16px;
          padding: 16px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          background: white;
        }
        
        .dark .comment-form {
          background: #1f2937;
          border-color: #374151;
        }
        
        .comment-textarea {
          width: 100%;
          min-height: 80px;
          padding: 8px;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          resize: vertical;
          font-family: inherit;
          margin-bottom: 8px;
        }
        
        .dark .comment-textarea {
          background: #111827;
          color: #f9fafb;
          border-color: #374151;
        }
        
        .comment-form-actions {
          display: flex;
          gap: 8px;
          justify-content: flex-end;
        }
        
        .comment-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.5);
          z-index: 999;
        }
      `;
      document.head.appendChild(style);
    }

    // Initialize comments for a file
    async initializeForFile(filePath) {
      this.currentFilePath = filePath;
      console.log('TreeCommentsUI: Initializing comments for file:', filePath);
      
      // Load all comments for the file
      try {
        const allComments = await CommentsAPI.getComments(filePath);
        this.commentsData.clear();
        
        console.log(`TreeCommentsUI: Loaded ${allComments.length} comments from API for file:`, filePath);
        
        // Group comments by tree_item
        for (const comment of allComments) {
          const treeItem = comment.tree_item;
          if (!this.commentsData.has(treeItem)) {
            this.commentsData.set(treeItem, []);
          }
          this.commentsData.get(treeItem).push(comment);
        }
        
        console.log('TreeCommentsUI: Grouped comments data by tree item:', this.commentsData);
        console.log('TreeCommentsUI: Number of tree items with comments:', this.commentsData.size);
        
        // Update tree indicators
        this.updateTreeIndicators();
      } catch (error) {
        console.error('TreeCommentsUI: Failed to load comments:', error);
      }
    }

    // Update comment indicators in the tree
    updateTreeIndicators() {
      // Find all tree nodes and add comment indicators
      const treeNodes = document.querySelectorAll('[data-extraction-id], [data-node-id]');
      console.log(`TreeCommentsUI: Found ${treeNodes.length} tree nodes for comment indicators`);
      
      if (treeNodes.length === 0) {
        console.warn('TreeCommentsUI: No tree nodes found with data-extraction-id or data-node-id attributes');
        console.log('TreeCommentsUI: Available elements in DOM:', document.querySelectorAll('[data-extraction-id]').length, 'with data-extraction-id,', document.querySelectorAll('[data-node-id]').length, 'with data-node-id');
      }
      
      for (const node of treeNodes) {
        const treeItem = node.dataset.extractionId || node.dataset.nodeId;
        if (!treeItem) {
          console.warn('TreeCommentsUI: Tree node found but no treeItem extracted:', node);
          continue;
        }
        
        console.log(`TreeCommentsUI: Processing tree item: ${treeItem}`);
        
        // Remove existing indicator
        const existingIndicator = node.querySelector('.tree-comment-indicator');
        if (existingIndicator) {
          existingIndicator.remove();
        }
        
        // Create new indicator
        const indicator = document.createElement('span');
        indicator.className = 'tree-comment-indicator';
        indicator.dataset.treeItem = treeItem;
        
        const comments = this.commentsData.get(treeItem) || [];
        const totalComments = this.countTotalComments(comments);
        
        if (totalComments > 0) {
          indicator.classList.add('has-comments');
          indicator.innerHTML = `<span class="tree-comment-count">${totalComments}</span>`;
          indicator.title = `${totalComments} comment(s)`;
          console.log(`TreeCommentsUI: Added indicator for ${treeItem} with ${totalComments} comments`);
        } else {
          indicator.classList.add('no-comments');
          indicator.innerHTML = '💬';
          indicator.title = 'Add comment';
          console.log(`TreeCommentsUI: Added indicator for ${treeItem} with no comments`);
        }
        
        // Add click handler
        indicator.addEventListener('click', (e) => {
          e.stopPropagation();
          this.showCommentsPanel(treeItem);
        });
        
        // Add indicator to the node
        const nodeContent = node.querySelector('.tree-node-content') || node;
        nodeContent.appendChild(indicator);
      }
      
      console.log(`TreeCommentsUI: Finished updating ${treeNodes.length} tree indicators`);
    }

    countTotalComments(comments) {
      let total = 0;
      for (const comment of comments) {
        total += 1;
        if (comment.replies) {
          total += comment.replies.length;
        }
      }
      return total;
    }

    // Show comments panel for a tree item
    async showCommentsPanel(treeItem) {
      this.closeActivePanel();
      
      // Get comments for this tree item
      const comments = await CommentsAPI.getComments(this.currentFilePath, treeItem);
      
      // Create overlay
      const overlay = document.createElement('div');
      overlay.className = 'comment-overlay';
      overlay.addEventListener('click', () => this.closeActivePanel());
      
      // Create panel
      const panel = document.createElement('div');
      panel.className = 'comment-panel';
      panel.addEventListener('click', (e) => e.stopPropagation());
      
      // Panel header
      const header = document.createElement('div');
      header.className = 'comment-panel-header';
      header.innerHTML = `
        <div class="comment-panel-title">Comments for ${this.escapeHTML(treeItem)}</div>
        <button class="comment-panel-close">&times;</button>
      `;
      
      header.querySelector('.comment-panel-close').addEventListener('click', () => {
        this.closeActivePanel();
      });
      
      // Panel body
      const body = document.createElement('div');
      body.className = 'comment-panel-body';
      
      // Render existing comments
      if (comments.length > 0) {
        for (const comment of comments) {
          body.appendChild(this.renderComment(comment, treeItem));
        }
      } else {
        body.innerHTML = '<p style="color: #6b7280; text-align: center; margin: 20px 0;">No comments yet. Be the first to comment!</p>';
      }
      
      // Add comment form
      body.appendChild(this.createCommentForm(treeItem));
      
      panel.appendChild(header);
      panel.appendChild(body);
      overlay.appendChild(panel);
      
      document.body.appendChild(overlay);
      this.activePanel = overlay;
    }

    renderComment(comment, treeItem) {
      const commentEl = document.createElement('div');
      commentEl.className = 'comment-item';
      commentEl.dataset.commentId = comment.id;
      
      const date = new Date(comment.created_at * 1000).toLocaleDateString();
      
      commentEl.innerHTML = `
        <div class="comment-header">
          <span class="comment-author">${this.escapeHTML(comment.author_name)}</span>
          <span>${date}</span>
        </div>
        <div class="comment-text" data-original-text="${this.escapeHTML(comment.text_body)}">${this.escapeHTML(comment.text_body)}</div>
        <div class="comment-actions">
          <button class="comment-btn reply-btn">Reply</button>
          <button class="comment-btn edit-btn">Edit</button>
          <button class="comment-btn comment-btn-danger delete-btn">Delete</button>
        </div>
      `;
      
      // Add event listeners
      commentEl.querySelector('.reply-btn').addEventListener('click', () => {
        this.showReplyForm(comment, commentEl, treeItem);
      });
      
      commentEl.querySelector('.edit-btn').addEventListener('click', () => {
        this.editComment(comment, commentEl);
      });
      
      commentEl.querySelector('.delete-btn').addEventListener('click', () => {
        this.deleteComment(comment, treeItem);
      });
      
      // Render replies
      if (comment.replies && comment.replies.length > 0) {
        for (const reply of comment.replies) {
          const replyEl = this.renderComment(reply, treeItem);
          replyEl.classList.add('comment-reply');
          commentEl.appendChild(replyEl);
        }
      }
      
      return commentEl;
    }

    createCommentForm(treeItem, parentCommentId = null) {
      const form = document.createElement('div');
      form.className = 'comment-form';
      
      const isReply = parentCommentId !== null;
      const title = isReply ? 'Add Reply' : 'Add Comment';
      
      form.innerHTML = `
        <h4 style="margin: 0 0 12px 0; font-size: 14px; font-weight: 600;">${title}</h4>
        <textarea class="comment-textarea" placeholder="Write your ${isReply ? 'reply' : 'comment'}..."></textarea>
        <div class="comment-form-actions">
          <button class="comment-btn cancel-btn">Cancel</button>
          <button class="comment-btn comment-btn-primary submit-btn">Submit</button>
        </div>
      `;
      
      const textarea = form.querySelector('.comment-textarea');
      const submitBtn = form.querySelector('.submit-btn');
      const cancelBtn = form.querySelector('.cancel-btn');
      
      submitBtn.addEventListener('click', async () => {
        const text = textarea.value.trim();
        if (!text) return;
        
        const userName = this.ensureUserName();
        if (!userName) return;
        
        try {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Submitting...';
          
          if (isReply) {
            await CommentsAPI.replyToComment(parentCommentId, {
              author_name: userName,
              text_body: text
            });
          } else {
            await CommentsAPI.createComment({
              file_path: this.currentFilePath,
              tree_item: treeItem,
              author_name: userName,
              text_body: text
            });
          }
          
          // Refresh the panel
          this.showCommentsPanel(treeItem);
          this.initializeForFile(this.currentFilePath); // Refresh indicators
          
        } catch (error) {
          alert('Failed to submit comment: ' + error.message);
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit';
        }
      });
      
      cancelBtn.addEventListener('click', () => {
        if (isReply) {
          form.remove();
        } else {
          textarea.value = '';
        }
      });
      
      return form;
    }

    showReplyForm(parentComment, parentElement, treeItem) {
      // Remove existing reply form if any
      const existingForm = parentElement.querySelector('.comment-form');
      if (existingForm) {
        existingForm.remove();
        return;
      }
      
      const replyForm = this.createCommentForm(treeItem, parentComment.id);
      parentElement.appendChild(replyForm);
      
      // Focus the textarea
      const textarea = replyForm.querySelector('.comment-textarea');
      textarea.focus();
    }

    async editComment(comment, commentElement) {
      const textElement = commentElement.querySelector('.comment-text');
      const originalText = textElement.dataset.originalText;
      
      // Replace text with textarea
      const textarea = document.createElement('textarea');
      textarea.className = 'comment-textarea';
      textarea.value = originalText;
      textarea.style.marginBottom = '8px';
      
      textElement.replaceWith(textarea);
      
      // Update actions
      const actions = commentElement.querySelector('.comment-actions');
      actions.innerHTML = `
        <button class="comment-btn cancel-edit-btn">Cancel</button>
        <button class="comment-btn comment-btn-primary save-edit-btn">Save</button>
      `;
      
      // Add event listeners
      actions.querySelector('.cancel-edit-btn').addEventListener('click', () => {
        textarea.replaceWith(textElement);
        // Restore original actions
        actions.innerHTML = `
          <button class="comment-btn reply-btn">Reply</button>
          <button class="comment-btn edit-btn">Edit</button>
          <button class="comment-btn comment-btn-danger delete-btn">Delete</button>
        `;
      });
      
      actions.querySelector('.save-edit-btn').addEventListener('click', async () => {
        const newText = textarea.value.trim();
        if (!newText) return;
        
        try {
          await CommentsAPI.updateComment(comment.id, newText);
          
          // Update the display
          textElement.textContent = newText;
          textElement.dataset.originalText = newText;
          textarea.replaceWith(textElement);
          
          // Restore original actions
          actions.innerHTML = `
            <button class="comment-btn reply-btn">Reply</button>
            <button class="comment-btn edit-btn">Edit</button>
            <button class="comment-btn comment-btn-danger delete-btn">Delete</button>
          `;
          
        } catch (error) {
          alert('Failed to update comment: ' + error.message);
        }
      });
      
      textarea.focus();
    }

    async deleteComment(comment, treeItem) {
      if (!confirm('Are you sure you want to delete this comment and all its replies?')) {
        return;
      }
      
      try {
        await CommentsAPI.deleteComment(comment.id);
        
        // Refresh the panel and indicators
        this.showCommentsPanel(treeItem);
        this.initializeForFile(this.currentFilePath);
        
      } catch (error) {
        alert('Failed to delete comment: ' + error.message);
      }
    }

    closeActivePanel() {
      if (this.activePanel) {
        this.activePanel.remove();
        this.activePanel = null;
      }
    }

    escapeHTML(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  }

  // Initialize when DOM is ready
  let treeCommentsUI = null;
  
  function initializeTreeComments() {
    if (!treeCommentsUI) {
      treeCommentsUI = new TreeCommentsUI();
      // Expose the instance globally for app.js to access
      window.treeCommentsUI = treeCommentsUI;
    }
    return treeCommentsUI;
  }

  // Export for global access
  window.TreeCommentsUI = TreeCommentsUI;
  window.initializeTreeComments = initializeTreeComments;

  // Auto-initialize if not already done
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTreeComments);
  } else {
    initializeTreeComments();
  }

})();