# DRY Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Input Validation](#example-1-input-validation)
- [Example 2: API Client Calls](#example-2-api-client-calls)
- [Example 3: Configuration Management](#example-3-configuration-management)
- [Example 4: Utility Functions](#example-4-utility-functions)
- [Example 5: Error Handling](#example-5-error-handling)
- [Example 6: Data Processing](#example-6-data-processing)
- [Example 7: Business Logic](#example-7-business-logic)
- [Example 8: String Operations](#example-8-string-operations)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the DRY (Don't Repeat Yourself) principle in Python. Each example demonstrates a common violation and a corrected implementation using Pythonic patterns.

## Example 1: Input Validation

### BAD Example: Repeated Validation Logic

```python
def register_user(name, email, age):
    if not name or len(name) < 2:
        raise ValueError("Name must be at least 2 characters")
    if '@' not in email:
        raise ValueError("Invalid email format")
    if age < 18 or age > 120:
        raise ValueError("Age must be between 18 and 120")

    print(f"User {name} registered")

def update_user_profile(user_id, name, email, age):
    if not name or len(name) < 2:
        raise ValueError("Name must be at least 2 characters")
    if '@' not in email:
        raise ValueError("Invalid email format")
    if age < 18 or age > 120:
        raise ValueError("Age must be between 18 and 120")

    print(f"User {user_id} updated")

def create_admin_account(name, email, age, role):
    if not name or len(name) < 2:
        raise ValueError("Name must be at least 2 characters")
    if '@' not in email:
        raise ValueError("Invalid email format")
    if age < 18 or age > 120:
        raise ValueError("Age must be between 18 and 120")

    print(f"Admin {name} created with role {role}")
```

**Problems:**
- Validation logic repeated across three functions
- Changes to validation rules require updating multiple locations
- Violates DRY principle by duplicating knowledge
- Increased maintenance burden

### GOOD Example: Validation Function and Decorator

```python
from functools import wraps

def validate_user_input(func):
    @wraps(func)
    def wrapper(name, email, age, *args, **kwargs):
        if not name or len(name) < 2:
            raise ValueError("Name must be at least 2 characters")
        if '@' not in email:
            raise ValueError("Invalid email format")
        if age < 18 or age > 120:
            raise ValueError("Age must be between 18 and 120")
        return func(name, email, age, *args, **kwargs)
    return wrapper

@validate_user_input
def register_user(name, email, age):
    print(f"User {name} registered")

@validate_user_input
def update_user_profile(user_id, name, email, age):
    print(f"User {user_id} updated")

@validate_user_input
def create_admin_account(name, email, age, role):
    print(f"Admin {name} created with role {role}")
```

**Improvements:**
- Validation logic defined once in decorator
- Single source of truth for validation rules
- Decorator pattern provides clean separation
- Easy to add or modify validation rules

### Explanation

The BAD example duplicates validation logic across three functions, creating maintenance issues when rules change. The GOOD example uses a Python decorator to extract the validation logic into a single reusable component. This follows the DRY principle by having one authoritative representation of the validation knowledge, applied consistently through the decorator pattern.

---

## Example 2: API Client Calls

### BAD Example: Repetitive HTTP Request Code

```python
import requests

def get_user(user_id):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    if response.status_code == 401:
        raise Exception("Unauthorized")
    if response.status_code == 429:
        raise Exception("Rate limit exceeded")
    if response.status_code >= 400:
        raise Exception(f"API Error: {response.status_code}")
    return response.json()

def get_orders(user_id):
    response = requests.get(f"https://api.example.com/users/{user_id}/orders")
    if response.status_code == 401:
        raise Exception("Unauthorized")
    if response.status_code == 429:
        raise Exception("Rate limit exceeded")
    if response.status_code >= 400:
        raise Exception(f"API Error: {response.status_code}")
    return response.json()

def create_order(user_id, items):
    url = f"https://api.example.com/users/{user_id}/orders"
    response = requests.post(url, json={'items': items})
    if response.status_code == 401:
        raise Exception("Unauthorized")
    if response.status_code == 429:
        raise Exception("Rate limit exceeded")
    if response.status_code >= 400:
        raise Exception(f"API Error: {response.status_code}")
    return response.json()
```

**Problems:**
- Error handling logic duplicated
- Base URL repeated throughout
- Repetitive response checking
- Difficult to add new API endpoints

### GOOD Example: Context Manager for API Requests

```python
import requests
from contextlib import contextmanager

class APIError(Exception):
    pass

class APIClient:
    BASE_URL = "https://api.example.com"

    def __init__(self, api_key):
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {api_key}'})

    def _request(self, method, endpoint, **kwargs):
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(method, url, **kwargs)

        if response.status_code == 401:
            raise APIError("Unauthorized")
        if response.status_code == 429:
            raise APIError("Rate limit exceeded")
        if response.status_code >= 400:
            raise APIError(f"API Error: {response.status_code}")

        return response.json()

    def get_user(self, user_id):
        return self._request('GET', f'/users/{user_id}')

    def get_orders(self, user_id):
        return self._request('GET', f'/users/{user_id}/orders')

    def create_order(self, user_id, items):
        return self._request('POST', f'/users/{user_id}/orders', json={'items': items})

client = APIClient(api_key="your-api-key")
user = client.get_user(123)
orders = client.get_orders(123)
order = client.create_order(123, ['item1', 'item2'])
```

**Improvements:**
- Single _request method handles all HTTP calls
- Error handling centralized in one place
- Base URL defined once as class constant
- Session reuse for better performance
- Type-safe error handling with custom exception

### Explanation

The BAD example repeats error handling and URL construction in every function. The GOOD example creates an APIClient class with a private _request method that encapsulates common logic. The context manager pattern (through requests.Session) and class-based design provide a single source of truth for API interaction logic, following DRY principles.

---

## Example 3: Configuration Management

### BAD Example: Scattered Configuration Values

```python
def connect_to_database():
    host = "localhost"
    port = 5432
    database = "myapp"
    username = "admin"
    password = "secret123"
    connection = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password
    )
    return connection

def connect_to_cache():
    host = "localhost"
    port = 6379
    client = redis.Redis(host=host, port=port)
    return client

def send_email():
    smtp_host = "localhost"
    smtp_port = 587
    smtp_user = "noreply@example.com"
    smtp_password = "secret456"
    server = smtplib.SMTP(smtp_host, smtp_port)
    server.login(smtp_user, smtp_password)
    return server
```

**Problems:**
- Configuration values scattered across functions
- Hard-coded values make testing difficult
- No single source of truth for settings
- Environment-specific changes require code changes

### GOOD Example: Centralized Configuration

```python
from dataclasses import dataclass
import os
from typing import Optional

@dataclass
class Config:
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "myapp"
    database_user: str = "admin"
    database_password: str = "secret123"

    cache_host: str = "localhost"
    cache_port: int = 6379

    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = "noreply@example.com"
    smtp_password: str = "secret456"

    @classmethod
    def from_env(cls):
        return cls(
            database_host=os.getenv('DB_HOST', cls.database_host),
            database_port=int(os.getenv('DB_PORT', cls.database_port)),
            database_name=os.getenv('DB_NAME', cls.database_name),
            database_user=os.getenv('DB_USER', cls.database_user),
            database_password=os.getenv('DB_PASSWORD', cls.database_password),
            cache_host=os.getenv('CACHE_HOST', cls.cache_host),
            cache_port=int(os.getenv('CACHE_PORT', cls.cache_port)),
            smtp_host=os.getenv('SMTP_HOST', cls.smtp_host),
            smtp_port=int(os.getenv('SMTP_PORT', cls.smtp_port)),
            smtp_user=os.getenv('SMTP_USER', cls.smtp_user),
            smtp_password=os.getenv('SMTP_PASSWORD', cls.smtp_password),
        )

config = Config.from_env()

def connect_to_database(cfg: Config = config):
    return psycopg2.connect(
        host=cfg.database_host,
        port=cfg.database_port,
        database=cfg.database_name,
        user=cfg.database_user,
        password=cfg.database_password
    )

def connect_to_cache(cfg: Config = config):
    return redis.Redis(host=cfg.cache_host, port=cfg.cache_port)

def send_email(cfg: Config = config):
    server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)
    server.login(cfg.smtp_user, cfg.smtp_password)
    return server
```

**Improvements:**
- All configuration in single dataclass
- Environment variable support for flexibility
- Default values provide sensible defaults
- Easy to mock for testing
- Type hints improve IDE support

### Explanation

The BAD example has configuration scattered across functions with hard-coded values. The GOOD example uses a dataclass to centralize all configuration in one place, with support for environment variables. This provides a single source of truth for all settings, making the code DRY and more maintainable.

---

## Example 4: Utility Functions

### BAD Example: Massive Utility Module

```python
# utils.py

def format_currency(amount):
    return f"${amount:.2f}"

def format_percentage(value):
    return f"{value:.1%}"

def format_date(date):
    return date.strftime("%Y-%m-%d")

def calculate_tax(amount, rate):
    return amount * rate

def calculate_discount(amount, percentage):
    return amount * (1 - percentage / 100)

def calculate_total(items):
    return sum(item.price for item in items)

def validate_email(email):
    return '@' in email and '.' in email.split('@')[1]

def validate_phone(phone):
    return len(phone) == 10 and phone.isdigit()

def sanitize_string(text):
    return text.strip().lower()

def generate_id():
    import uuid
    return str(uuid.uuid4())

def hash_password(password):
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()

# 50+ more unrelated functions...
```

**Problems:**
- Functions grouped by implementation, not domain
- No clear responsibility or theme
- Difficult to discover related utilities
- Violates single responsibility
- Hard to test individual concerns

### GOOD Example: Domain-Aligned Modules

```python
# formatters.py
class CurrencyFormatter:
    @staticmethod
    def format(amount: float, currency: str = "USD") -> str:
        return f"{currency}{amount:.2f}"

class DateFormatter:
    @staticmethod
    def format(date: datetime, fmt: str = "%Y-%m-%d") -> str:
        return date.strftime(fmt)

# finance.py
class FinanceCalculator:
    @staticmethod
    def calculate_tax(amount: float, rate: float) -> float:
        return amount * rate

    @staticmethod
    def calculate_discount(amount: float, percentage: float) -> float:
        return amount * (1 - percentage / 100)

    @staticmethod
    def calculate_total(items: list) -> float:
        return sum(item.price for item in items)

# validators.py
class EmailValidator:
    @staticmethod
    def is_valid(email: str) -> bool:
        pattern = r'^[^@]+@[^@]+\.[^@]+$'
        import re
        return re.match(pattern, email) is not None

class PhoneValidator:
    @staticmethod
    def is_valid(phone: str) -> bool:
        return len(phone) == 10 and phone.isdigit()

# security.py
class PasswordHasher:
    @staticmethod
    def hash(password: str) -> str:
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()

class IDGenerator:
    @staticmethod
    def generate() -> str:
        import uuid
        return str(uuid.uuid4())
```

**Improvements:**
- Each module has clear domain responsibility
- Functions grouped by business logic, not implementation
- Easy to discover utilities by domain
- Follows single responsibility principle
- Better testability and maintainability

### Explanation

The BAD example creates a massive utility module with unrelated functions. The GOOD example organizes utilities into domain-aligned modules, each with a single, clear responsibility. This follows DRY by ensuring each piece of domain logic has a single, authoritative representation, making the code more maintainable and discoverable.

---

## Example 5: Error Handling

### BAD Example: Repetitive Try-Except Blocks

```python
def process_order(order_id):
    try:
        order = database.get_order(order_id)
        return order
    except database.DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise ProcessingError("Failed to process order")

def process_payment(payment_id):
    try:
        payment = database.get_payment(payment_id)
        return payment
    except database.DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise ProcessingError("Failed to process payment")

def process_shipment(shipment_id):
    try:
        shipment = database.get_shipment(shipment_id)
        return shipment
    except database.DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise ProcessingError("Failed to process shipment")

def process_invoice(invoice_id):
    try:
        invoice = database.get_invoice(invoice_id)
        return invoice
    except database.DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise ProcessingError("Failed to process invoice")
```

**Problems:**
- Error handling logic duplicated across functions
- Same logging and error raising pattern repeated
- Difficult to change error handling strategy
- Violates DRY principle

### GOOD Example: Decorator for Error Handling

```python
from functools import wraps

class ProcessingError(Exception):
    pass

def handle_database_errors(error_message):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except database.DatabaseError as e:
                logger.error(f"Database error in {func.__name__}: {e}")
                raise ProcessingError(error_message)
        return wrapper
    return decorator

@handle_database_errors("Failed to process order")
def process_order(order_id):
    return database.get_order(order_id)

@handle_database_errors("Failed to process payment")
def process_payment(payment_id):
    return database.get_payment(payment_id)

@handle_database_errors("Failed to process shipment")
def process_shipment(shipment_id):
    return database.get_shipment(shipment_id)

@handle_database_errors("Failed to process invoice")
def process_invoice(invoice_id):
    return database.get_invoice(invoice_id)
```

**Improvements:**
- Error handling logic defined once in decorator
- Logging and error raising centralized
- Each function specifies its own error message
- Easy to modify error handling strategy globally
- Cleaner, more readable function implementations

### Explanation

The BAD example repeats the same try-except block with logging and error raising in every function. The GOOD example uses a decorator factory to encapsulate the error handling logic, allowing each function to specify only its error message. This provides a single source of truth for database error handling, making the code DRY and maintainable.

---

## Example 6: Data Processing

### BAD Example: Repeated Data Transformations

```python
def process_users(users):
    processed = []
    for user in users:
        processed_user = {
            'id': user['id'],
            'name': user['name'].title(),
            'email': user['email'].lower(),
            'active': user['status'] == 'active',
            'created': user['created_at'].strftime('%Y-%m-%d')
        }
        processed.append(processed_user)
    return processed

def process_products(products):
    processed = []
    for product in products:
        processed_product = {
            'id': product['id'],
            'name': product['name'].title(),
            'price': product['price'],
            'available': product['stock'] > 0,
            'created': product['created_at'].strftime('%Y-%m-%d')
        }
        processed.append(processed_product)
    return processed

def process_orders(orders):
    processed = []
    for order in orders:
        processed_order = {
            'id': order['id'],
            'user_id': order['user_id'],
            'total': order['total'],
            'status': order['status'].upper(),
            'created': order['created_at'].strftime('%Y-%m-%d')
        }
        processed.append(processed_order)
    return processed
```

**Problems:**
- Similar transformation logic repeated
- Date formatting duplicated
- Manual loop pattern repeated
- Difficult to maintain consistent transformations
- No reuse of common patterns

### GOOD Example: Generic Processor with Comprehensions

```python
from typing import Callable, Dict, Any, List
from datetime import datetime

class DataProcessor:
    @staticmethod
    def transform_field(value: Any, transform: Callable) -> Any:
        return transform(value)

    @staticmethod
    def process_data(
        items: List[Dict],
        field_mapping: Dict[str, str],
        transforms: Dict[str, Callable] = None
    ) -> List[Dict]:
        transforms = transforms or {}

        return [
            {
                new_name: transforms.get(new_name, lambda x: x)(item.get(old_name))
                for old_name, new_name in field_mapping.items()
            }
            for item in items
        ]

def process_users(users):
    return DataProcessor.process_data(
        users,
        field_mapping={
            'id': 'id',
            'name': 'name',
            'email': 'email',
            'status': 'active',
            'created_at': 'created'
        },
        transforms={
            'name': lambda x: x.title(),
            'email': lambda x: x.lower(),
            'active': lambda x: x == 'active',
            'created': lambda x: x.strftime('%Y-%m-%d')
        }
    )

def process_products(products):
    return DataProcessor.process_data(
        products,
        field_mapping={
            'id': 'id',
            'name': 'name',
            'price': 'price',
            'stock': 'available',
            'created_at': 'created'
        },
        transforms={
            'name': lambda x: x.title(),
            'available': lambda x: x > 0,
            'created': lambda x: x.strftime('%Y-%m-%d')
        }
    )

def process_orders(orders):
    return DataProcessor.process_data(
        orders,
        field_mapping={
            'id': 'id',
            'user_id': 'user_id',
            'total': 'total',
            'status': 'status',
            'created_at': 'created'
        },
        transforms={
            'status': lambda x: x.upper(),
            'created': lambda x: x.strftime('%Y-%m-%d')
        }
    )
```

**Improvements:**
- Generic processor handles transformation pattern
- Single method for all data transformations
- List comprehensions for concise code
- Flexible field mapping and transforms
- Reusable across different data types

### Explanation

The BAD example repeats similar transformation logic across three functions, with duplicated date formatting and manual loops. The GOOD example creates a generic DataProcessor class with a reusable process_data method that uses Python's list comprehensions and lambda functions. This provides a single source of truth for data transformation logic, making the code DRY and more flexible.

---

## Example 7: Business Logic

### BAD Example: Duplicated Business Rules

```python
def calculate_order_discount(order):
    discount = 0

    if order['total'] > 1000:
        discount = 0.10
    elif order['total'] > 500:
        discount = 0.05
    elif order['total'] > 100:
        discount = 0.02

    if order['customer_tier'] == 'gold':
        discount += 0.05
    elif order['customer_tier'] == 'silver':
        discount += 0.03

    return order['total'] * discount

def calculate_quote_discount(quote):
    discount = 0

    if quote['total'] > 1000:
        discount = 0.10
    elif quote['total'] > 500:
        discount = 0.05
    elif quote['total'] > 100:
        discount = 0.02

    if quote['customer_tier'] == 'gold':
        discount += 0.05
    elif quote['customer_tier'] == 'silver':
        discount += 0.03

    return quote['total'] * discount

def calculate_invoice_discount(invoice):
    discount = 0

    if invoice['total'] > 1000:
        discount = 0.10
    elif invoice['total'] > 500:
        discount = 0.05
    elif invoice['total'] > 100:
        discount = 0.02

    if invoice['customer_tier'] == 'gold':
        discount += 0.05
    elif invoice['customer_tier'] == 'silver':
        discount += 0.03

    return invoice['total'] * discount
```

**Problems:**
- Business rules duplicated across functions
- Changes to discount policy require updating three locations
- Violates DRY principle for business logic
- Increased risk of inconsistencies

### GOOD Example: Centralized Business Logic

```python
from typing import Dict, Protocol
from enum import Enum

class CustomerTier(Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"

class DiscountPolicy(Protocol):
    total: float
    customer_tier: str

class DiscountCalculator:
    VOLUME_DISCOUNTS = [
        (1000, 0.10),
        (500, 0.05),
        (100, 0.02),
    ]

    TIER_DISCOUNTS = {
        CustomerTier.GOLD: 0.05,
        CustomerTier.SILVER: 0.03,
        CustomerTier.BRONZE: 0.00,
    }

    @classmethod
    def calculate_volume_discount(cls, total: float) -> float:
        for threshold, discount in cls.VOLUME_DISCOUNTS:
            if total > threshold:
                return discount
        return 0.0

    @classmethod
    def calculate_tier_discount(cls, tier: str) -> float:
        try:
            return cls.TIER_DISCOUNTS[CustomerTier(tier)]
        except (ValueError, KeyError):
            return 0.0

    @classmethod
    def calculate_total_discount(cls, policy: DiscountPolicy) -> float:
        volume_discount = cls.calculate_volume_discount(policy.total)
        tier_discount = cls.calculate_tier_discount(policy.customer_tier)

        total_discount = volume_discount + tier_discount

        return min(total_discount, 0.20)  # Cap at 20%

    @classmethod
    def calculate_discount_amount(cls, policy: DiscountPolicy) -> float:
        discount_rate = cls.calculate_total_discount(policy)
        return policy.total * discount_rate

def calculate_order_discount(order):
    return DiscountCalculator.calculate_discount_amount(order)

def calculate_quote_discount(quote):
    return DiscountCalculator.calculate_discount_amount(quote)

def calculate_invoice_discount(invoice):
    return DiscountCalculator.calculate_discount_amount(invoice)
```

**Improvements:**
- Business rules defined once in DiscountCalculator
- Volume and tier discounts separated and centralized
- Single source of truth for discount logic
- Easy to modify discount policies
- Type-safe with Protocol and Enum

### Explanation

The BAD example duplicates the same discount calculation logic across three different contexts. The GOOD example extracts the business rules into a DiscountCalculator class with separate methods for volume and tier discounts. This ensures the discount policy has a single, authoritative representation, following the DRY principle and making the business logic maintainable.

---

## Example 8: String Operations

### BAD Example: Repeated String Manipulations

```python
def format_user_name(first, last):
    first = first.strip()
    last = last.strip()
    first = first.capitalize()
    last = last.capitalize()
    return f"{first} {last}"

def format_address(street, city, state, zip_code):
    street = street.strip()
    city = city.strip()
    state = state.strip()
    zip_code = zip_code.strip()

    street = street.title()
    city = city.title()
    state = state.upper()

    return f"{street}\n{city}, {state} {zip_code}"

def format_product_name(name, brand):
    name = name.strip()
    brand = brand.strip()

    name = name.title()
    brand = brand.upper()

    return f"{brand} - {name}"

def parse_email(email):
    email = email.strip().lower()

    username, domain = email.split('@')
    username = username.strip()

    return {'username': username, 'domain': domain}
```

**Problems:**
- Strip and capitalize operations repeated
- String formatting patterns duplicated
- No reuse of common string operations
- Inconsistent casing logic

### GOOD Example: String Utilities and Composition

```python
from typing import Callable, List
from functools import reduce

class StringUtils:
    @staticmethod
    def clean(text: str) -> str:
        return text.strip()

    @staticmethod
    def to_title(text: str) -> str:
        return text.title()

    @staticmethod
    def to_upper(text: str) -> str:
        return text.upper()

    @staticmethod
    def to_lower(text: str) -> str:
        return text.lower()

    @staticmethod
    def to_capitalize(text: str) -> str:
        return text.capitalize()

    @staticmethod
    def compose(*functions: Callable[[str], str]) -> Callable[[str], str]:
        def composed(text: str) -> str:
            return reduce(lambda acc, f: f(acc), functions, text)
        return composed

clean_title = StringUtils.compose(
    StringUtils.clean,
    StringUtils.to_title
)

clean_upper = StringUtils.compose(
    StringUtils.clean,
    StringUtils.to_upper
)

clean_lower = StringUtils.compose(
    StringUtils.clean,
    StringUtils.to_lower
)

def format_user_name(first: str, last: str) -> str:
    return f"{clean_title(first)} {clean_title(last)}"

def format_address(street: str, city: str, state: str, zip_code: str) -> str:
    return f"{clean_title(street)}\n{clean_title(city)}, {clean_upper(state)} {StringUtils.clean(zip_code)}"

def format_product_name(name: str, brand: str) -> str:
    return f"{clean_upper(brand)} - {clean_title(name)}"

def parse_email(email: str) -> dict:
    email = clean_lower(email)
    username, domain = email.split('@')
    return {'username': StringUtils.clean(username), 'domain': domain}
```

**Improvements:**
- String operations defined once in StringUtils
- Compose function enables reusable transformation pipelines
- Clean, reusable transformation functions
- Consistent application of string operations
- Functional programming style reduces duplication

### Explanation

The BAD example repeats strip and casing operations across multiple functions. The GOOD example creates a StringUtils class with atomic string operations and a compose function that allows building transformation pipelines. This follows DRY by providing reusable string manipulation utilities that can be composed in various ways, eliminating code duplication.

---

## Language-Specific Notes

### Idioms and Patterns

- **Decorators**: Use `@wraps` and `functools` for cross-cutting concerns
- **Context Managers**: Use `with` statements and `@contextmanager` for resource management
- **Dataclasses**: Use `@dataclass` for configuration and data containers
- **List Comprehensions**: Use for concise data transformations
- **Generators**: Use `yield` for lazy evaluation of large datasets
- **Protocol**: Use typing.Protocol for structural subtyping and flexible interfaces

### Language Features

**Features that help:**
- **First-class functions**: Enable decorator and higher-order function patterns
- **List/dict comprehensions**: Reduce duplication in data transformation
- **Decorators**: Clean syntax for cross-cutting concerns
- **Type hints**: Improve documentation and catch errors early
- **Dataclasses**: Reduce boilerplate for data containers

**Features that hinder:**
- **Dynamic typing**: Can lead to runtime errors if not careful
- **Multiple inheritance**: Can encourage inappropriate code sharing
- **Metaclasses**: Often overused for premature abstraction

### Framework Considerations

- **Django**: Use mixins for shared behavior, avoid massive utility modules
- **Flask**: Use decorators for route-specific logic
- **FastAPI**: Use dependency injection to avoid code duplication
- **Pytest**: Use fixtures for reusable test setup

### Common Pitfalls

1. **Helper Hell**: Avoid creating massive utils.py files with unrelated functions. Organize by domain instead.
2. **Over-decorating**: Don't create decorators that add more complexity than duplication.
3. **Premature generalization**: Wait for the "Rule of Three" before extracting common code.
4. **False abstraction**: Don't create generic solutions for specific problems.
5. **Magic methods abuse**: Use dunder methods only when they provide clear value.
