---
name: code-yagni-principle
description: "Essential guidance for applying YAGNI (You Aren't Gonna Need It) principle in software development. Focus on implementing only what's needed now, avoiding speculative features, and embracing incremental development"
---

# YAGNI Principle

You Aren't Gonna Need It: Always implement things when you actually need them, never when you just foresee that you need them.

## Core Principle

**Definition**: YAGNI (You Aren't Gonna Need It) is a principle of extreme programming (XP) that states that a programmer should not add functionality until it is necessary.

**Philosophy**: Resist the urge to implement features that you think you might need in the future. Build only what's required for the current requirements and nothing more.

**Origins**: Introduced by Ron Jeffries and the Extreme Programming community in the late 1990s as a counter to "big design up front" and over-engineering.

**Key Quotes**:
- "Always implement things when you actually need them, never when you just foresee that you need them." - Ron Jeffries
- "YAGNI says don't design in features you don't need now." - Martin Fowler
- "The rule is simple: Do not add features that are not currently required." - Kent Beck

## Quick Guidelines

**Apply YAGNI When:**
- You're adding features for "someday"
- You're creating abstractions before they're needed
- You're making code "flexible" for unknown future requirements
- You're building a framework instead of an application

**Balancing YAGNI:**
- YAGNI complements SOLID principles
- YAGNI works with iterative development
- Defer architectural decisions until necessary
- Focus on delivering value now, not perfect code

## Benefits

- Faster delivery to production
- Less wasted development effort
- Simpler, easier to understand codebase
- Reduced maintenance burden
- Better focus on actual user needs
- Lower defect rate from untested speculative code

## Python Examples

- **Examples**: [references/python/examples.md](references/python/examples.md) - Core GOOD/BAD examples
- **Anti-patterns**: [references/python/anti-patterns.md](references/python/anti-patterns.md) - Common over-engineering violations
- **Real-world**: [references/python/real-world.md](references/python/real-world.md) - Practical scenarios

## Remember

"YAGNI is not about avoiding future work, it's about postponing it until you have the information to do it right."

Use this skill when:
- Planning new features and wondering what to include
- Reviewing code that seems over-engineered
- Designing architecture for a new project
- Refactoring existing code
- Making decisions about abstraction layers
- Deciding between multiple implementation approaches

Focus on implementing what's needed now, embrace incremental development, and trust that future requirements can be addressed when they become actual requirements.
