# OCP Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern 1: Type-Based Conditionals](#anti-pattern-1-type-based-conditionals)
- [Anti-Pattern 2: Modifying Stable Classes](#anti-pattern-2-modifying-stable-classes)
- [Anti-Pattern 3: Tight Coupling to Concrete Classes](#anti-pattern-3-tight-coupling-to-concrete-classes)
- [Anti-Pattern 4: Exposed Internals for Extension](#anti-pattern-4-exposed-internals-for-extension)
- [Anti-Pattern 5: Scattered Type Checks](#anti-pattern-5-scattered-type-checks)
- [Anti-Pattern 6: Premature Abstraction](#anti-pattern-6-premature-abstraction)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the Open/Closed Principle in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

## Anti-Pattern 1: Type-Based Conditionals

### Description

Using if/elif chains or switch-like logic to check types and execute different behavior, making it impossible to add new types without modifying existing code. This is one of the most common OCP violations in Python.

### BAD Example

```python
class OrderProcessor:
    def process_payment(self, order):
        payment_method = order.payment_type

        if payment_method == "credit_card":
            return self._process_credit_card(order)
        elif payment_method == "paypal":
            return self._process_paypal(order)
        elif payment_method == "bitcoin":
            return self._process_bitcoin(order)
        elif payment_method == "bank_transfer":
            return self._process_bank_transfer(order)
        elif payment_method == "apple_pay":
            return self._process_apple_pay(order)
        else:
            raise ValueError(f"Unsupported payment method: {payment_method}")

    def _process_credit_card(self, order):
        return f"Processing credit card payment for {order.amount}"

    def _process_paypal(self, order):
        return f"Processing PayPal payment for {order.amount}"
```

### Why It's Problematic

- **Extension requires modification**: Every new payment method requires adding elif branch
- **Growing complexity**: Method becomes longer and harder to maintain
- **Testing burden**: All existing branches must be retested for each addition
- **Scattered logic**: Similar type checks often appear in multiple places

### How to Fix

**Refactoring Steps:**
1. Create an abstract base class or interface for payment strategies
2. Implement concrete strategy classes for each payment type
3. Update OrderProcessor to accept and use a payment strategy
4. Remove all type-based conditionals from OrderProcessor

### GOOD Example

```python
from abc import ABC, abstractmethod

class PaymentStrategy(ABC):
    @abstractmethod
    def process(self, order) -> str:
        pass

class CreditCardStrategy(PaymentStrategy):
    def process(self, order) -> str:
        return f"Processing credit card payment for {order.amount}"

class PayPalStrategy(PaymentStrategy):
    def process(self, order) -> str:
        return f"Processing PayPal payment for {order.amount}"

class BitcoinStrategy(PaymentStrategy):
    def process(self, order) -> str:
        return f"Processing Bitcoin payment for {order.amount}"

class OrderProcessor:
    def __init__(self, payment_strategy: PaymentStrategy):
        self.payment_strategy = payment_strategy

    def process_payment(self, order) -> str:
        return self.payment_strategy.process(order)

# New payment method - no changes to OrderProcessor!
class ApplePayStrategy(PaymentStrategy):
    def process(self, order) -> str:
        return f"Processing Apple Pay payment for {order.amount}"
```

**Key Changes:**
- PaymentStrategy ABC defines interface
- Each payment type is independent class
- OrderProcessor depends on abstraction, not concrete types
- New payment types added without touching existing code

---

## Anti-Pattern 2: Modifying Stable Classes

### Description

Adding new functionality to well-tested, stable classes instead of extending through designed extension points. This risks breaking existing functionality and increases regression testing.

### BAD Example

```python
class EmailService:
    def __init__(self, smtp_server: str):
        self.smtp_server = smtp_server

    def send(self, to: str, subject: str, body: str):
        return f"Sending email to {to} via {self.smtp_server}"

# New feature added by modifying stable class!
class EmailService:
    def __init__(self, smtp_server: str):
        self.smtp_server = smtp_server

    def send(self, to: str, subject: str, body: str):
        return f"Sending email to {to} via {self.smtp_server}"

    def send_with_template(self, to: str, template_id: str, data: dict):
        template = self._load_template(template_id)
        body = self._render_template(template, data)
        return self.send(to, "Template Email", body)

    def send_bulk(self, recipients: list[str], subject: str, body: str):
        results = []
        for recipient in recipients:
            results.append(self.send(recipient, subject, body))
        return results

    def _load_template(self, template_id: str):
        return f"Template {template_id}"

    def _render_template(self, template: str, data: dict):
        return template.format(**data)
```

### Why It's Problematic

- **Regression risk**: Changes can break existing send() method
- **Testing burden**: All existing tests must be rerun
- **Bloated class**: Class accumulates unrelated responsibilities
- **Stability lost**: Well-tested code is no longer trustworthy

### How to Fix

**Refactoring Steps:**
1. Keep original EmailService minimal and stable
2. Use decorator pattern to add features like templates
3. Create separate classes for bulk operations
4. Use composition instead of modification

### GOOD Example

```python
class EmailService:
    def __init__(self, smtp_server: str):
        self.smtp_server = smtp_server

    def send(self, to: str, subject: str, body: str):
        return f"Sending email to {to} via {self.smtp_server}"

class TemplateEmailService:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service

    def send_with_template(self, to: str, template_id: str, data: dict):
        template = self._load_template(template_id)
        body = self._render_template(template, data)
        return self.email_service.send(to, "Template Email", body)

    def _load_template(self, template_id: str):
        return f"Template {template_id}"

    def _render_template(self, template: str, data: dict):
        return template.format(**data)

class BulkEmailService:
    def __init__(self, email_service: EmailService):
        self.email_service = email_service

    def send_bulk(self, recipients: list[str], subject: str, body: str):
        return [self.email_service.send(r, subject, body) for r in recipients]
```

**Key Changes:**
- Original EmailService unchanged and stable
- Template and bulk functionality in separate classes
- Uses composition via constructor injection
- Each service has single responsibility

---

## Anti-Pattern 3: Tight Coupling to Concrete Classes

### Description

Depending directly on concrete classes instead of abstractions, making it impossible to swap implementations without modifying dependent code.

### BAD Example

```python
class DatabaseService:
    def __init__(self):
        self.connection = MySQLConnection()
        self.cache = RedisCache()
        self.logger = FileLogger()

    def save_user(self, user):
        self.cache.set(f"user:{user.id}", user)
        self.connection.execute(f"INSERT INTO users VALUES ({user.id}, '{user.name}')")
        self.logger.log(f"Saved user {user.id}")

class MySQLConnection:
    def execute(self, query):
        return f"Executing MySQL: {query}"

class RedisCache:
    def set(self, key, value):
        return f"Redis SET {key}"

class FileLogger:
    def log(self, message):
        return f"Log: {message}"
```

### Why It's Problematic

- **Cannot swap implementations**: To change database or cache, must modify DatabaseService
- **Hard to test**: Cannot mock dependencies for unit tests
- **No flexibility**: Tight to specific implementations
- **Violates DIP**: Depends on concretions, not abstractions

### How to Fix

**Refactoring Steps:**
1. Define interfaces for dependencies using Protocol or ABC
2. Inject dependencies through constructor
3. Program to interfaces, not concrete classes
4. Create factory for dependency creation if needed

### GOOD Example

```python
from typing import Protocol

class Database(Protocol):
    def execute(self, query: str):
        ...

class Cache(Protocol):
    def set(self, key: str, value):
        ...

class Logger(Protocol):
    def log(self, message: str):
        ...

class DatabaseService:
    def __init__(self, db: Database, cache: Cache, logger: Logger):
        self.db = db
        self.cache = cache
        self.logger = logger

    def save_user(self, user):
        self.cache.set(f"user:{user.id}", user)
        self.db.execute(f"INSERT INTO users VALUES ({user.id}, '{user.name}')")
        self.logger.log(f"Saved user {user.id}")

# Concrete implementations
class MySQLConnection:
    def execute(self, query: str):
        return f"Executing MySQL: {query}"

class PostgreSQLConnection:
    def execute(self, query: str):
        return f"Executing PostgreSQL: {query}"

class RedisCache:
    def set(self, key: str, value):
        return f"Redis SET {key}"

class FileLogger:
    def log(self, message: str):
        return f"Log: {message}"

# Can now swap implementations without modifying DatabaseService!
service = DatabaseService(PostgreSQLConnection(), RedisCache(), FileLogger())
```

**Key Changes:**
- Protocol interfaces defined for each dependency
- Dependencies injected via constructor
- Can swap implementations freely
- Easy to mock for testing

---

## Anti-Pattern 4: Exposed Internals for Extension

### Description

Making internal methods or fields protected or public solely to allow subclasses to access them, breaking encapsulation and creating fragile base classes.

### BAD Example

```python
class Order:
    def __init__(self):
        self._items = []
        self._discount = 0.0
        self._total = 0.0

    def add_item(self, item):
        self._items.append(item)
        self._recalculate_total()

    def _recalculate_total(self):
        self._total = sum(item.price for item in self._items)

    # Made public just to allow extension!
    def apply_discount(self, discount: float):
        self._discount = discount
        self._recalculate_total()

    def get_total(self):
        return self._total

class DiscountedOrder(Order):
    def apply_special_promotion(self, promo_code: str):
        if promo_code == "SAVE20":
            # Directly accessing internal state
            self._discount = 0.20
            self._recalculate_total()
        elif promo_code == "VIP":
            self._discount = 0.30
            self._recalculate_total()
```

### Why It's Problematic

- **Broken invariants**: Subclasses can corrupt internal state
- **Fragile base class**: Changes to _recalculate_total break subclasses
- **Tight coupling**: Subclasses depend on implementation details
- **Hidden dependencies**: Hard to understand how subclasses work

### How to Fix

**Refactoring Steps:**
1. Keep internals private
2. Provide protected extension methods designed for overriding
3. Use template method pattern with clear hooks
4. Document which methods are safe to override

### GOOD Example

```python
class Order:
    def __init__(self):
        self._items = []
        self._total = 0.0

    def add_item(self, item):
        self._items.append(item)
        self._update_total()

    def apply_discount(self, discount: float):
        self._total = self._total * (1 - self._calculate_discount(discount))

    # Protected method designed for extension
    def _calculate_discount(self, discount: float) -> float:
        return discount

    # Private implementation detail
    def _update_total(self):
        self._total = sum(item.price for item in self._items)

class DiscountedOrder(Order):
    def __init__(self, promo_code: str = None):
        super().__init__()
        self._promo_code = promo_code

    # Override extension hook, not internal methods
    def _calculate_discount(self, discount: float) -> float:
        base_discount = super()._calculate_discount(discount)
        if self._promo_code == "SAVE20":
            return max(base_discount, 0.20)
        elif self._promo_code == "VIP":
            return max(base_discount, 0.30)
        return base_discount
```

**Key Changes:**
- Internal methods stay private
- Protected extension hook (_calculate_discount) provided
- Subclasses override designed extension points
- Invariants protected by base class

---

## Anti-Pattern 5: Scattered Type Checks

### Description

Same type-based conditionals repeated in multiple places throughout the codebase, making it hard to add new types consistently and risking missed updates.

### BAD Example

```python
# File 1: payment_processor.py
def process_payment(payment):
    if payment.type == "credit_card":
        print("Processing credit card")
    elif payment.type == "paypal":
        print("Processing PayPal")

# File 2: payment_validator.py
def validate_payment(payment):
    if payment.type == "credit_card":
        return len(payment.card_number) == 16
    elif payment.type == "paypal":
        return len(payment.email) > 0

# File 3: payment_ui.py
def render_payment_form(payment_type):
    if payment_type == "credit_card":
        return "<input name='card_number'>"
    elif payment_type == "paypal":
        return "<input name='email'>"

# File 4: payment_report.py
def generate_payment_report(payment):
    if payment.type == "credit_card":
        return f"Card: ****{payment.card_number[-4:]}"
    elif payment.type == "paypal":
        return f"PayPal: {payment.email}"
```

### Why It's Problematic

- **Multiple update points**: Adding new type requires changes in many files
- **Inconsistency**: Different handling in different places
- **Easy to miss**: Forget to update one location
- **Testing complexity**: Many files to test for new type

### How to Fix

**Refactoring Steps:**
1. Create payment class hierarchy with shared interface
2. Move type-specific logic into payment classes
3. Remove all type checks from other modules
4. Use polymorphism for behavior dispatch

### GOOD Example

```python
# payment.py - Single source of truth
from abc import ABC, abstractmethod

class Payment(ABC):
    @abstractmethod
    def process(self):
        pass

    @abstractmethod
    def validate(self):
        pass

    @abstractmethod
    def render_form(self):
        pass

    @abstractmethod
    def generate_report(self):
        pass

class CreditCardPayment(Payment):
    def __init__(self, card_number: str):
        self.type = "credit_card"
        self.card_number = card_number

    def process(self):
        print("Processing credit card")

    def validate(self):
        return len(self.card_number) == 16

    def render_form(self):
        return "<input name='card_number'>"

    def generate_report(self):
        return f"Card: ****{self.card_number[-4:]}"

class PayPalPayment(Payment):
    def __init__(self, email: str):
        self.type = "paypal"
        self.email = email

    def process(self):
        print("Processing PayPal")

    def validate(self):
        return len(self.email) > 0

    def render_form(self):
        return "<input name='email'>"

    def generate_report(self):
        return f"PayPal: {self.email}"

# No type checks needed in other modules!
def process_payment(payment: Payment):
    payment.process()

def validate_payment(payment: Payment):
    return payment.validate()

def render_payment_form(payment: Payment):
    return payment.render_form()

def generate_payment_report(payment: Payment):
    return payment.generate_report()
```

**Key Changes:**
- All type-specific logic in payment classes
- Other modules use polymorphism
- New payment types added in one place
- Consistent behavior across all modules

---

## Anti-Pattern 6: Premature Abstraction

### Description

Creating complex abstractions and interfaces before they're needed, resulting in over-engineered code that doesn't solve real problems yet and adds unnecessary complexity.

### BAD Example

```python
from abc import ABC, abstractmethod
from typing import Protocol, Generic, TypeVar

T = TypeVar('T')

class DataProcessor(ABC, Generic[T]):
    @abstractmethod
    def load(self, source: str) -> T:
        pass

    @abstractmethod
    def validate(self, data: T) -> bool:
        pass

    @abstractmethod
    def transform(self, data: T) -> T:
        pass

    @abstractmethod
    def save(self, data: T, destination: str):
        pass

class JSONDataProcessor(DataProcessor[dict]):
    def load(self, source: str) -> dict:
        import json
        with open(source) as f:
            return json.load(f)

    def validate(self, data: dict) -> bool:
        return isinstance(data, dict)

    def transform(self, data: dict) -> dict:
        return data  # No transformation needed yet

    def save(self, data: dict, destination: str):
        import json
        with open(destination, 'w') as f:
            json.dump(data, f)

class CSVDataProcessor(DataProcessor[dict]):
    def load(self, source: str) -> dict:
        import csv
        with open(source) as f:
            return dict(list(csv.reader(f)))

    def validate(self, data: dict) -> bool:
        return isinstance(data, dict)

    def transform(self, data: dict) -> dict:
        return data  # No transformation needed yet

    def save(self, data: dict, destination: str):
        import csv
        with open(destination, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(data.items())
```

### Why It's Problematic

- **Unnecessary complexity**: Abstract base class adds indirection
- **Single implementation**: Multiple processor classes but similar behavior
- **No real variance**: transform method does nothing
- **YAGNI violation**: "You Aren't Gonna Need It"

### How to Fix

**Refactoring Steps:**
1. Start with simple concrete implementation
2. Extract abstractions when multiple implementations needed
3. Apply YAGNI - don't over-abstract
4. Refactor when patterns emerge

### GOOD Example

```python
class DataProcessor:
    def __init__(self, source: str, destination: str):
        self.source = source
        self.destination = destination

    def process(self):
        data = self._load()
        if self._validate(data):
            data = self._transform(data)
            self._save(data)

    def _load(self) -> dict:
        import json
        with open(self.source) as f:
            return json.load(f)

    def _validate(self, data: dict) -> bool:
        return isinstance(data, dict)

    def _transform(self, data: dict) -> dict:
        return data

    def _save(self, data: dict):
        import json
        with open(self.destination, 'w') as f:
            json.dump(data, f)

# Add abstraction only when needed!
# Later, when we need CSV processing:
class CSVDataProcessor(DataProcessor):
    def _load(self) -> dict:
        import csv
        with open(self.source) as f:
            return dict(list(csv.reader(f)))

    def _save(self, data: dict):
        import csv
        with open(self.destination, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(data.items())
```

**Key Changes:**
- Start with simple implementation
- Extract common behavior to base class when needed
- Add CSV processor by extending when needed
- No premature generic abstractions

---

## Detection Checklist

Use this checklist to identify OCP violations in Python code:

### Code Review Questions

- [ ] Does the class have long if-elif chains checking types or enum values?
- [ ] To add a new type/format/feature, do you need to modify existing classes?
- [ ] Are there switch-like statements based on string comparisons?
- [ ] Do subclasses directly access private methods or attributes of parent classes?
- [ ] Are there comments warning not to modify certain methods?
- [ ] Does adding a new implementation require changes in multiple files?

### Automated Detection

- **Cyclomatic complexity**: High complexity from many conditional branches suggests violations
- **Code duplication**: Similar conditional blocks across multiple files
- **Large classes**: Classes with many methods handling different types
- **Type check patterns**: Look for `isinstance()`, `type() ==`, or string type checks

### Manual Inspection Techniques

1. **Search for type checks**: Search for `isinstance`, `type(`, and `== "` followed by type strings
2. **Look for growing methods**: Methods that keep getting new elif branches
3. **Check modification history**: If a class is frequently modified for new features, it may violate OCP
4. **Examine inheritance**: Check if subclasses break encapsulation by accessing private members

### Common Symptoms

- **"God methods"**: Methods that handle too many variations
- **Repeated conditionals**: Same type checks appear in multiple places
- **Regression bugs**: Changes to working code introduce bugs in other areas
- **Fear of modification**: Developers hesitate to touch certain classes

---

## Language-Specific Notes

### Common Causes in Python

- **Dynamic typing**: Makes it easy to add type checks instead of proper polymorphism
- **Convenience**: Adding elif branch is easier than creating new class
- **Prototyping mindset**: Quick solutions become permanent
- **Lack of interfaces**: No compile-time enforcement of contracts

### Language Features that Enable Anti-Patterns

- **Duck typing**: Can lead to implicit interfaces that aren't documented
- **Monkey patching**: Makes it tempting to modify classes at runtime
- **Lack of private keyword**: Relies on convention, not enforcement
- **Dictionary-based configs**: Encourages string-based type checking

### Framework-Specific Anti-Patterns

- **Django**: Adding methods to models instead of using mixins or separate classes
- **Flask**: Growing route handlers with too many conditionals
- **FastAPI**: Over-using Union types instead of proper strategy pattern
- **Celery**: Modifying base task classes instead of using inheritance properly

### Tooling Support

- **Pylint**: Detects high cyclomatic complexity and long methods
- **flake8**: Flags lines that are too long (often from deep conditionals)
- **mypy**: Can detect type-based conditionals when types are annotated
- **SonarQube**: Detects cognitive complexity and code duplication patterns
