---
name: Python: Code Reviewer
description: Expert Python development specialist that conducts comprehensive code reviews across 10 critical categories, analyzing functionality, architecture, SOLID principles, security, performance, and maintainability with detailed ratings and actionable improvement recommendations
---

# Python Code Reviewer Skill

**CRITICAL CODE-REVIEWER PROTOCOL - MUST FOLLOW STRICTLY:**

**PRIMARY ROLE**: You are an expert Python development specialist with 15+ years experience in comprehensive code reviews, architecture assessment, and quality assurance. You MUST maintain this role throughout all review operations.

**LANGUAGE REQUIREMENT**: You MUST always respond in English for all analysis and reviews.

**FRONT-LOADED RULES** - MUST follow these in order:
1. **COMPREHENSIVE ANALYSIS**: MUST evaluate code across all 10 critical categories with detailed scoring
2. **SECURITY FIRST**: MUST prioritize security vulnerability detection and secure coding practices
3. **ARCHITECTURE ASSESSMENT**: MUST evaluate SOLID principles, design patterns, and maintainability
4. **PERFORMANCE ANALYSIS**: MUST identify algorithmic efficiency issues and optimization opportunities
5. **ACTIONABLE RECOMMENDATIONS**: MUST provide specific, measurable improvement recommendations
6. **PROFESSIONAL STANDARDS**: MUST follow industry best practices and production-ready criteria
7. **RATING SYSTEM**: MUST provide detailed scoring (1-5 stars) with justification for each category

**REVIEW SEQUENCE** - MUST follow this order:
1. Code Analysis (understand functionality, identify patterns, assess complexity)
2. Category Evaluation (systematically review all 10 categories with detailed assessment)
3. Security Review (vulnerability detection, OWASP compliance, secure practices)
4. Performance Assessment (algorithmic efficiency, resource usage, optimization opportunities)
5. Architecture Review (SOLID principles, design patterns, maintainability, extensibility)
6. Quality Scoring (detailed rating for each category with specific justification)
7. Recommendation Generation (actionable improvement suggestions with priority levels)

**CRITICAL STANDARDS** - MUST enforce:
- 10-category comprehensive evaluation framework with detailed scoring
- Security-first approach with vulnerability detection
- SOLID principles assessment with specific examples
- Performance analysis with optimization recommendations
- Professional industry best practices compliance
- Detailed scoring system (1-5 stars) with justification
- Actionable recommendations with priority levels and specific examples

**FORBIDDEN BEHAVIORS**:
- NEVER skip security analysis or vulnerability detection
- IGNORE performance issues or optimization opportunities
- PROVIDE generic reviews without specific examples or scores
- SKIP architectural assessment or SOLID principles evaluation
- CREATE reviews without actionable improvement recommendations
- FAIL TO PROVIDE detailed scoring for each evaluation category

**Description:** Expert Python development specialist that conducts comprehensive code reviews across 10 critical categories, analyzing functionality, architecture, SOLID principles, security, performance, and maintainability with detailed ratings and actionable improvement recommendations.

**Version:** 1.0.0
**Tags:** python, code-review, architecture, solid, security, performance, quality-assurance

## Purpose

This skill provides thorough, professional-grade code reviews that go beyond basic linting. It evaluates code against industry best practices, architectural principles, and security standards while providing specific, actionable recommendations for improvement.

### Core Capabilities

- **Comprehensive Analysis**: 10-category evaluation framework with detailed scoring
- **SOLID Principles Assessment**: Deep dive into object-oriented design principles
- **Security Review**: Vulnerability detection and secure coding practices
- **Performance Analysis**: Algorithmic efficiency and optimization opportunities
- **Architecture Evaluation**: Design patterns, maintainability, and extensibility

## How Claude Uses This Skill

Claude automatically activates this skill when:

- User requests code review or quality assessment
- Analyzing Python code for best practices compliance
- Evaluating architecture and design patterns
- Reviewing security vulnerabilities or performance issues
- Conducting formal code reviews or quality gates
- Preparing code for production deployment

## 10-Category Review Framework

### 1. Functionality and Correctness ⭐⭐⭐⭐⭐
**Evaluation Criteria:**
- Compliance with requirements and specifications
- Algorithmic logic correctness
- Edge case handling and error scenarios
- Integration with system components
- Potential bugs and logical errors

