# DRY Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Helper Hell](#helper-hell)
- [Over-Abstraction with Decorators](#over-abstraction-with-decorators)
- [Premature Class Generalization](#premature-class-generalization)
- [Inappropriate Metaclass Usage](#inappropriate-metaclass-usage)
- [False Abstraction with ABCs](#false-abstraction-with-abcs)
- [Configuration Overkill](#configuration-overkill)
- [Dogmatic DRY](#dogmatic-dry)
- [Abstraction Inversion](#abstraction-inversion)
- [Magic Method Abuse](#magic-method-abuse)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate DRY principle in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

## Helper Hell

### Description

Helper Hell occurs when developers create massive utility modules with hundreds of unrelated functions under generic names like `utils.py`, `helpers.py`, or `common.py`, making code difficult to discover, test, and maintain.

### BAD Example

```python
# utils.py - The infamous "kitchen sink"

import re
import json
import hashlib
from datetime import datetime
import requests
from database import db
from email_service import send_email

def format_currency(amount):
    return f"${amount:.2f}"

def validate_email(email):
    return re.match(r'[^@]+@[^@]+\.[^@]+', email)

def get_current_user():
    return db.query('SELECT * FROM users WHERE id = ?', (session['user_id'],))

def send_welcome_email(user_email):
    send_email(user_email, "Welcome!")

def parse_json_date(json_str):
    data = json.loads(json_str)
    return datetime.fromisoformat(data['date'])

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def calculate_tax(amount, rate):
    return amount * rate

def sanitize_html(html):
    # HTML sanitization
    pass

def fetch_external_api(url):
    return requests.get(url).json()

def generate_uuid():
    import uuid
    return str(uuid.uuid4())

def format_phone(phone):
    return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"

def truncate_text(text, length):
    return text[:length] + "..." if len(text) > length else text

# ... 50+ more unrelated functions
```

### Why It's Problematic

- **No clear domain**: Functions have nothing in common beyond being "utilities"
- **Discovery is impossible**: Developers don't know what utilities exist
- **Testing is difficult**: Can't test related functionality together
- **Dependencies are hidden**: Functions depend on global state implicitly
- **Coupling is high**: Changes to one utility affect unrelated code
- **Naming conflicts**: Generic names lead to conflicts and confusion

### How to Fix

**Refactoring Steps:**
1. Identify domain boundaries in the utility module
2. Create separate modules for each domain (finance, validation, security, etc.)
3. Group related functions into classes or cohesive modules
4. Make dependencies explicit through parameters
5. Use descriptive module and class names

### GOOD Example

```python
# currency.py
class CurrencyFormatter:
    @staticmethod
    def format(amount: float, currency: str = 'USD') -> str:
        return f"{currency}{amount:.2f}"

# validation.py
class EmailValidator:
    @staticmethod
    def is_valid(email: str) -> bool:
        pattern = r'^[^@]+@[^@]+\.[^@]+$'
        return re.match(pattern, email) is not None

class PhoneValidator:
    @staticmethod
    def is_valid(phone: str) -> bool:
        return len(phone) == 10 and phone.isdigit()

    @staticmethod
    def format(phone: str) -> str:
        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"

# authentication.py
class UserService:
    def __init__(self, db_connection):
        self.db = db_connection

    def get_current_user(self, user_id: int) -> dict:
        return self.db.query('SELECT * FROM users WHERE id = ?', (user_id,))

# notification.py
class NotificationService:
    def __init__(self, email_service):
        self.email_service = email_service

    def send_welcome(self, user_email: str) -> None:
        self.email_service.send(user_email, "Welcome!")

# security.py
class PasswordHasher:
    @staticmethod
    def hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

class IDGenerator:
    @staticmethod
    def generate() -> str:
        import uuid
        return str(uuid.uuid4())

# finance.py
class TaxCalculator:
    @staticmethod
    def calculate(amount: float, rate: float) -> float:
        return amount * rate

# text.py
class TextFormatter:
    @staticmethod
    def truncate(text: str, length: int) -> str:
        return text[:length] + "..." if len(text) > length else text

# sanitization.py
class HTMLSanitizer:
    @staticmethod
    def sanitize(html: str) -> str:
        # HTML sanitization
        pass
```

**Key Changes:**
- Each module has single, clear responsibility
- Related functions grouped by domain
- Dependencies explicit through constructors
- Easy to discover utilities by domain
- Testable in isolation

---

## Over-Abstraction with Decorators

### Description

Over-abstraction with decorators occurs when developers create complex, parameterized decorators to handle every possible variation of cross-cutting concerns, resulting in code that's harder to understand than the duplication it replaces.

### BAD Example

```python
from functools import wraps
import time
import logging
from typing import Any, Callable, Optional, Dict, List

def universal_decorator(
    log: bool = True,
    timing: bool = False,
    cache: bool = False,
    cache_ttl: int = 300,
    retry: int = 0,
    retry_delay: float = 1.0,
    validate: Optional[Dict[str, Any]] = None,
    transform_input: Optional[Callable] = None,
    transform_output: Optional[Callable] = None,
    error_handler: Optional[Callable] = None,
    rate_limit: Optional[int] = None,
    on_success: Optional[Callable] = None,
    on_failure: Optional[Callable] = None,
    max_execution_time: Optional[float] = None,
    require_permissions: Optional[List[str]] = None,
):
    def decorator(func):
        cache_store = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # Input transformation
            if transform_input:
                args = tuple(transform_input(arg) for arg in args)
                kwargs = {k: transform_input(v) for k, v in kwargs.items()}

            # Validation
            if validate:
                for key, value in validate.items():
                    if key in kwargs and not isinstance(kwargs[key], value):
                        raise TypeError(f"Invalid type for {key}")

            # Rate limiting
            if rate_limit:
                if not hasattr(wrapper, '_call_count'):
                    wrapper._call_count = 0
                    wrapper._last_reset = time.time()
                if time.time() - wrapper._last_reset > 60:
                    wrapper._call_count = 0
                    wrapper._last_reset = time.time()
                if wrapper._call_count >= rate_limit:
                    raise RateLimitError("Too many calls")

            # Caching
            cache_key = (args, frozenset(kwargs.items()))
            if cache and cache_ttl:
                if cache_key in cache_store:
                    if time.time() - cache_store[cache_key]['time'] < cache_ttl:
                        return cache_store[cache_key]['value']

            # Retries
            for attempt in range(retry + 1):
                try:
                    # Check max execution time
                    if max_execution_time and time.time() - start_time > max_execution_time:
                        raise TimeoutError("Function exceeded max execution time")

                    result = func(*args, **kwargs)

                    # Output transformation
                    if transform_output:
                        result = transform_output(result)

                    # Cache result
                    if cache:
                        cache_store[cache_key] = {'value': result, 'time': time.time()}

                    # Timing
                    if timing:
                        elapsed = time.time() - start_time
                        print(f"{func.__name__} took {elapsed:.2f}s")

                    # Logging
                    if log:
                        logging.info(f"Called {func.__name__} with args={args}, kwargs={kwargs}")

                    # Success callback
                    if on_success:
                        on_success(result)

                    return result

                except Exception as e:
                    if attempt == retry:
                        # Error handler
                        if error_handler:
                            return error_handler(e, args, kwargs)
                        # Failure callback
                        if on_failure:
                            on_failure(e)
                        raise

                    # Retry delay
                    if retry_delay:
                        time.sleep(retry_delay)

            return wrapper

        wrapper._call_count = 0
        wrapper._last_reset = time.time()
        return wrapper

    return decorator

# Usage - overly complex for simple needs
@universal_decorator(
    log=True,
    timing=True,
    cache=True,
    cache_ttl=600,
    retry=3,
    retry_delay=0.5,
    validate={'user_id': int, 'email': str},
    error_handler=lambda e, a, k: {'error': str(e)},
    rate_limit=100,
    max_execution_time=5.0
)
def get_user_data(user_id, email):
    return database.query_user(user_id, email)
```

### Why It's Problematic

- **Decorator is more complex than the functions it decorates**
- **Parameters are overwhelming**: 12+ parameters make usage difficult
- **Hidden behavior**: Hard to understand what actually happens
- **Performance overhead**: All features checked even when not used
- **Testing complexity**: Need to test all parameter combinations
- **Maintenance nightmare**: Changes affect many decorated functions

### How to Fix

**Refactoring Steps:**
1. Separate concerns into focused decorators
2. Create specific decorators for each concern
3. Compose decorators when multiple concerns needed
4. Keep each decorator simple and focused
5. Use sensible defaults to reduce parameters

### GOOD Example

```python
from functools import wraps
import time
import logging
from typing import Callable, Any

def log_calls(func: Callable) -> Callable:
    """Simple logging decorator"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"Calling {func.__name__} with {args}, {kwargs}")
        try:
            result = func(*args, **kwargs)
            logging.info(f"{func.__name__} succeeded")
            return result
        except Exception as e:
            logging.error(f"{func.__name__} failed: {e}")
            raise
    return wrapper

def timed(func: Callable) -> Callable:
    """Simple timing decorator"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"{func.__name__} took {elapsed:.2f}s")
        return result
    return wrapper

def retry(max_attempts: int = 3, delay: float = 1.0):
    """Simple retry decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator

def cache_result(ttl: int = 300):
    """Simple caching decorator"""
    def decorator(func):
        cache = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in cache:
                if time.time() - cache[key]['time'] < ttl:
                    return cache[key]['value']

            result = func(*args, **kwargs)
            cache[key] = {'value': result, 'time': time.time()}
            return result
        return wrapper
    return decorator

# Compose decorators as needed
@log_calls
@timed
@retry(max_attempts=3, delay=0.5)
def get_user_data(user_id: int, email: str) -> dict:
    return database.query_user(user_id, email)

@cache_result(ttl=600)
def get_user_profile(user_id: int) -> dict:
    return database.query_profile(user_id)
```

**Key Changes:**
- Each decorator has single responsibility
- Simple, focused implementations
- Easy to understand what each decorator does
- Compose decorators as needed
- No hidden complexity or overwhelming parameters

---

## Premature Class Generalization

### Description

Premature class generalization occurs when developers create base classes and inheritance hierarchies to share code before understanding the actual relationships, leading to inappropriate abstractions that make code harder to understand and maintain.

### BAD Example

```python
class BaseEntity:
    """Base class for all entities - premature generalization"""

    def __init__(self, id, created_at, updated_at):
        self.id = id
        self.created_at = created_at
        self.updated_at = updated_at
        self._attributes = {}

    def save(self):
        """Save entity to database"""
        print(f"Saving {self.__class__.__name__} {self.id}")

    def delete(self):
        """Delete entity from database"""
        print(f"Deleting {self.__class__.__name__} {self.id}")

    def update(self, **kwargs):
        """Update entity attributes"""
        for key, value in kwargs.items():
            setattr(self, key, value)
        self._attributes.update(kwargs)

    def validate(self):
        """Validate entity - implemented by subclasses"""
        raise NotImplementedError

    def to_dict(self):
        """Convert entity to dictionary"""
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            **self._attributes
        }

class User(BaseEntity):
    def __init__(self, id, name, email, created_at, updated_at):
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.email = email

    def validate(self):
        if not self.name:
            raise ValueError("Name is required")
        if '@' not in self.email:
            raise ValueError("Invalid email")

    def send_email(self, message):
        print(f"Sending email to {self.email}: {message}")

class Product(BaseEntity):
    def __init__(self, id, name, price, created_at, updated_at):
        super().__init__(id, created_at, updated_at)
        self.name = name
        self.price = price

    def validate(self):
        if not self.name:
            raise ValueError("Name is required")
        if self.price <= 0:
            raise ValueError("Price must be positive")

    def calculate_tax(self, rate):
        return self.price * rate

class Order(BaseEntity):
    def __init__(self, id, user_id, total, created_at, updated_at):
        super().__init__(id, created_at, updated_at)
        self.user_id = user_id
        self.total = total

    def validate(self):
        if not self.user_id:
            raise ValueError("User ID is required")
        if self.total <= 0:
            raise ValueError("Total must be positive")

    def process_payment(self):
        print(f"Processing payment for order {self.id}")
```

### Why It's Problematic

- **Forced "is-a" relationship**: User, Product, Order don't share meaningful behavior
- **Fragile base class**: Changes to BaseEntity affect all subclasses
- **Little code reuse**: Each class overrides validate() completely
- **Confusing hierarchy**: Unclear what behavior is shared
- **Can't evolve independently**: Changes to one entity may affect others
- **Inappropriate inheritance**: Used for code sharing, not conceptual modeling

### How to Fix

**Refactoring Steps:**
1. Identify actual shared behavior
2. Use composition instead of inheritance for code sharing
3. Create protocols/ABCs for common interfaces
4. Let each entity be independent
5. Use mixins only for truly shared cross-cutting concerns

### GOOD Example

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Entity:
    """Simple entity dataclass"""
    id: int
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

class Validatable(ABC):
    """Protocol for validatable entities"""

    @abstractmethod
    def validate(self) -> None:
        """Validate entity"""
        pass

@dataclass
class User(Entity, Validatable):
    name: str
    email: str

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Name is required")
        if '@' not in self.email:
            raise ValueError("Invalid email")

    def send_email(self, message: str) -> None:
        print(f"Sending email to {self.email}: {message}")

@dataclass
class Product(Entity, Validatable):
    name: str
    price: float

    def validate(self) -> None:
        if not self.name:
            raise ValueError("Name is required")
        if self.price <= 0:
            raise ValueError("Price must be positive")

    def calculate_tax(self, rate: float) -> float:
        return self.price * rate

@dataclass
class Order(Entity, Validatable):
    user_id: int
    total: float

    def validate(self) -> None:
        if not self.user_id:
            raise ValueError("User ID is required")
        if self.total <= 0:
            raise ValueError("Total must be positive")

    def process_payment(self) -> None:
        print(f"Processing payment for order {self.id}")

# Repository pattern for persistence
class EntityRepository:
    def save(self, entity: Entity) -> None:
        print(f"Saving {entity.__class__.__name__} {entity.id}")

    def delete(self, entity: Entity) -> None:
        print(f"Deleting {entity.__class__.__name__} {entity.id}")
```

**Key Changes:**
- Each entity is independent with own attributes
- Validatable protocol defines interface, not implementation
- Repository pattern separates persistence logic
- No forced inheritance hierarchy
- Clear separation of concerns
- Entities can evolve independently

---

## Inappropriate Metaclass Usage

### Description

Inappropriate metaclass usage occurs when developers create complex metaclasses to share behavior across classes, resulting in code that's hard to understand, debug, and maintain.

### BAD Example

```python
class ValidateMeta(type):
    """Metaclass that adds validation to all classes"""

    def __new__(cls, name, bases, namespace):
        # Create class
        new_class = super().__new__(cls, name, bases, namespace)

        # Add validation to all methods
        for attr_name, attr_value in namespace.items():
            if callable(attr_value) and not attr_name.startswith('_'):
                def create_validated_method(method):
                    @functools.wraps(method)
                    def wrapper(self, *args, **kwargs):
                        # Pre-validation
                        if hasattr(self, '_validate_before'):
                            self._validate_before(attr_name, args, kwargs)

                        # Call method
                        result = method(self, *args, **kwargs)

                        # Post-validation
                        if hasattr(self, '_validate_after'):
                            self._validate_after(attr_name, result)

                        return result
                    return wrapper

                setattr(new_class, attr_name, create_validated_method(attr_value))

        # Add logging
        original_init = new_class.__init__

        @functools.wraps(original_init)
        def logged_init(self, *args, **kwargs):
            print(f"Creating {name}")
            original_init(self, *args, **kwargs)
            print(f"Created {name}")

        new_class.__init__ = logged_init

        # Add timestamp
        new_class._created_at = datetime.now()

        return new_class

class RegisteredUsersMeta(type):
    """Metaclass that registers all classes"""

    _registry = {}

    def __new__(cls, name, bases, namespace):
        new_class = super().__new__(cls, name, bases, namespace)

        # Register class
        if name != 'Base':
            cls._registry[name] = new_class

        # Add class method to get all instances
        @classmethod
        def get_all_instances(cls_sub):
            instances = []
            for instance in cls_sub._instances:
                instances.append(instance)
            return instances

        new_class.get_all_instances = get_all_instances
        new_class._instances = []

        return new_class

    def __getitem__(cls, name):
        return cls._registry.get(name)

class User(metaclass=ValidateMeta):
    def __init__(self, name, email):
        self.name = name
        self.email = email

    def update_name(self, new_name):
        self.name = new_name

    def update_email(self, new_email):
        self.email = new_email

class Product(metaclass=RegisteredUsersMeta):
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def update_price(self, new_price):
        self.price = new_price

# Usage - complex behavior hidden in metaclasses
user = User("Alice", "alice@example.com")
user.update_name("Bob")  # Validation happens invisibly
```

### Why It's Problematic

- **Hidden behavior**: Hard to understand what metaclasses actually do
- **Complex debugging**: Stack traces become confusing
- **Limited flexibility**: Metaclasses affect entire class
- **Code is opaque**: Can't see behavior by looking at class definition
- **Testing is difficult**: Need to understand metaclass to test properly
- **Over-engineering**: Simple problems don't need metaclasses

### How to Fix

**Refactoring Steps:**
1. Replace metaclass behavior with decorators
2. Use class decorators for class-level behavior
3. Use method decorators for method-level behavior
4. Use explicit registration patterns
5. Keep metaclasses for framework-level concerns only

### GOOD Example

```python
import functools
from datetime import datetime

def validate_methods(cls):
    """Class decorator to add validation to methods"""
    for attr_name, attr_value in cls.__dict__.items():
        if callable(attr_value) and not attr_name.startswith('_'):
            original_method = attr_value

            @functools.wraps(original_method)
            def wrapper(self, *args, __original=original_method, **kwargs):
                # Pre-validation
                if hasattr(self, '_validate_before'):
                    self._validate_before(attr_name, args, kwargs)

                # Call method
                result = __original(self, *args, **kwargs)

                # Post-validation
                if hasattr(self, '_validate_after'):
                    self._validate_after(attr_name, result)

                return result

            setattr(cls, attr_name, wrapper)
    return cls

def log_creation(cls):
    """Class decorator to add logging to __init__"""
    original_init = cls.__init__

    @functools.wraps(original_init)
    def logged_init(self, *args, **kwargs):
        print(f"Creating {cls.__name__}")
        original_init(self, *args, **kwargs)
        print(f"Created {cls.__name__}")

    cls.__init__ = logged_init
    return cls

class Registry:
    """Simple class registry"""
    _registry = {}

    @classmethod
    def register(cls, name: str):
        def decorator(class_type):
            cls._registry[name] = class_type
            return class_type
        return decorator

    @classmethod
    def get(cls, name: str):
        return cls._registry.get(name)

@log_creation
@validate_methods
class User:
    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email
        self._created_at = datetime.now()

    def _validate_before(self, method_name: str, args, kwargs):
        if method_name == 'update_name':
            if args and not args[0]:
                raise ValueError("Name cannot be empty")

    def update_name(self, new_name: str) -> None:
        self.name = new_name

    def update_email(self, new_email: str) -> None:
        self.email = new_email

@Registry.register('Product')
class Product:
    _instances = []

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price
        Product._instances.append(self)

    def update_price(self, new_price: float) -> None:
        self.price = new_price

    @classmethod
    def get_all_instances(cls):
        return cls._instances[:]

# Usage - explicit and clear
user = User("Alice", "alice@example.com")
user.update_name("Bob")

product = Product("Widget", 10.0)
all_products = Product.get_all_instances()
```

**Key Changes:**
- Behavior explicit through decorators
- Clear what each decorator does
- No hidden metaclass magic
- Easier to understand and debug
- Explicit registration pattern
- Testable in isolation

---

## False Abstraction with ABCs

### Description

False abstraction with ABCs occurs when developers create abstract base classes that don't represent meaningful abstractions, often just to share code or satisfy a perceived need for "proper" object-oriented design.

### BAD Example

```python
from abc import ABC, abstractmethod

class Processor(ABC):
    """Base processor - false abstraction"""

    def __init__(self, data):
        self.data = data
        self.processed = False

    def process(self):
        """Template method"""
        self._validate()
        result = self._transform()
        self._save()
        self.processed = True
        return result

    @abstractmethod
    def _validate(self):
        pass

    @abstractmethod
    def _transform(self):
        pass

    @abstractmethod
    def _save(self):
        pass

class CSVProcessor(Processor):
    def __init__(self, csv_data):
        super().__init__(csv_data)
        self.headers = []

    def _validate(self):
        self.headers = self.data[0]
        if not self.headers:
            raise ValueError("CSV has no headers")

    def _transform(self):
        rows = []
        for row in self.data[1:]:
            rows.append(dict(zip(self.headers, row)))
        self.data = rows
        return rows

    def _save(self):
        with open('output.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
            for row in self.data:
                writer.writerow(row.values())

class JSONProcessor(Processor):
    def __init__(self, json_data):
        super().__init__(json_data)

    def _validate(self):
        if not isinstance(self.data, dict):
            raise ValueError("JSON must be a dict")

    def _transform(self):
        pass

    def _save(self):
        with open('output.json', 'w') as f:
            json.dump(self.data, f)

class XMLProcessor(Processor):
    def __init__(self, xml_data):
        super().__init__(xml_data)

    def _validate(self):
        pass

    def _transform(self):
        root = ET.fromstring(self.data)
        self.data = {child.tag: child.text for child in root}

    def _save(self):
        root = ET.Element('data')
        for key, value in self.data.items():
            child = ET.SubElement(root, key)
            child.text = str(value)
        tree = ET.ElementTree(root)
        tree.write('output.xml')
```

### Why It's Problematic

- **Forced common interface**: CSV, JSON, XML don't share meaningful behavior
- **Template method adds no value**: Each implementation is completely different
- **ABC used for code sharing**: Not its intended purpose
- **Hard to extend**: Adding new formats requires understanding pattern
- **No real polymorphism**: Can't use processors interchangeably
- **Misleading abstraction**: Suggests generic processing when implementations are specific

### How to Fix

**Refactoring Steps:**
1. Remove ABC if there's no meaningful shared behavior
2. Create separate processors for each format
3. Use composition for any shared utilities
4. Create protocol only if multiple implementations need to be interchangeable
5. Focus on what each processor actually does

### GOOD Example

```python
import csv
import json
import xml.etree.ElementTree as ET

class CSVProcessor:
    """Process CSV data"""

    def __init__(self, csv_data: list):
        self.data = csv_data
        self.headers = []

    def process(self) -> list:
        self.headers = self.data[0]
        if not self.headers:
            raise ValueError("CSV has no headers")

        rows = []
        for row in self.data[1:]:
            rows.append(dict(zip(self.headers, row)))

        self._save(rows)
        return rows

    def _save(self, rows: list) -> None:
        with open('output.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
            for row in rows:
                writer.writerow(row.values())

class JSONProcessor:
    """Process JSON data"""

    def __init__(self, json_data: dict):
        self.data = json_data

    def process(self) -> dict:
        if not isinstance(self.data, dict):
            raise ValueError("JSON must be a dict")

        self._save(self.data)
        return self.data

    def _save(self, data: dict) -> None:
        with open('output.json', 'w') as f:
            json.dump(data, f)

class XMLProcessor:
    """Process XML data"""

    def __init__(self, xml_data: str):
        self.data = xml_data

    def process(self) -> dict:
        root = ET.fromstring(self.data)
        result = {child.tag: child.text for child in root}

        self._save(result)
        return result

    def _save(self, data: dict) -> None:
        root = ET.Element('data')
        for key, value in data.items():
            child = ET.SubElement(root, key)
            child.text = str(value)
        tree = ET.ElementTree(root)
        tree.write('output.xml')

# If you need a common interface:
from typing import Protocol

class DataProcessor(Protocol):
    """Protocol for data processors"""

    def process(self) -> any:
        ...

def process_file(processor: DataProcessor) -> any:
    """Process a file using any processor"""
    return processor.process()
```

**Key Changes:**
- Each processor is independent
- Clear what each processor does
- No forced abstraction
- Protocol only defines interface when needed
- Easier to understand and maintain
- Realistic expectations

---

## Configuration Overkill

### Description

Configuration overkill occurs when developers make everything configurable through complex configuration files, resulting in code that's hard to understand, debug, and maintain.

### BAD Example

```yaml
# config/data_processing.yml

data_processing:
  input_sources:
    - type: csv
      path: data/input.csv
      delimiter: ","
      encoding: utf-8
      has_header: true
      skip_rows: 0
      max_rows: null
      encoding_errors: strict

    - type: json
      path: data/input.json
      encoding: utf-8
      parse_dates: true
      date_format: iso8601

    - type: api
      url: https://api.example.com/data
      method: GET
      headers:
        Authorization: Bearer ${API_TOKEN}
        Content-Type: application/json
      timeout: 30
      retries: 3
      retry_delay: 1.0

  transformations:
    - type: filter
      field: status
      operator: eq
      value: active

    - type: map
      field: email
      operation: lowercase

    - type: map
      field: name
      operation: trim

    - type: validate
      rules:
        - field: email
          type: regex
          pattern: ^[^@]+@[^@]+\.[^@]+$
          error: Invalid email

        - field: age
          type: range
          min: 18
          max: 120
          error: Invalid age

    - type: enrich
      source: database
      query: SELECT * FROM users WHERE id = {id}
      cache: true
      cache_ttl: 3600

  output_destinations:
    - type: csv
      path: data/output.csv
      delimiter: ","
      encoding: utf-8
      include_header: true

    - type: database
      connection_string: ${DATABASE_URL}
      table: processed_data
      mode: upsert
      key_fields:
        - id

  validation:
    strict: true
    fail_on_error: true
    log_errors: true
    error_log: errors.log

  performance:
    batch_size: 1000
    parallel_workers: 4
    memory_limit: 1GB
```

```python
# data_processor.py

class DataProcessor:
    def __init__(self, config_path):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

    def process(self):
        for source in self.config['data_processing']['input_sources']:
            data = self._load_source(source)

            for transform in self.config['data_processing']['transformations']:
                data = self._apply_transform(data, transform)

            for destination in self.config['data_processing']['output_destinations']:
                self._save_destination(data, destination)

    def _load_source(self, source_config):
        if source_config['type'] == 'csv':
            # 50+ lines of CSV loading logic
            pass
        elif source_config['type'] == 'json':
            # 50+ lines of JSON loading logic
            pass
        elif source_config['type'] == 'api':
            # 50+ lines of API loading logic
            pass

    def _apply_transform(self, data, transform_config):
        if transform_config['type'] == 'filter':
            # 20+ lines of filter logic
            pass
        elif transform_config['type'] == 'map':
            # 20+ lines of map logic
            pass
        elif transform_config['type'] == 'validate':
            # 30+ lines of validation logic
            pass
        elif transform_config['type'] == 'enrich':
            # 30+ lines of enrichment logic
            pass

    def _save_destination(self, data, dest_config):
        if dest_config['type'] == 'csv':
            # 30+ lines of CSV saving logic
            pass
        elif dest_config['type'] == 'database':
            # 30+ lines of database saving logic
            pass
```

### Why It's Problematic

- **Configuration is code**: Complex logic expressed in YAML
- **Hard to debug**: Errors come from config, not code
- **No type safety**: Config values not validated until runtime
- **Overly complex**: 100+ lines for simple processing
- **Difficult to test**: Need to test all config combinations
- **Hidden behavior**: Can't understand flow by reading config

### How to Fix

**Refactoring Steps:**
1. Move logic from config to code
2. Keep config for values, not behavior
3. Use Python for complex logic
4. Provide sensible defaults
5. Make config minimal and focused

### GOOD Example

```yaml
# config/settings.yml

database:
  url: ${DATABASE_URL}
  table: processed_data

paths:
  input_csv: data/input.csv
  output_csv: data/output.csv

api:
  url: https://api.example.com/data
  timeout: 30

processing:
  batch_size: 1000
  parallel_workers: 4
```

```python
# data_processor.py

from dataclasses import dataclass
from typing import List, Dict, Any
import pandas as pd

@dataclass
class ProcessingConfig:
    database_url: str
    database_table: str
    input_csv_path: str
    output_csv_path: str
    api_url: str
    api_timeout: int
    batch_size: int
    parallel_workers: int

class DataProcessor:
    def __init__(self, config: ProcessingConfig):
        self.config = config

    def process_user_data(self):
        # Clear, readable logic in code
        data = self._load_csv(self.config.input_csv_path)
        data = self._validate_data(data)
        data = self._transform_data(data)
        data = self._enrich_data(data)
        self._save_to_database(data)
        self._save_to_csv(data)

    def _load_csv(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path)
        df = df[df['status'] == 'active']
        return df

    def _validate_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if not data['email'].str.match(r'^[^@]+@[^@]+\.[^@]+$').all():
            raise ValueError("Invalid email format")

        if not ((data['age'] >= 18) & (data['age'] <= 120)).all():
            raise ValueError("Invalid age range")

        return data

    def _transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        data['email'] = data['email'].str.lower()
        data['name'] = data['name'].str.strip()
        return data

    def _enrich_data(self, data: pd.DataFrame) -> pd.DataFrame:
        # Enrich with database lookup
        user_ids = data['id'].tolist()
        enriched = self._batch_lookup_users(user_ids)
        data = data.merge(enriched, on='id', how='left')
        return data

    def _save_to_database(self, data: pd.DataFrame) -> None:
        engine = create_engine(self.config.database_url)
        data.to_sql(
            self.config.database_table,
            engine,
            if_exists='replace',
            chunksize=self.config.batch_size
        )

    def _save_to_csv(self, data: pd.DataFrame) -> None:
        data.to_csv(self.config.output_csv_path, index=False)
```

**Key Changes:**
- Logic in code, config for values
- Simple, focused configuration
- Clear, readable processing pipeline
- Type-safe with dataclasses
- Easy to understand and debug
- Minimal config for what needs to vary

---

## Dogmatic DRY

### Description

Dogmatic DRY is the rigid application of DRY principle without considering context, leading to worse code quality through over-abstraction and loss of clarity.

### BAD Example

```python
# Original code - clear and simple
def send_email(to: str, subject: str, body: str) -> None:
    smtp.send(to, subject, body)

def send_sms(to: str, message: str) -> None:
    twilio.send(to, message)

def send_push(to: str, notification: dict) -> None:
    firebase.send(to, notification)

# Dogmatic DRY - everything must be the same!
def send_message(channel: str, to: str, **kwargs) -> None:
    """Send a message through any channel"""

    if channel == 'email':
        if 'subject' not in kwargs or 'body' not in kwargs:
            raise ValueError("Email requires subject and body")
        smtp.send(to, kwargs['subject'], kwargs['body'])

    elif channel == 'sms':
        if 'message' not in kwargs:
            raise ValueError("SMS requires message")
        twilio.send(to, kwargs['message'])

    elif channel == 'push':
        if 'notification' not in kwargs:
            raise ValueError("Push requires notification")
        firebase.send(to, kwargs['notification'])

    else:
        raise ValueError(f"Unknown channel: {channel}")

# Another example - merging slightly similar functions
def process_data(data: list, operation: str) -> list:
    """Process data with various operations"""

    if operation == 'filter_active':
        return [item for item in data if item['status'] == 'active']

    elif operation == 'filter_valid':
        return [item for item in data if item['valid'] is True]

    elif operation == 'filter_positive':
        return [item for item in data if item['value'] > 0]

    elif operation == 'transform_upper':
        return [{'name': item['name'].upper()} for item in data]

    elif operation == 'transform_lower':
        return [{'name': item['name'].lower()} for item in data]

    else:
        raise ValueError(f"Unknown operation: {operation}")
```

### Why It's Problematic

- **Less clear than original**: Original code was more readable
- **Loses type safety**: **kwargs hide required parameters
- **Errors only at runtime**: Can't catch issues statically
- **No actual code reuse**: Just adds indirection
- **Harder to understand**: Need to read function to know API
- **String-based dispatch**: Error-prone and not type-safe

### How to Fix

**Refactoring Steps:**
1. Accept appropriate duplication
2. Keep APIs explicit and type-safe
3. Only extract when there's real shared logic
4. Use protocols/interfaces when polymorphism is needed
5. Prioritize clarity over eliminating duplication

### GOOD Example

```python
# Keep separate, clear APIs
def send_email(to: str, subject: str, body: str) -> None:
    """Send an email"""
    smtp.send(to, subject, body)

def send_sms(to: str, message: str) -> None:
    """Send an SMS message"""
    twilio.send(to, message)

def send_push(to: str, notification: dict) -> None:
    """Send a push notification"""
    firebase.send(to, notification)

# Extract shared logic when it's genuinely shared
def send_notification(to: str, message: str, channels: List[str]) -> None:
    """Send notification through multiple channels"""
    if 'email' in channels:
        send_email(to, message, message)
    if 'sms' in channels:
        send_sms(to, message)
    if 'push' in channels:
        send_push(to, {'body': message})

# Specific operations are clearer
def filter_active(data: List[Dict]) -> List[Dict]:
    return [item for item in data if item['status'] == 'active']

def filter_valid(data: List[Dict]) -> List[Dict]:
    return [item for item in data if item['valid'] is True]

def filter_positive(data: List[Dict]) -> List[Dict]:
    return [item for item in data if item['value'] > 0]

def transform_names_upper(data: List[Dict]) -> List[Dict]:
    return [{'name': item['name'].upper()} for item in data]

def transform_names_lower(data: List[Dict]) -> List[Dict]:
    return [{'name': item['name'].lower()} for item in data]

# Or use a functional approach when appropriate
from typing import Callable, List, Dict

def filter_data(data: List[Dict], predicate: Callable[[Dict], bool]) -> List[Dict]:
    return [item for item in data if predicate(item)]

def transform_data(data: List[Dict], transform: Callable[[Dict], Dict]) -> List[Dict]:
    return [transform(item) for item in data]

# Usage
active_items = filter_data(items, lambda x: x['status'] == 'active')
upper_names = transform_data(items, lambda x: {'name': x['name'].upper()})
```

**Key Changes:**
- Clear, explicit APIs
- Type-safe with specific parameters
- Accept appropriate duplication
- Functional approach when beneficial
- Higher-order functions for shared patterns
- Prioritize readability over eliminating duplication

---

## Abstraction Inversion

### Description

Abstraction inversion occurs when abstractions become more complex than the code they abstract, creating unnecessary complexity and indirection that makes code harder to understand and maintain.

### BAD Example

```python
class DataStore(ABC):
    """Abstract data storage"""

    @abstractmethod
    def get(self, key: str) -> Any:
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        pass

class CacheDataStore(DataStore):
    """Cache-backed data store"""

    def __init__(self, cache):
        self.cache = cache

    def get(self, key: str) -> Any:
        return self.cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self.cache.set(key, value)

class PersistentDataStore(DataStore):
    """Persistent data store"""

    def __init__(self, storage):
        self.storage = storage

    def get(self, key: str) -> Any:
        return self.storage.load(key)

    def set(self, key: str, value: Any) -> None:
        self.storage.save(key, value)

class CacheWithPersistentDataStore(DataStore):
    """Cache with persistent storage"""

    def __init__(self, cache, storage):
        self.cache_layer = CacheDataStore(cache)
        self.persistent_layer = PersistentDataStore(storage)

    def get(self, key: str) -> Any:
        value = self.cache_layer.get(key)
        if value is None:
            value = self.persistent_layer.get(key)
            if value is not None:
                self.cache_layer.set(key, value)
        return value

    def set(self, key: str, value: Any) -> None:
        self.cache_layer.set(key, value)
        self.persistent_layer.set(key, value)

class SecureDataStore(DataStore):
    """Secure data store with encryption"""

    def __init__(self, data_store: DataStore, encryption):
        self.data_store = data_store
        self.encryption = encryption

    def get(self, key: str) -> Any:
        encrypted = self.data_store.get(key)
        return self.encryption.decrypt(encrypted)

    def set(self, key: str, value: Any) -> None:
        encrypted = self.encryption.encrypt(value)
        self.data_store.set(key, encrypted)

class AuditedDataStore(DataStore):
    """Audited data store with logging"""

    def __init__(self, data_store: DataStore, logger):
        self.data_store = data_store
        self.logger = logger

    def get(self, key: str) -> Any:
        self.logger.log(f"GET {key}")
        return self.data_store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.logger.log(f"SET {key}")
        self.data_store.set(key, value)

# Usage - look at all this for a simple cache!
cache = Cache()
storage = FileStorage()
encryption = AESEncryption()
logger = Logger()

secure_persistent_cache = SecureDataStore(
    AuditedDataStore(
        CacheWithPersistentDataStore(cache, storage),
        logger
    ),
    encryption
)

value = secure_persistent_cache.get('key')
secure_persistent_cache.set('key', 'value')
```

### Why It's Problematic

- **6 classes for simple caching**: Over-engineered
- **Indirection everywhere**: Can't see what code does
- **Each layer adds complexity**: No net benefit
- **More code than functionality**: Violates YAGNI
- **Hard to understand**: Need to read multiple files
- **Testing is complex**: Need to mock multiple layers

### How to Fix

**Refactoring Steps:**
1. Flatten the abstraction hierarchy
2. Combine related concerns into single classes
3. Use composition instead of wrapping
4. Keep implementations direct and simple
5. Only abstract when there's real polymorphism

### GOOD Example

```python
class SimpleCache:
    """Simple cache with optional persistence and encryption"""

    def __init__(self, cache=None, storage=None, encryption=None, logger=None):
        self.cache = cache or {}
        self.storage = storage
        self.encryption = encryption
        self.logger = logger

    def get(self, key: str) -> Any:
        if self.logger:
            self.logger.log(f"GET {key}")

        value = self.cache.get(key)
        if value is None and self.storage:
            value = self.storage.load(key)
            if value is not None:
                if self.encryption:
                    value = self.encryption.decrypt(value)
                self.cache[key] = value
        return value

    def set(self, key: str, value: Any) -> None:
        if self.logger:
            self.logger.log(f"SET {key}")

        encrypted_value = self.encryption.encrypt(value) if self.encryption else value
        self.cache[key] = encrypted_value

        if self.storage:
            self.storage.save(key, encrypted_value)

# Usage - clear and simple
cache = SimpleCache(
    cache={},
    storage=FileStorage(),
    encryption=AESEncryption(),
    logger=Logger()
)

value = cache.get('key')
cache.set('key', 'value')
```

**Key Changes:**
- Single class instead of 6
- Clear what the cache does
- No unnecessary indirection
- Easy to understand
- Simple to test
- Only complexity that's needed

---

## Magic Method Abuse

### Description

Magic method abuse occurs when developers use Python's dunder methods (special methods) to implement complex behavior that would be clearer with explicit methods, resulting in code that's hard to understand and debug.

### BAD Example

```python
class FlexibleContainer:
    """Container that does too much with magic methods"""

    def __init__(self):
        self._data = {}

    def __setitem__(self, key, value):
        # Set item with automatic type conversion
        if isinstance(value, str):
            value = value.strip().lower()
        elif isinstance(value, (int, float)):
            value = max(0, value)
        self._data[key] = value

    def __getitem__(self, key):
        # Get item with logging and caching
        print(f"Accessing {key}")
        return self._data.get(key)

    def __getattr__(self, name):
        # Auto-generate getters/setters
        if name.startswith('get_'):
            key = name[4:]
            return lambda: self._data.get(key)
        elif name.startswith('set_'):
            key = name[4:]
            return lambda value: self._set_value(key, value)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def _set_value(self, key, value):
        # Set value with validation
        if key in self._data and self._data[key] == value:
            print(f"{key} already has this value")
        else:
            self._data[key] = value

    def __call__(self, operation, *args):
        # Execute operations based on string
        if operation == 'filter':
            return {k: v for k, v in self._data.items() if args[0] in str(v)}
        elif operation == 'transform':
            return {k: args[0](v) for k, v in self._data.items()}
        elif operation == 'aggregate':
            return sum(self._data.values())

    def __add__(self, other):
        # Merge with other container
        if isinstance(other, FlexibleContainer):
            result = FlexibleContainer()
            result._data = {**self._data, **other._data}
            return result
        return self

    def __contains__(self, item):
        # Check if item exists (with loose comparison)
        return any(str(item).lower() in str(v).lower() for v in self._data.values())

# Usage - confusing and magical
container = FlexibleContainer()
container['name'] = '  Alice  '  # Automatic conversion
container['age'] = -5  # Auto-corrected to 0

value = container.get_name()  # Magic getter
container.set_age(25)  # Magic setter

filtered = container('filter', 'Alice')  # Callable container
transformed = container('transform', str.upper)
total = container('aggregate')

if 'alice' in container:  # Loose matching
    print("Found!")

merged = container + FlexibleContainer()
```

### Why It's Problematic

- **Hidden behavior**: Can't see what container does by looking at usage
- **Hard to debug**: Magic methods have implicit behavior
- **Confusing API**: Same syntax means different things
- **Violates principle of least surprise**: Unexpected behavior
- **Hard to document**: Magic methods have complex interactions
- **Type checking impossible**: Dynamic behavior breaks static analysis

### How to Fix

**Refactoring Steps:**
1. Replace magic methods with explicit methods
2. Keep magic methods for their intended purpose
3. Use descriptive method names
4. Make behavior explicit and clear
5. Reserve dunder methods for natural operations

### GOOD Example

```python
from typing import Dict, Any, Callable, List

class DataContainer:
    """Container with clear, explicit methods"""

    def __init__(self):
        self._data: Dict[str, Any] = {}

    def set(self, key: str, value: Any, auto_convert: bool = False) -> None:
        """Set a value with optional auto-conversion"""
        if auto_convert:
            value = self._auto_convert(value)
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value, returning default if not found"""
        return self._data.get(key, default)

    def get_or_set(self, key: str, factory: Callable[[], Any]) -> Any:
        """Get value or create it with factory if not exists"""
        if key not in self._data:
            self._data[key] = factory()
        return self._data[key]

    def update(self, data: Dict[str, Any]) -> None:
        """Update multiple values"""
        self._data.update(data)

    def filter(self, predicate: Callable[[str, Any], bool]) -> Dict[str, Any]:
        """Filter items by predicate"""
        return {k: v for k, v in self._data.items() if predicate(k, v)}

    def transform(self, transform: Callable[[Any], Any]) -> Dict[str, Any]:
        """Transform all values"""
        return {k: transform(v) for k, v in self._data.items()}

    def aggregate(self, operation: str) -> Any:
        """Aggregate values"""
        if operation == 'sum':
            return sum(v for v in self._data.values() if isinstance(v, (int, float)))
        elif operation == 'count':
            return len(self._data)
        elif operation == 'avg':
            values = [v for v in self._data.values() if isinstance(v, (int, float))]
            return sum(values) / len(values) if values else 0
        raise ValueError(f"Unknown operation: {operation}")

    def contains(self, value: Any, strict: bool = True) -> bool:
        """Check if value exists in container"""
        if strict:
            return value in self._data.values()
        return any(str(value).lower() in str(v).lower() for v in self._data.values())

    def merge(self, other: 'DataContainer') -> 'DataContainer':
        """Merge with another container"""
        result = DataContainer()
        result.update(self._data)
        result.update(other._data)
        return result

    def _auto_convert(self, value: Any) -> Any:
        """Auto-convert common types"""
        if isinstance(value, str):
            return value.strip().lower()
        elif isinstance(value, (int, float)):
            return max(0, value)
        return value

# Usage - clear and explicit
container = DataContainer()
container.set('name', '  Alice  ', auto_convert=True)
container.set('age', -5, auto_convert=True)

name = container.get('name')
age = container.get_or_set('age', lambda: 0)

filtered = container.filter(lambda k, v: 'Alice' in str(v))
transformed = container.transform(str.upper)
total = container.aggregate('sum')

if container.contains('alice', strict=False):
    print("Found!")

merged = container.merge(DataContainer())
```

**Key Changes:**
- Explicit method names
- Clear behavior from usage
- Optional features via parameters
- Type hints for better IDE support
- Predictable and testable
- Magic methods only where natural

---

## Detection Checklist

Use this checklist to identify DRY violations in Python code:

### Code Review Questions

- [ ] Does `utils.py` contain more than 15 unrelated functions?
- [ ] Are there multiple decorators doing the same thing with different parameters?
- [ ] Are there base classes that subclasses completely override?
- [ ] Are metaclasses used for non-framework code?
- [ ] Are ABCs used without meaningful polymorphism?
- [ ] Is configuration larger than the code it configures?
- [ ] Are similar functions merged with string-based dispatch?
- [ ] Are there more than 3 layers of class wrapping?
- [ ] Are magic methods used for complex business logic?
- [ ] Does code have string-based type selection?

### Automated Detection

- **Pyflakes/PyLint**: Check for duplicate code blocks
- **Ruff**: Fast linter that catches duplication patterns
- **Pylint with similarity checker**: `pylint --enable=duplicate-code`
- **Vulture**: Detect unused code (signs of over-abstraction)
- **McCabe complexity**: High complexity in "utility" functions

### Manual Inspection Techniques

1. **Count import locations**: Same module imported many times suggests duplication
2. **Search for copy-paste**: Look for similar function names (`process_X`, `handle_Y`)
3. **Check inheritance depth**: More than 3 levels suggests over-Abstraction
4. **Review decorator stacks**: More than 3 decorators suggests over-engineering
5. **Count utility functions**: More than 20 in one module is a red flag

### Common Symptoms

- **Large utility modules**: `utils.py` > 200 lines is suspicious
- **Configuration files**: `config.yml` > 100 lines suggests overkill
- **String-based dispatch**: `if type == 'foo'` patterns everywhere
- **Deep inheritance**: Classes inheriting from 4+ levels
- **Massive decorators**: Decorators with > 5 parameters
- **Metaclasses**: Rarely needed in application code
- **Magic method abuse**: Complex behavior in `__getattr__`, `__call__`

---

## Language-Specific Notes

### Common Causes in Python

- **Duck typing**: Encourages treating different things the same way
- **Batteries included**: Rich standard library leads to "use everything" mentality
- **Dynamic nature**: Easy to create generic, flexible code
- **Metaprogramming**: Powerful features tempt over-engineering
- **Conciseness**: Desire for "Pythonic" one-liners can hide complexity

### Language Features that Enable Anti-Patterns

- **Decorators**: Powerful but easy to overuse
- **Metaclasses**: Enable magic behavior, often abused
- **Multiple inheritance**: Tempts inappropriate code sharing
- **Dunder methods**: Can hide complex behavior
- **Dynamic typing**: Makes string-based dispatch tempting
- **`*args, **kwargs`**: Can lead to loss of type safety

### Framework-Specific Anti-Patterns

- **Django**: Massive `utils.py` modules, over-abstracted views
- **Flask**: Complex request context managers, over-generic decorators
- **FastAPI**: Over-parameterized dependencies, magic validation
- **Pydantic**: Over-complex validators, schema overkill

### Tooling Support

- **Ruff**: Fast Python linter with duplication detection
- **Pylint**: Comprehensive code analysis with similarity checker
- **Black**: Code formatter that helps spot patterns
- **isort**: Import organizer that reveals duplication
- **mypy**: Static type checker that catches loose typing
