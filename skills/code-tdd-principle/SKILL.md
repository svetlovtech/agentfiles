---
name: code-tdd-principle
description: "Complete guide to Test-Driven Development using the Red-Green-Refactor cycle. Write failing tests first, then implement code to make them pass, and refactor for clean design"
---

# TDD (Test-Driven Development)

Complete guide to Test-Driven Development using the Red-Green-Refactor cycle. Write failing tests first, then implement code to make them pass, and refactor for clean design.

## The TDD Cycle

### 1. Red
- Write a failing test
- Test should describe the desired behavior
- Test must fail initially
- Keep tests small and focused

### 2. Green
- Write the minimum code needed to make the test pass
- No extra functionality
- Code may be "ugly" but must work
- Get to green quickly

### 3. Refactor
- Clean up the code while keeping tests green
- Improve design and remove duplication
- Apply design principles (SOLID, DRY, KISS)
- All tests must still pass

## When to Use TDD

- **New Features**: Write tests before implementation
- **Bug Fixes**: Write a test that reproduces the bug, then fix
- **Refactoring**: Add tests before refactoring legacy code
- **API Development**: Test endpoints before implementation
- **Complex Logic**: Test edge cases and error conditions

## Test Categories

### Unit Tests
- Test individual components in isolation
- Fast and focused
- Mock external dependencies

### Integration Tests
- Test how components work together
- Test interactions between modules
- Use real dependencies when possible

### Acceptance Tests
- Test from user perspective
- End-to-end scenarios
- Test business requirements

## Common TDD Patterns

### Arrange-Act-Assert (AAA)
```python
# Arrange
user = User("test@example.com")
user.add_balance(100)

# Act
user.withdraw(50)

# Assert
assert user.balance == 50
```

### Given-When-Then (GWT)
```gherkin
Given a user with $100 balance
When they withdraw $50
Then their balance should be $50
```

## Benefits

- **Design**: Forces good design decisions
- **Documentation**: Tests serve as documentation
- **Confidence**: Safe refactoring
- **Regression**: Catches breaking changes
- **Focus**: Clear requirements

## Tools and Frameworks

- **Test Runners**: pytest
- **Mocking**: unittest.mock
- **Coverage**: Coverage.py
- **Continuous Integration**: Automated test execution

## Test Smells to Avoid

- **Long Setup**: Complex test initialization
- **Multiple Assertions**: Too many assertions in one test
- **Testing Implementation**: Testing how rather than what
- **Test Coupling**: Tests depend on each other
- **Magic Numbers**: Hardcoded values in tests

## Python TDD Examples

- **Examples**: [references/python/examples.md](references/python/examples.md) - TDD Red-Green-Refactor cycle
- **Anti-patterns**: [references/python/anti-patterns.md](references/python/anti-patterns.md) - Test smells
- **Real-world**: [references/python/real-world.md](references/python/real-world.md) - Practical scenarios

## Best Practices

1. **Write tests first** - Always before implementation
2. **Keep tests fast** - Unit tests should run in milliseconds
3. **One assertion per test** - Clear purpose
4. **Descriptive names** - Test names should describe behavior
5. **Test edge cases** - Boundary conditions and errors
6. **Maintain test suite** - Keep tests organized and up-to-date

## Quick Start Checklist

- [ ] Write a failing test (Red)
- [ ] Make it pass (Green)
- [ ] Refactor while keeping it green (Refactor)
- [ ] Repeat for next requirement

## Remember

> "If you don't have a test for it, it doesn't exist." - Unknown
