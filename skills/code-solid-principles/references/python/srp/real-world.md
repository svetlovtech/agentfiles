# SRP Real-World Scenarios - Python

## Table of Contents

- [Introduction](#introduction)
- [Scenario 1: User Management System](#scenario-1-user-management-system)
- [Scenario 2: E-Commerce Order Processing](#scenario-2-e-commerce-order-processing)
- [Scenario 3: Data Pipeline Processing](#scenario-3-data-pipeline-processing)
- [Scenario 4: REST API Service Layer](#scenario-4-rest-api-service-layer)
- [Scenario 5: Notification System](#scenario-5-notification-system)
- [Scenario 6: Report Generation System](#scenario-6-report-generation-system)
- [Migration Guide](#migration-guide)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document presents real-world scenarios where the Single Responsibility Principle is applied in Python. Each scenario includes a practical problem, analysis of violations, and step-by-step solution with code examples.

## Scenario 1: User Management System

### Context

A web application needs to handle user registration, authentication, password management, profile updates, and email notifications. The current implementation has all this functionality mixed in a single `User` class.

### Problem Description

The `User` model in the application handles data storage, password hashing, authentication, validation, email notifications, and API formatting. This makes the class difficult to test, modify, and maintain. Changing the email provider requires modifying the user model, and testing authentication requires setting up email infrastructure.

### Analysis of Violations

**Current Issues:**
- **Multiple responsibilities**: Data model, persistence, authentication, password management, validation, notifications, formatting
- **Low cohesion**: Methods don't share a common purpose beyond "user-related"
- **High coupling**: Class depends on database, email service, password hashing libraries
- **Testability**: Cannot test authentication without email service, or password hashing without database

**Impact:**
- **Code quality**: Hard to understand and navigate; developers don't know where to add new features
- **Maintainability**: Any change risks breaking unrelated functionality; requires comprehensive regression testing
- **Development velocity**: Merge conflicts common as multiple developers modify same class; slow deployment due to extensive testing

### BAD Approach

```python
import hashlib
import smtplib
from email.mime.text import MIMEText
from typing import Optional
from dataclasses import dataclass


@dataclass
class User:
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    name: str = ""

    def save_to_database(self, db_connection) -> None:
        if self.id:
            cursor = db_connection.cursor()
            cursor.execute(
                "UPDATE users SET username=?, email=?, password_hash=?, name=? WHERE id=?",
                (self.username, self.email, self.password_hash, self.name, self.id)
            )
        else:
            cursor = db_connection.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, name) VALUES (?, ?, ?, ?)",
                (self.username, self.email, self.password_hash, self.name)
            )
            self.id = cursor.lastrowid

    @staticmethod
    def find_by_username(db_connection, username: str) -> Optional['User']:
        cursor = db_connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return User(id=row[0], username=row[1], email=row[2],
                       password_hash=row[3], name=row[4])
        return None

    def set_password(self, password: str) -> None:
        self.password_hash = self._hash_password(password)

    def check_password(self, password: str) -> bool:
        return self._hash_password(password) == self.password_hash

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def validate_email(self) -> bool:
        return '@' in self.email and '.' in self.email

    def validate_username(self) -> bool:
        return len(self.username) >= 3 and self.username.isalnum()

    def send_welcome_email(self) -> None:
        msg = MIMEText(f"Welcome {self.username}!")
        msg['Subject'] = 'Welcome to our app'
        msg['From'] = 'noreply@example.com'
        msg['To'] = self.email

        with smtplib.SMTP('localhost') as server:
            server.send_message(msg)

    def send_password_reset_email(self, reset_token: str) -> None:
        msg = MIMEText(f"Reset your password: {reset_token}")
        msg['Subject'] = 'Password Reset'
        msg['From'] = 'noreply@example.com'
        msg['To'] = self.email

        with smtplib.SMTP('localhost') as server:
            server.send_message(msg)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'name': self.name
        }

    def to_api_response(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'fullName': self.name
        }
```

**Why This Approach Fails:**
- Changing password hashing algorithm requires modifying the User model
- Switching email provider requires modifying User model
- Testing password validation requires database setup
- Cannot send emails without creating a User object
- API formatting logic mixed with domain model

### GOOD Approach

**Solution Strategy:**
1. Extract data persistence to repository pattern
2. Extract password operations to password service
3. Extract validation to validator classes
4. Extract email sending to notification service
5. Extract formatting to response formatter
6. Keep User as pure data model

```python
from dataclasses import dataclass
from typing import Optional, Protocol
import hashlib


@dataclass
class User:
    """Pure domain model for user data."""
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    name: str = ""


class PasswordHasher:
    """Handles password hashing and verification."""

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, password_hash: str) -> bool:
        return self.hash_password(password) == password_hash


class EmailValidator:
    """Validates email format."""

    def is_valid(self, email: str) -> bool:
        return '@' in email and '.' in email


class UsernameValidator:
    """Validates username format."""

    def is_valid(self, username: str) -> bool:
        return len(username) >= 3 and username.isalnum()


class UserRepository(Protocol):
    """Repository interface for user data access."""

    def save(self, user: User) -> User: ...

    def find_by_username(self, username: str) -> Optional[User]: ...

    def find_by_id(self, user_id: int) -> Optional[User]: ...


class SQLiteUserRepository:
    """SQLite implementation of UserRepository."""

    def __init__(self, db_connection):
        self.db = db_connection

    def save(self, user: User) -> User:
        cursor = self.db.cursor()
        if user.id:
            cursor.execute(
                "UPDATE users SET username=?, email=?, password_hash=?, name=? WHERE id=?",
                (user.username, user.email, user.password_hash, user.name, user.id)
            )
        else:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, name) VALUES (?, ?, ?, ?)",
                (user.username, user.email, user.password_hash, user.name)
            )
            user.id = cursor.lastrowid
        return user

    def find_by_username(self, username: str) -> Optional[User]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row:
            return User(id=row[0], username=row[1], email=row[2],
                       password_hash=row[3], name=row[4])
        return None

    def find_by_id(self, user_id: int) -> Optional[User]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return User(id=row[0], username=row[1], email=row[2],
                       password_hash=row[3], name=row[4])
        return None


class EmailService(Protocol):
    """Email service interface."""

    def send_welcome(self, username: str, email: str) -> None: ...

    def send_password_reset(self, email: str, reset_token: str) -> None: ...


class SMTPEmailService:
    """SMTP implementation of EmailService."""

    def __init__(self, smtp_host: str = 'localhost', smtp_port: int = 25):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def _send_email(self, to_email: str, subject: str, body: str) -> None:
        from email.mime.text import MIMEText
        import smtplib

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = 'noreply@example.com'
        msg['To'] = to_email

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.send_message(msg)

    def send_welcome(self, username: str, email: str) -> None:
        self._send_email(email, 'Welcome to our app', f"Welcome {username}!")

    def send_password_reset(self, email: str, reset_token: str) -> None:
        self._send_email(email, 'Password Reset', f"Reset your password: {reset_token}")


class UserFormatter:
    """Formats user data for different contexts."""

    def to_dict(self, user: User) -> dict:
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': user.name
        }

    def to_api_response(self, user: User) -> dict:
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'fullName': user.name
        }


class UserService:
    """High-level service for user operations."""

    def __init__(self, user_repo: UserRepository, password_hasher: PasswordHasher,
                 email_validator: EmailValidator, username_validator: UsernameValidator,
                 email_service: EmailService):
        self.user_repo = user_repo
        self.password_hasher = password_hasher
        self.email_validator = email_validator
        self.username_validator = username_validator
        self.email_service = email_service

    def register_user(self, username: str, email: str, password: str, name: str) -> User:
        if not self.username_validator.is_valid(username):
            raise ValueError("Invalid username")

        if not self.email_validator.is_valid(email):
            raise ValueError("Invalid email")

        if self.user_repo.find_by_username(username):
            raise ValueError("Username already exists")

        user = User(
            username=username,
            email=email,
            password_hash=self.password_hasher.hash_password(password),
            name=name
        )

        user = self.user_repo.save(user)
        self.email_service.send_welcome(username, email)

        return user

    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.user_repo.find_by_username(username)

        if not user:
            return None

        if self.password_hasher.verify_password(password, user.password_hash):
            return user

        return None
```

**Benefits:**
- Each class has a single, well-defined responsibility
- Password hashing can be changed without touching user model
- Email provider can be swapped without modifying business logic
- All components can be tested independently
- Easy to add new features (e.g., SMS notifications) without modifying existing code

### Implementation Steps

1. **Step 1: Create pure data model**
   - Create `User` dataclass with only attributes
   - Remove all methods from the class

2. **Step 2: Extract password operations**
   - Create `PasswordHasher` class
   - Move `hash_password` and `verify_password` methods

3. **Step 3: Extract validation logic**
   - Create `EmailValidator` and `UsernameValidator` classes
   - Move validation methods to these classes

4. **Step 4: Extract data access**
   - Create `UserRepository` protocol
   - Create `SQLiteUserRepository` implementation
   - Move database operations to repository

5. **Step 5: Extract email sending**
   - Create `EmailService` protocol
   - Create `SMTPEmailService` implementation
   - Move email methods to service

6. **Step 6: Extract formatting**
   - Create `UserFormatter` class
   - Move formatting methods

7. **Step 7: Create orchestrator**
   - Create `UserService` that coordinates all services
   - Use dependency injection to wire components

### Testing the Solution

**Test Cases:**
- `TestPasswordHasher`: Verify password hashing and verification work correctly
- `TestEmailValidator`: Test email validation with valid and invalid emails
- `TestUsernameValidator`: Test username validation with various inputs
- `TestUserRepository`: Mock database and verify CRUD operations
- `TestEmailService`: Mock SMTP server and verify emails are sent correctly
- `TestUserService`: Integration test using mock dependencies

**Verification:**
- Verify that changing password hashing algorithm only requires modifying `PasswordHasher`
- Verify that switching to a different email provider only requires creating new `EmailService` implementation
- Verify that all tests pass without needing actual database or email server

---

## Scenario 2: E-Commerce Order Processing

### Context

An e-commerce platform processes orders from customers. The order processing system currently handles validation, pricing calculation, inventory management, payment processing, database persistence, and email notifications all in one class.

### Problem Description

The `OrderProcessor` class is responsible for validating orders, calculating prices and taxes, applying discounts, checking inventory, processing payments, saving orders to the database, sending confirmation emails, and generating invoices. This violates SRP as changes to any of these concerns require modifying the same class, making it difficult to test and maintain.

### Analysis of Violations

**Current Issues:**
- **Too many responsibilities**: Validation, pricing, inventory, payment, persistence, notifications, invoicing
- **Change impact**: Changing discount rules affects payment processing; changing payment gateway affects email sending
- **Testing complexity**: Requires database, payment API, email server, and inventory system for tests
- **Low reusability**: Cannot use pricing calculation without processing entire order

**Impact:**
- **Code quality**: Monolithic class with thousands of lines; difficult to navigate and understand
- **Maintainability**: Single point of failure; bugs in email can break payment processing
- **Development velocity**: Features blocked by multiple concerns; slow iteration due to extensive testing

### BAD Approach

```python
import sqlite3
import requests
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class OrderItem:
    product_id: str
    quantity: int
    price: float


@dataclass
class Order:
    customer_id: str
    items: List[OrderItem]
    email: str
    payment_token: str
    discount_code: str = None


class OrderProcessor:
    """Processes orders from validation to confirmation."""

    def __init__(self, db_path: str = 'orders.db'):
        self.db_path = db_path

    def process_order(self, order: Order) -> Dict:
        # Validation
        if not order.customer_id:
            raise ValueError("Customer ID required")

        if not order.items:
            raise ValueError("Items required")

        for item in order.items:
            if item.quantity <= 0:
                raise ValueError("Quantity must be positive")

        # Pricing
        subtotal = sum(item.quantity * item.price for item in order.items)

        if order.discount_code == 'SAVE10':
            subtotal *= 0.9
        elif order.discount_code == 'SAVE20':
            subtotal *= 0.8

        tax = subtotal * 0.1
        total = subtotal + tax

        # Inventory check
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for item in order.items:
            cursor.execute(
                "SELECT quantity FROM inventory WHERE product_id = ?",
                (item.product_id,)
            )
            result = cursor.fetchone()

            if not result or result[0] < item.quantity:
                conn.close()
                raise ValueError(f"Insufficient inventory for {item.product_id}")

        # Payment processing
        response = requests.post(
            'https://payment-gateway.com/api/charge',
            json={'amount': total, 'token': order.payment_token}
        )

        if response.status_code != 200:
            conn.close()
            raise ValueError("Payment failed")

        # Save order
        cursor.execute(
            "INSERT INTO orders (customer_id, total, status) VALUES (?, ?, ?)",
            (order.customer_id, total, 'confirmed')
        )
        order_id = cursor.lastrowid

        for item in order.items:
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) "
                "VALUES (?, ?, ?, ?)",
                (order_id, item.product_id, item.quantity, item.price)
            )

        # Update inventory
        for item in order.items:
            cursor.execute(
                "UPDATE inventory SET quantity = quantity - ? "
                "WHERE product_id = ?",
                (item.quantity, item.product_id)
            )

        conn.commit()
        conn.close()

        # Send email
        msg = MIMEText(f"Your order {order_id} is confirmed! Total: ${total:.2f}")
        msg['Subject'] = 'Order Confirmation'
        msg['To'] = order.email

        with smtplib.SMTP('localhost') as server:
            server.send_message(msg)

        return {'order_id': order_id, 'total': total, 'status': 'confirmed'}
```

**Why This Approach Fails:**
- Changing discount logic requires modifying the entire process
- Cannot use pricing calculation independently
- Testing payment processing requires database and email server
- Switching payment gateway requires modifying the class
- Cannot add new payment methods without modifying the class

### GOOD Approach

**Solution Strategy:**
1. Extract validation to validator classes
2. Extract pricing to pricing calculator
3. Extract inventory check to inventory manager
4. Extract payment processing to payment service
5. Extract data access to repository
6. Extract email sending to notification service
7. Create orchestrator service to coordinate

```python
from dataclasses import dataclass
from typing import List, Dict, Protocol, Optional
import json


@dataclass
class OrderItem:
    product_id: str
    quantity: int
    price: float


@dataclass
class Order:
    customer_id: str
    items: List[OrderItem]
    email: str
    payment_token: str
    discount_code: str = None


class OrderValidator:
    """Validates order data."""

    def validate(self, order: Order) -> List[str]:
        errors = []

        if not order.customer_id:
            errors.append("Customer ID required")

        if not order.items:
            errors.append("Items required")

        for item in order.items:
            if item.quantity <= 0:
                errors.append(f"Quantity must be positive for {item.product_id}")

        return errors


class PricingCalculator:
    """Calculates order pricing including discounts and tax."""

    DISCOUNTS = {
        'SAVE10': 0.1,
        'SAVE20': 0.2,
        'WELCOME': 0.15
    }

    def calculate_total(self, order: Order, tax_rate: float = 0.1) -> float:
        subtotal = sum(item.quantity * item.price for item in order.items)

        if order.discount_code in self.DISCOUNTS:
            subtotal *= (1 - self.DISCOUNTS[order.discount_code])

        return subtotal * (1 + tax_rate)


class InventoryManager(Protocol):
    """Manages inventory operations."""

    def check_availability(self, items: List[OrderItem]) -> bool: ...

    def reserve_items(self, items: List[OrderItem]) -> None: ...


class PaymentService(Protocol):
    """Processes payment transactions."""

    def charge(self, amount: float, token: str) -> bool: ...


class OrderRepository(Protocol):
    """Persists order data."""

    def save_order(self, order: Order, total: float) -> int: ...

    def save_order_items(self, order_id: int, items: List[OrderItem]) -> None: ...


class NotificationService(Protocol):
    """Sends order notifications."""

    def send_confirmation(self, email: str, order_id: int, total: float) -> None: ...


class OrderProcessor:
    """Orchestrates order processing workflow."""

    def __init__(self, validator: OrderValidator,
                 pricing_calculator: PricingCalculator,
                 inventory_manager: InventoryManager,
                 payment_service: PaymentService,
                 order_repository: OrderRepository,
                 notification_service: NotificationService):
        self.validator = validator
        self.pricing_calculator = pricing_calculator
        self.inventory_manager = inventory_manager
        self.payment_service = payment_service
        self.order_repository = order_repository
        self.notification_service = notification_service

    def process_order(self, order: Order) -> Dict:
        errors = self.validator.validate(order)

        if errors:
            raise ValueError(f"Invalid order: {errors}")

        total = self.pricing_calculator.calculate_total(order)

        if not self.inventory_manager.check_availability(order.items):
            raise ValueError("Insufficient inventory")

        if not self.payment_service.charge(total, order.payment_token):
            raise ValueError("Payment failed")

        order_id = self.order_repository.save_order(order, total)
        self.order_repository.save_order_items(order_id, order.items)

        self.inventory_manager.reserve_items(order.items)
        self.notification_service.send_confirmation(order.email, order_id, total)

        return {'order_id': order_id, 'total': total, 'status': 'confirmed'}
```

**Benefits:**
- Each service has single responsibility
- Can test pricing calculation without database or payment API
- Can add new payment methods by implementing `PaymentService`
- Can switch email provider by implementing `NotificationService`
- Can change discount rules without modifying order processing

### Implementation Steps

1. **Step 1: Extract validation**
   - Create `OrderValidator` class
   - Move all validation logic to this class

2. **Step 2: Extract pricing**
   - Create `PricingCalculator` class
   - Move pricing, discount, and tax logic

3. **Step 3: Define inventory interface**
   - Create `InventoryManager` protocol
   - Implement concrete class with database operations

4. **Step 4: Define payment interface**
   - Create `PaymentService` protocol
   - Implement concrete class with HTTP calls

5. **Step 5: Define repository interface**
   - Create `OrderRepository` protocol
   - Implement concrete class with database operations

6. **Step 6: Define notification interface**
   - Create `NotificationService` protocol
   - Implement concrete class with email operations

7. **Step 7: Create orchestrator**
   - Create `OrderProcessor` that coordinates all services
   - Use dependency injection

### Testing the Solution

**Test Cases:**
- `TestOrderValidator`: Test validation with valid and invalid orders
- `TestPricingCalculator`: Test pricing calculation with various discounts
- `TestInventoryManager`: Mock database and test inventory checks
- `TestPaymentService`: Mock payment gateway and test charging
- `TestOrderRepository`: Mock database and test order persistence
- `TestNotificationService`: Mock email server and test notifications
- `TestOrderProcessor`: Integration test using all mock dependencies

**Verification:**
- Verify that adding a new discount code only requires modifying `PricingCalculator`
- Verify that switching payment gateways only requires implementing new `PaymentService`
- Verify that all tests pass without needing actual database, payment API, or email server

---

## Scenario 3: Data Pipeline Processing

### Context

A data engineering team needs to build a pipeline that reads files from various sources, validates and transforms data, calculates statistics, and outputs results to multiple destinations (database, file, API). The current implementation mixes all these concerns in one class.

### Problem Description

The `DataPipeline` class handles file reading, data parsing, validation, transformation, statistics calculation, and output to multiple destinations. This makes it impossible to reuse individual components, difficult to test transformations without file I/O, and hard to add new data sources or destinations without modifying the pipeline.

### Analysis of Violations

**Current Issues:**
- **Mixed concerns**: File I/O, parsing, validation, transformation, calculation, output
- **No separation**: Cannot use transformer without reading files
- **No flexibility**: Adding new data sources requires modifying pipeline
- **Testing complexity**: Requires files, database, and API for tests

**Impact:**
- **Code quality**: Large, complex class difficult to understand
- **Maintainability**: Changes to one concern affect entire pipeline
- **Development velocity**: Cannot iterate on transformations independently

### BAD Approach

```python
import csv
import json
import sqlite3
import requests
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class DataRecord:
    id: str
    name: str
    value: float


class DataPipeline:
    """End-to-end data processing pipeline."""

    def __init__(self, db_path: str = 'data.db'):
        self.db_path = db_path

    def process_csv_file(self, input_path: str) -> None:
        # Read file
        with open(input_path, 'r') as f:
            reader = csv.DictReader(f)
            raw_data = list(reader)

        # Validate
        records = []
        for row in raw_data:
            if not row.get('id') or not row.get('name') or not row.get('value'):
                continue

            try:
                value = float(row['value'])
                if value < 0:
                    continue

                record = DataRecord(
                    id=row['id'],
                    name=row['name'].strip().upper(),
                    value=value
                )
                records.append(record)
            except ValueError:
                continue

        # Calculate statistics
        values = [r.value for r in records]
        stats = {
            'count': len(values),
            'sum': sum(values),
            'avg': sum(values) / len(values) if values else 0,
            'min': min(values) if values else 0,
            'max': max(values) if values else 0
        }

        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO statistics (count, sum, avg, min, max) VALUES (?, ?, ?, ?, ?)",
            (stats['count'], stats['sum'], stats['avg'], stats['min'], stats['max'])
        )

        for record in records:
            cursor.execute(
                "INSERT INTO data_records (id, name, value) VALUES (?, ?, ?)",
                (record.id, record.name, record.value)
            )

        conn.commit()
        conn.close()

        # Send to API
        requests.post(
            'https://api.example.com/data',
            json={
                'statistics': stats,
                'records': [r.__dict__ for r in records]
            }
        )

        # Write output file
        with open('output.json', 'w') as f:
            json.dump({
                'statistics': stats,
                'records': [r.__dict__ for r in records]
            }, f, indent=2)
```

**Why This Approach Fails:**
- Cannot transform data without reading files
- Cannot save to database without calculating statistics
- Cannot use transformer for different input sources
- Testing validation requires file system, database, and API
- Adding new output destination requires modifying pipeline

### GOOD Approach

**Solution Strategy:**
1. Extract file reading to reader components
2. Extract parsing to parser components
3. Extract validation to validator
4. Extract transformation to transformer
5. Extract statistics calculation to calculator
6. Extract output to writer components
7. Create pipeline orchestrator

```python
from typing import List, Dict, Protocol, Iterator
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class DataRecord:
    id: str
    name: str
    value: float


class DataSource(Protocol):
    """Data source interface."""

    def read(self) -> List[Dict]: ...


class CSVDataSource:
    """Reads data from CSV files."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def read(self) -> List[Dict]:
        import csv

        with open(self.file_path, 'r') as f:
            reader = csv.DictReader(f)
            return list(reader)


class JSONDataSource:
    """Reads data from JSON files."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def read(self) -> List[Dict]:
        import json

        with open(self.file_path, 'r') as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]


class DataValidator:
    """Validates data records."""

    def validate_record(self, raw: Dict) -> bool:
        return bool(raw.get('id') and raw.get('name') and raw.get('value'))

    def validate_value(self, value: float) -> bool:
        return value >= 0


class DataTransformer:
    """Transforms raw data into structured records."""

    def transform(self, raw: Dict) -> DataRecord:
        return DataRecord(
            id=raw['id'],
            name=raw['name'].strip().upper(),
            value=float(raw['value'])
        )


class StatisticsCalculator:
    """Calculates data statistics."""

    def calculate(self, records: List[DataRecord]) -> Dict:
        values = [r.value for r in records]

        return {
            'count': len(values),
            'sum': sum(values),
            'avg': sum(values) / len(values) if values else 0,
            'min': min(values) if values else 0,
            'max': max(values) if values else 0
        }


class DataSink(Protocol):
    """Data sink interface."""

    def write(self, data: Dict) -> None: ...


class DatabaseSink:
    """Writes data to SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def write(self, data: Dict) -> None:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = data['statistics']
        records = data['records']

        cursor.execute(
            "INSERT INTO statistics (count, sum, avg, min, max) VALUES (?, ?, ?, ?, ?)",
            (stats['count'], stats['sum'], stats['avg'], stats['min'], stats['max'])
        )

        for record in records:
            cursor.execute(
                "INSERT INTO data_records (id, name, value) VALUES (?, ?, ?)",
                (record['id'], record['name'], record['value'])
            )

        conn.commit()
        conn.close()


class HTTPSink:
    """Writes data to HTTP API."""

    def __init__(self, api_url: str):
        self.api_url = api_url

    def write(self, data: Dict) -> None:
        import requests

        requests.post(self.api_url, json=data)


class FileSink:
    """Writes data to file."""

    def __init__(self, file_path: str, format: str = 'json'):
        self.file_path = file_path
        self.format = format

    def write(self, data: Dict) -> None:
        import json

        with open(self.file_path, 'w') as f:
            if self.format == 'json':
                json.dump(data, f, indent=2)


class DataPipeline:
    """Orchestrates data processing workflow."""

    def __init__(self, source: DataSource, validator: DataValidator,
                 transformer: DataTransformer, calculator: StatisticsCalculator,
                 sinks: List[DataSink]):
        self.source = source
        self.validator = validator
        self.transformer = transformer
        self.calculator = calculator
        self.sinks = sinks

    def process(self) -> Dict:
        raw_data = self.source.read()

        validated = [row for row in raw_data if self.validator.validate_record(row)]

        records = []
        for row in validated:
            try:
                record = self.transformer.transform(row)

                if self.validator.validate_value(record.value):
                    records.append(record)
            except (ValueError, KeyError):
                continue

        stats = self.calculator.calculate(records)

        output = {
            'statistics': stats,
            'records': [r.__dict__ for r in records]
        }

        for sink in self.sinks:
            sink.write(output)

        return output
```

**Benefits:**
- Each component has single responsibility
- Can test transformation without file I/O
- Can mix and match sources, transformations, and sinks
- Can add new data sources by implementing `DataSource`
- Can add new destinations by implementing `DataSink`

### Implementation Steps

1. **Step 1: Create data model**
   - Create `DataRecord` dataclass

2. **Step 2: Define source interface**
   - Create `DataSource` protocol
   - Implement `CSVDataSource` and `JSONDataSource`

3. **Step 3: Extract validation**
   - Create `DataValidator` class

4. **Step 4: Extract transformation**
   - Create `DataTransformer` class

5. **Step 5: Extract calculation**
   - Create `StatisticsCalculator` class

6. **Step 6: Define sink interface**
   - Create `DataSink` protocol
   - Implement `DatabaseSink`, `HTTPSink`, and `FileSink`

7. **Step 7: Create orchestrator**
   - Create `DataPipeline` that coordinates all components

### Testing the Solution

**Test Cases:**
- `TestCSVDataSource`: Mock file system and test CSV reading
- `TestDataValidator`: Test validation with various inputs
- `TestDataTransformer`: Test transformation with valid and invalid data
- `TestStatisticsCalculator`: Test calculation with various datasets
- `TestDatabaseSink`: Mock database and test writing
- `TestHTTPSink`: Mock HTTP client and test API calls
- `TestDataPipeline`: Integration test using all mock components

**Verification:**
- Verify that adding a new file format only requires implementing `DataSource`
- Verify that adding a new output destination only requires implementing `DataSink`
- Verify that all tests pass without needing actual files, database, or API

---

## Scenario 4: REST API Service Layer

### Context

A REST API built with Flask has business logic mixed with HTTP concerns in the route handlers. Validation, authentication, authorization, business logic, data access, and response formatting are all handled in the view functions.

### Problem Description

The Flask application has route handlers that directly interact with the database, perform validation, check authentication, apply business rules, and format JSON responses. This makes the code difficult to test, violates separation of concerns, and makes it hard to reuse business logic outside of the HTTP layer.

### Analysis of Violations

**Current Issues:**
- **Mixed concerns**: HTTP handling, validation, authentication, business logic, data access, formatting
- **No separation**: Cannot use business logic without HTTP
- **Tight coupling**: Business logic depends on Flask request/response objects
- **Testing complexity**: Requires HTTP client for testing business logic

**Impact:**
- **Code quality**: Large route handlers with many lines
- **Maintainability**: Changes to business logic require modifying HTTP layer
- **Development velocity**: Cannot iterate on business logic independently

### BAD Approach

```python
from flask import Flask, request, jsonify
import sqlite3
import hashlib

app = Flask(__name__)


@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()

    # Validation
    if not data.get('username'):
        return jsonify({'error': 'Username required'}), 400

    if not data.get('email'):
        return jsonify({'error': 'Email required'}), 400

    if not data.get('password'):
        return jsonify({'error': 'Password required'}), 400

    # Authentication check
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Unauthorized'}), 401

    token = auth_header.split(' ')[1]
    if token != 'admin-token':
        return jsonify({'error': 'Forbidden'}), 403

    # Data access
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ?", (data['username'],))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Username already exists'}), 409

    # Business logic
    password_hash = hashlib.sha256(data['password'].encode()).hexdigest()

    cursor.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (data['username'], data['email'], password_hash)
    )

    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Response formatting
    return jsonify({
        'id': user_id,
        'username': data['username'],
        'email': data['email'],
        'createdAt': '2024-01-01T00:00:00Z'
    }), 201


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    # Authentication check
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'Unauthorized'}), 401

    # Data access
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()

    conn.close()

    if not row:
        return jsonify({'error': 'User not found'}), 404

    # Response formatting
    return jsonify({
        'id': row[0],
        'username': row[1],
        'email': row[2],
        'createdAt': '2024-01-01T00:00:00Z'
    })
```

**Why This Approach Fails:**
- Cannot test user creation without HTTP server
- Cannot reuse validation logic outside of API
- Cannot use business logic in CLI tools or other interfaces
- Authentication logic duplicated across routes
- Business logic mixed with HTTP concerns

### GOOD Approach

**Solution Strategy:**
1. Extract validation to validators
2. Extract authentication to middleware
3. Extract business logic to service layer
4. Extract data access to repository layer
5. Extract response formatting to serializers
6. Keep views thin as controllers

```python
from dataclasses import dataclass
from typing import Optional, Protocol
from flask import Flask, request, jsonify, g
import hashlib


@dataclass
class User:
    id: Optional[int] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""


class UserValidator:
    """Validates user input data."""

    def validate_create(self, data: dict) -> list:
        errors = []

        if not data.get('username'):
            errors.append('Username required')

        if not data.get('email'):
            errors.append('Email required')

        if not data.get('password'):
            errors.append('Password required')

        return errors


class AuthService:
    """Handles authentication and authorization."""

    def __init__(self, admin_token: str = 'admin-token'):
        self.admin_token = admin_token

    def authenticate(self, token: str) -> bool:
        return token == self.admin_token

    def get_current_user(self) -> Optional[str]:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        return 'admin' if self.authenticate(token) else None


class UserRepository(Protocol):
    """User repository interface."""

    def save(self, user: User) -> User: ...

    def find_by_username(self, username: str) -> Optional[User]: ...

    def find_by_id(self, user_id: int) -> Optional[User]: ...


class SQLiteUserRepository:
    """SQLite implementation of user repository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def save(self, user: User) -> User:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (user.username, user.email, user.password_hash)
        )

        user.id = cursor.lastrowid
        conn.commit()
        conn.close()

        return user

    def find_by_username(self, username: str) -> Optional[User]:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return User(id=row[0], username=row[1], email=row[2], password_hash=row[3])
        return None

    def find_by_id(self, user_id: int) -> Optional[User]:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return User(id=row[0], username=row[1], email=row[2], password_hash=row[3])
        return None


class PasswordHasher:
    """Handles password hashing."""

    @staticmethod
    def hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()


class UserService:
    """Business logic for user operations."""

    def __init__(self, user_repo: UserRepository, hasher: PasswordHasher):
        self.user_repo = user_repo
        self.hasher = hasher

    def create_user(self, username: str, email: str, password: str) -> User:
        if self.user_repo.find_by_username(username):
            raise ValueError("Username already exists")

        user = User(
            username=username,
            email=email,
            password_hash=self.hasher.hash(password)
        )

        return self.user_repo.save(user)

    def get_user(self, user_id: int) -> Optional[User]:
        return self.user_repo.find_by_id(user_id)


class UserSerializer:
    """Serializes user data for API responses."""

    @staticmethod
    def to_dict(user: User) -> dict:
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'createdAt': '2024-01-01T00:00:00Z'
        }


app = Flask(__name__)

auth_service = AuthService()
user_validator = UserValidator()
user_repo = SQLiteUserRepository('app.db')
hasher = PasswordHasher()
user_service = UserService(user_repo, hasher)
user_serializer = UserSerializer()


@app.before_request
def check_auth():
    """Authentication middleware."""
    if request.path.startswith('/api/'):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not auth_service.authenticate(token):
            return jsonify({'error': 'Unauthorized'}), 401


@app.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user."""
    data = request.get_json()

    errors = user_validator.validate_create(data)

    if errors:
        return jsonify({'error': 'Invalid data', 'details': errors}), 400

    try:
        user = user_service.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password']
        )

        return jsonify(user_serializer.to_dict(user)), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 409


@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get a user by ID."""
    user = user_service.get_user(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user_serializer.to_dict(user))
```

**Benefits:**
- Views are thin and only handle HTTP concerns
- Business logic can be tested without HTTP server
- Can reuse services in CLI tools, background jobs, or other interfaces
- Authentication logic centralized in middleware
- Easy to add new API endpoints using same services

### Implementation Steps

1. **Step 1: Create domain model**
   - Create `User` dataclass

2. **Step 2: Extract validation**
   - Create `UserValidator` class

3. **Step 3: Extract authentication**
   - Create `AuthService` class
   - Implement authentication middleware

4. **Step 4: Extract data access**
   - Create `UserRepository` protocol
   - Implement `SQLiteUserRepository`

5. **Step 5: Extract business logic**
   - Create `UserService` class
   - Move business rules here

6. **Step 6: Extract serialization**
   - Create `UserSerializer` class

7. **Step 7: Simplify views**
   - Refactor route handlers to use services
   - Keep views as thin controllers

### Testing the Solution

**Test Cases:**
- `TestUserValidator`: Test validation with valid and invalid data
- `TestAuthService`: Test authentication with valid and invalid tokens
- `TestUserRepository`: Mock database and test CRUD operations
- `TestUserService`: Test business logic using mock repository
- `TestUserSerializer`: Test serialization
- `TestAPI`: Integration tests using Flask test client

**Verification:**
- Verify that business logic can be tested without Flask
- Verify that validation logic can be reused outside of API
- Verify that adding new endpoints only requires creating new view functions

---

## Scenario 5: Notification System

### Context

A notification system needs to send notifications via multiple channels (email, SMS, push notifications, in-app). The current implementation mixes notification logic with template rendering, retry logic, and delivery tracking all in one class.

### Problem Description

The `NotificationService` class handles message formatting, template rendering, sending via different channels, retrying failed deliveries, tracking delivery status, and logging. This violates SRP as changes to any of these concerns require modifying the same class.

### Analysis of Violations

**Current Issues:**
- **Multiple responsibilities**: Formatting, rendering, sending, retrying, tracking, logging
- **Mixed channels**: Email, SMS, and push logic all in one class
- **Low reusability**: Cannot use email templates without sending notifications
- **Testing complexity**: Requires all channel providers for tests

**Impact:**
- **Code quality**: Large class with many conditional branches
- **Maintainability**: Adding new channel requires modifying existing class
- **Development velocity**: Cannot iterate on templates independently

### BAD Approach

```python
import smtplib
from email.mime.text import MIMEText
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class Notification:
    recipient: str
    subject: str
    body: str
    channel: str = 'email'


class NotificationService:
    """Handles notification sending with multiple channels."""

    def __init__(self, smtp_host: str = 'localhost', max_retries: int = 3):
        self.smtp_host = smtp_host
        self.max_retries = max_retries

    def send_notification(self, notification: Notification) -> bool:
        if notification.channel == 'email':
            return self._send_email(notification)
        elif notification.channel == 'sms':
            return self._send_sms(notification)
        elif notification.channel == 'push':
            return self._send_push(notification)
        else:
            raise ValueError(f"Unknown channel: {notification.channel}")

    def _send_email(self, notification: Notification) -> bool:
        for attempt in range(self.max_retries):
            try:
                msg = MIMEText(notification.body)
                msg['Subject'] = notification.subject
                msg['From'] = 'noreply@example.com'
                msg['To'] = notification.recipient

                with smtplib.SMTP(self.smtp_host) as server:
                    server.send_message(msg)

                self._log_delivery(notification, 'email', True)
                return True

            except Exception as e:
                print(f"Email send attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    self._log_delivery(notification, 'email', False)
                    return False

        return False

    def _send_sms(self, notification: Notification) -> bool:
        for attempt in range(self.max_retries):
            try:
                import requests

                response = requests.post(
                    'https://sms-gateway.com/api/send',
                    json={
                        'to': notification.recipient,
                        'message': f"{notification.subject}\n{notification.body}"
                    }
                )

                if response.status_code == 200:
                    self._log_delivery(notification, 'sms', True)
                    return True

            except Exception as e:
                print(f"SMS send attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    self._log_delivery(notification, 'sms', False)
                    return False

        return False

    def _send_push(self, notification: Notification) -> bool:
        for attempt in range(self.max_retries):
            try:
                import requests

                response = requests.post(
                    'https://push-gateway.com/api/send',
                    json={
                        'token': notification.recipient,
                        'title': notification.subject,
                        'body': notification.body
                    }
                )

                if response.status_code == 200:
                    self._log_delivery(notification, 'push', True)
                    return True

            except Exception as e:
                print(f"Push send attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    self._log_delivery(notification, 'push', False)
                    return False

        return False

    def _log_delivery(self, notification: Notification, channel: str, success: bool) -> None:
        status = 'delivered' if success else 'failed'
        print(f"[DELIVERY] {channel} to {notification.recipient}: {status}")

    def send_welcome_notification(self, username: str, email: str) -> bool:
        body = f"""
        Welcome {username}!

        Thank you for registering. We're excited to have you on board.

        Best regards,
        The Team
        """
        notification = Notification(
            recipient=email,
            subject='Welcome!',
            body=body,
            channel='email'
        )
        return self.send_notification(notification)

    def send_order_confirmation(self, order_id: int, email: str, total: float) -> bool:
        body = f"""
        Your order #{order_id} has been confirmed!

        Total: ${total:.2f}

        Thank you for your purchase.
        """
        notification = Notification(
            recipient=email,
            subject='Order Confirmed',
            body=body,
            channel='email'
        )
        return self.send_notification(notification)
```

**Why This Approach Fails:**
- Cannot use email templates without sending notifications
- Adding new channel requires modifying existing class
- Retry logic duplicated across channels
- Cannot test email sending without SMS and push
- Template rendering mixed with sending logic

### GOOD Approach

**Solution Strategy:**
1. Extract template rendering to template engine
2. Extract retry logic to retry manager
3. Extract delivery tracking to tracker
4. Create channel interface for senders
5. Implement senders for each channel
6. Create notification service that coordinates

```python
from dataclasses import dataclass
from typing import Protocol, Dict, Optional
from abc import ABC, abstractmethod
import time


@dataclass
class Notification:
    recipient: str
    subject: str
    body: str
    channel: str = 'email'


class TemplateRenderer:
    """Renders notification templates."""

    def render_welcome(self, username: str) -> str:
        return f"""
        Welcome {username}!

        Thank you for registering. We're excited to have you on board.

        Best regards,
        The Team
        """

    def render_order_confirmation(self, order_id: int, total: float) -> str:
        return f"""
        Your order #{order_id} has been confirmed!

        Total: ${total:.2f}

        Thank you for your purchase.
        """


class DeliveryTracker(Protocol):
    """Tracks notification delivery status."""

    def log(self, notification: Notification, channel: str, success: bool) -> None: ...


class ConsoleDeliveryTracker:
    """Console implementation of delivery tracker."""

    def log(self, notification: Notification, channel: str, success: bool) -> None:
        status = 'delivered' if success else 'failed'
        print(f"[DELIVERY] {channel} to {notification.recipient}: {status}")


class NotificationChannel(Protocol):
    """Notification channel interface."""

    def send(self, notification: Notification) -> bool: ...


class EmailChannel:
    """Email notification channel."""

    def __init__(self, smtp_host: str = 'localhost'):
        self.smtp_host = smtp_host

    def send(self, notification: Notification) -> bool:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(notification.body)
        msg['Subject'] = notification.subject
        msg['From'] = 'noreply@example.com'
        msg['To'] = notification.recipient

        with smtplib.SMTP(self.smtp_host) as server:
            server.send_message(msg)

        return True


class SMSChannel:
    """SMS notification channel."""

    def send(self, notification: Notification) -> bool:
        import requests

        response = requests.post(
            'https://sms-gateway.com/api/send',
            json={
                'to': notification.recipient,
                'message': f"{notification.subject}\n{notification.body}"
            }
        )

        return response.status_code == 200


class PushChannel:
    """Push notification channel."""

    def send(self, notification: Notification) -> bool:
        import requests

        response = requests.post(
            'https://push-gateway.com/api/send',
            json={
                'token': notification.recipient,
                'title': notification.subject,
                'body': notification.body
            }
        )

        return response.status_code == 200


class RetryManager:
    """Manages retry logic for failed deliveries."""

    def __init__(self, max_retries: int = 3, delay: float = 1.0):
        self.max_retries = max_retries
        self.delay = delay

    def execute_with_retry(self, func) -> bool:
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.delay * (attempt + 1))

        raise last_exception


class NotificationService:
    """Orchestrates notification sending."""

    def __init__(self, template_renderer: TemplateRenderer,
                 retry_manager: RetryManager,
                 delivery_tracker: DeliveryTracker,
                 channels: Dict[str, NotificationChannel]):
        self.template_renderer = template_renderer
        self.retry_manager = retry_manager
        self.delivery_tracker = delivery_tracker
        self.channels = channels

    def send_notification(self, notification: Notification) -> bool:
        channel = self.channels.get(notification.channel)

        if not channel:
            raise ValueError(f"Unknown channel: {notification.channel}")

        def send():
            return channel.send(notification)

        try:
            success = self.retry_manager.execute_with_retry(send)
        except Exception:
            success = False

        self.delivery_tracker.log(notification, notification.channel, success)
        return success

    def send_welcome_notification(self, username: str, email: str) -> bool:
        body = self.template_renderer.render_welcome(username)

        notification = Notification(
            recipient=email,
            subject='Welcome!',
            body=body,
            channel='email'
        )

        return self.send_notification(notification)

    def send_order_confirmation(self, order_id: int, email: str, total: float) -> bool:
        body = self.template_renderer.render_order_confirmation(order_id, total)

        notification = Notification(
            recipient=email,
            subject='Order Confirmed',
            body=body,
            channel='email'
        )

        return self.send_notification(notification)
```

**Benefits:**
- Each component has single responsibility
- Can add new channels without modifying existing code
- Can use template renderer independently
- Retry logic reusable across channels
- Easy to test each component independently

### Implementation Steps

1. **Step 1: Create data model**
   - Create `Notification` dataclass

2. **Step 2: Extract template rendering**
   - Create `TemplateRenderer` class

3. **Step 3: Extract tracking**
   - Create `DeliveryTracker` protocol
   - Implement `ConsoleDeliveryTracker`

4. **Step 4: Define channel interface**
   - Create `NotificationChannel` protocol
   - Implement `EmailChannel`, `SMSChannel`, and `PushChannel`

5. **Step 5: Extract retry logic**
   - Create `RetryManager` class

6. **Step 6: Create orchestrator**
   - Create `NotificationService` that coordinates components

### Testing the Solution

**Test Cases:**
- `TestTemplateRenderer`: Test template rendering with various inputs
- `TestEmailChannel`: Mock SMTP and test email sending
- `TestSMSChannel`: Mock HTTP client and test SMS sending
- `TestPushChannel`: Mock HTTP client and test push sending
- `TestRetryManager`: Test retry logic with failing functions
- `TestNotificationService`: Integration test using mock components

**Verification:**
- Verify that adding a new channel only requires implementing `NotificationChannel`
- Verify that template rendering can be tested without sending
- Verify that retry logic can be tested independently

---

## Scenario 6: Report Generation System

### Context

A reporting system needs to generate various reports (sales, inventory, customer) from different data sources and output to different formats (PDF, CSV, HTML). The current implementation mixes data fetching, calculation, formatting, and file generation all in one class.

### Problem Description

The `ReportGenerator` class handles database queries, data aggregation, calculations, report formatting, and file output. This makes it impossible to reuse calculations without generating reports, difficult to test formatting without database, and hard to add new report types or output formats.

### Analysis of Violations

**Current Issues:**
- **Mixed concerns**: Data fetching, calculation, formatting, file generation
- **Low reusability**: Cannot use calculations without generating reports
- **No flexibility**: Adding new report types or formats requires modifying generator
- **Testing complexity**: Requires database and file system for tests

**Impact:**
- **Code quality**: Large class with many similar methods
- **Maintainability**: Changes to data source affect all reports
- **Development velocity**: Cannot iterate on formatting independently

### BAD Approach

```python
import sqlite3
from typing import List, Dict
from datetime import datetime


class ReportGenerator:
    """Generates various reports from database."""

    def __init__(self, db_path: str = 'reports.db'):
        self.db_path = db_path

    def generate_sales_report(self, start_date: str, end_date: str, format: str = 'csv') -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT date, product_id, quantity, total FROM sales "
            "WHERE date BETWEEN ? AND ?",
            (start_date, end_date)
        )

        rows = cursor.fetchall()
        conn.close()

        if format == 'csv':
            return self._format_sales_as_csv(rows)
        elif format == 'html':
            return self._format_sales_as_html(rows)
        elif format == 'json':
            return self._format_sales_as_json(rows)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _format_sales_as_csv(self, rows: List[tuple]) -> str:
        lines = ['date,product_id,quantity,total']
        for row in rows:
            lines.append(f"{row[0]},{row[1]},{row[2]},{row[3]}")
        return '\n'.join(lines)

    def _format_sales_as_html(self, rows: List[tuple]) -> str:
        html = '<html><body><table><tr><th>Date</th><th>Product</th><th>Quantity</th><th>Total</th></tr>'
        for row in rows:
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td></tr>'
        html += '</table></body></html>'
        return html

    def _format_sales_as_json(self, rows: List[tuple]) -> str:
        import json
        data = [{'date': r[0], 'product_id': r[1], 'quantity': r[2], 'total': r[3]} for r in rows]
        return json.dumps(data)

    def generate_inventory_report(self, format: str = 'csv') -> str:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT product_id, name, quantity, price FROM inventory")
        rows = cursor.fetchall()
        conn.close()

        if format == 'csv':
            return self._format_inventory_as_csv(rows)
        elif format == 'html':
            return self._format_inventory_as_html(rows)
        elif format == 'json':
            return self._format_inventory_as_json(rows)
        else:
            raise ValueError(f"Unknown format: {format}")

    def _format_inventory_as_csv(self, rows: List[tuple]) -> str:
        lines = ['product_id,name,quantity,price']
        for row in rows:
            lines.append(f"{row[0]},{row[1]},{row[2]},{row[3]}")
        return '\n'.join(lines)

    def _format_inventory_as_html(self, rows: List[tuple]) -> str:
        html = '<html><body><table><tr><th>ID</th><th>Name</th><th>Quantity</th><th>Price</th></tr>'
        for row in rows:
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td></tr>'
        html += '</table></body></html>'
        return html

    def _format_inventory_as_json(self, rows: List[tuple]) -> str:
        import json
        data = [{'product_id': r[0], 'name': r[1], 'quantity': r[2], 'price': r[3]} for r in rows]
        return json.dumps(data)

    def save_report_to_file(self, report: str, filename: str) -> None:
        with open(filename, 'w') as f:
            f.write(report)
```

**Why This Approach Fails:**
- Cannot use sales calculations without generating report
- Cannot use CSV formatter for inventory without sales logic
- Adding new report type requires duplicating formatting code
- Testing formatting requires database
- Cannot use data for multiple formats in one report

### GOOD Approach

**Solution Strategy:**
1. Extract data fetching to repositories
2. Extract calculations to calculators
3. Define formatter interface for output formats
4. Implement formatters for each format
5. Create report service that coordinates

```python
from dataclasses import dataclass
from typing import List, Protocol, Dict
from abc import ABC, abstractmethod
import json


@dataclass
class SalesRecord:
    date: str
    product_id: str
    quantity: int
    total: float


@dataclass
class InventoryRecord:
    product_id: str
    name: str
    quantity: int
    price: float


class SalesRepository(Protocol):
    """Sales data repository interface."""

    def get_sales_by_date_range(self, start_date: str, end_date: str) -> List[SalesRecord]: ...


class InventoryRepository(Protocol):
    """Inventory data repository interface."""

    def get_all_inventory(self) -> List[InventoryRecord]: ...


class SQLiteSalesRepository:
    """SQLite implementation of sales repository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_sales_by_date_range(self, start_date: str, end_date: str) -> List[SalesRecord]:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT date, product_id, quantity, total FROM sales "
            "WHERE date BETWEEN ? AND ?",
            (start_date, end_date)
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            SalesRecord(date=row[0], product_id=row[1], quantity=row[2], total=row[3])
            for row in rows
        ]


class SQLiteInventoryRepository:
    """SQLite implementation of inventory repository."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_all_inventory(self) -> List[InventoryRecord]:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT product_id, name, quantity, price FROM inventory")
        rows = cursor.fetchall()
        conn.close()

        return [
            InventoryRecord(product_id=row[0], name=row[1], quantity=row[2], price=row[3])
            for row in rows
        ]


class ReportFormatter(Protocol):
    """Report formatter interface."""

    def format_sales(self, data: List[SalesRecord]) -> str: ...

    def format_inventory(self, data: List[InventoryRecord]) -> str: ...


class CSVFormatter:
    """CSV report formatter."""

    def format_sales(self, data: List[SalesRecord]) -> str:
        lines = ['date,product_id,quantity,total']
        for record in data:
            lines.append(f"{record.date},{record.product_id},{record.quantity},{record.total}")
        return '\n'.join(lines)

    def format_inventory(self, data: List[InventoryRecord]) -> str:
        lines = ['product_id,name,quantity,price']
        for record in data:
            lines.append(f"{record.product_id},{record.name},{record.quantity},{record.price}")
        return '\n'.join(lines)


class HTMLFormatter:
    """HTML report formatter."""

    def format_sales(self, data: List[SalesRecord]) -> str:
        html = '<html><body><table><tr><th>Date</th><th>Product</th><th>Quantity</th><th>Total</th></tr>'
        for record in data:
            html += f'<tr><td>{record.date}</td><td>{record.product_id}</td><td>{record.quantity}</td><td>{record.total}</td></tr>'
        html += '</table></body></html>'
        return html

    def format_inventory(self, data: List[InventoryRecord]) -> str:
        html = '<html><body><table><tr><th>ID</th><th>Name</th><th>Quantity</th><th>Price</th></tr>'
        for record in data:
            html += f'<tr><td>{record.product_id}</td><td>{record.name}</td><td>{record.quantity}</td><td>{record.price}</td></tr>'
        html += '</table></body></html>'
        return html


class JSONFormatter:
    """JSON report formatter."""

    def format_sales(self, data: List[SalesRecord]) -> str:
        records = [
            {'date': r.date, 'product_id': r.product_id, 'quantity': r.quantity, 'total': r.total}
            for r in data
        ]
        return json.dumps(records, indent=2)

    def format_inventory(self, data: List[InventoryRecord]) -> str:
        records = [
            {'product_id': r.product_id, 'name': r.name, 'quantity': r.quantity, 'price': r.price}
            for r in data
        ]
        return json.dumps(records, indent=2)


class ReportService:
    """Orchestrates report generation."""

    def __init__(self, sales_repo: SalesRepository,
                 inventory_repo: InventoryRepository,
                 formatters: Dict[str, ReportFormatter]):
        self.sales_repo = sales_repo
        self.inventory_repo = inventory_repo
        self.formatters = formatters

    def generate_sales_report(self, start_date: str, end_date: str, format: str = 'csv') -> str:
        data = self.sales_repo.get_sales_by_date_range(start_date, end_date)
        formatter = self.formatters.get(format)

        if not formatter:
            raise ValueError(f"Unknown format: {format}")

        return formatter.format_sales(data)

    def generate_inventory_report(self, format: str = 'csv') -> str:
        data = self.inventory_repo.get_all_inventory()
        formatter = self.formatters.get(format)

        if not formatter:
            raise ValueError(f"Unknown format: {format}")

        return formatter.format_inventory(data)
```

**Benefits:**
- Each component has single responsibility
- Can use formatters independently of data sources
- Can add new formats by implementing `ReportFormatter`
- Can test formatting without database
- Can reuse data for multiple formats

### Implementation Steps

1. **Step 1: Create data models**
   - Create `SalesRecord` and `InventoryRecord` dataclasses

2. **Step 2: Define repository interfaces**
   - Create `SalesRepository` protocol
   - Create `InventoryRepository` protocol

3. **Step 3: Implement repositories**
   - Implement `SQLiteSalesRepository`
   - Implement `SQLiteInventoryRepository`

4. **Step 4: Define formatter interface**
   - Create `ReportFormatter` protocol

5. **Step 5: Implement formatters**
   - Implement `CSVFormatter`
   - Implement `HTMLFormatter`
   - Implement `JSONFormatter`

6. **Step 6: Create orchestrator**
   - Create `ReportService` that coordinates components

### Testing the Solution

**Test Cases:**
- `TestSalesRepository`: Mock database and test data fetching
- `TestInventoryRepository`: Mock database and test data fetching
- `TestCSVFormatter`: Test CSV formatting with sample data
- `TestHTMLFormatter`: Test HTML formatting with sample data
- `TestJSONFormatter`: Test JSON formatting with sample data
- `TestReportService`: Integration test using mock components

**Verification:**
- Verify that adding a new format only requires implementing `ReportFormatter`
- Verify that formatting can be tested without database
- Verify that data fetching can be tested without formatting

---

## Migration Guide

### Refactoring Existing Codebases

When refactoring existing Python code to follow SRP:

1. **Phase 1: Assessment**
   - Identify violations using code review questions and automated tools
   - Measure class complexity with radon or pylint
   - Count imports to identify mixed concerns
   - Prioritize by impact and complexity (start with high-impact, low-complexity)

2. **Phase 2: Planning**
   - Create refactoring roadmap based on identified responsibilities
   - Design new architecture with clear separation of concerns
   - Plan incremental changes to maintain backwards compatibility
   - Create test suite to ensure refactoring doesn't break functionality

3. **Phase 3: Implementation**
   - Implement changes incrementally, one responsibility at a time
   - Add comprehensive tests for each new component
   - Use dependency injection to wire components together
   - Maintain backwards compatibility with facades or adapters where needed

4. **Phase 4: Verification**
   - Run all existing tests to ensure no regressions
   - Run new tests to verify refactored components
   - Measure improvements in code metrics
   - Update documentation and architecture diagrams

### Incremental Refactoring Strategies

**Strategy 1: Extract Method to Extract Class**
- Start by extracting complex methods into separate methods within the same class
- Once methods are identified, move related methods to new classes
- Replace original class methods with calls to new classes
- This approach allows gradual refactoring while maintaining functionality

**Strategy 2: Facade Pattern**
- Create new, properly-structured classes for each responsibility
- Create a facade class that delegates to the new classes
- Gradually move callers to use the new classes directly
- Remove facade once migration is complete
- This approach maintains backwards compatibility during transition

### Common Refactoring Patterns

1. **Extract Class**: Move related methods and fields to a new class
   - When to use: When a class has multiple clear responsibilities
   - How it helps: Creates focused, single-responsibility classes

2. **Replace Conditional with Polymorphism**: Replace conditional logic with separate classes
   - When to use: When conditional blocks handle different concerns
   - How it helps: Each implementation has single responsibility

3. **Replace Type Code with State/Strategy**: Replace type checking with separate classes
   - When to use: When type codes indicate different behaviors
   - How it helps: Each state/strategy has single responsibility

4. **Introduce Parameter Object**: Replace long parameter lists with objects
   - When to use: When methods have many parameters for different concerns
   - How it helps: Group related data, making responsibilities clearer

### Testing During Refactoring

**Regression Testing:**
- Run full test suite before each refactoring step
- Use pytest for comprehensive testing
- Ensure all existing tests pass after each change
- Add integration tests to verify components work together

**Integration Testing:**
- Test that refactored components work together correctly
- Use dependency injection to mock dependencies in tests
- Verify that facades properly delegate to new components
- Test backwards compatibility during transition

---

## Language-Specific Notes

### Common Real-World Challenges in Python

- **Dynamic typing**: Makes it harder to see when classes have too many responsibilities; use type hints to make dependencies explicit
- **ORM models**: Django and SQLAlchemy models tend to accumulate responsibilities; use service layer pattern
- **Utility modules**: Easy to create `utils.py` with unrelated functions; group related utilities into focused modules
- **Class decorators**: Can hide added responsibilities; use them sparingly and for clear, single purposes

### Framework-Specific Scenarios

- **Django**:
  - Extract business logic from models to services
  - Use Django's service layer pattern or domain-driven design
  - Keep views thin and delegate to services

- **Flask**:
  - Use blueprints to organize routes by domain
  - Keep route handlers thin and delegate to services
  - Use extensions for cross-cutting concerns (auth, logging)

- **FastAPI**:
  - Use dependency injection for services
  - Keep route handlers thin
  - Use Pydantic models for validation only

### Ecosystem Tools

**Refactoring Tools:**
- **Rope**: Advanced Python refactoring IDE support
- **Bowler**: Safe code refactoring tool
- **pylint**: Detects high complexity and suggests refactoring

**Analysis Tools:**
- **Radon**: Calculates complexity metrics
- **vulture**: Detects dead code
- **wily**: Tracks complexity over time
- **coverage.py**: Ensures tests cover refactored code

### Best Practices for Python

1. **Use dataclasses for pure data models**: Keep models focused on data only
2. **Use protocols for interfaces**: Define clear contracts without implementation
3. **Use dependency injection**: Make dependencies explicit and testable
4. **Keep modules focused**: One module, one concern
5. **Use type hints**: Make dependencies and contracts explicit

### Case Studies

**Case Study 1: Django E-Commerce Project**
- Context: Large Django application with fat models
- Problem: Models contained business logic, validation, and data access
- Solution: Extracted business logic to service layer, validation to form classes, data access to repositories
- Results: Reduced model complexity by 70%, improved test coverage, faster feature development

**Case Study 2: Flask REST API**
- Context: Flask API with business logic in route handlers
- Problem: Routes contained validation, authentication, business logic, and formatting
- Solution: Extracted validation to validators, authentication to middleware, business logic to services, formatting to serializers
- Results: Routes reduced from 100+ lines to 10-20 lines each, independent testing possible, easier to add new endpoints

**Case Study 3: Data Pipeline**
- Context: ETL pipeline with mixed concerns in single script
- Problem: Script handled file I/O, parsing, validation, transformation, and loading
- Solution: Separated into readers, parsers, validators, transformers, and writers using protocols
- Results: Can test transformations without files, can swap data sources easily, can add new transformations without modifying pipeline
