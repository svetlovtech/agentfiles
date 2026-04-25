# High Cohesion Examples - Python

## Introduction

This document provides paired examples of BAD and GOOD implementations of the High Cohesion principle in Python. High Cohesion means a class should have a single, well-focused responsibility.

## Example 1: God Class

### BAD Example

```python
class UserService:
    # BAD: Multiple unrelated responsibilities
    def create_user(self, data): pass
    def validate_user(self, user): pass
    def send_welcome_email(self, user): pass
    def generate_report(self): pass
    def backup_data(self): pass
    def calculate_discount(self, user): pass
    def log_user_activity(self, user): pass
    def format_user_data(self, user): pass
```

### GOOD Example

```python
class UserService:
    def create_user(self, data: User) -> User:
        self.user_repo.save(data)

class UserValidator:
    def validate(self, user: User) -> List[str]:
        errors = []
        if not user.email:
            errors.append("Email required")
        return errors

class EmailService:
    def send_welcome(self, user: User):
        self.email_client.send(to=user.email, subject="Welcome")

class ReportService:
    def generate_user_report(self) -> dict:
        return self.user_repo.get_statistics()

class DiscountService:
    def calculate_user_discount(self, user: User) -> float:
        return 0.1 if user.is_vip else 0.0
```

**Improvements:**
- Single responsibility per class
- Each class highly cohesive
- Easy to test and maintain
- Clear separation of concerns

## Example 2: Low Cohesion Method

### BAD Example

```python
class OrderService:
    def process_order(self, order_id):
        # BAD: Method doing many unrelated things
        order = self.order_repo.find(order_id)
        self._validate_order(order)
        self._calculate_totals(order)
        self._charge_payment(order)
        self._update_inventory(order)
        self._send_email(order)
        self._log_activity(order)
        self._update_analytics(order)
        self._archive_old_orders()
```

### GOOD Example

```python
class OrderService:
    def process_order(self, order_id: int) -> Order:
        order = self.order_repo.find(order_id)
        self._validate_order(order)
        self._charge_payment(order)
        self._update_inventory(order)
        return order

class OrderValidator:
    def validate(self, order: Order):
        if not order.items:
            raise ValidationError("Order needs items")

class PaymentService:
    def charge(self, order: Order):
        self.payment_gateway.process(order.total, order.payment_details)

class InventoryService:
    def reserve(self, order: Order):
        for item in order.items:
            self.inventory.deduct(item.product_id, item.quantity)

class EmailService:
    def send_order_confirmation(self, order: Order):
        self.email_client.send(to=order.customer.email, subject="Order confirmed")

class AnalyticsService:
    def track_order(self, order: Order):
        self.analytics.track('order_processed', {'amount': order.total})
```

**Improvements:**
- Each method focused on single concern
- Each service has cohesive responsibility
- Easy to understand and modify
- Better testability

## Example 3: Mixed Responsibilities in Data Class

### BAD Example

```python
class Order:
    # BAD: Data class with business logic, formatting, persistence
    def __init__(self, customer_id, items, status):
        self.customer_id = customer_id
        self.items = items
        self.status = status
    
    def calculate_total(self): pass
    def validate(self): pass
    def save(self): pass
    def delete(self): pass
    def to_json(self): pass
    def to_csv(self): pass
    def send_email(self): pass
```

### GOOD Example

```python
class Order:
    # GOOD: Data and business logic only
    def __init__(self, customer_id: int, items: List[OrderItem]):
        self.customer_id = customer_id
        self.items = items
        self.status = 'PENDING'
    
    def calculate_total(self) -> float:
        return sum(item.subtotal() for item in self.items)
    
    def validate(self) -> List[str]:
        if not self.items:
            return ["Order must have items"]
        return []

class OrderRepository:
    def save(self, order: Order) -> Order:
        # Persistence logic
        pass
    
    def delete(self, order_id: int) -> None:
        # Deletion logic
        pass

class OrderFormatter:
    def to_json(self, order: Order) -> str:
        return json.dumps({
            'id': order.id,
            'total': order.calculate_total()
        })
    
    def to_csv(self, order: Order) -> str:
        return f"{order.id},{order.calculate_total()}\n"

class OrderEmailService:
    def send_confirmation(self, order: Order):
        self.email_client.send(to=order.customer.email, body="Order confirmed")
```

**Improvements:**
- Order focused on data and core behavior
- Persistence in separate repository
- Formatting in dedicated formatter
- Email in dedicated service
- Each class highly cohesive

## Language-Specific Notes

### Python-Specific Cohesion Patterns

- **Modules**: Use modules to group related classes
- **Packages**: Group related modules together
- **Mixins**: Careful use for adding behavior
- **Dataclasses**: Good for simple data-only classes
- **@property**: Use for derived data in cohesive classes

### Common Pitfalls

1. **Batteries-included mentality**: Putting everything in one class
   - Split into focused classes

2. **Utility class abuse**: "Utils" class with everything
   - Create specific service classes

3. **Fat views/controllers**: Too much logic in one view
   - Extract to services and domain classes
