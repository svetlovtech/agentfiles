# DIP Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern A: Direct Instantiation](#anti-pattern-a-direct-instantiation)
- [Anti-Pattern B: Tight Coupling](#anti-pattern-b-tight-coupling)
- [Anti-Pattern C: Static Dependencies](#anti-pattern-c-static-dependencies)
- [Anti-Pattern D: Service Locator](#anti-pattern-d-service-locator)
- [Anti-Pattern E: Layer Violation](#anti-pattern-e-layer-violation)
- [Anti-Pattern F: Concrete Dependencies](#anti-pattern-f-concrete-dependencies)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the DIP (Dependency Inversion Principle) principle in Python.

## Anti-Pattern A: Direct Instantiation

### Description

Direct instantiation occurs when high-level modules create concrete dependencies directly using `new ClassName()` or similar, creating tight coupling that's hard to change or test.

### BAD Example

```python
class MySQLDatabase:
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "mysql://localhost"

    def save(self, data):
        print(f"Saving to MySQL: {data}")


class UserRepository:
    def __init__(self):
        self.database = MySQLDatabase()

    def save_user(self, user):
        self.database.save(user)


class UserService:
    def __init__(self):
        self.user_repo = UserRepository()

    def create_user(self, name, email):
        user = {"name": name, "email": email}
        self.user_repo.save_user(user)


service = UserService()
service.create_user("John", "john@example.com")
```

### Why It's Problematic

- **Tight coupling**: UserService → UserRepository → MySQLDatabase
- **Hard to test**: Can't mock database
- **Hard to change**: Switching to PostgreSQL requires code changes
- **Hidden dependencies**: Not obvious what dependencies exist

### How to Fix

**Refactoring Steps:**
1. Define abstract interfaces for dependencies
2. Inject dependencies through constructor
3. Move creation logic to composition root
4. Use factory or DI container for wiring

### GOOD Example

```python
from abc import ABC, abstractmethod


class Database(ABC):
    @abstractmethod
    def save(self, data):
        pass


class UserRepository(ABC):
    @abstractmethod
    def save_user(self, user):
        pass


class MySQLDatabase(Database):
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "mysql://localhost"

    def save(self, data):
        print(f"Saving to MySQL: {data}")


class PostgreSQLDatabase(Database):
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "postgresql://localhost"

    def save(self, data):
        print(f"Saving to PostgreSQL: {data}")


class SQLUserRepository(UserRepository):
    def __init__(self, database: Database):
        self.database = database

    def save_user(self, user):
        self.database.save(user)


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def create_user(self, name, email):
        user = {"name": name, "email": email}
        self.user_repo.save_user(user)


# Composition root
database = PostgreSQLDatabase()
user_repo = SQLUserRepository(database)
service = UserService(user_repo)
service.create_user("John", "john@example.com")
```

**Key Changes:**
- Abstract interfaces defined
- Dependencies injected through constructors
- Wiring logic in composition root
- Easy to swap implementations

---

## Anti-Pattern B: Tight Coupling

### Description

Tight coupling occurs when high-level modules depend directly on low-level implementation details, making them inseparable and difficult to change independently.

### BAD Example

```python
class EmailService:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.port = 587
        self.username = "user@gmail.com"
        self.password = "password"

    def send_email(self, to, subject, body):
        print(f"Connecting to {self.smtp_server}:{self.port}")
        print(f"Sending email to {to}")


class NotificationService:
    def __init__(self):
        self.email_service = EmailService()

    def notify_user(self, user, message):
        self.email_service.send_email(
            user.email,
            "Notification",
            message
        )


class OrderService:
    def __init__(self):
        self.notification_service = NotificationService()

    def process_order(self, order):
        self.notification_service.notify_user(
            order.user,
            f"Order {order.id} processed"
        )


order_service = OrderService()
```

### Why It's Problematic

- **Dependent on implementation**: OrderService knows about EmailService
- **Hard to test**: Can't use mock notification service
- **Hard to change**: Adding SMS requires modifying multiple classes
- **Rigid architecture**: Changes ripple through layers

### How to Fix

**Refactoring Steps:**
1. Define abstraction for notification sending
2. Inject abstraction into OrderService
3. Let NotificationService decide how to notify
4. Remove coupling to specific email implementation

### GOOD Example

```python
from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def notify(self, user, message):
        pass


class EmailNotifier(Notifier):
    def __init__(self, smtp_server, port, username, password):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password

    def notify(self, user, message):
        print(f"Email to {user.email}: {message}")


class SMSNotifier(Notifier):
    def __init__(self, api_key):
        self.api_key = api_key

    def notify(self, user, message):
        print(f"SMS to {user.phone}: {message}")


class NotificationService:
    def __init__(self, notifier: Notifier):
        self.notifier = notifier

    def notify_user(self, user, message):
        self.notifier.notify(user, message)


class OrderService:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    def process_order(self, order):
        self.notification_service.notify_user(
            order.user,
            f"Order {order.id} processed"
        )


# Can easily switch notifier
email_notifier = EmailNotifier("smtp.gmail.com", 587, "user", "pass")
sms_notifier = SMSNotifier("api_key_123")

notification_service = NotificationService(email_notifier)
order_service = OrderService(notification_service)
```

**Key Changes:**
- Notifier abstraction defined
- OrderService depends on NotificationService abstraction
- NotificationService depends on Notifier abstraction
- Easy to switch notification methods

---

## Anti-Pattern C: Static Dependencies

### Description

Static dependencies use static methods or class-level instances to access services, creating global state and hidden dependencies that are difficult to test and manage.

### BAD Example

```python
class Database:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance

    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "mysql://localhost"

    def save(self, data):
        print(f"Saving: {data}")


class Logger:
    @staticmethod
    def log(message):
        print(f"LOG: {message}")


class UserService:
    def create_user(self, name, email):
        Logger.log(f"Creating user: {name}")
        user = {"name": name, "email": email}
        Database.get_instance().save(user)
        Logger.log("User created")
        return user


service = UserService()
service.create_user("John", "john@example.com")
```

### Why It's Problematic

- **Global state**: Database instance is global singleton
- **Hidden dependencies**: Not obvious that UserService uses Database and Logger
- **Hard to test**: Can't mock static dependencies
- **Tight coupling**: Code coupled to concrete static implementations

### How to Fix

**Refactoring Steps:**
1. Convert static dependencies to instance-based
2. Define abstractions for dependencies
3. Inject dependencies through constructor
4. Remove global state

### GOOD Example

```python
from abc import ABC, abstractmethod


class Database(ABC):
    @abstractmethod
    def save(self, data):
        pass


class MySQLDatabase(Database):
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "mysql://localhost"

    def save(self, data):
        print(f"Saving to MySQL: {data}")


class Logger(ABC):
    @abstractmethod
    def log(self, message):
        pass


class ConsoleLogger(Logger):
    def log(self, message):
        print(f"LOG: {message}")


class UserService:
    def __init__(self, database: Database, logger: Logger):
        self.database = database
        self.logger = logger

    def create_user(self, name, email):
        self.logger.log(f"Creating user: {name}")
        user = {"name": name, "email": email}
        self.database.save(user)
        self.logger.log("User created")
        return user


# Dependencies explicitly injected
database = MySQLDatabase()
logger = ConsoleLogger()
service = UserService(database, logger)
service.create_user("John", "john@example.com")
```

**Key Changes:**
- No static methods or global state
- Dependencies explicitly declared in constructor
- Abstractions allow implementation swapping
- Clear dependency graph

---

## Anti-Pattern D: Service Locator

### Description

Service locator pattern uses a global registry to look up dependencies, which is an improvement over direct instantiation but still creates hidden dependencies and global state.

### BAD Example

```python
class ServiceLocator:
    _services = {}

    @classmethod
    def register(cls, name, service):
        cls._services[name] = service

    @classmethod
    def get(cls, name):
        if name not in cls._services:
            raise ValueError(f"Service not found: {name}")
        return cls._services[name]


class Database:
    def save(self, data):
        print(f"Saving: {data}")


class Logger:
    def log(self, message):
        print(f"LOG: {message}")


class UserService:
    def create_user(self, name, email):
        logger = ServiceLocator.get("logger")
        database = ServiceLocator.get("database")

        logger.log(f"Creating user: {name}")
        user = {"name": name, "email": email}
        database.save(user)
        logger.log("User created")
        return user


# Register services
ServiceLocator.register("database", Database())
ServiceLocator.register("logger", Logger())

service = UserService()
service.create_user("John", "john@example.com")
```

### Why It's Problematic

- **Hidden dependencies**: Constructor doesn't show what's needed
- **Global state**: Service locator is global
- **Runtime errors**: Missing services discovered at runtime
- **Hard to test**: Need to configure global locator for tests

### How to Fix

**Refactoring Steps:**
1. Remove service locator usage
2. Inject dependencies directly through constructor
3. Make dependencies explicit
4. Use composition root for wiring

### GOOD Example

```python
from abc import ABC, abstractmethod


class Database(ABC):
    @abstractmethod
    def save(self, data):
        pass


class MySQLDatabase(Database):
    def save(self, data):
        print(f"Saving to MySQL: {data}")


class Logger(ABC):
    @abstractmethod
    def log(self, message):
        pass


class ConsoleLogger(Logger):
    def log(self, message):
        print(f"LOG: {message}")


class UserService:
    def __init__(self, database: Database, logger: Logger):
        self.database = database
        self.logger = logger

    def create_user(self, name, email):
        self.logger.log(f"Creating user: {name}")
        user = {"name": name, "email": email}
        self.database.save(user)
        self.logger.log("User created")
        return user


# Dependencies explicit in constructor
database = MySQLDatabase()
logger = ConsoleLogger()
service = UserService(database, logger)
service.create_user("John", "john@example.com")
```

**Key Changes:**
- No service locator
- Dependencies explicit in constructor
- No hidden global state
- Easy to test with mocks

---

## Anti-Pattern E: Layer Violation

### Description

Layer violation occurs when high-level business logic depends directly on low-level technical implementations like database APIs, file systems, or HTTP clients.

### BAD Example

```python
import sqlite3


class OrderService:
    def __init__(self):
        self.connection = sqlite3.connect("orders.db")
        self.cursor = self.connection.cursor()

    def create_order(self, order):
        self.cursor.execute(
            "INSERT INTO orders (user_id, total) VALUES (?, ?)",
            (order.user_id, order.total)
        )
        self.connection.commit()

    def get_order(self, order_id):
        self.cursor.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        )
        return self.cursor.fetchone()


service = OrderService()
service.create_order(order)
```

### Why It's Problematic

- **Coupled to SQLite**: Can't switch databases
- **Hard to test**: Requires real database
- **SQL in business logic**: Business layer knows persistence details
- **Hard to change**: Schema changes require code changes

### How to Fix

**Refactoring Steps:**
1. Define repository abstraction
2. Create repository implementation with SQL
3. Inject repository into service
4. Keep business logic persistence-agnostic

### GOOD Example

```python
from abc import ABC, abstractmethod
import sqlite3
from typing import Optional


class OrderRepository(ABC):
    @abstractmethod
    def save(self, order):
        pass

    @abstractmethod
    def find_by_id(self, order_id) -> Optional[dict]:
        pass


class SQLOrderRepository(OrderRepository):
    def __init__(self, connection_string):
        self.connection = sqlite3.connect(connection_string)
        self.cursor = self.connection.cursor()

    def save(self, order):
        self.cursor.execute(
            "INSERT INTO orders (user_id, total) VALUES (?, ?)",
            (order.user_id, order.total)
        )
        self.connection.commit()

    def find_by_id(self, order_id) -> Optional[dict]:
        self.cursor.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,)
        )
        return self.cursor.fetchone()


class OrderService:
    def __init__(self, order_repo: OrderRepository):
        self.order_repo = order_repo

    def create_order(self, order):
        self.order_repo.save(order)
        return order

    def get_order(self, order_id):
        return self.order_repo.find_by_id(order_id)


# Business logic separated from persistence
order_repo = SQLOrderRepository("orders.db")
service = OrderService(order_repo)
service.create_order(order)
```

**Key Changes:**
- Repository abstraction defined
- SQL details in repository, not service
- Service depends on abstraction
- Easy to test with mock repository

---

## Anti-Pattern F: Concrete Dependencies

### Description

This anti-pattern occurs when classes depend on concrete implementations rather than abstractions, often due to convenience or lack of clear interface design.

### BAD Example

```python
class FileStorage:
    def __init__(self, filepath):
        self.filepath = filepath

    def store(self, data):
        with open(self.filepath, "w") as f:
            f.write(data)


class Cache:
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value


class DataProcessor:
    def __init__(self):
        self.storage = FileStorage("data.txt")
        self.cache = Cache()

    def process(self, key, data):
        cached = self.cache.get(key)
        if cached:
            return cached

        result = self._transform(data)
        self.cache.set(key, result)
        self.storage.store(result)
        return result

    def _transform(self, data):
        return data.upper()


processor = DataProcessor()
```

### Why It's Problematic

- **Coupled to concrete implementations**: Storage and cache are concrete
- **Hard to test**: Can't mock storage or cache
- **Hard to change**: Switching storage requires code changes
- **Hidden dependencies**: Not obvious what's used

### How to Fix

**Refactoring Steps:**
1. Define abstractions for storage and cache
2. Inject abstractions through constructor
3. Create concrete implementations separately
4. Wire in composition root

### GOOD Example

```python
from abc import ABC, abstractmethod


class Storage(ABC):
    @abstractmethod
    def store(self, data):
        pass


class Cache(ABC):
    @abstractmethod
    def get(self, key):
        pass

    @abstractmethod
    def set(self, key, value):
        pass


class FileStorage(Storage):
    def __init__(self, filepath):
        self.filepath = filepath

    def store(self, data):
        with open(self.filepath, "w") as f:
            f.write(data)


class InMemoryCache(Cache):
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value


class DataProcessor:
    def __init__(self, storage: Storage, cache: Cache):
        self.storage = storage
        self.cache = cache

    def process(self, key, data):
        cached = self.cache.get(key)
        if cached:
            return cached

        result = self._transform(data)
        self.cache.set(key, result)
        self.storage.store(result)
        return result

    def _transform(self, data):
        return data.upper()


# Dependencies explicitly injected
storage = FileStorage("data.txt")
cache = InMemoryCache()
processor = DataProcessor(storage, cache)
processor.process("key1", "data")
```

**Key Changes:**
- Storage and Cache abstractions defined
- Dependencies injected through constructor
- Easy to swap implementations
- Testable with mocks

---

## Detection Checklist

### Code Review Questions

- [ ] Are classes creating dependencies with `ClassName()`?
- [ ] Are static methods used for service access?
- [ ] Are there global singletons?
- [ ] Do constructors reveal all dependencies?
- [ ] Are SQL or file I/O in business logic?
- [ ] Can dependencies be swapped without code changes?
- [ ] Are abstractions defined for all dependencies?

### Automated Detection

- **pylint**: Detect direct instantiation and global state
- **vulture**: Find unused code that might be hidden dependencies
- **mypy**: Use strict mode to detect missing abstractions
- **bandit**: Find security issues with global state

### Manual Inspection Techniques

1. **Follow new statements**: Find where dependencies are created
2. **Check constructors**: See if all dependencies are parameters
3. **Look for static methods**: Global access points
4. **Review imports**: Direct imports of concrete classes
5. **Test pain points**: Hard-to-test code indicates coupling

### Common Symptoms

- **Hard to test**: Can't mock dependencies
- **Global state**: Singletons or static access
- **Hidden dependencies**: Not obvious from constructor
- **Tight coupling**: Changes require many file edits
- **Runtime configuration**: Can't change without recompiling

---

## Language-Specific Notes

### Common Causes in Python

- **Convenience**: Direct instantiation is easiest
- **Lack of DI frameworks**: No built-in dependency injection
- **Duck typing**: Encourages using concrete types directly
- **Script heritage**: Scripts often have global state
- **Rapid prototyping**: Quick solutions become permanent

### Language Features that Enable Anti-Patterns

- **No private constructors**: Can't force factory pattern
- **Dynamic typing**: No compile-time checking of abstractions
- **Classes are objects**: Easy to create at runtime
- **Global module state**: Easy to have global singletons
- **Optional typing**: Type hints not enforced

### Framework-Specific Anti-Patterns

- **Django**: Models often have tight coupling to database
- **Flask**: Global `app` object
- **FastAPI**: Better DI but still can have issues
- **SQLAlchemy**: Direct session usage in business logic

### Tooling Support

- **injector**: Dependency injection framework
- **pyramid-sockjs**: Better dependency management
- **pytest**: Fixtures provide DI for tests
- **mypy**: Strict typing catches many issues
- **unittest.mock**: Mock concrete dependencies
