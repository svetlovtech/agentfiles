# Interface Segregation Principle - Real-World Scenarios

> **Status**: Placeholder - Content to be added

## What is ISP?

The Interface Segregation Principle states that clients should not be forced to depend on interfaces they do not use. Many client-specific interfaces are better than one general-purpose interface.

## Real-World Applications

### 1. Authentication Interfaces

```code
// Instead of one large AuthInterface, segregate by capability
interface CanLogin {
    login(credentials);
}

interface CanRegister {
    register(userInfo);
}

interface CanResetPassword {
    resetPassword(email);
}
```

### 2. Payment Processing

```code
// Segregate by payment capability
interface CanProcessPayment {
    processPayment(amount);
}

interface CanRefund {
    refund(transactionId);
}

interface CanSubscribe {
    createSubscription(plan);
}
```

### 3. IoT Device Interfaces

- Different devices implement only the interfaces they support
- Sensors: only read interfaces
- Actuators: only write interfaces
- Controllers: both read and write

## Key Takeaways

- Split large interfaces into smaller, focused ones
- Clients should only know about methods they need
- Prefer composition over inheritance for interface reuse
- Avoid "fat" interfaces that force unnecessary dependencies
