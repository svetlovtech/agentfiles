---
name: code-solid-principles
description: "Essential object-oriented design principles for creating maintainable, scalable, and robust software. Each principle includes practical examples, common violations, and refactoring techniques"
---

# SOLID Principles

Essential object-oriented design principles for creating maintainable, scalable, and robust software. Each principle includes practical examples, common violations, and refactoring techniques.

## The Five Principles

### S - Single Responsibility Principle (SRP)
- A class should have only one reason to change
- One responsibility per class/module
- Cohesive functionality

### O - Open/Closed Principle (OCP)
- Open for extension, closed for modification
- Extend behavior without changing existing code
- Use interfaces and abstraction

### L - Liskov Substitution Principle (LSP)
- Subtypes must be substitutable for their base types
- Derived classes must not break parent class expectations
- Design contracts carefully

### I - Interface Segregation Principle (ISP)
- Many client-specific interfaces are better than one general-purpose interface
- Avoid fat interfaces
- Clients shouldn't depend on methods they don't use

### D - Dependency Inversion Principle (DIP)
- Depend on abstractions, not concretions
- High-level modules shouldn't depend on low-level modules
- Both should depend on abstractions

## When to Apply SOLID

- **Design phase**: Planning class hierarchies and interfaces
- **Refactoring**: Improving existing code structure
- **Code reviews**: Evaluating design quality
- **Architecture**: Designing system components

## Quick Reference Table

| Principle | Python |
|-----------|--------|
| SRP | [examples](references/python/srp/examples.md), [anti-patterns](references/python/srp/anti-patterns.md) |
| OCP | [examples](references/python/ocp/examples.md), [anti-patterns](references/python/ocp/anti-patterns.md) |
| LSP | [examples](references/python/lsp/examples.md), [anti-patterns](references/python/lsp/anti-patterns.md) |
| ISP | [examples](references/python/isp/examples.md), [anti-patterns](references/python/isp/anti-patterns.md) |
| DIP | [examples](references/python/dip/examples.md), [anti-patterns](references/python/dip/anti-patterns.md) |

## Resources by Principle and Language

### SRP (Single Responsibility Principle)

#### Python
- **Examples**: [references/python/srp/examples.md](references/python/srp/examples.md)
- **Anti-patterns**: [references/python/srp/anti-patterns.md](references/python/srp/anti-patterns.md)
- **Real-world**: [references/python/srp/real-world.md](references/python/srp/real-world.md)

### OCP (Open/Closed Principle)

#### Python
- **Examples**: [references/python/ocp/examples.md](references/python/ocp/examples.md)
- **Anti-patterns**: [references/python/ocp/anti-patterns.md](references/python/ocp/anti-patterns.md)
- **Real-world**: [references/python/ocp/real-world.md](references/python/ocp/real-world.md)

### LSP (Liskov Substitution Principle)

#### Python
- **Examples**: [references/python/lsp/examples.md](references/python/lsp/examples.md)
- **Anti-patterns**: [references/python/lsp/anti-patterns.md](references/python/lsp/anti-patterns.md)
- **Real-world**: [references/python/lsp/real-world.md](references/python/lsp/real-world.md)

### ISP (Interface Segregation Principle)

#### Python
- **Examples**: [references/python/isp/examples.md](references/python/isp/examples.md)
- **Anti-patterns**: [references/python/isp/anti-patterns.md](references/python/isp/anti-patterns.md)
- **Real-world**: [references/python/isp/real-world.md](references/python/isp/real-world.md)

### DIP (Dependency Inversion Principle)

#### Python
- **Examples**: [references/python/dip/examples.md](references/python/dip/examples.md)
- **Anti-patterns**: [references/python/dip/anti-patterns.md](references/python/dip/anti-patterns.md)
- **Real-world**: [references/python/dip/real-world.md](references/python/dip/real-world.md)

## Benefits

- **Maintainability**: Changes isolated to single components
- **Testability**: Each component can be tested independently
- **Flexibility**: Easy to extend and modify
- **Reusability**: Components can be reused in different contexts
- **Collaboration**: Team members can work independently

## Refactoring Strategies

- **Extract Classes**: Break large classes into smaller ones
- **Introduce Interfaces**: Define contracts between components
- **Use Composition**: Favor composition over inheritance
- **Dependency Injection**: Inject dependencies instead of creating them
- **Strategy Pattern**: Encapsulate algorithms

## Remember

> "SOLID is not about rules, but about principles that guide us to write better code." - Robert C. Martin
