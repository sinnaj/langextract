# UI Integration Plan for Comments System

## Overview
This document outlines the plan for creating a very simple commenting system backend and integrating it into the existing tree view of the existing Web App UI . THE backend utilizes a SQLite database and REST API endpoints.


## Backend API Summary

There is an existing solution that was severely overengineered. I want you to adjust the current implementation to a very streamlined approach that links Comments to dedicated extraction entities.
Comments/Comment Threads should only exist in reference to a specific tree item.
The item is itentified by combining the currently viewed Run and the items id.

You can see the current implementation in `\web\static\comments.js`, `\web\comments_db.py` , `\web\app.py`

Modify the backend to reflect this much more straighforward commenting behaviour. Remove any logic related to floating comments, comment position, mouse position.
Remove any behaviour that is not directly linked to creating, fetching, viewing, editing, deleting comments or replying to comments.

### GET `/api/comments?file_path=<path>`
- Retrieves all comments for a specific file
- Returns comments organized with replies nested under root comments
- Response format: `{"comments": [...]}`

### POST `/api/comments`
- Creates a new comment
- Required fields: `file_path`, `author_name`, `text_body`, `tree_item`
- Optional fields: `parent_comment_id`
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
When users views a document in UBERMODE in the Preview Section users should be able to commenmt on individual items within the tree.


#### Comment Display
- Load comments for the current file using `GET /api/comments?file_path=<path>`
- Comment Indicators are shown as a Message Icon on the right side of the Tree Item
- If no comments exist for the item, the Icon is blue
- If comments already exist, the Icon is Green
- Existing comments are displayed as an overlay panel when inspected

#### Comment Creation

- On tapping the message icon (when no comment exist yet):Show comment creation modal/form with fields:
  - Author name (could be session-based or user input)
  - Comment text
  - Position data (auto-populated based on context)
  - Show save / cancel options
- On tapping the message icon (when a comment exists): 
   - Show a panel with the existing comments
   - Show comment creation modal/form below it
   - Show reply/new comment/cancel options

#### Comment Interactions
- **View comments**: Click on comment indicators to expand/collapse
- **Edit comments**: Add edit button (with permission checks if needed)
- **Delete comments**: Add delete button (with confirmation dialog)


### 4. User Session Management
Implement basic user identification:
- Store user name in localStorage or session
- Use consistent author names across comments

## Implementation Phases

### Phase 1: Basic Comment Display (Essential)
1. **File Viewer Enhancement**
   - Modify existing file preview components to load comments
   - Add comment indicators in file content

2. **Comment Sidebar/Panel**
   - Add collapsible comment panel to file viewers
   - Display comments in chronological order
   - Show replies indented under parent comments

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


## Testing Strategy
1. **Unit Tests**: Test individual comment UI components
2. **Integration Tests**: Test API communication
3. **E2E Tests**: Test complete comment workflows
4. **Accessibility Tests**: Ensure WCAG compliance
5. **Cross-browser Tests**: Verify compatibility