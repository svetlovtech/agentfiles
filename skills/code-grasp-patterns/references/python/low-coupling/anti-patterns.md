# Low Coupling Anti-Patterns - Python

## Introduction

This document catalogs common anti-patterns that violate Low Coupling principle in Python.

## Anti-Pattern: Tight Concrete Coupling

### Description

Directly depending on concrete classes instead of abstractions.

### BAD Example

```python
class OrderService:
    def __init__(self):
        # BAD: Tight coupling to concrete implementations
        self.user_repo = UserRepository()  # Django specific
        self.email_sender = SMTPEmailSender()
        self.payment_gateway = StripeGateway('sk_test_xxx')
        self.cache = RedisCache(host='localhost')
```

### Why It's Problematic

- **Can't swap implementations**: Locked into specific implementations
- **Hard to test**: Can't use mocks
- **Hard to configure**: Hardcoded dependencies
- **Violates DIP**: Depends on concrete classes

### GOOD Example

```python
class OrderService:
    def __init__(self,
                 user_repo: UserRepositoryProtocol,
                 email_sender: EmailSenderProtocol,
                 payment_gateway: PaymentGatewayProtocol,
                 cache: CacheProtocol):
        # GOOD: Depend on abstractions
        self.user_repo = user_repo
        self.email_sender = email_sender
        self.payment_gateway = payment_gateway
        self.cache = cache

# Protocols
class UserRepositoryProtocol(Protocol):
    def find(self, user_id: int) -> User:
        ...

class EmailSenderProtocol(Protocol):
    def send(self, to: str, subject: str, body: str) -> None:
        ...

# Usage
service = OrderService(
    user_repo=DjangoUserRepository(),
    email_sender=SMTPEmailSender(),
    payment_gateway=StripeGateway('sk_test_xxx'),
    cache=RedisCache(host='localhost')
)
```

**Key Changes:**
- Depend on protocols/ABCs
- Easy to swap implementations
- Easy to test with mocks
- Follows DIP

## Anti-Pattern: Import Coupling

### Description

Importing and using concrete classes directly creates tight coupling.

### BAD Example

```python
# BAD: Importing concrete implementations
from myapp.repositories.django_user_repo import DjangoUserRepository
from myapp.email.smtp_email import SMTPEmailSender
from myapp.payments.stripe_gateway import StripeGateway

class OrderService:
    def __init__(self):
        self.user_repo = DjangoUserRepository()
        self.email_sender = SMTPEmailSender()
        self.payment_gateway = StripeGateway('sk_test_xxx')
```

### Why It's Problematic

- **Module coupling**: Tightly coupled to specific implementations
- **Hard to test**: Can't mock at module level
- **Deployment coupling**: Can't change implementation without code change
- **Circular dependencies**: More likely with concrete imports

### GOOD Example

```python
# GOOD: Import protocols/interfaces
from myapp.repositories.protocols import UserRepository
from myapp.email.protocols import EmailSender
from myapp.payments.protocols import PaymentGateway

class OrderService:
    def __init__(self,
                 user_repo: UserRepository,
                 email_sender: EmailSender,
                 payment_gateway: PaymentGateway):
        self.user_repo = user_repo
        self.email_sender = email_sender
        self.payment_gateway = payment_gateway

# Factory for creating configured instances
class ServiceFactory:
    @staticmethod
    def create_order_service() -> OrderService:
        return OrderService(
            user_repo=DjangoUserRepository(),
            email_sender=SMTPEmailSender(),
            payment_gateway=StripeGateway(config.STRIPE_KEY)
        )
```

**Key Changes:**
- Import protocols, not implementations
- Factory handles concrete instantiation
- Configuration centralized

## Detection Checklist

### Code Review Questions

- [ ] Does class depend on concrete implementations?
- [ ] Are classes instantiated within methods?
- [ ] Can't swap implementations without code changes?
- [ ] Can't test without full environment?
- [ ] Are concrete classes imported directly?

### Common Symptoms

- **Concrete instantiation**: `ClassName()` in methods
- **Hardcoded dependencies**: Specific implementations in constructors
- **Test difficulties**: Can't use mocks easily
- **Configuration coupling**: Hard to change implementations