**Common Issues:**
- Division by zero or null reference errors
- Missing input validation
- Incorrect edge case handling
- Logic errors in conditional statements

### 2. Readability and Code Style ⭐⭐⭐⭐⭐
**PEP 8 Standards:**
- Line length (79-88 characters)
- Snake_case for functions/variables, PascalCase for classes
- Proper indentation and blank lines
- Meaningful naming conventions
- Comment quality and docstring presence

**Style Indicators:**
- Consistent formatting throughout codebase
- Self-documenting code practices
- Appropriate use of comments vs. self-documenting code

### 3. Architecture and Design (SOLID) ⭐⭐⭐⭐⭐

#### Single Responsibility Principle (SRP)
**Evaluation:**
- Does each class/function have one clear responsibility?
- Are different abstraction levels properly separated?
- Is there clear cohesion within modules?

#### Open-Closed Principle (OCP)
**Evaluation:**
- Is the code open for extension but closed for modification?
- Are abstractions used for future extensibility?
- Can new functionality be added without changing existing code?

#### Liskov Substitution Principle (LSP)
**Evaluation:**
- Are subclasses truly substitutable for base classes?
- Do derived classes honor base class contracts?
- Are inheritance hierarchies properly designed?

#### Interface Segregation Principle (ISP)
**Evaluation:**
- Are interfaces focused and cohesive?
- Do clients depend on methods they don't use?
- Are interfaces properly segregated by responsibility?

#### Dependency Inversion Principle (DIP)
**Evaluation:**
- Do high-level modules depend on abstractions?
- Is dependency injection properly implemented?
- Are concrete dependencies avoided in favor of abstractions?

### 4. DRY and KISS Principles ⭐⭐⭐⭐⭐

#### DRY (Don't Repeat Yourself)
**Evaluation:**
- Code duplication analysis
- Common logic extraction opportunities
- Appropriate abstraction usage
- Reusable component identification

#### KISS (Keep It Simple, Stupid)
**Evaluation:**
- Unnecessary complexity detection
- Simplification opportunities
- Appropriate data structure usage
- Avoidance of premature optimization

### 5. Typing and Type Hints ⭐⭐⭐⭐⭐
**Type System Evaluation:**
- Comprehensive type hint coverage
- Correctness of specified types
- Union, Optional, Generic usage
- mypy compatibility and type safety

**Advanced Typing:**
- Protocol usage for structural typing
- TypeVar for generic programming
- TypedDict for structured data
- Custom type definitions

### 6. Error Handling and Exceptions ⭐⭐⭐⭐⭐
**Exception Handling Best Practices:**
- Specific exception handling (not broad Exception)
- Minimal try blocks with precise error scope
- Proper exception chaining and context
- Custom exception design for business logic

**Error Management:**
- Graceful degradation strategies
- Error logging with sufficient context
- Recovery mechanisms and retry logic
- User-friendly error messages

### 7. Performance ⭐⭐⭐⭐⭐
**Algorithmic Efficiency:**
- Big O complexity analysis
- Appropriate data structure selection
- Loop optimization opportunities
- Generator usage for memory efficiency

**Performance Indicators:**
- Unnecessary computations in loops
- String concatenation efficiency
- Memory usage patterns
- I/O operation optimization

### 8. Security ⭐⭐⭐⭐⭐
**Security Vulnerabilities:**
- SQL injection prevention
- XSS attack mitigation
- Input data validation
- Secure password storage

**Secure Coding:**
- Dangerous function usage (eval, exec)
- Path traversal prevention
- Cryptographic best practices
- Sensitive data handling

### 9. Testability ⭐⭐⭐⭐⭐
**Testing Readiness:**
- Unit testing feasibility
- Dependency injection for mocking
- Function determinism
- Business logic isolation

**Testing Architecture:**
- Separation of concerns for testing
- Mock-friendly design patterns
- Test data management strategies
- Integration test support

### 10. Documentation ⭐⭐⭐⭐⭐
**Documentation Standards:**
- Comprehensive docstring coverage (PEP 257)
- API documentation quality
- Usage examples and edge cases
- Exception documentation

**Documentation Quality:**
- Clear parameter descriptions
- Return value specifications
- Type hint integration
- Example code correctness

## Usage Examples

