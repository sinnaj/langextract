# Coding Standards & Best Practices

This document establishes coding standards, conventions, and best practices for the arqio langextract project to ensure consistent, maintainable, and high-quality code.

## Code Style & Formatting

### Python Code Style
- Follow **PEP 8** for Python code style
- Use **Ruff** for linting and **Black** for formatting (configured in `pyproject.toml`)
- Maximum line length: **88 characters** (Black default)
- Use **4 spaces** for indentation (no tabs)
- Run `make format` and `make lint` before commits

### Naming Conventions
- **Classes**: PascalCase (`UserService`, `ProjectRepository`)
- **Functions/Methods**: snake_case (`create_user`, `get_project_by_id`)
- **Variables**: snake_case (`user_id`, `project_data`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_FILE_SIZE`, `DEFAULT_PAGE_SIZE`)
- **Files/Modules**: snake_case (`user_service.py`, `auth_middleware.py`)
- **Database Tables**: snake_case (`users`, `project_documents`)
- **Database Columns**: snake_case (`created_at`, `is_active`)

### Import Organization
```python
# 1. Standard library imports
import asyncio
import uuid
from datetime import datetime
from typing import List, Optional

# 2. Third-party imports
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# 3. Local application imports
from app.core.config import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
```

## Code Documentation

### Docstrings
- Use **Google-style docstrings** for all public classes and methods
- Include parameter types, return types, and raised exceptions

```python
async def create_user(
    self,
    db: AsyncSession,
    user_data: UserCreateRequest,
    current_user_id: UUID
) -> UserResponse:
    """Create a new user account.
    
    Args:
        db: Database session
        user_data: User creation data
        current_user_id: ID of user performing the action
        
    Returns:
        UserResponse: Created user data
        
    Raises:
        HTTPException: If user creation fails or email already exists
        ValidationError: If user data is invalid
    """
```

### Comments
- Use comments to explain **why**, not **what**
- Keep comments up-to-date with code changes
- Use TODO comments sparingly and include issue references

## Error Handling

### HTTP Exceptions
- Use consistent HTTP status codes:
  - `400 Bad Request`: Invalid input data
  - `401 Unauthorized`: Missing or invalid authentication
  - `403 Forbidden`: Insufficient permissions
  - `404 Not Found`: Resource not found
  - `409 Conflict`: Resource conflict (duplicate email)
  - `422 Unprocessable Entity`: Validation errors
  - `500 Internal Server Error`: Unexpected server errors

### Error Response Format
- Use standardized error envelopes for consistency
- Include error codes for client handling
- Never expose sensitive information in error messages

```python
{
    "detail": "User with email already exists",
    "error_code": "USER_EMAIL_DUPLICATE", 
    "field_errors": {
        "email": ["Email address must be unique"]
    }
}
```

## Performance Guidelines

### Database Operations
- Use async patterns consistently (`AsyncSession`, `await`)
- Implement eager loading to avoid N+1 queries
- Use pagination for large result sets
- Index frequently queried columns
- Use `selectinload()` for relationships in queries

### Caching Strategy
- Cache expensive computations and frequent queries
- Use Redis for session storage and distributed caching
- Implement cache invalidation patterns
- Monitor cache hit ratios

### Response Optimization
- Use background tasks for non-critical operations
- Implement proper pagination with cursor-based pagination for large datasets
- Return only necessary data fields in API responses
- Use compression for large responses

## Testing Standards

### Test Organization
- Place all tests in `/tests` directory
- Mirror the application structure in test organization
- Use descriptive test file names: `test_[module]_[feature].py`

### Test Categories
- **Unit Tests**: Test individual functions/methods in isolation
- **Integration Tests**: Test interaction between components
- **API Tests**: Test complete request/response cycles
- **Repository Tests**: Test database interactions

### Test Naming
```python
def test_create_user_with_valid_data_should_return_user():
    """Test that creating user with valid data returns user object."""
    pass

def test_create_user_with_duplicate_email_should_raise_conflict():
    """Test that creating user with existing email raises HTTP 409."""
    pass
```

## Logging Standards

### Structured Logging
- Use `structlog` for consistent, structured logs
- Include contextual information: `user_id`, `request_id`, `operation`
- Never log sensitive data (passwords, tokens, PII)

```python
logger.info("User created successfully",
           user_id=str(user.id),
           email=user.email,
           operation="create_user")

logger.warning("Authentication failed",
              email=email_attempt,
              ip_address=request.client.host,
              operation="login")
```

### Log Levels
- **DEBUG**: Detailed information for debugging
- **INFO**: General information about application flow  
- **WARNING**: Something unexpected but not necessarily wrong
- **ERROR**: Error conditions that need attention
- **CRITICAL**: Serious errors that may abort the program

## Git & Version Control

### Commit Messages
Follow conventional commit format:
```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(auth): add magic link authentication
fix(user): resolve duplicate email validation
docs(api): update authentication endpoint documentation
```

### Branch Strategy
- Use feature branches: `feature/auth-magic-link`
- Use fix branches: `fix/user-email-validation`
- Keep branches focused and short-lived
- Delete branches after merging

## Code Review Guidelines

### Before Requesting Review
- [ ] Code follows style guidelines (run `make format`, `make lint`)
- [ ] All tests pass (`make test`)
- [ ] Documentation is updated
- [ ] No sensitive data in commits
- [ ] Branch is up-to-date with main

### Review Checklist
- [ ] Code is readable and well-documented
- [ ] Business logic is correct
- [ ] Error handling is appropriate
- [ ] Performance impact is reasonable
- [ ] Tests cover new functionality
- [ ] No code duplication or dead code

## Tool Integration

### Development Tools
- **Ruff**: Primary linter and formatter
- **MyPy**: Static type checking
- **pytest**: Testing framework
- **pre-commit**: Git hooks for quality checks

### IDE/Editor Configuration
- Configure your editor to:
  - Use project's Python interpreter
  - Auto-format with Black on save
  - Show linting errors in real-time
  - Use 4-space indentation
  - Remove trailing whitespace

## Continuous Integration

### Quality Gates
All PRs must pass:
- [ ] Linting (`make lint`)
- [ ] Type checking (`make type-check`) 
- [ ] Tests (`make test`)
- [ ] Coverage thresholds


---

> **Remember**: These standards exist to maintain code quality and team productivity. When in doubt, prioritize readability and maintainability over cleverness.