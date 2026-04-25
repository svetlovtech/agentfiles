# Low Coupling Examples - Python

## Introduction

This document provides paired examples of BAD and GOOD implementations of Low Coupling principle in Python.

## Example 1: Direct Dependency

### BAD Example

```python
class OrderService:
    def __init__(self):
        # BAD: Direct concrete dependencies
        self.db_connection = psycopg2.connect(host='localhost')
        self.email_sender = SMTPEmailSender()
        self.payment_gateway = StripeGateway('sk_test_xxx')
```

### GOOD Example

```python
class OrderService:
    def __init__(self,
                 db: Database,
                 email: EmailSender,
                 payment: PaymentGateway):
        # GOOD: Depend on abstractions
        self.db = db
        self.email = email
        self.payment = payment

# Usage with dependency injection
service = OrderService(
    db=PostgresDatabase(config),
    email=ConsoleEmailSender(),  # Easy to swap
    payment=StripeGateway(config.api_key)
)
```

**Improvements:**
- Dependencies injected
- Easy to test with mocks
- Easy to swap implementations
- Loose coupling

## Example 2: Concrete Class Coupling

### BAD Example

```python
class ReportService:
    def generate_report(self, user_id):
        # BAD: Direct dependency on concrete classes
        user = UserRepository()  # Tightly coupled
        orders = OrderRepository()  # Tightly coupled
        payments = PaymentRepository()  # Tightly coupled
        
        user_data = user.find(user_id)
        order_data = orders.get_user_orders(user_id)
        payment_data = payments.get_user_payments(user_id)
        
        return self._compile_report(user_data, order_data, payment_data)
```

### GOOD Example

```python
class ReportService:
    def __init__(self,
                 user_repo: UserRepository,
                 order_repo: OrderRepository,
                 payment_repo: PaymentRepository):
        # GOOD: Injected abstractions
        self.user_repo = user_repo
        self.order_repo = order_repo
        self.payment_repo = payment_repo
    
    def generate_report(self, user_id: int) -> dict:
        user_data = self.user_repo.find(user_id)
        order_data = self.order_repo.get_user_orders(user_id)
        payment_data = self.payment_repo.get_user_payments(user_id)
        
        return self._compile_report(user_data, order_data, payment_data)
```

**Improvements:**
- Repositories injected
- Can use different implementations
- Easy to test with mocks
- Lower coupling

## Example 3: Tight Service Coupling

### BAD Example

```python
class OrderController:
    def create_order(self, request):
        # BAD: Calling multiple services directly
        user_service = UserService()
        inventory_service = InventoryService()
        payment_service = PaymentService()
        email_service = EmailService()
        
        user = user_service.get_user(request['user_id'])
        inventory_service.check_stock(request['items'])
        payment = payment_service.process(request['payment'])
        email_service.send_confirmation(user)
```

### GOOD Example

```python
class OrderController:
    def __init__(self, order_service: OrderService):
        # GOOD: Single service dependency
        self.order_service = order_service
    
    def create_order(self, request: dict) -> Order:
        # GOOD: Single delegated call
        return self.order_service.create_order(request)

class OrderService:
    def __init__(self,
                 user_service: UserService,
                 inventory_service: InventoryService,
                 payment_service: PaymentService,
                 email_service: EmailService):
        # GOOD: All dependencies injected
        self.user_service = user_service
        self.inventory_service = inventory_service
        self.payment_service = payment_service
        self.email_service = email_service
    
    def create_order(self, request: dict) -> Order:
        user = self.user_service.get_user(request['user_id'])
        self.inventory_service.check_stock(request['items'])
        payment = self.payment_service.process(request['payment'])
        self.email_service.send_confirmation(user)
```

**Improvements:**
- Dependency injection
- Clear layer separation
- Testable design
- Lower coupling

## Language-Specific Notes

### Python-Specific Patterns

- **Protocols**: Use `Protocol` for interfaces
- **ABC**: Use `abc.ABC` for abstract base classes
- **Dependency injection**: Use constructor injection or framework DI
- **Type hints**: Improve clarity of dependencies

### Common Pitfalls

1. **Importing concrete classes**: Direct imports create coupling
   - Import protocols/interfaces, not concrete classes

2. **Creating instances in methods**: Tight coupling to concrete types
   - Inject dependencies via constructor

3. **Global state**: Creates hidden dependencies
   - Avoid global variables and singletons