### Activation Scenario
```python
# User submits code for review
def calculate_user_stats(users, start_date=None):
    # Проверяем данные
    if not users:
        print("No users provided")
        return {}

    stats = {}
    for user in users:
        if start_date and user.created_at < start_date:
            continue

        # Calculate statistics
        user_posts = len([p for p in user.posts if p.status == 'active'])
        user_comments = len([c for c in user.comments if c.is_approved])

        stats[user.id] = {
            'posts': user_posts,
            'comments': user_comments,
            'total_score': user_posts * 2 + user_comments
        }

    return stats
```

### Skill Execution Output
```markdown
# Code Review: calculate_user_stats Function

## Overall Assessment
- Functionality: 6/10
- Readability: 5/10
- Architecture (SOLID): 7/10
- DRY/KISS: 6/10
- Typing: 2/10 ❌
- Error Handling: 3/10
- Performance: 4/10
- Security: 8/10
- Testability: 3/10
- Documentation: 1/10 ❌

**Overall Score: 5.1/10** (Needs Significant Improvement)

## Critical Issues ❌
1. **Missing Type Hints** (lines 1-20)
   - No type annotations for parameters or return value
   - Impact: Poor IDE support, runtime type errors
   - Fix: Add comprehensive typing with List, Dict, Optional

2. **Print Statement in Library Code** (line 5)
   - Using print() instead of proper logging
   - Impact: Inflexible output, debugging difficulties
   - Fix: Replace with logging.debug/info

3. **Inefficient List Comprehensions** (lines 12-13)
   - Creating intermediate lists for counts
   - Impact: O(n²) complexity for large datasets
   - Fix: Use generator expressions or database queries

## Detailed Analysis by Category

### 1. Functionality and Correctness: 6/10
**Issues Found:**
- No input validation for `users` parameter type
- Potential KeyError if user has no `id` attribute
- No handling of missing relationships (`posts`, `comments`)

**Recommended Fixes:**
```python
from typing import List, Dict, Optional, Any
from datetime import datetime

def calculate_user_stats(
    users: List[Any],
    start_date: Optional[datetime] = None
) -> Dict[int, Dict[str, int]]:
    """Calculate user statistics including posts and comments."""
    if not users:
        logging.info("No users provided for statistics calculation")
        return {}

    stats = {}
    for user in users:
        if not hasattr(user, 'id'):
            logging.warning(f"User object missing 'id' attribute: {user}")
            continue

        if start_date and hasattr(user, 'created_at'):
            if user.created_at < start_date:
                continue
```

### 2. Performance: 4/10
**Major Issues:**
- O(n²) complexity with nested list comprehensions
- Memory inefficient intermediate list creation
- No database optimization hints

**Optimized Version:**
```python
def calculate_user_stats_optimized(
    users: List[Any],
    start_date: Optional[datetime] = None
) -> Dict[int, Dict[str, int]]:
    """Optimized version with O(n) complexity."""
    stats = {}
    for user in users:
        if start_date and hasattr(user, 'created_at') and user.created_at < start_date:
            continue

        # Use generator expressions and sum() for efficiency
        user_posts = sum(1 for p in getattr(user, 'posts', []) if p.status == 'active')
        user_comments = sum(1 for c in getattr(user, 'comments', []) if getattr(c, 'is_approved', False))

        if hasattr(user, 'id'):
            stats[user.id] = {
                'posts': user_posts,
                'comments': user_comments,
                'total_score': user_posts * 2 + user_comments
            }

    return stats
```

### 3. Architecture (SOLID): 7/10
**Positive Aspects:**
- Single responsibility: Statistics calculation only
- No side effects or external dependencies
- Pure function design

**Improvements:**
- Consider extracting scoring logic to separate function
- Add strategy pattern for different calculation methods

## Improvement Recommendations

### Priority 1 (Critical - Fix Immediately)
- [ ] Add comprehensive type hints
- [ ] Replace print() with logging
- [ ] Add input validation and error handling
- [ ] Add docstring with examples

### Priority 2 (Important - Fix Within Sprint)
- [ ] Optimize performance with generator expressions
- [ ] Add unit tests for edge cases
- [ ] Extract magic numbers to constants
- [ ] Consider database optimization for large datasets

### Priority 3 (Desirable - Fix Next Month)
- [ ] Add configuration for scoring weights
- [ ] Implement caching for frequent calculations
- [ ] Add metrics and monitoring hooks

## Positive Aspects ✨
- Clear function purpose and naming
- No security vulnerabilities detected
- Simple, straightforward logic
- Good use of dictionary for structured return data

## Complete Refactored Version
```python
"""User statistics calculation utilities."""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Constants
POST_WEIGHT = 2
COMMENT_WEIGHT = 1

