# Pure Fabrication Examples - Python

## Introduction

This document provides paired examples of BAD and GOOD implementations of Pure Fabrication pattern in Python. Pure Fabrication creates a class that doesn't represent a domain concept but performs a specific function.

## Example 1: Missing Service Layer

### BAD Example

```python
class OrderController:
    def create_order(self, request):
        # BAD: Business logic in controller, no service layer
        order = Order.objects.create(customer_id=request['customer_id'])
        
        # Direct operations in controller
        for item in request['items']:
            OrderItem.objects.create(
                order_id=order.id,
                product_id=item['product_id'],
                quantity=item['quantity']
            )
        
        # Send email directly
        send_email(order.customer.email, 'Order created')
        
        # Update inventory directly
        for item in request['items']:
            product = Product.objects.get(id=item['product_id'])
            product.stock -= item['quantity']
            product.save()
```

### GOOD Example

```python
class OrderService:
    # GOOD: Pure fabrication - not a domain concept
    def __init__(self,
                 order_repo: OrderRepository,
                 product_repo: ProductRepository,
                 email_service: EmailService,
                 inventory_service: InventoryService):
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.email_service = email_service
        self.inventory_service = inventory_service
    
    def create_order(self, request: dict) -> Order:
        order = Order.create(request['customer_id'])
        
        for item in request['items']:
            order.add_item(item['product_id'], item['quantity'])
        
        self.order_repo.save(order)
        self.inventory_service.reserve_stock(order.items)
        self.email_service.send_order_confirmation(order)
        
        return order

class InventoryService:
    # GOOD: Pure fabrication - manages inventory
    def reserve_stock(self, items: List[OrderItem]):
        for item in items:
            product = self.product_repo.find_by_id(item.product_id)
            product.reserve_stock(item.quantity)
            self.product_repo.save(product)

class EmailService:
    # GOOD: Pure fabrication - handles email
    def send_order_confirmation(self, order: Order):
        self.email_client.send(
            to=order.customer.email,
            subject='Order Confirmation',
            body=f'Your order {order.id} has been received'
        )

class OrderController:
    def __init__(self, order_service: OrderService):
        # GOOD: Controller delegates to service
        self.order_service = order_service
    
    def create_order(self, request: dict) -> Order:
        return self.order_service.create_order(request)
```

**Improvements:**
- Service layer as pure fabrication
- Business logic in services
- Clear separation of concerns
- Reusable across contexts

## Example 2: Repository as Pure Fabrication

### BAD Example

```python
class OrderController:
    def get_order(self, order_id):
        # BAD: Direct database queries
        return Order.objects.get(id=order_id)
    
    def update_order_status(self, order_id, status):
        # BAD: Direct database updates
        Order.objects.filter(id=order_id).update(status=status)
```

### GOOD Example

```python
class OrderRepository(ABC):
    # GOOD: Pure fabrication - data access abstraction
    @abstractmethod
    def find_by_id(self, order_id: int) -> Order:
        pass
    
    @abstractmethod
    def save(self, order: Order) -> None:
        pass
    
    @abstractmethod
    def update_status(self, order_id: int, status: str) -> None:
        pass

class SQLOrderRepository(OrderRepository):
    # GOOD: Concrete implementation as pure fabrication
    def __init__(self, db_connection):
        self.db = db_connection
    
    def find_by_id(self, order_id: int) -> Order:
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
        row = cursor.fetchone()
        return Order.from_db_row(row)
    
    def save(self, order: Order) -> None:
        cursor = self.db.cursor()
        cursor.execute(
            'INSERT INTO orders (customer_id, status) VALUES (%s, %s)',
            (order.customer_id, order.status)
        )
        order.id = cursor.lastrowid
    
    def update_status(self, order_id: int, status: str) -> None:
        cursor = self.db.cursor()
        cursor.execute(
            'UPDATE orders SET status = %s WHERE id = %s',
            (status, order_id)
        )

class OrderController:
    def __init__(self, order_repo: OrderRepository):
        # GOOD: Repository provides abstraction
        self.order_repo = order_repo
    
    def get_order(self, order_id: int) -> Order:
        return self.order_repo.find_by_id(order_id)
    
    def update_order_status(self, order_id: int, status: str):
        self.order_repo.update_status(order_id, status)
```

**Improvements:**
- Repository as pure fabrication
- Database details hidden
- Easy to swap implementations
- Lower coupling

## Example 3: Validator as Pure Fabrication

### BAD Example

```python
class OrderService:
    def create_order(self, request):
        # BAD: Validation logic in service
        if not request.get('customer_id'):
            raise ValueError('Customer ID required')
        
        if not request.get('items') or len(request['items']) == 0:
            raise ValueError('Items required')
        
        for item in request['items']:
            if item.get('quantity', 0) <= 0:
                raise ValueError('Quantity must be positive')
```

### GOOD Example

```python
class OrderValidator:
    # GOOD: Pure fabrication - validation logic
    def __init__(self, product_repo: ProductRepository):
        self.product_repo = product_repo
    
    def validate_order_request(self, request: dict) -> List[str]:
        errors = []
        
        if not request.get('customer_id'):
            errors.append('Customer ID required')
        
        if not request.get('items') or len(request['items']) == 0:
            errors.append('Items required')
        
        for item in request.get('items', []):
            if item.get('quantity', 0) <= 0:
                errors.append(f'Invalid quantity for product {item.get("product_id")}')
        
        return errors

class OrderService:
    def __init__(self,
                 order_repo: OrderRepository,
                 validator: OrderValidator):
        self.order_repo = order_repo
        self.validator = validator
    
    def create_order(self, request: dict) -> Order:
        # GOOD: Delegate validation
        errors = self.validator.validate_order_request(request)
        if errors:
            raise ValidationError(errors)
        
        order = Order.create(request['customer_id'])
        self.order_repo.save(order)
        return order
```

**Improvements:**
- Validator as pure fabrication
- Validation logic centralized
- Reusable across contexts
- Clear single responsibility

## Language-Specific Notes

### Python Pure Fabrication Patterns

- **Service classes**: Classes that orchestrate domain objects
- **Repository classes**: Data access abstractions
- **Validator classes**: Validation logic
- **Factory classes**: Object creation logic
- **Utility modules**: Reusable helper functions
- **Not domain concepts**: Pure fabrications aren't real-world entities
