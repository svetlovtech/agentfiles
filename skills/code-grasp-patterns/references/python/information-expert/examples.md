# Information Expert Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Order Calculations](#example-1-order-calculations)
- [Example 2: Validation Logic](#example-2-validation-logic)
- [Example 3: Data Transformation](#example-3-data-transformation)
- [Example 4: State Transitions](#example-4-state-transitions)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the Information Expert pattern in Python. The pattern states that responsibility should be assigned to the class that has the information necessary to fulfill the responsibility.

## Example 1: Order Calculations

### BAD Example: Feature Envy

```python
class OrderService:
    def calculate_order_total(self, order_id: int) -> float:
        # BAD: Service doing calculations on order's data
        order = self.order_repo.find_by_id(order_id)
        
        total = 0
        for item in order.items:
            total += item.price * item.quantity
        
        # BAD: Discount calculation in service
        if total > 1000:
            total *= 0.9  # 10% discount
        
        # BAD: Tax calculation in service
        total *= 1.08  # 8% tax
        
        return total
    
    def calculate_order_subtotal(self, order_id: int) -> float:
        # BAD: Another calculation in service
        order = self.order_repo.find_by_id(order_id)
        return sum(item.price * item.quantity for item in order.items)
```

**Problems:**
- Feature envy: Service envious of Order's data
- Calculations not where data lives
- Order class is anemic
- Hard to reuse logic
- Violates Information Expert

### GOOD Example: Behavior in Information Expert

```python
class Order:
    def __init__(self, customer_id: int, items: List[OrderItem]):
        self.customer_id = customer_id
        self.items = items
        self.discount_multiplier = 1.0
        self.tax_rate = 0.08
    
    # GOOD: Calculations in the object that has the data
    def calculate_total(self) -> float:
        subtotal = self.calculate_subtotal()
        return self._apply_discount_and_tax(subtotal)
    
    def calculate_subtotal(self) -> float:
        # GOOD: Subtotal calculation where items live
        return sum(item.subtotal() for item in self.items)
    
    def apply_discount(self, discount: float):
        self.discount_multiplier = 1.0 - discount
    
    def _apply_discount_and_tax(self, amount: float) -> float:
        discounted = amount * self.discount_multiplier
        return discounted * (1 + self.tax_rate)


class OrderItem:
    def __init__(self, product_id: int, quantity: int, price: float):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price
    
    # GOOD: Each item knows its own subtotal
    def subtotal(self) -> float:
        return self.price * self.quantity


class OrderService:
    def get_order_total(self, order_id: int) -> float:
        # GOOD: Delegate to information expert
        order = self.order_repo.find_by_id(order_id)
        return order.calculate_total()
```

**Improvements:**
- Behavior placed with data
- Order class not anemic
- Easy to reuse calculations
- Clear information expert assignment
- Better encapsulation

### Explanation

The GOOD example follows Information Expert by placing calculation methods in the Order class, which has the data needed for calculations. OrderItem calculates its own subtotal. OrderService only delegates, respecting that Order is the information expert for its own calculations.

---

## Example 2: Validation Logic

### BAD Example: Validation in Service Layer

```python
class OrderService:
    def validate_order(self, order: Order) -> List[str]:
        errors = []
        
        # BAD: Checking order's data in service
        if not order.customer_id:
            errors.append("Customer required")
        
        if not order.items or len(order.items) == 0:
            errors.append("Order must have items")
        
        # BAD: Checking each item in service
        for item in order.items:
            if item.quantity <= 0:
                errors.append(f"Invalid quantity for item {item.product_id}")
            
            if item.price < 0:
                errors.append(f"Invalid price for item {item.product_id}")
        
        # BAD: Order-specific rules in service
        if order.calculate_total() > 10000:
            errors.append("Order total exceeds maximum")
        
        return errors


class UserValidator:
    def validate_user(self, user: User) -> List[str]:
        errors = []
        
        # BAD: Validating user's data externally
        if not user.email or '@' not in user.email:
            errors.append("Invalid email")
        
        if len(user.password) < 8:
            errors.append("Password too short")
        
        if not user.age or user.age < 18:
            errors.append("User must be 18 or older")
        
        return errors
```

**Problems:**
- Validation logic separated from data
- Objects don't know their validity
- Anemic domain model
- Validation rules scattered
- Hard to maintain invariants

### GOOD Example: Self-Validation in Domain Objects

```python
class Order:
    def __init__(self, customer_id: int, items: List[OrderItem]):
        self.customer_id = customer_id
        self.items = items
        self.MAX_TOTAL = 10000
    
    # GOOD: Object validates itself
    def validate(self) -> List[str]:
        errors = []
        
        if not self.customer_id:
            errors.append("Customer required")
        
        if not self.items or len(self.items) == 0:
            errors.append("Order must have items")
        
        # GOOD: Delegation to item validation
        for item in self.items:
            errors.extend(item.validate())
        
        total = self.calculate_total()
        if total > self.MAX_TOTAL:
            errors.append(f"Order total {total} exceeds maximum {self.MAX_TOTAL}")
        
        return errors
    
    def is_valid(self) -> bool:
        return len(self.validate()) == 0


class OrderItem:
    def __init__(self, product_id: int, quantity: int, price: float):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price
    
    # GOOD: Each item validates itself
    def validate(self) -> List[str]:
        errors = []
        
        if self.quantity <= 0:
            errors.append(f"Invalid quantity {self.quantity} for item {self.product_id}")
        
        if self.price < 0:
            errors.append(f"Invalid price {self.price} for item {self.product_id}")
        
        return errors
    
    def is_valid(self) -> bool:
        return len(self.validate()) == 0


class User:
    MIN_AGE = 18
    MIN_PASSWORD_LENGTH = 8
    
    def __init__(self, email: str, password: str, age: int = None):
        self.email = email
        self.password = password
        self.age = age
    
    # GOOD: User validates its own data
    def validate(self) -> List[str]:
        errors = []
        
        if not self.email or '@' not in self.email:
            errors.append("Invalid email")
        
        if len(self.password) < self.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters")
        
        if self.age is not None and self.age < self.MIN_AGE:
            errors.append(f"User must be {self.MIN_AGE} or older")
        
        return errors
    
    def is_valid(self) -> bool:
        return len(self.validate()) == 0


class OrderService:
    def create_order(self, order_data: dict) -> Order:
        order = Order.create(order_data)
        
        # GOOD: Let object validate itself
        if not order.is_valid():
            raise ValidationError(order.validate())
        
        self.order_repo.save(order)
        return order
```

**Improvements:**
- Objects validate themselves
- Validation logic with data
- Clear invariants
- Easy to maintain
- Better encapsulation

### Explanation

The GOOD example follows Information Expert by having each domain object validate its own data. Order validates itself and delegates validation to OrderItems. User validates its own data. This ensures validation rules stay with the data they validate, making the code more maintainable and encapsulated.

---

## Example 3: Data Transformation

### BAD Example: Transformation in Service Layer

```python
class UserService:
    def get_user_profile_response(self, user_id: int) -> dict:
        user = self.user_repo.find_by_id(user_id)
        
        # BAD: Transforming user data in service
        return {
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'full_name': f"{user.first_name} {user.last_name}",
            'age': user.calculate_age(),
            'is_adult': user.age >= 18,
            'account_status': 'active' if user.is_active else 'inactive',
            'registration_date': user.created_at.strftime('%Y-%m-%d'),
            'total_orders': self.order_service.get_user_order_count(user.id)
        }


class OrderService:
    def get_order_summary(self, order_id: int) -> dict:
        order = self.order_repo.find_by_id(order_id)
        
        # BAD: Transforming order data in service
        return {
            'order_id': order.id,
            'customer_name': f"{order.customer.first_name} {order.customer.last_name}",
            'item_count': len(order.items),
            'total': order.calculate_total(),
            'tax': order.calculate_total() * 0.08,
            'shipping': self._calculate_shipping(order.calculate_subtotal()),
            'status_display': order.status.replace('_', ' ').title(),
            'created_date': order.created_at.strftime('%Y-%m-%d %H:%M')
        }
```

**Problems:**
- Transformation logic not where data lives
- Format logic duplicated
- Objects don't know how to represent themselves
- Violates Information Expert

### GOOD Example: Transformation in Domain Objects

```python
class User:
    def __init__(self, first_name: str, last_name: str, email: str, 
                 birth_date: datetime, is_active: bool):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.birth_date = birth_date
        self.is_active = is_active
        self.created_at = datetime.now()
    
    # GOOD: Object knows how to calculate derived data
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self) -> int:
        today = datetime.now().date()
        birth = self.birth_date.date()
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    
    @property
    def is_adult(self) -> bool:
        return self.age >= 18
    
    # GOOD: Object knows how to represent itself
    def to_profile_dict(self, order_count: int = None) -> dict:
        data = {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'full_name': self.full_name,
            'age': self.age,
            'is_adult': self.is_adult,
            'account_status': 'active' if self.is_active else 'inactive',
            'registration_date': self.created_at.strftime('%Y-%m-%d')
        }
        
        if order_count is not None:
            data['total_orders'] = order_count
        
        return data


class Order:
    def __init__(self, customer: User, items: List[OrderItem], status: str):
        self.customer = customer
        self.items = items
        self.status = status
        self.created_at = datetime.now()
        self.SHIPPING_THRESHOLD = 50.0
    
    # GOOD: Object knows how to represent itself
    def to_summary_dict(self) -> dict:
        subtotal = self.calculate_subtotal()
        
        return {
            'order_id': self.id,
            'customer_name': self.customer.full_name,
            'item_count': len(self.items),
            'total': self.calculate_total(),
            'tax': self.calculate_tax(),
            'shipping': self._calculate_shipping(subtotal),
            'status_display': self._format_status(),
            'created_date': self.created_at.strftime('%Y-%m-%d %H:%M')
        }
    
    def calculate_subtotal(self) -> float:
        return sum(item.subtotal() for item in self.items)
    
    def calculate_tax(self) -> float:
        return self.calculate_subtotal() * 0.08
    
    def _calculate_shipping(self, subtotal: float) -> float:
        return 0 if subtotal >= self.SHIPPING_THRESHOLD else 9.99
    
    def _format_status(self) -> str:
        return self.status.replace('_', ' ').title()


class UserService:
    def get_user_profile(self, user_id: int) -> dict:
        user = self.user_repo.find_by_id(user_id)
        order_count = self.order_service.get_user_order_count(user.id)
        
        # GOOD: Delegate transformation to domain object
        return user.to_profile_dict(order_count)
```

**Improvements:**
- Objects know how to transform their data
- Format logic encapsulated
- Derived data calculated in right place
- Clear information expert assignment

### Explanation

The GOOD example follows Information Expert by having domain objects know how to transform and represent their own data. User has properties for derived data (full_name, age) and a method to create a profile dictionary. Order knows how to create a summary dictionary with formatted status. Services only orchestrate data gathering.

---

## Example 4: State Transitions

### BAD Example: State Management in Service Layer

```python
class OrderService:
    def process_order(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # BAD: Checking and changing state in service
        if order.status == 'PENDING':
            if self._validate_stock(order):
                order.status = 'PROCESSING'
                order.processed_at = datetime.now()
        
        elif order.status == 'PROCESSING':
            if self._process_payment(order):
                order.status = 'PAID'
                order.paid_at = datetime.now()
        
        elif order.status == 'PAID':
            if self._ship_order(order):
                order.status = 'SHIPPED'
                order.shipped_at = datetime.now()
        
        elif order.status == 'SHIPPED':
            if self._confirm_delivery(order):
                order.status = 'COMPLETED'
                order.completed_at = datetime.now()
        
        self.order_repo.save(order)
        return order
    
    def cancel_order(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # BAD: Cancel logic in service
        if order.status in ['PENDING', 'PROCESSING']:
            order.status = 'CANCELLED'
            order.cancelled_at = datetime.now()
        else:
            raise ValueError(f"Cannot cancel order in status {order.status}")
        
        self.order_repo.save(order)
        return order
```

**Problems:**
- State transitions managed externally
- Order doesn't know its valid transitions
- Business rules scattered
- Hard to maintain state machine
- Violates Information Expert

### GOOD Example: State Management in Domain Object

```python
class Order:
    VALID_TRANSITIONS = {
        'PENDING': ['PROCESSING', 'CANCELLED'],
        'PROCESSING': ['PAID', 'CANCELLED'],
        'PAID': ['SHIPPED', 'REFUNDED'],
        'SHIPPED': ['COMPLETED', 'RETURNED'],
        'COMPLETED': [],
        'CANCELLED': [],
        'REFUNDED': [],
        'RETURNED': []
    }
    
    def __init__(self, customer_id: int, items: List[OrderItem]):
        self.customer_id = customer_id
        self.items = items
        self.status = 'PENDING'
        self.created_at = datetime.now()
        self._set_timestamp('created')
    
    # GOOD: Order knows its valid transitions
    def transition_to(self, new_status: str):
        valid_transitions = self.VALID_TRANSITIONS[self.status]
        
        if new_status not in valid_transitions:
            raise InvalidStateTransitionError(
                self.status, new_status, valid_transitions
            )
        
        self.status = new_status
        
        # Set appropriate timestamp
        if new_status == 'PROCESSING':
            self._set_timestamp('processed')
        elif new_status == 'PAID':
            self._set_timestamp('paid')
        elif new_status == 'SHIPPED':
            self._set_timestamp('shipped')
        elif new_status == 'COMPLETED':
            self._set_timestamp('completed')
        elif new_status == 'CANCELLED':
            self._set_timestamp('cancelled')
    
    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.VALID_TRANSITIONS[self.status]
    
    # GOOD: Business methods that handle state
    def process(self):
        self._validate_stock()
        self.transition_to('PROCESSING')
    
    def pay(self):
        if not self.can_transition_to('PAID'):
            raise InvalidStateError(f"Cannot pay order in {self.status} state")
        
        self._process_payment()
        self.transition_to('PAID')
    
    def ship(self):
        if not self.can_transition_to('SHIPPED'):
            raise InvalidStateError(f"Cannot ship order in {self.status} state")
        
        self._ship_order()
        self.transition_to('SHIPPED')
    
    def complete(self):
        if not self.can_transition_to('COMPLETED'):
            raise InvalidStateError(f"Cannot complete order in {self.status} state")
        
        self._confirm_delivery()
        self.transition_to('COMPLETED')
    
    def cancel(self):
        if not self.can_transition_to('CANCELLED'):
            raise InvalidStateError(f"Cannot cancel order in {self.status} state")
        
        self._release_reserved_stock()
        self.transition_to('CANCELLED')
    
    def _set_timestamp(self, event: str):
        setattr(self, f'{event}_at', datetime.now())
    
    def _validate_stock(self):
        for item in self.items:
            product = Product.find(item.product_id)
            if product.stock < item.quantity:
                raise InsufficientStockError(product.id, item.quantity)
    
    def _process_payment(self):
        # Payment processing logic
        pass
    
    def _ship_order(self):
        # Shipping logic
        pass
    
    def _confirm_delivery(self):
        # Delivery confirmation logic
        pass
    
    def _release_reserved_stock(self):
        # Release stock logic
        pass


class OrderService:
    def process_order(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # GOOD: Delegate to domain object
        order.process()
        self.order_repo.save(order)
        return order
    
    def cancel_order(self, order_id: int):
        order = self.order_repo.find_by_id(order_id)
        
        # GOOD: Delegate to domain object
        order.cancel()
        self.order_repo.save(order)
        return order
```

**Improvements:**
- State transitions managed by Order
- Clear valid state transitions
- Business methods in domain object
- Easy to extend with new states
- Better encapsulation

### Explanation

The GOOD example follows Information Expert by having Order manage its own state transitions. Order knows valid transitions (defined in VALID_TRANSITIONS), has methods for state-changing operations, and sets appropriate timestamps. Services only delegate to domain methods, keeping business logic with the data.

---

## Language-Specific Notes

### Idioms and Patterns

- **@property**: Use for derived data fields
- **Dataclasses**: Use for simple value objects
- **`__str__` and `__repr__`**: For string representation
- **Validation decorators**: For common validation patterns

### Language Features

**Features that help:**
- **@property decorator**: Natural computed fields
- **Methods**: First-class functions for behavior
- **Type hints**: Improve clarity of signatures
- **Dataclasses**: Clean value object definitions

**Features that hinder:**
- **Mutable default arguments**: Can cause bugs in validation
- **Property setter complexity**: Can make logic hard to find

### Framework Considerations

- **Django**: Put behavior in model methods, not managers
- **Pydantic**: Use model validators for self-validation
- **SQLAlchemy**: Use hybrid properties for derived data

### Common Pitfalls

1. **Anemic domain models**: Objects without behavior
   - Add methods to objects with the data

2. **Feature envy**: Services manipulating object data
   - Move behavior to the information expert

3. **Getters/setters instead of methods**: Not Pythonic
   - Use methods for behavior, properties for computed fields
