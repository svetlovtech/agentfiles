# Indirection Examples - Python

## Introduction

This document provides paired examples of BAD and GOOD implementations of Indirection pattern in Python.

## Example 1: Direct Service Calls

### BAD Example

```python
class OrderController:
    def create_order(self, request):
        # BAD: Direct calls to multiple services
        user_service = UserService()
        inventory_service = InventoryService()
        payment_service = PaymentService()
        email_service = EmailService()
        
        user = user_service.get_user(request['user_id'])
        inventory_service.check_stock(request['items'])
        payment_service.process(request['payment'])
        email_service.send_confirmation(user)
```

### GOOD Example

```python
class OrderFacade:
    def __init__(self,
                 user_service: UserService,
                 inventory_service: InventoryService,
                 payment_service: PaymentService,
                 email_service: EmailService):
        self.user_service = user_service
        self.inventory_service = inventory_service
        self.payment_service = payment_service
        self.email_service = email_service
    
    def create_order(self, request: dict) -> Order:
        # GOOD: Single point of indirection
        user = self.user_service.get_user(request['user_id'])
        self.inventory_service.check_stock(request['items'])
        self.payment_service.process(request['payment'])
        self.email_service.send_confirmation(user)

class OrderController:
    def __init__(self, order_facade: OrderFacade):
        self.facade = order_facade
    
    def create_order(self, request: dict) -> Order:
        # GOOD: Single call to facade
        return self.facade.create_order(request)
```

**Improvements:**
- Facade provides indirection
- Controller simplified
- Easy to modify underlying services
- Clear separation

## Example 2: Direct Database Access

### BAD Example

```python
class OrderService:
    def get_order(self, order_id):
        # BAD: Direct database access
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
        return cursor.fetchone()
```

### GOOD Example

```python
class OrderRepository(ABC):
    @abstractmethod
    def find_by_id(self, order_id: int) -> Order:
        pass

class SQLOrderRepository(OrderRepository):
    def __init__(self, db_connection):
        self.db = db_connection
    
    def find_by_id(self, order_id: int) -> Order:
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
        row = cursor.fetchone()
        return Order.from_db_row(row)

class OrderService:
    def __init__(self, order_repo: OrderRepository):
        # GOOD: Repository provides indirection from database
        self.order_repo = order_repo
    
    def get_order(self, order_id: int) -> Order:
        return self.order_repo.find_by_id(order_id)
```

**Improvements:**
- Repository provides abstraction
- Database details hidden
- Easy to swap implementations
- Lower coupling

## Example 3: Direct External API Calls

### BAD Example

```python
class OrderService:
    def process_payment(self, order):
        # BAD: Direct external API call
        import requests
        response = requests.post(
            'https://api.stripe.com/v1/charges',
            json={'amount': order.total, 'card': order.card}
        )
        return response.json()
```

### GOOD Example

```python
class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: float, card_details: dict) -> PaymentResult:
        pass

class StripeGateway(PaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def charge(self, amount: float, card_details: dict) -> PaymentResult:
        import requests
        response = requests.post(
            'https://api.stripe.com/v1/charges',
            json={'amount': amount, 'card': card_details},
            headers={'Authorization': f'Bearer {self.api_key}'}
        )
        return PaymentResult.from_response(response.json())

class OrderService:
    def __init__(self, payment_gateway: PaymentGateway):
        # GOOD: Gateway provides indirection from external API
        self.payment_gateway = payment_gateway
    
    def process_payment(self, order: Order) -> PaymentResult:
        return self.payment_gateway.charge(order.total, order.card_details)
```

**Improvements:**
- Gateway abstracts external API
- Easy to swap payment providers
- Error handling centralized
- Lower coupling

## Language-Specific Notes

### Python Indirection Patterns

- **ABC**: Use abstract base classes for interfaces
- **Protocol**: Use Protocol for structural typing
- **Middleware**: Use in web frameworks for cross-cutting concerns
- **Facade pattern**: Simplify complex subsystems
- **Proxy pattern**: Add indirection for lazy loading, caching, etc.
