# Information Expert Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern: Anemic Domain Model](#anti-pattern-anemic-domain-model)
- [Anti-Pattern: Feature Envy](#anti-pattern-feature-envy)
- [Anti-Pattern: Getter/Setter Anti-Pattern](#anti-pattern-gettersetter-anti-pattern)
- [Anti-Pattern: Primitive Obsession](#anti-pattern-primitive-obsession)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the Information Expert pattern in Python. The pattern states that responsibility should be assigned to the class that has the information necessary to fulfill the responsibility.

## Anti-Pattern: Anemic Domain Model

### Description

Domain objects that contain only data (fields) without behavior (methods). All business logic lives in services or controllers. This is essentially procedural programming with classes instead of structs.

### BAD Example

```python
class Order:
    # BAD: Only data, no behavior
    def __init__(self, customer_id, items, status, created_at):
        self.customer_id = customer_id
        self.items = items
        self.status = status
        self.created_at = created_at


class OrderItem:
    # BAD: Only data, no behavior
    def __init__(self, product_id, quantity, price):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price


class OrderService:
    # BAD: All business logic in service
    def calculate_total(self, order):
        return sum(item.price * item.quantity for item in order.items)
    
    def apply_discount(self, order, discount_rate):
        total = self.calculate_total(order)
        return total * (1 - discount_rate)
    
    def add_item(self, order, product_id, quantity, price):
        item = OrderItem(product_id, quantity, price)
        order.items.append(item)
        return item
    
    def validate_order(self, order):
        if not order.customer_id:
            raise ValueError("Customer required")
        if not order.items:
            raise ValueError("Items required")
    
    def can_ship(self, order):
        return order.status == 'PAID'
```

### Why It's Problematic

- **Violates OOP**: Objects should have behavior
- **Procedural style**: Just structs with procedures
- **Hard to reuse**: Logic trapped in services
- **Violates Information Expert**: Behavior not with data
- **Hard to maintain**: Business logic scattered
- **No encapsulation**: Everything accessible from services

### How to Fix

**Refactoring Steps:**
1. Identify operations on domain objects
2. Move methods to domain objects
3. Make services coordinate, not calculate
4. Use domain methods for behavior

### GOOD Example

```python
class Order:
    def __init__(self, customer_id: int):
        self.customer_id = customer_id
        self.items = []
        self.status = 'PENDING'
        self.created_at = datetime.now()
        self.discount_rate = 0.0
    
    # GOOD: Behavior with data
    def calculate_total(self) -> float:
        total = sum(item.subtotal() for item in self.items)
        return total * (1 - self.discount_rate)
    
    def add_item(self, product_id: int, quantity: int, price: float) -> OrderItem:
        item = OrderItem(product_id, quantity, price)
        self.items.append(item)
        return item
    
    def validate(self):
        if not self.customer_id:
            raise ValueError("Customer required")
        if not self.items:
            raise ValueError("Items required")
    
    def can_ship(self) -> bool:
        return self.status == 'PAID'
    
    def apply_discount(self, discount_rate: float):
        self.discount_rate = discount_rate


class OrderItem:
    def __init__(self, product_id: int, quantity: int, price: float):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price
    
    # GOOD: Behavior with data
    def subtotal(self) -> float:
        return self.price * self.quantity


class OrderService:
    # GOOD: Service coordinates, doesn't calculate
    def create_order(self, customer_id: int) -> Order:
        order = Order(customer_id)
        order.validate()
        self.order_repo.save(order)
        return order
    
    def process_order(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        if order.can_ship():
            self.shipping_service.ship(order)
            order.status = 'SHIPPED'
            self.order_repo.save(order)
```

**Key Changes:**
- Order has behavior with its data
- OrderItem calculates its own subtotal
- Services coordinate, not calculate
- Clear information expert assignment
- Better encapsulation

---

## Anti-Pattern: Feature Envy

### Description

A method that accesses more data from another class than its own. The method "envies" the features of the other class and should be moved there.

### BAD Example

```python
class OrderService:
    def process_order_discount(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # BAD: Feature envy - accessing order's data extensively
        total = sum(item.price * item.quantity for item in order.items)
        
        if len(order.items) > 5:
            total *= 0.9  # 10% bulk discount
        
        if order.customer.tier == 'VIP':
            total *= 0.85  # 15% VIP discount
        
        if order.customer.years_as_customer > 5:
            total *= 0.95  # 5% loyalty discount
        
        order.total = total
        
        # BAD: More feature envy
        if order.status == 'PENDING' and total > 0:
            order.status = 'PROCESSING'
        
        self.order_repo.save(order)


class ReportService:
    def generate_order_report(self, order_id: int) -> dict:
        order = self.order_repo.find_by_id(order_id)
        
        # BAD: Feature envy for both order and customer
        return {
            'order_id': order.id,
            'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
            'customer_email': order.customer.email,
            'customer_tier': order.customer.tier,
            'item_count': len(order.items),
            'total': sum(item.price * item.quantity for item in order.items),
            'status': order.status,
            'created_date': order.created_at.strftime('%Y-%m-%d'),
            'days_since_creation': (datetime.now() - order.created_at).days
        }


class InventoryService:
    def update_order_inventory(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # BAD: Feature envy for order's items
        for item in order.items:
            product = self.product_repo.find_by_id(item.product_id)
            product.stock -= item.quantity
            self.product_repo.save(product)
```

### Why It's Problematic

- **Violates encapsulation**: Accessing internal data
- **High coupling**: Tightly coupled to other classes
- **Hard to maintain**: Changes in accessed class affect envy method
- **Violates Information Expert**: Responsibility with wrong class
- **Code smell**: Method belongs in other class

### How to Fix

**Refactoring Steps:**
1. Identify methods accessing other class data
2. Move methods to the class that owns the data
3. Replace method calls with calls to moved methods
4. Simplify service layer

### GOOD Example

```python
class Order:
    def __init__(self, customer: Customer, items: List[OrderItem]):
        self.customer = customer
        self.items = items
        self.status = 'PENDING'
        self.created_at = datetime.now()
    
    # GOOD: Method uses order's own data
    def calculate_discounted_total(self) -> float:
        total = sum(item.subtotal() for item in self.items)
        total *= self._get_bulk_discount_multiplier()
        total *= self._get_customer_discount_multiplier()
        return total
    
    def _get_bulk_discount_multiplier(self) -> float:
        return 0.9 if len(self.items) > 5 else 1.0
    
    def _get_customer_discount_multiplier(self) -> float:
        discount = 1.0
        
        if self.customer.tier == 'VIP':
            discount *= 0.85
        
        if self.customer.years_as_customer > 5:
            discount *= 0.95
        
        return discount
    
    def can_process(self) -> bool:
        return self.status == 'PENDING' and self.calculate_discounted_total() > 0
    
    def to_report_dict(self) -> dict:
        return {
            'order_id': self.id,
            'customer_name': self.customer.full_name,
            'customer_email': self.customer.email,
            'customer_tier': self.customer.tier,
            'item_count': len(self.items),
            'total': self.calculate_discounted_total(),
            'status': self.status,
            'created_date': self.created_at.strftime('%Y-%m-%d'),
            'days_since_creation': self.days_since_creation
        }
    
    @property
    def days_since_creation(self) -> int:
        return (datetime.now() - self.created_at).days
    
    def deduct_inventory(self, product_repo: ProductRepository):
        for item in self.items:
            product = product_repo.find_by_id(item.product_id)
            product.deduct_stock(item.quantity)
            product_repo.save(product)


class Customer:
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Product:
    def deduct_stock(self, quantity: int):
        self.stock -= quantity


class OrderService:
    def process_order(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # GOOD: Use order's methods
        if order.can_process():
            order.calculate_discounted_total()
            order.status = 'PROCESSING'
            self.order_repo.save(order)


class ReportService:
    def generate_order_report(self, order_id: int) -> dict:
        order = self.order_repo.find_by_id(order_id)
        
        # GOOD: Order knows how to represent itself
        return order.to_report_dict()


class InventoryService:
    def update_order_inventory(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # GOOD: Order handles its inventory deduction
        order.deduct_inventory(self.product_repo)
```

**Key Changes:**
- Methods moved to owning classes
- Low coupling between classes
- Clear information expert assignment
- Services delegate to domain methods

---

## Anti-Pattern: Getter/Setter Anti-Pattern

### Description

Using explicit getters and setters for all fields, often with no additional logic. In Python, this is usually unnecessary and violates the language's idioms.

### BAD Example

```python
class User:
    def __init__(self, name, email, age):
        self._name = name
        self._email = email
        self._age = age
    
    # BAD: Unnecessary getters and setters
    def get_name(self):
        return self._name
    
    def set_name(self, name):
        if not name or len(name) < 2:
            raise ValueError("Invalid name")
        self._name = name
    
    def get_email(self):
        return self._email
    
    def set_email(self, email):
        if '@' not in email:
            raise ValueError("Invalid email")
        self._email = email
    
    def get_age(self):
        return self._age
    
    def set_age(self, age):
        if age < 0:
            raise ValueError("Age cannot be negative")
        self._age = age
    
    def get_full_name(self):
        return f"{self._name}"


class Order:
    def __init__(self, items):
        self._items = items
    
    def get_items(self):
        return self._items
    
    def set_items(self, items):
        if not items:
            raise ValueError("Order must have items")
        self._items = items
    
    def get_total(self):
        total = 0
        for item in self._items:
            total += item.get_price() * item.get_quantity()
        return total
```

### Why It's Problematic

- **Not Pythonic**: Python doesn't need getters/setters
- **Verbose**: Unnecessary boilerplate
- **No encapsulation benefit**: Still exposes internal state
- **Harder to use**: `obj.get_name()` vs `obj.name`
- **Violates DRY**: Boilerplate repeated

### How to Fix

**Refactoring Steps:**
1. Use direct attribute access
2. Use @property for computed fields
3. Use @property.setter only when validation needed
4. Keep it simple

### GOOD Example

```python
class User:
    # GOOD: Direct attributes with properties for computed/validation
    def __init__(self, name: str, email: str, age: int):
        self.name = name
        self.email = email
        self.age = age
    
    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, value: str):
        if not value or len(value) < 2:
            raise ValueError("Invalid name")
        self._name = value
    
    @property
    def email(self) -> str:
        return self._email
    
    @email.setter
    def email(self, value: str):
        if '@' not in value:
            raise ValueError("Invalid email")
        self._email = value
    
    @property
    def age(self) -> int:
        return self._age
    
    @age.setter
    def age(self, value: int):
        if value < 0:
            raise ValueError("Age cannot be negative")
        self._age = value
    
    # GOOD: Computed property
    @property
    def full_name(self) -> str:
        return f"{self.name}"


class Order:
    def __init__(self, items: List[OrderItem]):
        self.items = items  # GOOD: Direct access
    
    # GOOD: Computed property
    @property
    def total(self) -> float:
        return sum(item.price * item.quantity for item in self.items)


# Usage is cleaner
user = User("John", "john@example.com", 30)
print(user.name)  # Direct access
user.name = "Jane"  # Uses setter if defined

order = Order(items)
print(order.total)  # Computed property
```

**Key Changes:**
- Direct attribute access
- Properties for computed fields
- Setters only when validation needed
- Pythonic and clean
- Less boilerplate

---

## Anti-Pattern: Primitive Obsession

### Description

Using primitive types (int, str, float) to represent domain concepts that should have their own types. This leads to primitive types carrying business meaning without enforcement.

### BAD Example

```python
class Order:
    # BAD: Primitives for domain concepts
    def __init__(self, customer_id, email, phone, price, quantity, 
                 order_date, ship_date, status):
        self.customer_id = customer_id  # int - should be CustomerId
        self.email = email  # str - should be Email
        self.phone = phone  # str - should be PhoneNumber
        self.price = price  # float - should be Money
        self.quantity = quantity  # int - should be Quantity
        self.order_date = order_date  # str - should be Date
        self.ship_date = ship_date  # str - should be Date
        self.status = status  # str - should be OrderStatus


class OrderService:
    def validate_order(self, order):
        # BAD: Validation scattered, using primitives
        if not isinstance(order.customer_id, int) or order.customer_id <= 0:
            raise ValueError("Invalid customer ID")
        
        if '@' not in order.email or len(order.email) < 5:
            raise ValueError("Invalid email")
        
        if not order.phone.startswith('+'):
            raise ValueError("Invalid phone")
        
        if order.price < 0:
            raise ValueError("Invalid price")
        
        if order.quantity <= 0:
            raise ValueError("Invalid quantity")
        
        if order.status not in ['PENDING', 'PAID', 'SHIPPED']:
            raise ValueError("Invalid status")
        
        try:
            datetime.strptime(order.order_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid order date")
    
    def format_price(self, price):
        # BAD: Formatting logic in service
        return f"${price:.2f}"
```

### Why It's Problematic

- **No type safety**: Primitives don't enforce business rules
- **Validation scattered**: Everywhere primitives are used
- **No encapsulation**: Anyone can create invalid values
- **Hard to understand**: Primitive values lose meaning
- **Code duplication**: Validation repeated everywhere

### How to Fix

**Refactoring Steps:**
1. Identify domain concepts
2. Create value objects with validation
3. Use value objects instead of primitives
4. Encapsulate business rules

### GOOD Example

```python
class CustomerId:
    def __init__(self, value: int):
        if not isinstance(value, int) or value <= 0:
            raise ValueError("Customer ID must be positive integer")
        self.value = value


class Email:
    def __init__(self, value: str):
        if '@' not in value or len(value) < 5:
            raise ValueError("Invalid email")
        self.value = value
    
    def __str__(self):
        return self.value


class PhoneNumber:
    def __init__(self, value: str):
        if not value.startswith('+'):
            raise ValueError("Phone must start with +")
        self.value = value
    
    def __str__(self):
        return self.value


class Money:
    def __init__(self, amount: float, currency: str = 'USD'):
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        self.amount = amount
        self.currency = currency
    
    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
    
    def __mul__(self, multiplier: float) -> 'Money':
        return Money(self.amount * multiplier, self.currency)
    
    def format(self) -> str:
        return f"${self.amount:.2f} {self.currency}"
    
    def __str__(self):
        return self.format()


class Quantity:
    def __init__(self, value: int):
        if value <= 0:
            raise ValueError("Quantity must be positive")
        self.value = value
    
    def __add__(self, other: 'Quantity') -> 'Quantity':
        return Quantity(self.value + other.value)
    
    def __mul__(self, multiplier: int) -> Quantity:
        return Quantity(self.value * multiplier)


class OrderStatus:
    VALID_STATUSES = ['PENDING', 'PAID', 'SHIPPED', 'COMPLETED', 'CANCELLED']
    
    def __init__(self, value: str):
        if value not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {value}")
        self.value = value
    
    def __str__(self):
        return self.value
    
    def can_transition_to(self, new_status: 'OrderStatus') -> bool:
        valid = {
            'PENDING': ['PAID', 'CANCELLED'],
            'PAID': ['SHIPPED'],
            'SHIPPED': ['COMPLETED']
        }
        return new_status.value in valid.get(self.value, [])


class OrderDate:
    def __init__(self, value: str):
        try:
            self._date = datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid date format: {value}")
        self._value = value
    
    def __str__(self):
        return self._value
    
    def days_until(self, other: 'OrderDate') -> int:
        return (other._date - self._date).days


class Order:
    # GOOD: Value objects instead of primitives
    def __init__(self, customer_id: CustomerId, email: Email, 
                 phone: PhoneNumber, price: Money, quantity: Quantity,
                 order_date: OrderDate, ship_date: OrderDate, 
                 status: OrderStatus):
        self.customer_id = customer_id
        self.email = email
        self.phone = phone
        self.price = price
        self.quantity = quantity
        self.order_date = order_date
        self.ship_date = ship_date
        self.status = status
    
    # GOOD: Validation built into value objects
    # No separate validation needed - already validated at construction


class OrderService:
    def format_order_price(self, order: Order) -> str:
        # GOOD: Money knows how to format itself
        return order.price.format()
    
    def calculate_total(self, price: Money, quantity: Quantity) -> Money:
        # GOOD: Type-safe operations
        return price * quantity.value
```

**Key Changes:**
- Value objects for domain concepts
- Validation in constructors
- Type safety through value objects
- Self-describing code
- No duplicate validation

---

## Detection Checklist

Use this checklist to identify Information Expert violations in Python code:

### Code Review Questions

- [ ] Do domain objects have only data (no methods)?
- [ ] Do services manipulate other objects' data extensively?
- [ ] Are getters/setters used without additional logic?
- [ ] Are primitives used for domain concepts instead of value objects?
- [ ] Is validation logic scattered across services?
- [ ] Do methods access more data from other classes than their own?

### Automated Detection

- **Method-to-field ratio**: Classes with low method-to-field ratio
- **Parameter coupling**: Methods with many parameters from other objects
- **Primitive overuse**: Frequent primitive types for business concepts
- **Validation duplication**: Same validation in multiple places

### Manual Inspection Techniques

1. **Read domain classes**: If they have no methods, they're anemic
2. **Check service methods**: If they access many other object fields, feature envy
3. **Look for getters/setters**: Unnecessary in most Python code
4. **Trace validation**: If scattered, value objects needed

### Common Symptoms

- **Anemic models**: Domain objects with only __init__
- **Fat services**: Services with all business logic
- **Feature envy**: Methods accessing other class data
- **Primitive abuse**: Strings/ints for complex concepts
- **Validation everywhere**: Same rules in multiple places

---

## Language-Specific Notes

### Common Causes in Python

- **Easy to create data classes**: Dataclasses encourage anemic models
- **No enforcement**: Language doesn't force behavior with data
- **Rapid prototyping**: Quick to put logic in services
- **Framework influence**: Django models encourage anemic design

### Language Features that Enable Anti-Patterns

- **Dynamic typing**: Can pass any primitive anywhere
- **Easy class creation**: Simple to make data-only classes
- **Property decorators**: Can hide complexity
- **Dataclasses**: Make anemic models even easier

### Framework-Specific Anti-Patterns

- **Django**: Anemic models with all logic in services
- **Pydantic**: Validation in validators instead of value objects
- **SQLAlchemy**: Plain classes without behavior

### Tooling Support

- **Pylint**: Detects method-to-field ratio issues
- **Mypy**: Type hints can reveal primitive obsession
- **Pytest**: Testing reveals tight coupling
- **Sourcery**: Suggests moving methods to data classes
