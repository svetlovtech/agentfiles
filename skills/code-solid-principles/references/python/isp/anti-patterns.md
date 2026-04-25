# ISP Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern A: Fat Interface](#anti-pattern-a-fat-interface)
- [Anti-Pattern B: God Interface](#anti-pattern-b-god-interface)
- [Anti-Pattern C: Interface Pollution](#anti-pattern-c-interface-pollution)
- [Anti-Pattern D: Unused Methods](#anti-pattern-d-unused-methods)
- [Anti-Pattern E: Forced Implementation](#anti-pattern-e-forced-implementation)
- [Anti-Pattern F: Coupled Interfaces](#anti-pattern-c-coupled-interfaces)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the ISP (Interface Segregation Principle) principle in Python.

## Anti-Pattern A: Fat Interface

### Description

Fat interfaces contain too many methods, mixing unrelated concerns. Clients are forced to depend on methods they don't use, leading to unnecessary coupling and empty implementations.

### BAD Example

```python
class UserService:
    def get_user(self, id):
        pass

    def save_user(self, user):
        pass

    def delete_user(self, id):
        pass

    def authenticate(self, credentials):
        pass

    def authorize(self, user, resource):
        pass

    def send_welcome_email(self, user):
        pass

    def send_password_reset(self, email):
        pass

    def log_activity(self, user, action):
        pass

    def validate_user_data(self, data):
        pass

    def export_user_data(self, user, format):
        pass


class SimpleUserClient(UserService):
    def get_user(self, id):
        print(f"Getting user {id}")

    def save_user(self, user):
        print(f"Saving user")

    def authenticate(self, credentials):
        raise NotImplementedError("Not supported")

    def authorize(self, user, resource):
        raise NotImplementedError("Not supported")

    def send_welcome_email(self, user):
        raise NotImplementedError("Not supported")

    def send_password_reset(self, email):
        raise NotImplementedError("Not supported")

    def log_activity(self, user, action):
        raise NotImplementedError("Not supported")

    def validate_user_data(self, data):
        raise NotImplementedError("Not supported")

    def export_user_data(self, user, format):
        raise NotImplementedError("Not supported")
```

### Why It's Problematic

- **Unnecessary dependencies**: Client depends on 10 methods, uses only 2
- **Empty implementations**: 8 methods throw NotImplementedError
- **Hard to maintain**: Changing interface affects many clients
- **Violates SRP**: Interface mixes user management, auth, email, logging

### How to Fix

**Refactoring Steps:**
1. Identify groups of related methods
2. Create focused interfaces for each group
3. Let clients depend only on needed interfaces
4. Implement classes combine relevant interfaces

### GOOD Example

```python
from abc import ABC, abstractmethod


class UserRepository(ABC):
    @abstractmethod
    def get_user(self, id):
        pass

    @abstractmethod
    def save_user(self, user):
        pass

    @abstractmethod
    def delete_user(self, id):
        pass


class AuthenticationService(ABC):
    @abstractmethod
    def authenticate(self, credentials):
        pass

    @abstractmethod
    def authorize(self, user, resource):
        pass


class EmailService(ABC):
    @abstractmethod
    def send_welcome_email(self, user):
        pass

    @abstractmethod
    def send_password_reset(self, email):
        pass


class ActivityLogger(ABC):
    @abstractmethod
    def log_activity(self, user, action):
        pass


class SimpleUserClient(UserRepository):
    def get_user(self, id):
        print(f"Getting user {id}")

    def save_user(self, user):
        print(f"Saving user")

    def delete_user(self, id):
        print(f"Deleting user {id}")
```

**Key Changes:**
- Separated concerns into focused interfaces
- Client only implements UserRepository
- No NotImplementedError needed
- Each interface has single responsibility

---

## Anti-Pattern B: God Interface

### Description

God interfaces attempt to do everything, becoming central hubs that all clients depend on. They're impossible to implement fully and create massive coupling.

### BAD Example

```python
class SystemInterface:
    def create_user(self, user):
        pass

    def delete_user(self, id):
        pass

    def send_email(self, to, subject, body):
        pass

    def save_file(self, path, content):
        pass

    def read_file(self, path):
        pass

    def connect_database(self):
        pass

    def query_database(self, sql):
        pass

    def log_message(self, level, message):
        pass

    def schedule_task(self, task, time):
        pass

    def cancel_task(self, task_id):
        pass

    def cache_get(self, key):
        pass

    def cache_set(self, key, value):
        pass

    def make_http_request(self, url):
        pass

    def validate_input(self, data, rules):
        pass

    def format_date(self, date, format):
        pass


class EmailService(SystemInterface):
    def send_email(self, to, subject, body):
        print(f"Email to {to}")

    def create_user(self, user):
        raise NotImplementedError("Not email")

    def delete_user(self, id):
        raise NotImplementedError("Not email")

    def save_file(self, path, content):
        raise NotImplementedError("Not email")

    def read_file(self, path):
        raise NotImplementedError("Not email")

    def connect_database(self):
        raise NotImplementedError("Not email")

    def query_database(self, sql):
        raise NotImplementedError("Not email")

    def log_message(self, level, message):
        raise NotImplementedError("Not email")

    def schedule_task(self, task, time):
        raise NotImplementedError("Not email")

    def cancel_task(self, task_id):
        raise NotImplementedError("Not email")

    def cache_get(self, key):
        raise NotImplementedError("Not email")

    def cache_set(self, key, value):
        raise NotImplementedError("Not email")

    def make_http_request(self, url):
        raise NotImplementedError("Not email")

    def validate_input(self, data, rules):
        raise NotImplementedError("Not email")

    def format_date(self, date, format):
        raise NotImplementedError("Not email")
```

### Why It's Problematic

- **Massive coupling**: All clients depend on all methods
- **Impossible to implement**: EmailService throws 13 exceptions
- **Single point of failure**: Changes affect entire system
- **Mixed concerns**: Email, database, cache, HTTP all in one interface

### How to Fix

**Refactoring Steps:**
1. Decompose God Interface into focused, domain-specific interfaces
2. Create separate services for each concern
3. Use dependency injection to combine services
4. Let each service implement only relevant interface

### GOOD Example

```python
from abc import ABC, abstractmethod


class EmailProvider(ABC):
    @abstractmethod
    def send_email(self, to, subject, body):
        pass


class FileManager(ABC):
    @abstractmethod
    def save_file(self, path, content):
        pass

    @abstractmethod
    def read_file(self, path):
        pass


class DatabaseConnector(ABC):
    @abstractmethod
    def connect_database(self):
        pass

    @abstractmethod
    def query_database(self, sql):
        pass


class Logger(ABC):
    @abstractmethod
    def log_message(self, level, message):
        pass


class Scheduler(ABC):
    @abstractmethod
    def schedule_task(self, task, time):
        pass

    @abstractmethod
    def cancel_task(self, task_id):
        pass


class CacheProvider(ABC):
    @abstractmethod
    def cache_get(self, key):
        pass

    @abstractmethod
    def cache_set(self, key, value):
        pass


class HTTPClient(ABC):
    @abstractmethod
    def make_http_request(self, url):
        pass


class EmailService(EmailProvider):
    def send_email(self, to, subject, body):
        print(f"Email to {to}: {subject}")
```

**Key Changes:**
- Split into 7 focused interfaces
- EmailService only implements EmailProvider
- No coupling between unrelated services
- Easy to add new services

---

## Anti-Pattern C: Interface Pollution

### Description

Interface pollution occurs when unrelated methods are added to existing interfaces over time, causing them to become bloated and unfocused.

### BAD Example

```python
class OrderService:
    def create_order(self, order):
        pass

    def get_order(self, id):
        pass

    def update_order(self, id, updates):
        pass

    def cancel_order(self, id):
        pass


# Over time, methods are added for different concerns
class OrderService:
    def create_order(self, order):
        pass

    def get_order(self, id):
        pass

    def update_order(self, id, updates):
        pass

    def cancel_order(self, id):
        pass

    def send_order_confirmation(self, order_id):
        pass

    def send_order_shipped(self, order_id):
        pass

    def send_order_delivered(self, order_id):
        pass

    def calculate_shipping(self, order):
        pass

    def track_order(self, tracking_number):
        pass

    def apply_discount(self, order_id, discount):
        pass

    def process_refund(self, order_id):
        pass

    def generate_invoice(self, order_id):
        pass

    def get_order_analytics(self, date_range):
        pass


class SimpleOrderProcessor(OrderService):
    def create_order(self, order):
        print("Creating order")

    def get_order(self, id):
        print(f"Getting order {id}")

    def update_order(self, id, updates):
        print(f"Updating order {id}")

    def cancel_order(self, id):
        print(f"Cancelling order {id}")

    def send_order_confirmation(self, order_id):
        raise NotImplementedError("Not supported")

    def send_order_shipped(self, order_id):
        raise NotImplementedError("Not supported")

    def send_order_delivered(self, order_id):
        raise NotImplementedError("Not supported")

    def calculate_shipping(self, order):
        raise NotImplementedError("Not supported")

    def track_order(self, tracking_number):
        raise NotImplementedError("Not supported")

    def apply_discount(self, order_id, discount):
        raise NotImplementedError("Not supported")

    def process_refund(self, order_id):
        raise NotImplementedError("Not supported")

    def generate_invoice(self, order_id):
        raise NotImplementedError("Not supported")

    def get_order_analytics(self, date_range):
        raise NotImplementedError("Not supported")
```

### Why It's Problematic

- **Creeping bloat**: Interface grows with each feature addition
- **Mixed concerns**: Orders, shipping, email, analytics all mixed
- **Forced implementation**: Clients must implement all methods
- **Hard to remove**: Can't remove methods without breaking existing code

### How to Fix

**Refactoring Steps:**
1. Extract related methods into separate interfaces
2. Keep core interface focused
3. Create extension interfaces for additional features
4. Let clients choose which interfaces to implement

### GOOD Example

```python
from abc import ABC, abstractmethod


class OrderManager(ABC):
    @abstractmethod
    def create_order(self, order):
        pass

    @abstractmethod
    def get_order(self, id):
        pass

    @abstractmethod
    def update_order(self, id, updates):
        pass

    @abstractmethod
    def cancel_order(self, id):
        pass


class OrderNotifier(ABC):
    @abstractmethod
    def send_order_confirmation(self, order_id):
        pass

    @abstractmethod
    def send_order_shipped(self, order_id):
        pass

    @abstractmethod
    def send_order_delivered(self, order_id):
        pass


class OrderShipping(ABC):
    @abstractmethod
    def calculate_shipping(self, order):
        pass

    @abstractmethod
    def track_order(self, tracking_number):
        pass


class OrderFinancials(ABC):
    @abstractmethod
    def apply_discount(self, order_id, discount):
        pass

    @abstractmethod
    def process_refund(self, order_id):
        pass

    @abstractmethod
    def generate_invoice(self, order_id):
        pass


class OrderAnalytics(ABC):
    @abstractmethod
    def get_order_analytics(self, date_range):
        pass


class SimpleOrderProcessor(OrderManager):
    def create_order(self, order):
        print("Creating order")

    def get_order(self, id):
        print(f"Getting order {id}")

    def update_order(self, id, updates):
        print(f"Updating order {id}")

    def cancel_order(self, id):
        print(f"Cancelling order {id}")
```

**Key Changes:**
- Segregated into 5 focused interfaces
- Core OrderManager interface remains clean
- Extensions in separate interfaces
- Client only implements what's needed

---

## Anti-Pattern D: Unused Methods

### Description

This anti-pattern occurs when interfaces contain methods that some clients never use. This creates unnecessary coupling and maintenance burden.

### BAD Example

```python
class Vehicle:
    def start(self):
        pass

    def stop(self):
        pass

    def accelerate(self):
        pass

    def brake(self):
        pass

    def turn_left(self):
        pass

    def turn_right(self):
        pass

    def fly(self):
        pass

    def dive(self):
        pass

    def climb(self):
        pass


class Car(Vehicle):
    def start(self):
        print("Car started")

    def stop(self):
        print("Car stopped")

    def accelerate(self):
        print("Car accelerating")

    def brake(self):
        print("Car braking")

    def turn_left(self):
        print("Car turning left")

    def turn_right(self):
        print("Car turning right")

    def fly(self):
        raise NotImplementedError("Cars don't fly")

    def dive(self):
        raise NotImplementedError("Cars don't dive")

    def climb(self):
        raise NotImplementedError("Cars don't climb")


class Airplane(Vehicle):
    def start(self):
        print("Airplane started")

    def stop(self):
        print("Airplane stopped")

    def accelerate(self):
        print("Airplane accelerating")

    def brake(self):
        print("Airplane braking")

    def turn_left(self):
        print("Airplane turning left")

    def turn_right(self):
        print("Airplane turning right")

    def fly(self):
        print("Airplane flying")

    def dive(self):
        raise NotImplementedError("Airplanes don't dive")

    def climb(self):
        print("Airplane climbing")
```

### Why It's Problematic

- **Interface too broad**: Vehicle mixes land, air, and sea operations
- **Unused methods**: Car implements fly/dive/climb but never uses them
- **Type coupling**: Clients depend on all vehicle operations
- **Maintenance overhead**: Changes affect all vehicles

### How to Fix

**Refactoring Steps:**
1. Identify groups of related operations
2. Create capability-based interfaces
3. Let each vehicle implement relevant capabilities
4. Remove unused methods from base interface

### GOOD Example

```python
from abc import ABC, abstractmethod


class Movable(ABC):
    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def accelerate(self):
        pass

    @abstractmethod
    def brake(self):
        pass


class Steerable(ABC):
    @abstractmethod
    def turn_left(self):
        pass

    @abstractmethod
    def turn_right(self):
        pass


class Flyable(ABC):
    @abstractmethod
    def fly(self):
        pass


class Diver(ABC):
    @abstractmethod
    def dive(self):
        pass


class Climber(ABC):
    @abstractmethod
    def climb(self):
        pass


class Car(Movable, Steerable):
    def start(self):
        print("Car started")

    def stop(self):
        print("Car stopped")

    def accelerate(self):
        print("Car accelerating")

    def brake(self):
        print("Car braking")

    def turn_left(self):
        print("Car turning left")

    def turn_right(self):
        print("Car turning right")


class Airplane(Movable, Steerable, Flyable, Climber):
    def start(self):
        print("Airplane started")

    def stop(self):
        print("Airplane stopped")

    def accelerate(self):
        print("Airplane accelerating")

    def brake(self):
        print("Airplane braking")

    def turn_left(self):
        print("Airplane turning left")

    def turn_right(self):
        print("Airplane turning right")

    def fly(self):
        print("Airplane flying")

    def climb(self):
        print("Airplane climbing")


class Submarine(Movable, Steerable, Diver, Climber):
    def start(self):
        print("Submarine started")

    def stop(self):
        print("Submarine stopped")

    def accelerate(self):
        print("Submarine accelerating")

    def brake(self):
        print("Submarine braking")

    def turn_left(self):
        print("Submarine turning left")

    def turn_right(self):
        print("Submarine turning right")

    def dive(self):
        print("Submarine diving")

    def climb(self):
        print("Submarine climbing")
```

**Key Changes:**
- Split into capability-based interfaces
- Each vehicle implements relevant capabilities
- No unused methods
- Clear what each vehicle can do

---

## Anti-Pattern E: Forced Implementation

### Description

This anti-pattern occurs when interfaces force clients to implement methods they don't need, often due to poor interface design or trying to be too generic.

### BAD Example

```python
class DataProcessor:
    def process_text(self, text):
        pass

    def process_number(self, number):
        pass

    def process_boolean(self, value):
        pass

    def process_date(self, date):
        pass

    def process_list(self, items):
        pass

    def process_dict(self, data):
        pass

    def process_binary(self, data):
        pass

    def process_null(self):
        pass


class TextOnlyProcessor(DataProcessor):
    def process_text(self, text):
        print(f"Processing text: {text}")

    def process_number(self, number):
        raise NotImplementedError("Text only")

    def process_boolean(self, value):
        raise NotImplementedError("Text only")

    def process_date(self, date):
        raise NotImplementedError("Text only")

    def process_list(self, items):
        raise NotImplementedError("Text only")

    def process_dict(self, data):
        raise NotImplementedError("Text only")

    def process_binary(self, data):
        raise NotImplementedError("Text only")

    def process_null(self):
        raise NotImplementedError("Text only")


class NumericProcessor(DataProcessor):
    def process_text(self, text):
        raise NotImplementedError("Numeric only")

    def process_number(self, number):
        print(f"Processing number: {number}")

    def process_boolean(self, value):
        raise NotImplementedError("Numeric only")

    def process_date(self, date):
        raise NotImplementedError("Numeric only")

    def process_list(self, items):
        raise NotImplementedError("Numeric only")

    def process_dict(self, data):
        raise NotImplementedError("Numeric only")

    def process_binary(self, data):
        raise NotImplementedError("Numeric only")

    def process_null(self):
        raise NotImplementedError("Numeric only")
```

### Why It's Problematic

- **Forced coupling**: Each processor implements all 8 methods
- **Unused implementations**: Most methods throw exceptions
- **Violates ISP**: Interface mixes unrelated data types
- **Hard to extend**: Adding new types requires updating all processors

### How to Fix

**Refactoring Steps:**
1. Create separate interfaces for each data type
2. Let processors implement only relevant interfaces
3. Use composition for multi-type processors
4. Remove generic DataProcessor interface

### GOOD Example

```python
from abc import ABC, abstractmethod


class TextProcessor(ABC):
    @abstractmethod
    def process_text(self, text):
        pass


class NumberProcessor(ABC):
    @abstractmethod
    def process_number(self, number):
        pass


class BooleanProcessor(ABC):
    @abstractmethod
    def process_boolean(self, value):
        pass


class DateProcessor(ABC):
    @abstractmethod
    def process_date(self, date):
        pass


class ListProcessor(ABC):
    @abstractmethod
    def process_list(self, items):
        pass


class DictProcessor(ABC):
    @abstractmethod
    def process_dict(self, data):
        pass


class BinaryProcessor(ABC):
    @abstractmethod
    def process_binary(self, data):
        pass


class TextOnlyProcessor(TextProcessor):
    def process_text(self, text):
        print(f"Processing text: {text}")


class NumericProcessor(NumberProcessor):
    def process_number(self, number):
        print(f"Processing number: {number}")


class UniversalProcessor(TextProcessor, NumberProcessor, BooleanProcessor, DateProcessor):
    def process_text(self, text):
        print(f"Processing text: {text}")

    def process_number(self, number):
        print(f"Processing number: {number}")

    def process_boolean(self, value):
        print(f"Processing boolean: {value}")

    def process_date(self, date):
        print(f"Processing date: {date}")
```

**Key Changes:**
- Separate interfaces for each data type
- Processors implement only relevant types
- No forced exceptions
- UniversalProcessor combines needed interfaces

---

## Anti-Pattern F: Coupled Interfaces

### Description

This anti-pattern occurs when interfaces depend on each other unnecessarily, creating coupling that makes implementations inflexible and hard to change.

### BAD Example

```python
class UserRepository:
    def get_user(self, id):
        pass

    def save_user(self, user):
        pass


class EmailService:
    def send_email(self, to, subject, body):
        pass


class UserService(UserRepository, EmailService):
    def get_user(self, id):
        print(f"Getting user {id}")

    def save_user(self, user):
        print(f"Saving user")

    def send_email(self, to, subject, body):
        print(f"Email to {to}: {subject}")


class SimpleUserService(UserService):
    def get_user(self, id):
        print(f"Getting user {id}")

    def save_user(self, user):
        print(f"Saving user")

    def send_email(self, to, subject, body):
        raise NotImplementedError("No email support")
```

### Why It's Problematic

- **Coupled concerns**: UserService must know about email
- **Forced dependencies**: SimpleUserService forced to implement email
- **Mixed responsibilities**: User management and email in same class
- **Hard to test**: Can't mock email separately from user operations

### How to Fix

**Refactoring Steps:**
1. Separate interfaces by responsibility
2. Use dependency injection to combine services
3. Keep interfaces independent
4. Let clients use needed services separately

### GOOD Example

```python
from abc import ABC, abstractmethod


class UserRepository(ABC):
    @abstractmethod
    def get_user(self, id):
        pass

    @abstractmethod
    def save_user(self, user):
        pass


class EmailService(ABC):
    @abstractmethod
    def send_email(self, to, subject, body):
        pass


class UserService:
    def __init__(self, user_repo: UserRepository, email_service: EmailService = None):
        self.user_repo = user_repo
        self.email_service = email_service

    def get_user(self, id):
        return self.user_repo.get_user(id)

    def save_user(self, user):
        self.user_repo.save_user(user)

    def send_welcome_email(self, user):
        if self.email_service:
            self.email_service.send_email(user.email, "Welcome", "Welcome!")


class SimpleUserClient:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    def get_user(self, id):
        return self.user_repo.get_user(id)

    def save_user(self, user):
        self.user_repo.save_user(user)
```

**Key Changes:**
- Interfaces remain independent
- Composition combines services as needed
- Email optional in UserService
- No forced implementation

---

## Detection Checklist

### Code Review Questions

- [ ] Do any interfaces have more than 10 methods?
- [ ] Do clients implement methods they never use?
- [ ] Are there many NotImplementedError exceptions?
- [ ] Do interfaces mix unrelated concerns?
- [ ] Are methods added to existing interfaces over time?
- [ ] Do clients depend on entire interface for one method?
- [ ] Are interfaces named generically (Manager, Service, Handler)?

### Automated Detection

- **pylint**: Look for W0223 (method not overridden abstract) and R0913 (too many arguments)
- **radon**: Measure complexity in interface implementations
- **pyreverse**: Generate diagrams to show interface relationships
- **unittest.mock**: Test interface substitutability

### Manual Inspection Techniques

1. **Count interface methods**: More than 7-10 indicates possible fat interface
2. **Check NotImplementedError**: Multiple occurrences suggest interface segregation needed
3. **Review client usage**: See which methods are actually called
4. **Analyze method groups**: Group related methods, consider separating

### Common Symptoms

- **NotImplementedError**: Indicates method shouldn't be in interface
- **Empty method bodies**: Methods that do nothing suggest unneeded
- **Complex constructors**: Many dependencies indicate too many interfaces
- **Generic naming**: "Service", "Manager" often indicate fat interfaces
- **Test pain**: Need many mocks indicates tight coupling

---

## Language-Specific Notes

### Common Causes in Python

- **Convenience methods**: Adding helpful methods to common interfaces
- **Feature creep**: Gradually adding methods to existing interfaces
- **Lack of formal interfaces**: Relying on duck typing without clear boundaries
- **ABC underuse**: Not using ABCs to formally define contracts
- **Quick solutions**: Adding methods to existing interface vs creating new one

### Language Features that Enable Anti-Patterns

- **Multiple inheritance**: Makes it easy to combine interfaces badly
- **Duck typing**: No compile-time checking of interface usage
- **Optional type hints**: Interfaces not enforced at runtime
- **Dynamic modification**: Can add methods at runtime
- **No formal interfaces**: Rely on conventions vs explicit contracts

### Framework-Specific Anti-Patterns

- **Django**: Fat model interfaces with many methods
- **SQLAlchemy**: Session interfaces that do too much
- **Pydantic**: Models with mixed validation and business logic
- **FastAPI**: Dependency injection with overly broad dependencies

### Tooling Support

- **mypy**: Detect unused interface members with strict mode
- **pylint**: Find implementations with many exceptions
- **vulture**: Find unused code in interface implementations
- **pyreverse**: Visualize interface relationships
- **unittest.mock**: Test interface substitutability
