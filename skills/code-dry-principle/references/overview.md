# DRY Principle - Comprehensive Overview

> **Status**: Placeholder - Content to be added

## What is DRY?

**DRY** stands for "Don't Repeat Yourself" - a fundamental principle in software development that aims to reduce repetition of software patterns, replacing it with abstractions or using data normalization to avoid redundancy.

## Core Philosophy

The principle was formulated by Andy Hunt and Dave Thomas in their book "The Pragmatic Programmer". The core idea is:

> "Every piece of knowledge must have a single, unambiguous, authoritative representation within a system."

## When to Apply DRY

### Apply DRY when:
- Same logic appears in multiple places
- Similar patterns exist across components
- Configuration is duplicated
- Business rules are repeated

### Avoid Over-DRY when:
- Code happens to look similar but serves different purposes
- Abstractions become more complex than duplicated code
- Coupling would increase unnecessarily

## The Balance: DRY vs WET

The opposite of DRY is **WET** (Write Everything Twice or We Enjoy Typing).

## Key Benefits

- **Maintainability**: Changes in one place
- **Consistency**: Same behavior across instances
- **Reusability**: Components can be used elsewhere
- **Smaller codebase**: Less total code to maintain

## Common Anti-Patterns

1. **Helper Hell**: God object with too many responsibilities
2. **Over-Abstraction**: Complex abstractions for simple problems
3. **Premature Generalization**: Abstracting before patterns emerge
4. **Inappropriate Inheritance**: Inheriting just to reuse code

## Language Examples

See the language-specific references:
- [Python](python/examples.md)
- [JavaScript](javascript/examples.md)
- [TypeScript](typescript/examples.md)
- [Java](java/examples.md)
- [Kotlin](kotlin/examples.md)
- [Go](golang/examples.md)
- [Rust](rust/examples.md)
