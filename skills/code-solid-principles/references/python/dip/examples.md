# DIP Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: E-Commerce Order Processing](#example-1-e-commerce-order-processing)
- [Example 2: Logger Dependency](#example-2-logger-dependency)
- [Example 3: Database Access](#example-3-database-access)
- [Example 4: Payment Processing](#example-4-payment-processing)
- [Example 5: Notification Service](#example-5-notification-service)
- [Example 6: Configuration Management](#example-6-configuration-management)
- [Example 7: Data Validation](#example-7-data-validation)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the DIP (Dependency Inversion Principle) principle in Python.

## Example 1: E-Commerce Order Processing

### BAD Example: Direct Concrete Dependencies

```python
class MySQLDatabase:
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "mysql://localhost"

    def save(self, order):
        print(f"Saving order to MySQL: {order}")


class SMTPEmailService:
    def __init__(self):
        self.smtp_server = "smtp.example.com"

    def send_confirmation(self, order):
        print(f"Sending email for order {order}")


class USATaxCalculator:
    def calculate(self, order):
        tax = order.total * 0.08
        print(f"USA tax: ${tax}")
        return tax


class StripePaymentGateway:
    def charge(self, amount):
        print(f"Charging ${amount} via Stripe")


class OrderProcessor:
    def __init__(self):
        self.database = MySQLDatabase()
        self.email_service = SMTPEmailService()
        self.tax_calculator = USATaxCalculator()
        self.payment_gateway = StripePaymentGateway()

    def process_order(self, order):
        if order.total > 1000:
            order.discount = 0.1

        tax = self.tax_calculator.calculate(order)
        total = order.total + tax

        self.payment_gateway.charge(total)
        self.email_service.send_confirmation(order)
        self.database.save(order)


order_processor = OrderProcessor()
```

**Problems:**
- Tight coupling to concrete implementations
- Can't switch to PostgreSQL without changing code
- Hard to test with mocks
- USA tax calculator hardcoded

### GOOD Example: Depend on Abstractions

```python
from abc import ABC, abstractmethod


class Database(ABC):
    @abstractmethod
    def save(self, order):
        pass


class EmailService(ABC):
    @abstractmethod
    def send_confirmation(self, order):
        pass


class TaxCalculator(ABC):
    @abstractmethod
    def calculate(self, order):
        pass


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount):
        pass


class MySQLDatabase(Database):
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "mysql://localhost"

    def save(self, order):
        print(f"Saving order to MySQL: {order}")


class PostgreSQLDatabase(Database):
    def __init__(self):
        self.connection = self._connect()

    def _connect(self):
        return "postgresql://localhost"

    def save(self, order):
        print(f"Saving order to PostgreSQL: {order}")


class SMTPEmailService(EmailService):
    def __init__(self):
        self.smtp_server = "smtp.example.com"

    def send_confirmation(self, order):
        print(f"Sending email for order {order}")


class USATaxCalculator(TaxCalculator):
    def calculate(self, order):
        tax = order.total * 0.08
        print(f"USA tax: ${tax}")
        return tax


class CanadaTaxCalculator(TaxCalculator):
    def calculate(self, order):
        tax = order.total * 0.05
        print(f"Canada tax: ${tax}")
        return tax


class StripePaymentGateway(PaymentGateway):
    def charge(self, amount):
        print(f"Charging ${amount} via Stripe")


class PayPalPaymentGateway(PaymentGateway):
    def charge(self, amount):
        print(f"Charging ${amount} via PayPal")


class OrderProcessor:
    def __init__(self, database: Database, email_service: EmailService,
                 tax_calculator: TaxCalculator, payment_gateway: PaymentGateway):
        self.database = database
        self.email_service = email_service
        self.tax_calculator = tax_calculator
        self.payment_gateway = payment_gateway

    def process_order(self, order):
        if order.total > 1000:
            order.discount = 0.1

        tax = self.tax_calculator.calculate(order)
        total = order.total + tax

        self.payment_gateway.charge(total)
        self.email_service.send_confirmation(order)
        self.database.save(order)


order_processor = OrderProcessor(
    database=PostgreSQLDatabase(),
    email_service=SMTPEmailService(),
    tax_calculator=CanadaTaxCalculator(),
    payment_gateway=PayPalPaymentGateway()
)
```

**Improvements:**
- Depends on abstractions, not concretions
- Easy to swap implementations
- Testable with mocks
- Flexible configuration

### Explanation

The BAD example creates concrete dependencies directly in OrderProcessor, making it tightly coupled to specific implementations. The GOOD example depends on abstract interfaces (Database, EmailService, etc.) injected through the constructor, allowing any implementation to be used without changing OrderProcessor code.

---

## Example 2: Logger Dependency

### BAD Example: Direct FileLogger Dependency

```python
class FileLogger:
    def __init__(self, filepath):
        self.filepath = filepath

    def log(self, message):
        with open(self.filepath, "a") as f:
            f.write(f"{message}\n")


class OrderProcessor:
    def __init__(self):
        self.logger = FileLogger("orders.log")

    def process_order(self, order):
        self.logger.log(f"Processing order: {order.id}")
        print(f"Order {order.id} processed")


processor = OrderProcessor()
processor.process_order(order)
```

**Problems:**
- OrderProcessor tightly coupled to FileLogger
- Can't switch to ConsoleLogger or DatabaseLogger
- Difficult to test (can't mock logger)
- File path hardcoded

### GOOD Example: Logger Abstraction

```python
from abc import ABC, abstractmethod


class Logger(ABC):
    @abstractmethod
    def log(self, message):
        pass


class FileLogger(Logger):
    def __init__(self, filepath):
        self.filepath = filepath

    def log(self, message):
        with open(self.filepath, "a") as f:
            f.write(f"{message}\n")


class ConsoleLogger(Logger):
    def log(self, message):
        print(f"LOG: {message}")


class DatabaseLogger(Logger):
    def __init__(self, connection):
        self.connection = connection

    def log(self, message):
        print(f"Writing to database: {message}")


class OrderProcessor:
    def __init__(self, logger: Logger):
        self.logger = logger

    def process_order(self, order):
        self.logger.log(f"Processing order: {order.id}")
        print(f"Order {order.id} processed")


file_processor = OrderProcessor(FileLogger("orders.log"))
console_processor = OrderProcessor(ConsoleLogger())
db_processor = OrderProcessor(DatabaseLogger("db_connection"))
```

**Improvements:**
- OrderProcessor depends on Logger abstraction
- Easy to swap logger implementations
- Testable with mock Logger
- Configuration-driven

### Explanation

The BAD example directly instantiates FileLogger in OrderProcessor, creating tight coupling. The GOOD example defines a Logger abstraction and injects it through the constructor, allowing any logger implementation to be used without modifying OrderProcessor.

---

## Example 3: Database Access

### BAD Example: Direct Database Connection

```python
class MySQLConnection:
    def __init__(self, host, user, password):
        self.connection = self._connect(host, user, password)

    def _connect(self, host, user, password):
        print(f"Connecting to MySQL at {host}")
        return f"mysql://{host}"

    def query(self, sql):
        print(f"Executing: {sql}")


class UserService:
    def __init__(self):
        self.db = MySQLConnection("localhost", "root", "password")

    def get_user(self, user_id):
        return self.db.query(f"SELECT * FROM users WHERE id = {user_id}")

    def save_user(self, user):
        self.db.query(f"INSERT INTO users VALUES ({user.id}, '{user.name}')")


service = UserService()
```

**Problems:**
- UserService tightly coupled to MySQL
- Can't switch databases without changing code
- Database credentials hardcoded in code
- Difficult to test with mock database

### GOOD Example: Repository Abstraction

```python
from abc import ABC, abstractmethod


class UserRepository(ABC):
    @abstractmethod
    def get_user(self, user_id):
        pass

    @abstractmethod
    def save_user(self, user):
        pass


class MySQLUserRepository(UserRepository):
    def __init__(self, connection_string):
        self.db = self._connect(connection_string)

    def _connect(self, connection_string):
        print(f"Connecting to MySQL: {connection_string}")
        return connection_string

    def get_user(self, user_id):
        print(f"SELECT * FROM users WHERE id = {user_id}")
        return {"id": user_id, "name": "John"}

    def save_user(self, user):
        print(f"INSERT INTO users VALUES ({user['id']}, '{user['name']}')")


class PostgreSQLUserRepository(UserRepository):
    def __init__(self, connection_string):
        self.db = self._connect(connection_string)

    def _connect(self, connection_string):
        print(f"Connecting to PostgreSQL: {connection_string}")
        return connection_string

    def get_user(self, user_id):
        print(f"SELECT * FROM users WHERE id = {user_id}")
        return {"id": user_id, "name": "John"}

    def save_user(self, user):
        print(f"INSERT INTO users VALUES ({user['id']}, '{user['name']}')")


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_user(self, user_id):
        return self.repository.get_user(user_id)

    def save_user(self, user):
        self.repository.save_user(user)


mysql_service = UserService(MySQLUserRepository("mysql://localhost"))
postgres_service = UserService(PostgreSQLUserRepository("postgresql://localhost"))
```

**Improvements:**
- UserService depends on UserRepository abstraction
- Easy to swap database implementations
- Testable with mock repository
- Configuration-driven database choice

### Explanation

The BAD example creates MySQLConnection directly in UserService, tightly coupling to MySQL. The GOOD example defines a UserRepository abstraction and injects the implementation, allowing any database to be used without changing UserService.

---

## Example 4: Payment Processing

### BAD Example: Hardcoded Payment Gateways

```python
class StripeGateway:
    def charge(self, amount):
        print(f"Charging ${amount} via Stripe")
        return "stripe_tx_123"


class PayPalGateway:
    def charge(self, amount):
        print(f"Charging ${amount} via PayPal")
        return "paypal_tx_456"


class SquareGateway:
    def charge(self, amount):
        print(f"Charging ${amount} via Square")
        return "square_tx_789"


class PaymentService:
    def __init__(self):
        self.stripe = StripeGateway()
        self.paypal = PayPalGateway()
        self.square = SquareGateway()

    def process_payment(self, order, provider):
        if provider == "stripe":
            tx_id = self.stripe.charge(order.total)
        elif provider == "paypal":
            tx_id = self.paypal.charge(order.total)
        elif provider == "square":
            tx_id = self.square.charge(order.total)
        else:
            raise ValueError(f"Unknown provider: {provider}")
        return tx_id


service = PaymentService()
service.process_payment(order, "stripe")
```

**Problems:**
- PaymentService creates all gateways
- Tightly coupled to specific implementations
- Adding new gateway requires code modification
- Violates Open/Closed Principle

### GOOD Example: Gateway Abstraction

```python
from abc import ABC, abstractmethod


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount):
        pass

    @abstractmethod
    def supports(self, provider):
        pass


class StripeGateway(PaymentGateway):
    def charge(self, amount):
        print(f"Charging ${amount} via Stripe")
        return "stripe_tx_123"

    def supports(self, provider):
        return provider == "stripe"


class PayPalGateway(PaymentGateway):
    def charge(self, amount):
        print(f"Charging ${amount} via PayPal")
        return "paypal_tx_456"

    def supports(self, provider):
        return provider == "paypal"


class SquareGateway(PaymentGateway):
    def charge(self, amount):
        print(f"Charging ${amount} via Square")
        return "square_tx_789"

    def supports(self, provider):
        return provider == "square"


class PaymentService:
    def __init__(self, gateways):
        self.gateways = gateways

    def process_payment(self, order, provider):
        for gateway in self.gateways:
            if gateway.supports(provider):
                return gateway.charge(order.total)
        raise ValueError(f"Unknown provider: {provider}")


service = PaymentService([
    StripeGateway(),
    PayPalGateway(),
    SquareGateway()
])
service.process_payment(order, "stripe")
```

**Improvements:**
- PaymentService depends on PaymentGateway abstraction
- Easy to add new gateways
- No code modification needed for new providers
- Configurable gateway list

### Explanation

The BAD example creates concrete gateways in PaymentService and uses conditional logic to route payments. The GOOD example depends on PaymentGateway abstraction and accepts a list of gateways, allowing new providers to be added by configuration without modifying PaymentService.

---

## Example 5: Notification Service

### BAD Example: Direct Notification Implementations

```python
class EmailNotifier:
    def send(self, recipient, message):
        print(f"Email to {recipient}: {message}")


class SMSNotifier:
    def send(self, recipient, message):
        print(f"SMS to {recipient}: {message}")


class PushNotifier:
    def send(self, recipient, message):
        print(f"Push to {recipient}: {message}")


class AlertService:
    def __init__(self):
        self.email = EmailNotifier()
        self.sms = SMSNotifier()
        self.push = PushNotifier()

    def send_alert(self, user, message, channels):
        if "email" in channels:
            self.email.send(user.email, message)
        if "sms" in channels:
            self.sms.send(user.phone, message)
        if "push" in channels:
            self.push.send(user.device_token, message)


service = AlertService()
service.send_alert(user, "Alert!", ["email", "sms"])
```

**Problems:**
- AlertService creates all notifiers
- Tightly coupled to specific implementations
- Hard to add new notification channels
- Can't test individual notifiers

### GOOD Example: Notifier Abstraction

```python
from abc import ABC, abstractmethod
from typing import List


class Notifier(ABC):
    @abstractmethod
    def send(self, recipient, message):
        pass

    @abstractmethod
    def get_recipient(self, user):
        pass


class EmailNotifier(Notifier):
    def send(self, recipient, message):
        print(f"Email to {recipient}: {message}")

    def get_recipient(self, user):
        return user.email


class SMSNotifier(Notifier):
    def send(self, recipient, message):
        print(f"SMS to {recipient}: {message}")

    def get_recipient(self, user):
        return user.phone


class PushNotifier(Notifier):
    def send(self, recipient, message):
        print(f"Push to {recipient}: {message}")

    def get_recipient(self, user):
        return user.device_token


class AlertService:
    def __init__(self, notifiers: List[Notifier]):
        self.notifiers = notifiers

    def send_alert(self, user, message, channels):
        for notifier in self.notifiers:
            if any(n.__class__.__name__.lower() == f"{channel}notifier"
                   for channel in channels):
                recipient = notifier.get_recipient(user)
                notifier.send(recipient, message)


service = AlertService([
    EmailNotifier(),
    SMSNotifier(),
    PushNotifier()
])
service.send_alert(user, "Alert!", ["email", "sms"])
```

**Improvements:**
- AlertService depends on Notifier abstraction
- Easy to add new notification types
- Configurable notifier list
- Testable with mock notifiers

### Explanation

The BAD example creates concrete notifiers in AlertService and uses conditionals to route messages. The GOOD example depends on Notifier abstraction and accepts a list of notifiers, making it easy to add new channels without modifying AlertService.

---

## Example 6: Configuration Management

### BAD Example: Direct File Access

```python
class JSONConfigReader:
    def __init__(self, filepath):
        self.filepath = filepath

    def read(self, key):
        with open(self.filepath, "r") as f:
            import json
            config = json.load(f)
        return config.get(key)


class ConfigManager:
    def __init__(self):
        self.reader = JSONConfigReader("config.json")

    def get_config(self, key):
        return self.reader.read(key)


manager = ConfigManager()
db_url = manager.get_config("database_url")
```

**Problems:**
- ConfigManager tightly coupled to JSON
- Can't switch to YAML, TOML, or environment variables
- File path hardcoded
- Difficult to test

### GOOD Example: Configuration Abstraction

```python
from abc import ABC, abstractmethod


class ConfigProvider(ABC):
    @abstractmethod
    def get(self, key):
        pass


class JSONConfigProvider(ConfigProvider):
    def __init__(self, filepath):
        self.filepath = filepath

    def get(self, key):
        with open(self.filepath, "r") as f:
            import json
            config = json.load(f)
        return config.get(key)


class YAMLConfigProvider(ConfigProvider):
    def __init__(self, filepath):
        self.filepath = filepath

    def get(self, key):
        with open(self.filepath, "r") as f:
            import yaml
            config = yaml.safe_load(f)
        return config.get(key)


class EnvironmentConfigProvider(ConfigProvider):
    def __init__(self, prefix=""):
        self.prefix = prefix

    def get(self, key):
        import os
        return os.getenv(f"{self.prefix}{key}")


class ConfigManager:
    def __init__(self, provider: ConfigProvider):
        self.provider = provider

    def get_config(self, key):
        return self.provider.get(key)


json_manager = ConfigManager(JSONConfigProvider("config.json"))
yaml_manager = ConfigManager(YAMLConfigProvider("config.yaml"))
env_manager = ConfigManager(EnvironmentConfigProvider("APP_"))
```

**Improvements:**
- ConfigManager depends on ConfigProvider abstraction
- Easy to switch configuration sources
- Configuration source configurable
- Testable with mock provider

### Explanation

The BAD example creates JSONConfigReader directly in ConfigManager, tightly coupling to JSON files. The GOOD example defines a ConfigProvider abstraction and injects it, allowing JSON, YAML, or environment variable configurations without changing ConfigManager.

---

## Example 7: Data Validation

### BAD Example: Direct Validator Instantiation

```python
class EmailValidator:
    def validate(self, email):
        if "@" not in email:
            raise ValueError("Invalid email")


class PasswordValidator:
    def validate(self, password):
        if len(password) < 8:
            raise ValueError("Password too short")


class PhoneValidator:
    def validate(self, phone):
        if not phone.isdigit():
            raise ValueError("Invalid phone")


class UserRegistrationService:
    def __init__(self):
        self.email_validator = EmailValidator()
        self.password_validator = PasswordValidator()
        self.phone_validator = PhoneValidator()

    def register_user(self, user):
        self.email_validator.validate(user.email)
        self.password_validator.validate(user.password)
        self.phone_validator.validate(user.phone)
        print("User registered")


service = UserRegistrationService()
service.register_user(user)
```

**Problems:**
- Service creates all validators
- Tightly coupled to specific validators
- Hard to add new validation rules
- Can't easily change validation logic

### GOOD Example: Validator Abstraction

```python
from abc import ABC, abstractmethod
from typing import List


class Validator(ABC):
    @abstractmethod
    def validate(self, value):
        pass

    @abstractmethod
    def applies_to(self, field_name):
        pass


class EmailValidator(Validator):
    def validate(self, email):
        if "@" not in email:
            raise ValueError("Invalid email")

    def applies_to(self, field_name):
        return field_name == "email"


class PasswordValidator(Validator):
    def validate(self, password):
        if len(password) < 8:
            raise ValueError("Password too short")

    def applies_to(self, field_name):
        return field_name == "password"


class PhoneValidator(Validator):
    def validate(self, phone):
        if not phone.isdigit():
            raise ValueError("Invalid phone")

    def applies_to(self, field_name):
        return field_name == "phone"


class UserRegistrationService:
    def __init__(self, validators: List[Validator]):
        self.validators = validators

    def register_user(self, user):
        user_dict = user.__dict__
        for validator in self.validators:
            for field_name, value in user_dict.items():
                if validator.applies_to(field_name):
                    validator.validate(value)
        print("User registered")


service = UserRegistrationService([
    EmailValidator(),
    PasswordValidator(),
    PhoneValidator()
])
service.register_user(user)
```

**Improvements:**
- Service depends on Validator abstraction
- Easy to add new validation rules
- Configurable validator list
- Testable with mock validators

### Explanation

The BAD example creates concrete validators directly in UserRegistrationService, tightly coupling to specific validation logic. The GOOD example depends on Validator abstraction and accepts a list of validators, making it easy to add new validation rules without modifying the service.

---

## Language-Specific Notes

### Idioms and Patterns

- **ABC module**: Use `abc.ABC` and `@abstractmethod` to define abstractions
- **Constructor injection**: Pass dependencies through `__init__` for clear contract
- **Dependency injection**: Use frameworks like `injector` or manual DI
- **Factory pattern**: Create abstraction for object creation
- **Type hints**: Document abstractions with typing

### Language Features

**Features that help:**
- **ABC module**: Formal way to define abstract interfaces
- **Type hints**: Document expected abstractions
- **Protocol**: Structural subtyping for flexible abstractions
- **Multiple inheritance**: Implement multiple abstractions
- **Dynamic typing**: Easy to use abstractions polymorphically

**Features that hinder:**
- **No formal interfaces**: Rely on ABCs or duck typing
- **Dynamic instantiation**: Can create concrete dependencies at runtime
- **No built-in DI**: Need manual DI or third-party libraries
- **Optional type hints**: Not enforced at runtime

### Framework Considerations

- **FastAPI**: Built-in dependency injection
- **Django**: Uses signals and middleware for loose coupling
- **Flask**: Use Flask-Injector or manual DI
- **pytest**: Fixtures provide dependency injection for tests

### Common Pitfalls

1. **Creating dependencies inside classes**: Always inject through constructor
2. **Tight coupling to concrete classes**: Depend on abstractions
3. **Service locator pattern**: Avoid global service locators
4. **New in constructors**: Don't create dependencies in constructors
5. **Not mocking in tests**: Use mocks to test abstractions
