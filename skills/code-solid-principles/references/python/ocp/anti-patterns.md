# Open/Closed Principle - Anti-Patterns

> **Status**: Placeholder - Content to be added

## Common OCP Violations

### 1. Switch Statements on Type

```code
// ANTI-PATTERN: Must modify when adding new types
function process(type) {
    switch(type) {
        case 'A': return processA();
        case 'B': return processB();
        // Must add new case for each new type!
    }
}
```

### 2. Hardcoded Conditionals

```code
// ANTI-PATTERN: Modifying existing code for new requirements
if (user.type === 'premium') {
    // premium logic
} else if (user.type === 'basic') {
    // basic logic
}
// Adding 'enterprise' requires modifying this code
```

## Proper Pattern

```code
// GOOD: Open for extension through polymorphism
interface User {
    getBenefits();
}
```

## Key Takeaways

- Avoid switch statements on types
- Use polymorphism instead of conditionals
- Apply patterns: Strategy, Template Method, Decorator
