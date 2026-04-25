---
name: code-dry-principle
description: "Comprehensive guide to the DRY principle - eliminating code duplication through proper abstraction and reusable components while avoiding common anti-patterns"
---

# DRY Principle (Don't Repeat Yourself)

## Core Principle

**DRY = Don't Repeat Yourself**
- Every piece of knowledge must have a single, unambiguous, authoritative representation
- Reduce redundancy and code duplication
- Create reusable abstractions instead of copying code

## The Balance: DRY vs WET

The opposite of DRY is **WET** (Write Everything Twice or We Enjoy Typing):
- **Proper DRY**: Abstract common patterns into reusable components
- **Anti-DRY**: Over-abstraction leads to complex, hard-to-maintain code
- **Finding balance**: DRY for clarity, not for the sake of abstraction

## Key Benefits

- **Maintainability**: Changes in one place
- **Consistency**: Same behavior across instances
- **Reusability**: Components can be used elsewhere
- **Smaller codebase**: Less total code to maintain

## When to Apply DRY

- **Apply DRY** when:
  - Same logic appears in multiple places
  - Similar patterns exist across components
  - Configuration is duplicated
  - Business rules are repeated

- **Don't over-apply DRY** when:
  - Code happens to look similar but serves different purposes
  - Abstractions become more complex than duplicated code
  - Coupling would increase unnecessarily

## Python Examples

- **Examples**: [references/python/examples.md](references/python/examples.md) - Core GOOD/BAD examples
- **Anti-patterns**: [references/python/anti-patterns.md](references/python/anti-patterns.md) - Common violations
- **Real-world**: [references/python/real-world.md](references/python/real-world.md) - Practical scenarios

## Common Anti-Patterns

1. **Helper Hell**: God object with too many responsibilities
2. **Over-Abstraction**: Complex abstractions for simple problems
3. **Premature Generalization**: Abstracting before patterns emerge
4. **Inappropriate Inheritance**: Inheriting just to reuse code

## Common DRY Violations

- Copied validation logic
- Repeated API calls
- Duplicated configuration
- Similar utility functions
- Repeated error handling

## Quick Reference

**When asking for DRY examples, specify:**
- "Python DRY examples" → [references/python/examples.md](references/python/examples.md)
- "Python anti-patterns" → [references/python/anti-patterns.md](references/python/anti-patterns.md)
- "Real-world DRY scenarios in Python" → [references/python/real-world.md](references/python/real-world.md)

**For comprehensive theory:**
- [Detailed Overview](references/overview.md) - Complete explanation and theory

## Remember

> "Good programmers write code that humans can understand, not just machines." - Martin Fowler

## Usage Questions

- **When refactoring**: "Is this logic repeated elsewhere?"
- **When designing**: "Can this be abstracted for reuse?"
- **When reviewing**: "Should this be extracted into a shared component?"
