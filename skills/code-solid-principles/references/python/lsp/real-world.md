# Liskov Substitution Principle - Real-World Scenarios

> **Status**: Placeholder - Content to be added

## What is LSP?

The Liskov Substitution Principle states that objects of a superclass should be replaceable with objects of its subclasses without breaking the application. Derived classes must be substitutable for their base classes.

## Real-World Applications

### 1. Collection Frameworks

```code
// Any List implementation should work where List is expected
function processItems(List items) {
    // Works with ArrayList, LinkedList, CustomList
    for (item in items) {
        process(item);
    }
}
```

### 2. Payment Processing

```code
// All payment methods must honor the contract
abstract class PaymentMethod {
    abstract processPayment(amount): PaymentResult;
}

// Subclasses must not throw unexpected exceptions
// or require additional parameters
```

### 3. Shape Hierarchies (Classic Example)

```code
// Square cannot extend Rectangle if it violates behavior
// Square.SetWidth changes height too - breaks LSP!
```

## Common LSP Violations

1. **Strengthening Preconditions**: Subclass requires more than parent
2. **Weakening Postconditions**: Subclass provides less than parent
3. **Throwing Unexpected Exceptions**: Subclass throws new exception types
4. **Violating Invariants**: Subclass breaks parent's state rules

## Key Takeaways

- Subtypes must honor parent contracts
- Don't violate invariants of parent class
- Design for substitutability from the start
- Consider composition over problematic inheritance
