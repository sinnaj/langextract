# UI Integration Plan for Comments System

## Overview
This document outlines the plan for integrating the backend commenting system with the existing web UI. The backend is now complete with SQLite database and REST API endpoints. The UI integration should wait until the ongoing UI refactoring is finished.

## Backend API Summary
The following REST API endpoints are available:

### GET `/api/comments?file_path=<path>`
- Retrieves all comments for a specific file
- Returns comments organized with replies nested under root comments
- Response format: `{"comments": [...]}`

### POST `/api/comments`
- Creates a new comment
- Required fields: `file_path`, `author_name`, `text_body`
- Optional fields: `position_data`, `parent_comment_id`
- Returns created comment with assigned ID

### PUT `/api/comments/<id>`
- Updates an existing comment's text
- Required field: `text_body`
- Returns updated comment

### DELETE `/api/comments/<id>`
- Deletes a comment and all its replies (cascade)
- Returns success message

### POST `/api/comments/<id>/reply`
- Creates a reply to a comment
- Required fields: `author_name`, `text_body`
- Automatically enforces depth=1 restriction
- Returns created reply comment

### GET `/api/comments/<id>`
- Gets details of a specific comment
- Includes reply count
- Returns comment details

## UI Integration Points

### 1. File Viewer Integration
When users view files in the web app (JSON, text, markdown, etc.), we need to:

#### Comment Display
- Load comments for the current file using `GET /api/comments?file_path=<path>`
- Display comments as overlays or sidebar panels
- Show comment indicators (badges/markers) at relevant positions in the file
- For different file types:
  - **Text files**: Show comments at specific line numbers
  - **JSON files**: Show comments at specific JSON paths (e.g., "root.users[0].name")
  - **Markdown files**: Show comments at character positions or sections
  - **Images**: Show comments as pinned markers at coordinates

#### Comment Creation
- Add "Add Comment" buttons/UI elements throughout the file viewer
- Context-aware comment creation:
  - **Text files**: Capture line and column numbers
  - **JSON files**: Capture JSON path being viewed/clicked
  - **Markdown files**: Capture position and section context
  - **Images**: Capture mouse coordinates
- Show comment creation modal/form with fields:
  - Author name (could be session-based or user input)
  - Comment text
  - Position data (auto-populated based on context)

#### Comment Interactions
- **View comments**: Click on comment indicators to expand/collapse
- **Reply to comments**: Add reply button on each comment
- **Edit comments**: Add edit button (with permission checks if needed)
- **Delete comments**: Add delete button (with confirmation dialog)

### 2. File List Integration
In the file listing views:
- Show comment count badges next to files that have comments
- Filter files by "has comments" status
- Sort files by comment activity

### 3. Comment Management Dashboard
Create a dedicated comments management section:
- List all comments across all files
- Filter by file, author, date range
- Bulk operations (delete, export)
- Comment moderation features if needed

### 4. User Session Management
Implement basic user identification:
- Store user name in localStorage or session
- Use consistent author names across comments
- Optional: Add simple user authentication

## Implementation Phases

### Phase 1: Basic Comment Display (Essential)
1. **File Viewer Enhancement**
   - Modify existing file preview components to load comments
   - Add comment indicators in file content
   - Show comment count in file headers

2. **Comment Sidebar/Panel**
   - Add collapsible comment panel to file viewers
   - Display comments in chronological order
   - Show replies indented under parent comments

### Phase 2: Comment Creation (Core)
1. **Context-Aware UI**
   - Add floating "Add Comment" buttons
   - Implement position capture for different file types
   - Create comment creation modal/form

2. **Form Handling**
   - Integrate with backend API
   - Handle success/error states
   - Refresh comment display after creation

### Phase 3: Comment Management (Enhanced)
1. **Edit/Delete Operations**
   - Add edit/delete buttons to comments
   - Implement inline editing
   - Handle confirmation dialogs

2. **Reply Functionality**
   - Add reply buttons and forms
   - Ensure proper nesting display
   - Enforce depth=1 restriction in UI

### Phase 4: Advanced Features (Optional)
1. **Search and Filtering**
   - Search comments by text content
   - Filter by author, date, file type
   - Highlight search results

2. **Comment Notifications**
   - Show new comment indicators
   - Optional: Email notifications
   - Comment activity feeds

3. **Export and Reporting**
   - Export comments to CSV/JSON
   - Generate comment reports
   - Analytics dashboard

## Technical Considerations

### JavaScript/CSS Integration
- Use existing CSS frameworks (Tailwind) for styling
- Integrate with existing JavaScript patterns in `app.js`
- Ensure responsive design for mobile viewing

### Performance Optimization
- Lazy load comments (only when file is opened)
- Implement pagination for files with many comments
- Cache comments in localStorage for offline viewing

### Error Handling
- Graceful degradation when API is unavailable
- Offline comment drafting (save to localStorage)
- Retry mechanisms for failed requests

### Security Considerations
- Input sanitization for comment text (XSS prevention)
- Rate limiting for comment creation
- Optional CSRF protection

### Accessibility
- Keyboard navigation for comment interactions
- Screen reader support for comment content
- High contrast mode support for comment UI

## Database Schema Notes
The current database schema supports flexible position tracking:

```json
{
  "line": 42,           // Text files
  "column": 10,         // Text files
  "page": 2,            // Multi-page documents
  "path": "root.users[0].name",  // JSON files
  "position": 1234,     // Markdown character position
  "section": "Overview", // Markdown section
  "x": 150,             // Image coordinates
  "y": 200              // Image coordinates
}
```

This flexibility allows the UI to support commenting on any file type with appropriate position tracking.

## Testing Strategy
1. **Unit Tests**: Test individual comment UI components
2. **Integration Tests**: Test API communication
3. **E2E Tests**: Test complete comment workflows
4. **Accessibility Tests**: Ensure WCAG compliance
5. **Cross-browser Tests**: Verify compatibility

## Migration from Existing Comment Systems
If there are existing comment systems (like the localStorage-based one in arqio_visualization):
1. Create migration scripts to convert existing comments to database format
2. Maintain backward compatibility during transition period
3. Provide import/export tools for user data

## Conclusion
The backend commenting system is now fully implemented and tested. The UI integration can proceed once the current UI refactoring is complete, following the phases outlined above for a smooth rollout of commenting functionality.
