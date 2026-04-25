---
name: code-grasp-patterns
description: "Comprehensive guide to GRASP (General Responsibility Assignment Software Patterns) - 9 patterns for assigning responsibilities to objects in OO design. Currently supports Python (100% complete)."
---

# GRASP Patterns

Comprehensive guide to General Responsibility Assignment Software Patterns - 9 fundamental patterns for assigning responsibilities to objects in object-oriented design.

## Overview

GRASP patterns provide a systematic approach to assigning responsibilities to objects in OO systems. Developed by Craig Larman, these patterns help designers create well-structured, maintainable code by answering "What object should be responsible for this task?" They form the foundation of object-oriented design and align closely with SOLID principles.

## Core Principles

GRASP addresses the fundamental question of object design: **How to assign responsibilities to objects?** Each pattern provides guidance on where to place specific behaviors and data to achieve:

- Clear separation of concerns
- Minimal coupling between objects
- High cohesion within objects
- Flexibility for future changes
- Reusability of components

## The 9 Patterns

| Pattern | Purpose | Key Question |
|---------|---------|--------------|
| **Controller** | Handles system events | Who handles system events? |
| **Creator** | Creates instances | Who creates this object? |
| **Information Expert** | Has needed information | Who has the information? |
| **High Cohesion** | Groups related responsibilities | Do responsibilities relate? |
| **Low Coupling** | Minimizes dependencies | How to reduce dependencies? |
| **Polymorphism** | Handles behavior variations | How to handle variations? |
| **Indirection** | Decouples components | How to decouple A and B? |
| **Protected Variations** | Encapsulates change | How to protect from change? |
| **Pure Fabrication** | Groups artificial responsibilities | Where to put artificial behavior? |

## Quick Reference Table

**Supported Language:** Python (100% complete)

| Pattern | Python |
|----------|---------|
| Controller | [link](#controller) |
| Creator | [link](#creator) |
| Information Expert | [link](#information-expert) |
| High Cohesion | [link](#high-cohesion) |
| Low Coupling | [link](#low-coupling) |
| Polymorphism | [link](#polymorphism) |
| Indirection | [link](#indirection) |
| Protected Variations | [link](#protected-variations) |
| Pure Fabrication | [link](#pure-fabrication) |

## Resources by Pattern and Language

### Controller

Handles system events and coordinates operations between objects.

**Examples:**
- [Python](references/python/controller/examples.md)

**Anti-patterns:**
- [Python](references/python/controller/anti-patterns.md)

### Creator

Decides which object should be responsible for creating instances of other objects.

**Examples:**
- [Python](references/python/creator/examples.md)

**Anti-patterns:**
- [Python](references/python/creator/anti-patterns.md)

### Information Expert

Assigns responsibility to class that has information needed to fulfill it.

**Examples:**
- [Python](references/python/information-expert/examples.md)

**Anti-patterns:**
- [Python](references/python/information-expert/anti-patterns.md)

### High Cohesion

Ensures that a class has a single, well-focused responsibility with related behaviors.

**Examples:**
- [Python](references/python/high-cohesion/examples.md)

**Anti-patterns:**
- [Python](references/python/high-cohesion/anti-patterns.md)

### Low Coupling

Minimizes dependencies between classes to reduce impact of changes.

**Examples:**
- [Python](references/python/low-coupling/examples.md)

**Anti-patterns:**
- [Python](references/python/low-coupling/anti-patterns.md)

### Polymorphism

Handles variations in behavior by assigning responsibility to type that varies.

**Examples:**
- [Python](references/python/polymorphism/examples.md)

**Anti-patterns:**
- [Python](references/python/polymorphism/anti-patterns.md)

### Indirection

Assigns responsibility to an intermediate object to mediate between other components.

**Examples:**
- [Python](references/python/indirection/examples.md)

**Anti-patterns:**
- [Python](references/python/indirection/anti-patterns.md)

### Protected Variations

Identifies points of predicted variation and creates stable interfaces around them.

**Examples:**
- [Python](references/python/protected-variations/examples.md)

**Anti-patterns:**
- [Python](references/python/protected-variations/anti-patterns.md)

### Pure Fabrication

Creates an artificial class that doesn't represent domain concepts but groups related behaviors.

**Examples:**
- [Python](references/python/pure-fabrication/examples.md)

**Anti-patterns:**
- [Python](references/python/pure-fabrication/anti-patterns.md)

## Benefits

Applying GRASP patterns provides:

- **Better Object-Oriented Design**: Clear responsibility assignment leads to well-structured systems
- **Clearer Responsibility Assignment**: Each object has a focused, well-defined role
- **More Maintainable Code**: Low coupling and high cohesion make changes easier
- **Balanced Coupling and Cohesion**: Optimal relationships between components
- **Alignment with SOLID**: GRASP principles complement and support SOLID principles
- **Improved Reusability**: Well-defined responsibilities enable component reuse
- **Easier Testing**: Focused responsibilities lead to testable code
- **Better Documentation**: Clear structure is self-documenting

## Additional Resources

- Wikipedia: [GRASP patterns](https://en.wikipedia.org/wiki/GRASP_(object-oriented_design))
- Craig Larman's book: Applying UML and Patterns
