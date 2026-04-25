# YAGNI Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Speculative Features](#example-1-speculative-features)
- [Example 2: Gold Plating](#example-2-gold-plating)
- [Example 3: Premature Abstraction](#example-3-premature-abstraction)
- [Example 4: Over-Generalization](#example-4-over-generalization)
- [Example 5: Unused Functionality](#example-5-unused-functionality)
- [Example 6: Dead Code](#example-6-dead-code)
- [Example 7: Framework Overkill](#example-7-framework-overkill)
- [Example 8: Configuration Overload](#example-8-configuration-overload)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the YAGNI (You Aren't Gonna Need It) principle in Python. Each example demonstrates a common violation where developers build for hypothetical futures rather than current needs, and the corrected minimal implementation.

## Example 1: Speculative Features

### BAD Example: Building for Multiple Payment Methods

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional


class PaymentMethod(ABC):
    @abstractmethod
    def process(self, amount: Decimal) -> dict:
        pass


class CreditCardPayment(PaymentMethod):
    def process(self, amount: Decimal) -> dict:
        # Credit card implementation
        return {"status": "success", "amount": amount}


class PayPalPayment(PaymentMethod):
    def process(self, amount: Decimal) -> dict:
        # PayPal implementation
        return {"status": "success", "amount": amount}


class StripePayment(PaymentMethod):
    def process(self, amount: Decimal) -> dict:
        # Stripe implementation
        return {"status": "success", "amount": amount}


class BitcoinPayment(PaymentMethod):
    def process(self, amount: Decimal) -> dict:
        # Bitcoin implementation (never used!)
        return {"status": "success", "amount": amount}


class ApplePayPayment(PaymentMethod):
    def process(self, amount: Decimal) -> dict:
        # Apple Pay implementation (never used!)
        return {"status": "success", "amount": amount}


class PaymentProcessor:
    def __init__(self):
        self.methods = {
            "credit_card": CreditCardPayment(),
            "paypal": PayPalPayment(),
            "stripe": StripePayment(),
            "bitcoin": BitcoinPayment(),
            "apple_pay": ApplePayPayment(),
        }

    def process_payment(self, method: str, amount: Decimal) -> dict:
        payment_method = self.methods.get(method)
        if not payment_method:
            raise ValueError(f"Unknown payment method: {method}")
        return payment_method.process(amount)
```

**Problems:**
- Built payment methods that are never requested (Bitcoin, Apple Pay)
- Complex architecture for a single actual need
- Unused code that must be maintained
- Added complexity without value
- Testing burden for unused functionality

### GOOD Example: Implement Only What's Needed

```python
from decimal import Decimal


def process_credit_card_payment(card_number: str, amount: Decimal) -> dict:
    """
    Process a credit card payment.
    Only implemented what's needed now.
    """
    # Actual credit card processing logic
    if not card_number or len(card_number) < 13:
        return {"status": "error", "message": "Invalid card number"}

    # Process payment with gateway
    return {"status": "success", "amount": amount, "transaction_id": "txn_123"}


def process_paypal_payment(email: str, amount: Decimal) -> dict:
    """
    Process a PayPal payment.
    Added this when it was actually requested.
    """
    # PayPal processing logic
    return {"status": "success", "amount": amount, "transaction_id": "paypal_456"}
```

**Improvements:**
- Only implements credit card and PayPal (actual requirements)
- Simple, direct functions instead of complex class hierarchy
- No unused payment methods
- Easy to understand and test
- Can add more methods when actually needed

### Explanation

The BAD example violates YAGNI by building a flexible payment system for all possible payment methods when only credit card was needed initially. The GOOD example implements only what's required, adding new payment methods only when they become actual requirements. This follows the YAGNI principle: build for now, not for hypothetical futures.

---

## Example 2: Gold Plating

### BAD Example: Over-Engineered User Model

```python
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"
    ARCHIVED = "archived"


class UserRole(Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"
    SUPER_ADMIN = "super_admin"
    CONTENT_CREATOR = "content_creator"


@dataclass
class UserProfile:
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    twitter_handle: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None
    birth_date: Optional[datetime] = None
    timezone: str = "UTC"
    language: str = "en"
    theme_preference: str = "light"
    notification_preferences: Dict[str, bool] = field(default_factory=dict)
    privacy_settings: Dict[str, str] = field(default_factory=dict)


@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    status: UserStatus = UserStatus.PENDING
    role: UserRole = UserRole.USER
    profile: Optional[UserProfile] = None
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    email_verified: bool = False
    phone_number: Optional[str] = None
    two_factor_enabled: bool = False
    two_factor_secret: Optional[str] = None
    login_attempts: int = 0
    locked_until: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate_password(self, password: str) -> bool:
        # Complex validation logic
        pass

    def update_profile(self, profile_data: dict) -> None:
        # Complex profile update logic
        pass

    def add_role(self, role: UserRole) -> None:
        # Role management (never used!)
        pass

    def remove_role(self, role: UserRole) -> None:
        # Role management (never used!)
        pass
```

**Problems:**
- Added fields and features never requested
- Complex user roles when only basic users needed
- Privacy settings that aren't used
- Two-factor authentication before it was needed
- Social media integration fields that aren't implemented
- Metadata dictionary that's always empty

### GOOD Example: Simple User Model

```python
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class User:
    """
    Simple user model with only what's needed now.
    """
    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime

    def validate_password(self, password: str) -> bool:
        """
        Validate password against stored hash.
        Only implemented what's needed.
        """
        # Password validation logic
        return check_password(self.password_hash, password)
```

**Improvements:**
- Only essential fields for basic authentication
- No unused role system
- No unimplemented social media fields
- Simple and easy to understand
- Can extend when features are actually requested

### Explanation

The BAD example demonstrates gold plating by adding numerous features and fields that sound impressive but aren't needed. The GOOD example follows YAGNI by implementing only the core user functionality required for basic authentication. Additional features like two-factor auth, roles, and social media integration can be added when they become actual requirements.

---

## Example 3: Premature Abstraction

### BAD Example: Abstracting Before Patterns Exist

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DataSource(ABC):
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def query(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        pass

    @abstractmethod
    def insert(self, table: str, data: Dict[str, Any]) -> int:
        pass

    @abstractmethod
    def update(self, table: str, id: int, data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def delete(self, table: str, id: int) -> bool:
        pass


class PostgreSQLDataSource(DataSource):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None

    def connect(self) -> None:
        import psycopg2
        self.connection = psycopg2.connect(self.connection_string)

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()

    def query(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        # PostgreSQL query logic
        pass

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        # PostgreSQL insert logic
        pass

    def update(self, table: str, id: int, data: Dict[str, Any]) -> bool:
        # PostgreSQL update logic
        pass

    def delete(self, table: str, id: int) -> bool:
        # PostgreSQL delete logic
        pass


class MySQLDataSource(DataSource):
    # Never used! Created "just in case"
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None

    def connect(self) -> None:
        import mysql.connector
        self.connection = mysql.connector.connect(self.connection_string)

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()

    def query(self, query: str, params: Dict[str, Any] = None) -> List[Dict]:
        # MySQL query logic (never called!)
        pass

    def insert(self, table: str, data: Dict[str, Any]) -> int:
        # MySQL insert logic (never called!)
        pass

    def update(self, table: str, id: int, data: Dict[str, Any]) -> bool:
        # MySQL update logic (never called!)
        pass

    def delete(self, table: str, id: int) -> bool:
        # MySQL delete logic (never called!)
        pass


class DataSourceFactory:
    def create_data_source(self, db_type: str, connection_string: str) -> DataSource:
        if db_type == "postgresql":
            return PostgreSQLDataSource(connection_string)
        elif db_type == "mysql":
            return MySQLDataSource(connection_string)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
```

**Problems:**
- Created abstract base class before multiple implementations existed
- Built MySQL support that's never used
- Factory pattern for single implementation
- Unnecessary abstraction layer
- Code complexity without benefit

### GOOD Example: Concrete Implementation Until Needed

```python
import psycopg2
from typing import Dict, List


class Database:
    """
    Direct PostgreSQL implementation.
    Only abstraction if/when multiple databases are actually needed.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None

    def connect(self) -> None:
        """Connect to PostgreSQL database."""
        self.connection = psycopg2.connect(self.connection_string)

    def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()

    def query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute query and return results."""
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results

    def insert(self, table: str, data: Dict) -> int:
        """Insert record into table."""
        # Insert logic
        pass

    def update(self, table: str, id: int, data: Dict) -> bool:
        """Update record in table."""
        # Update logic
        pass

    def delete(self, table: str, id: int) -> bool:
        """Delete record from table."""
        # Delete logic
        pass
```

**Improvements:**
- Direct PostgreSQL implementation
- No unused MySQL code
- No unnecessary abstraction
- Simpler codebase
- Easy to understand

### Explanation

The BAD example creates an abstract data source interface and multiple implementations before they're actually needed. The GOOD example uses a concrete implementation directly, following YAGNI by deferring abstraction until multiple database types are actually required. This reduces complexity and avoids writing unused code.

---

## Example 4: Over-Generalization

### BAD Example: Generic Configuration System

```python
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path
import json
import yaml


class ConfigLoader:
    """
    Over-engineered configuration system for uncertain future needs.
    """

    def __init__(self):
        self.sources: List[str] = []
        self.cache: Dict[str, Any] = {}
        self.validators: Dict[str, Callable] = {}
        self.transformers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []

    def add_source(self, source: str) -> "ConfigLoader":
        self.sources.append(source)
        return self

    def add_validator(self, key: str, validator: Callable) -> "ConfigLoader":
        self.validators[key] = validator
        return self

    def add_transformer(self, key: str, transformer: Callable) -> "ConfigLoader":
        self.transformers[key] = transformer
        return self

    def use_middleware(self, middleware: Callable) -> "ConfigLoader":
        self.middleware.append(middleware)
        return self

    def load(self) -> Dict[str, Any]:
        config = {}
        for source in self.sources:
            source_config = self._load_from_source(source)
            config = {**config, **source_config}
        config = self._apply_validators(config)
        config = self._apply_transformers(config)
        config = self._apply_middleware(config)
        self.cache = config
        return config

    def _load_from_source(self, source: str) -> Dict[str, Any]:
        path = Path(source)
        if path.suffix == ".json":
            return json.loads(path.read_text())
        elif path.suffix in [".yaml", ".yml"]:
            return yaml.safe_load(path.read_text())
        elif path.suffix == ".env":
            return self._parse_env_file(path)
        else:
            raise ValueError(f"Unsupported config format: {path.suffix}")

    def _parse_env_file(self, path: Path) -> Dict[str, Any]:
        # Complex env file parsing
        pass

    def _apply_validators(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # Complex validation logic
        pass

    def _apply_transformers(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # Complex transformation logic
        pass

    def _apply_middleware(self, config: Dict[str, Any]) -> Dict[str, Any]:
        for middleware in self.middleware:
            config = middleware(config)
        return config

    def get(self, key: str, default: Any = None) -> Any:
        return self.cache.get(key, default)
```

**Problems:**
- Complex configuration system for simple needs
- Support for multiple formats when only JSON is used
- Validation and transformation never actually used
- Middleware support that's not needed
- Over 100 lines for loading a config file

### GOOD Example: Simple Configuration Loading

```python
import json
from pathlib import Path


def load_config(config_path: str) -> dict:
    """
    Load JSON configuration file.
    Simple and direct implementation.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open() as f:
        return json.load(f)


def get_config_value(config: dict, key: str, default=None):
    """
    Get configuration value with optional default.
    """
    keys = key.split(".")
    value = config

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value
```

**Improvements:**
- Simple JSON loading function
- No unused format support
- No complex validation/transform/middleware
- Easy to understand and test
- Can add complexity when actually needed

### Explanation

The BAD example creates a highly generic configuration system with support for multiple formats, validators, transformers, and middleware - none of which are actually needed. The GOOD example implements simple JSON configuration loading, following YAGNI by only building what's required. Additional features can be added when they become necessary.

---

## Example 5: Unused Functionality

### BAD Example: Logging System with Unused Features

```python
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import json


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogFormat(Enum):
    TEXT = "text"
    JSON = "json"
    XML = "xml"
    HTML = "html"  # Never used!


class LogHandler:
    def __init__(self):
        self.handlers: List[logging.Handler] = []
        self.filters: List[logging.Filter] = []
        self.formatters: Dict[LogFormat, logging.Formatter] = {}

    def add_handler(self, handler: logging.Handler) -> None:
        self.handlers.append(handler)

    def add_filter(self, filter_obj: logging.Filter) -> None:
        self.filters.append(filter_obj)

    def set_formatter(self, log_format: LogFormat) -> None:
        if log_format == LogFormat.TEXT:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        elif log_format == LogFormat.JSON:
            formatter = logging.Formatter("%(message)s")
        elif log_format == LogFormat.XML:
            formatter = logging.Formatter("<log><message>%(message)s</message></log>")
        elif log_format == LogFormat.HTML:
            formatter = logging.Formatter(
                "<div class='log'>%(message)s</div>"  # Never used!
            )
        self.formatters[log_format] = formatter

    def configure(self, level: LogLevel, format_type: LogFormat) -> None:
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.value.upper()))

        formatter = self.formatters.get(format_type)
        if formatter:
            for handler in self.handlers:
                handler.setFormatter(formatter)

        for handler in self.handlers:
            root_logger.addHandler(handler)

        for filter_obj in self.filters:
            root_logger.addFilter(filter_obj)


class Logger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context: Dict[str, Any] = {}

    def set_context(self, key: str, value: Any) -> None:
        self.context[key] = value

    def clear_context(self) -> None:
        self.context.clear()

    def _log(self, level: LogLevel, message: str, **kwargs) -> None:
        log_message = {**self.context, **kwargs}
        if any(self.context.values()):
            log_message = f"{message} | Context: {json.dumps(log_message)}"
        else:
            log_message = message

        getattr(self.logger, level.value)(log_message)

    def debug(self, message: str, **kwargs) -> None:
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        self._log(LogLevel.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        self._log(LogLevel.CRITICAL, message, **kwargs)
```

**Problems:**
- XML and HTML log formats never used
- Complex context system that's always empty
- Multiple handlers and filters never configured
- Over-engineered for simple logging needs
- File handler, rotating file handler, syslog handler all implemented but never used

### GOOD Example: Simple Logging Setup

```python
import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Simple logging configuration.
    Only what's actually needed.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger(__name__)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
```

**Improvements:**
- Simple logging setup
- No unused format options
- No complex context system
- Direct use of Python's built-in logging
- Easy to understand and maintain

### Explanation

The BAD example implements a complex logging system with multiple formats, handlers, filters, and context management - most of which are never used. The GOOD example uses Python's built-in logging with simple configuration, following YAGNI by implementing only what's needed for the application's logging requirements.

---

## Example 6: Dead Code

### BAD Example: Accumulated Dead Code

```python
from typing import List, Optional, Dict, Any
from datetime import datetime


class OrderProcessor:
    """
    Order processing with accumulated dead code.
    """

    def __init__(self):
        self.repository = OrderRepository()

    def process_order(self, order: "Order") -> "Order":
        # Current implementation
        if order.status == "pending":
            order.status = "processing"
        elif order.status == "processing":
            order.status = "shipped"
        order.save()
        return order

    # ========== DEAD CODE - Remove! ==========

    def validate_order_v1(self, order: "Order") -> bool:
        # Old validation - replaced by v2
        return order.items is not None and len(order.items) > 0

    def calculate_discount_v1(self, order: "Order") -> float:
        # Old discount logic - moved to separate service
        return 0.0

    def notify_customer_v1(self, order: "Order", message: str) -> None:
        # Old notification - replaced by event system
        pass

    def process_order_v2(self, order: "Order") -> "Order":
        # Previous implementation - replaced by v3
        state_machine = OrderStateMachine(order)
        state_machine.advance()
        return order

    def process_order_v3(self, order: "Order") -> "Order":
        # Previous implementation - replaced by current
        if order.status == "pending":
            order.status = "processing"
            order.save()
        elif order.status == "processing":
            order.status = "shipped"
            order.save()
        return order

    def send_email_notification(self, to: str, subject: str, body: str) -> None:
        # Email sending - moved to NotificationService
        pass

    def send_sms_notification(self, to: str, message: str) -> None:
        # SMS sending - never implemented!
        pass

    def send_push_notification(self, to: str, message: str) -> None:
        # Push notifications - never implemented!
        pass

    def generate_invoice_pdf(self, order: "Order") -> bytes:
        # PDF generation - never implemented!
        pass

    def generate_invoice_html(self, order: "Order") -> str:
        # HTML invoice - never implemented!
        pass

    def calculate_tax_by_state(self, state: str) -> float:
        # State-based tax - replaced by external service
        return 0.0

    def apply_loyalty_points(self, user_id: int, points: int) -> None:
        # Loyalty points - moved to separate service
        pass

    def track_shipment(self, order: "Order") -> Dict[str, Any]:
        # Shipment tracking - never implemented!
        pass

    def get_shipping_estimate(self, order: "Order") -> float:
        # Shipping estimates - never implemented!
        pass

    def schedule_delivery(self, order: "Order", delivery_date: datetime) -> None:
        # Delivery scheduling - never implemented!
        pass

    def cancel_order(self, order: "Order") -> bool:
        # Order cancellation - never implemented!
        return False

    def refund_order(self, order: "Order", amount: float) -> bool:
        # Order refund - never implemented!
        return False

    def return_order(self, order: "Order") -> bool:
        # Order return - never implemented!
        return False
```

**Problems:**
- Multiple versions of same method (v1, v2, v3)
- Methods never implemented (always pass or return False)
- Methods moved to other services but not deleted
- Commented code suggesting "keep just in case"
- Dead code makes codebase confusing and harder to navigate

### GOOD Example: Clean Code Without Dead Code

```python
from typing import Optional


class OrderProcessor:
    """
    Clean order processing implementation.
    Only current, active code.
    """

    def __init__(self):
        self.repository = OrderRepository()

    def process_order(self, order: "Order") -> "Order":
        """
        Process order through simple state transition.
        """
        if order.status == "pending":
            order.status = "processing"
        elif order.status == "processing":
            order.status = "shipped"
        order.save()
        return order
```

**Improvements:**
- No dead code
- No unused methods
- Only current implementation
- Clear and focused
- Easy to understand and maintain
- Old versions safely stored in version control

### Explanation

The BAD example accumulates dead code over time: old implementations, unimplemented features, and methods that were moved elsewhere but not deleted. The GOOD example keeps only the current, active implementation. Following YAGNI means removing dead code rather than keeping it "just in case" - version control preserves history.

---

## Example 7: Framework Overkill

### BAD Example: Microservices for Simple CRUD

```python
# user_service/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import redis
import pika
import json


class User(BaseModel):
    id: Optional[int] = None
    username: str
    email: str


app = FastAPI()

# Redis cache
redis_client = redis.Redis(host="localhost", port=6379, db=0)

# RabbitMQ for event bus
connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()
channel.queue_declare(queue="user_events")


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # Check cache first
    cached = redis_client.get(f"user:{user_id}")
    if cached:
        return json.loads(cached)

    # Fetch from database
    user = fetch_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Cache it
    redis_client.setex(f"user:{user_id}", 3600, json.dumps(user))

    # Publish event
    channel.basic_publish(
        exchange="",
        routing_key="user_events",
        body=json.dumps({"event": "user_fetched", "user_id": user_id}),
    )

    return user


@app.post("/users")
async def create_user(user: User):
    # Create in database
    created = create_in_db(user)

    # Invalidate cache
    redis_client.delete(f"user:{created.id}")

    # Publish event
    channel.basic_publish(
        exchange="",
        routing_key="user_events",
        body=json.dumps({"event": "user_created", "user": created.dict()}),
    )

    return created


# More microservices:
# - order_service/app.py
# - product_service/app.py
# - notification_service/app.py
# - email_service/app.py
# - sms_service/app.py
# - analytics_service/app.py
# Each with Docker, Kubernetes, service discovery, etc.
```

**Problems:**
- Microservices architecture for simple CRUD application
- Event bus and cache overkill for low traffic
- Complex deployment and monitoring
- Network overhead between services
- Hard to debug distributed issues
- Team doesn't have scale to justify overhead

### GOOD Example: Simple Monolith

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional


class User(BaseModel):
    id: Optional[int] = None
    username: str
    email: str


class Order(BaseModel):
    id: Optional[int] = None
    user_id: int
    total: float


app = FastAPI()


@app.get("/users/{user_id}")
def get_user(user_id: int) -> User:
    """Simple user retrieval."""
    user = fetch_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/users")
def create_user(user: User) -> User:
    """Simple user creation."""
    return create_user_in_db(user)


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> Order:
    """Simple order retrieval."""
    order = fetch_order_from_db(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders")
def create_order(order: Order) -> Order:
    """Simple order creation."""
    return create_order_in_db(order)
```

**Improvements:**
- Simple monolithic application
- Direct database queries
- No unnecessary caching or event bus
- Easy to deploy and debug
- Scales when actually needed
- Can extract services later if/when needed

### Explanation

The BAD example implements microservices architecture with caching, message queues, and complex deployment for a simple CRUD application. The GOOD example uses a monolithic approach that's much simpler and easier to maintain. Following YAGNI means starting with a monolith and extracting microservices only when there's clear need (scale, team size, or domain boundaries).

---

## Example 8: Configuration Overload

### BAD Example: Over-Configured Application

```python
from typing import Any, Dict
import yaml
import os


class Config:
    """
    Over-engineered configuration with options never used.
    """

    def __init__(self, config_file: str = "config.yaml"):
        with open(config_file) as f:
            self.config = yaml.safe_load(f)

    # ========== Database ==========

    def get_db_host(self) -> str:
        return self.config.get("database", {}).get("host", "localhost")

    def get_db_port(self) -> int:
        return self.config.get("database", {}).get("port", 5432)

    def get_db_name(self) -> str:
        return self.config.get("database", {}).get("name", "myapp")

    def get_db_user(self) -> str:
        return self.config.get("database", {}).get("user", "postgres")

    def get_db_password(self) -> str:
        return self.config.get("database", {}).get("password", "")

    def get_db_pool_size(self) -> int:
        return self.config.get("database", {}).get("pool_size", 10)

    def get_db_max_overflow(self) -> int:
        return self.config.get("database", {}).get("max_overflow", 20)

    def get_db_pool_timeout(self) -> int:
        return self.config.get("database", {}).get("pool_timeout", 30)

    def get_db_pool_recycle(self) -> int:
        return self.config.get("database", {}).get("pool_recycle", 3600)

    def get_db_echo(self) -> bool:
        return self.config.get("database", {}).get("echo", False)

    # ========== Cache (Never Used!) ==========

    def get_cache_type(self) -> str:
        return self.config.get("cache", {}).get("type", "redis")

    def get_cache_host(self) -> str:
        return self.config.get("cache", {}).get("host", "localhost")

    def get_cache_port(self) -> int:
        return self.config.get("cache", {}).get("port", 6379)

    def get_cache_db(self) -> int:
        return self.config.get("cache", {}).get("db", 0)

    def get_cache_password(self) -> str:
        return self.config.get("cache", {}).get("password", "")

    def get_cache_default_ttl(self) -> int:
        return self.config.get("cache", {}).get("default_ttl", 3600)

    def get_cache_key_prefix(self) -> str:
        return self.config.get("cache", {}).get("key_prefix", "myapp")

    def get_cache_max_connections(self) -> int:
        return self.config.get("cache", {}).get("max_connections", 50)

    def get_cache_connection_timeout(self) -> int:
        return self.config.get("cache", {}).get("connection_timeout", 5)

    # ========== Logging (Never Used!) ==========

    def get_logging_level(self) -> str:
        return self.config.get("logging", {}).get("level", "INFO")

    def get_logging_format(self) -> str:
        return self.config.get("logging", {}).get("format", "text")

    def get_logging_file(self) -> Optional[str]:
        return self.config.get("logging", {}).get("file")

    def get_logging_max_size(self) -> int:
        return self.config.get("logging", {}).get("max_size", 10485760)

    def get_logging_backup_count(self) -> int:
        return self.config.get("logging", {}).get("backup_count", 5)

    def get_logging_rotation(self) -> str:
        return self.config.get("logging", {}).get("rotation", "daily")

    def get_logging_compression(self) -> str:
        return self.config.get("logging", {}).get("compression", "gzip")

    # ========== API (Never Used!) ==========

    def get_api_host(self) -> str:
        return self.config.get("api", {}).get("host", "0.0.0.0")

    def get_api_port(self) -> int:
        return self.config.get("api", {}).get("port", 3000)

    def get_api_workers(self) -> int:
        return self.config.get("api", {}).get("workers", 4)

    def get_api_timeout(self) -> int:
        return self.config.get("api", {}).get("timeout", 30)

    def get_api_max_request_size(self) -> int:
        return self.config.get("api", {}).get("max_request_size", 10485760)

    def get_api_cors_enabled(self) -> bool:
        return self.config.get("api", {}).get("cors_enabled", True)

    def get_api_cors_origins(self) -> str:
        return self.config.get("api", {}).get("cors_origins", "*")

    def get_api_cors_methods(self) -> str:
        return self.config.get("api", {}).get("cors_methods", "GET,POST,PUT,DELETE")

    # ========== More Never Used Sections ==========

    def get_feature_enabled(self, feature_name: str) -> bool:
        return self.config.get("features", {}).get(feature_name, {}).get("enabled", False)

    def get_rate_limit_enabled(self) -> bool:
        return self.config.get("rate_limiting", {}).get("enabled", False)

    def get_security_encryption(self) -> bool:
        return self.config.get("security", {}).get("encryption", True)

    def get_performance_compression(self) -> bool:
        return self.config.get("performance", {}).get("compression", True)

    def get_analytics_provider(self) -> str:
        return self.config.get("analytics", {}).get("provider", "google")


# config.yaml with 100+ lines of configuration
# Most never changed from defaults
```

**Problems:**
- Configuration for features never used (cache, analytics, etc.)
- Multiple unused database pool settings
- API configuration never adjusted
- Over 50 configuration methods for simple needs
- Configuration file is 100+ lines with most values at defaults

### GOOD Example: Minimal Configuration

```python
from dataclasses import dataclass
import os


@dataclass
class Config:
    """
    Minimal configuration with only what's needed.
    """
    db_url: str
    port: int

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            db_url=os.getenv("DATABASE_URL", "postgresql://localhost:5432/myapp"),
            port=int(os.getenv("PORT", "3000")),
        )


config = Config.from_env()
```

**Improvements:**
- Only essential configuration values
- Simple dataclass
- Environment-based configuration
- No unused options
- Easy to understand and extend

### Explanation

The BAD example creates an extensive configuration system with dozens of options for features that are never implemented or used. The GOOD example follows YAGNI by only configuring what's actually needed: database connection and server port. Additional configuration can be added when new features require it.

---

## Language-Specific Notes

### Idioms and Patterns

- **EAFP vs LBYL**: "Easier to Ask Forgiveness than Permission" is more Pythonic than checking conditions beforehand, helping avoid over-defensive programming
- **Duck typing**: Python's dynamic typing enables simpler code without premature interface definitions
- **Context managers**: Use `with` statements for resource management instead of building complex wrappers
- **Simple data structures**: Prefer dicts, lists, and tuples over custom classes until behavior is needed

### Language Features

**Features that help:**
- **Dynamic typing**: Allows deferring type abstractions until needed
- **List/dict comprehensions**: Simple, powerful data transformations without helper functions
- **Decorators**: Can add functionality (logging, caching) without changing implementation
- **First-class functions**: Enable passing functions directly, avoiding premature abstraction

**Features that hinder:**
- **Abstract base classes (ABC)**: Easy to overuse creating interfaces for single implementations
- **Type hints**: Can lead to over-engineering when every function has complex type annotations
- **Properties**: Sometimes overused to add getters/setters that aren't needed
- **Metaclasses**: Powerful but often unnecessary complexity

### Framework Considerations

- **Django**: ORM and models encourage good separation, but be careful with over-customizing admin and forms
- **FastAPI**: Type hints and Pydantic models are great, but don't create overly complex schemas upfront
- **Flask**: Minimal framework encourages simplicity - keep it that way
- **SQLAlchemy**: Use base models, but don't create abstract base classes before needed

### Common Pitfalls

1. **Over-using class inheritance**: Composition is often simpler than complex inheritance hierarchies
2. **Creating base classes**: Don't create base classes until multiple similar classes exist
3. **Premature factory patterns**: Direct instantiation is simpler until multiple types are needed
4. **Over-configuration**: Don't make everything configurable - hardcode sensible defaults
5. **Exception hierarchies**: Use built-in exceptions until custom ones provide clear value
