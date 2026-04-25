# Pure Fabrication Anti-Patterns - Python

## Anti-Pattern: Anemic Domain Model

### BAD Example

```python
class Order:
    def __init__(self, customer_id, items):
        self.customer_id = customer_id
        self.items = items

# All logic in services
```

### GOOD Example

```python
class Order:
    def calculate_total(self) -> float:
        return sum(item.subtotal() for item in self.items)

class OrderService:
    # Pure fabrication for orchestration
    def create_order(self, request):
        order = Order.create(request)
        self.order_repo.save(order)
        return order
```

## Detection Checklist

- [ ] No service layer
- [ ] All logic in controllers
- [ ] Anemic domain models
- [ ] No repository pattern