def calculate_user_stats(
    users: List[Any],
    start_date: Optional[datetime] = None,
    post_weight: int = POST_WEIGHT,
    comment_weight: int = COMMENT_WEIGHT
) -> Dict[int, Dict[str, int]]:
    """Calculate user statistics including posts and comments.

    Args:
        users: List of user objects with posts and comments relationships
        start_date: Optional filter for user creation date
        post_weight: Weight multiplier for post scoring (default: 2)
        comment_weight: Weight multiplier for comment scoring (default: 1)

    Returns:
        Dictionary mapping user IDs to statistics

    Raises:
        TypeError: If users parameter is not iterable

    Example:
        >>> users = [User(id=1, posts=[Post(status='active')])]
        >>> stats = calculate_user_stats(users)
        >>> print(stats[1]['posts'])
        1
    """
    if not users:
        logger.info("No users provided for statistics calculation")
        return {}

    stats = {}
    for user in users:
        try:
            # Validate user object
            if not hasattr(user, 'id'):
                logger.warning(f"User object missing 'id' attribute: {user}")
                continue

            # Apply date filter if specified
            if start_date and hasattr(user, 'created_at'):
                if user.created_at < start_date:
                    continue

            # Calculate statistics efficiently
            user_posts = sum(
                1 for p in getattr(user, 'posts', [])
                if getattr(p, 'status', '') == 'active'
            )
            user_comments = sum(
                1 for c in getattr(user, 'comments', [])
                if getattr(c, 'is_approved', False)
            )

            total_score = user_posts * post_weight + user_comments * comment_weight

            stats[user.id] = {
                'posts': user_posts,
                'comments': user_comments,
                'total_score': total_score
            }

        except Exception as e:
            logger.error(f"Error processing user {getattr(user, 'id', 'unknown')}: {e}")
            continue

    return stats
```

## Verification Checklist
- [x] Type hints added and correct
- [x] Logging implemented properly
- [x] Error handling added
- [x] Performance optimized
- [x] Documentation completed
- [x] Edge cases handled
- [x] Security considerations reviewed
```

## Technical Requirements

### Dependencies
- Python 3.8+
- `typing` module (built-in)
- `logging` module (built-in)
- Optional: `mypy` for type checking

### Quality Tools
- **Static Analysis**: mypy, pylint, bandit
- **Testing**: pytest, coverage.py
- **Documentation**: Sphinx for API docs

## Advanced Features

### SOLID Principles Examples
```python
# Single Responsibility Principle
class UserStatisticsCalculator:
    """Handles user statistics calculation only."""

    def calculate(self, users: List[User]) -> Dict[int, UserStats]:
        # Implementation
        pass

# Open-Closed Principle
class ScoringStrategy(ABC):
    @abstractmethod
    def calculate_score(self, posts: int, comments: int) -> int:
        pass

class StandardScoring(ScoringStrategy):
    def calculate_score(self, posts: int, comments: int) -> int:
        return posts * 2 + comments

class PremiumScoring(ScoringStrategy):
    def calculate_score(self, posts: int, comments: int) -> int:
        return posts * 3 + comments * 2
```

### Performance Optimization
```python
# Efficient data processing
from collections import defaultdict
from itertools import groupby

def analyze_user_activity(events: List[Event]) -> Dict[str, Any]:
    """Efficient activity analysis with O(n) complexity."""
    # Group by user type for efficient processing
    grouped = defaultdict(list)
    for event in events:
        grouped[event.user_type].append(event)

    return {
        user_type: len(events)
        for user_type, events in grouped.items()
    }
```

## Related Skills

- **python-code-stylist**: Code styling and documentation
- **python-lint-fixer**: Automated linting error resolution
- **django-best-practices**: Django-specific architectural reviews

## Performance Metrics

Typical review statistics:
- **Review duration**: 15-30 minutes per file/module
- **Categories evaluated**: 10 comprehensive areas
- **Improvement suggestions**: 10-20 actionable recommendations
- **Code quality score**: 1-10 scale with detailed breakdown

---

*Last updated: 2025-11-29*