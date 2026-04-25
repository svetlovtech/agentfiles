# Open/Closed Principle - Examples

> **Status**: Placeholder - Content to be added

## What is OCP?

The Open/Closed Principle states that software entities should be **open for extension but closed for modification**.

## Core Concept

- **Open for Extension**: You can extend the behavior of the module
- **Closed for Modification**: You cannot modify the source code of the module

## Basic Example

```code
// GOOD: Using abstraction to allow extension
// New shapes can be added without modifying existing code
```

## Key Takeaways

- Use interfaces/abstractions to enable extension
- Avoid modifying existing, tested code
- Apply Strategy Pattern for varying behaviors
