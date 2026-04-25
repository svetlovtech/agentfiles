# YAGNI Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern 1: Speculative Features](#anti-pattern-1-speculative-features)
- [Anti-Pattern 2: Gold Plating](#anti-pattern-2-gold-plating)
- [Anti-Pattern 3: Premature Abstraction](#anti-pattern-3-premature-abstraction)
- [Anti-Pattern 4: Over-Generalization](#anti-pattern-4-over-generalization)
- [Anti-Pattern 5: Unused Functionality](#anti-pattern-5-unused-functionality)
- [Anti-Pattern 6: Dead Code Accumulation](#anti-pattern-6-dead-code-accumulation)
- [Anti-Pattern 7: Framework Overkill](#anti-pattern-7-framework-overkill)
- [Anti-Pattern 8: Configuration Overload](#anti-pattern-8-configuration-overload)
- [Anti-Pattern 9: Crystal Ball Syndrome](#anti-pattern-9-crystal-ball-syndrome)
- [Anti-Pattern 10: Premature Optimization](#anti-pattern-10-premature-optimization)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the YAGNI (You Aren't Gonna Need It) principle in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example following YAGNI principles.

## Anti-Pattern 1: Speculative Features

### Description

Speculative features occur when developers implement functionality for hypothetical future use cases instead of current requirements. In Python, this often manifests as building "flexible" systems with multiple implementations, extensible architectures, or support for features that may never be needed.

### BAD Example

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional, Dict, List
import logging


class PaymentMethod(ABC):
    """Abstract base class for payment methods."""

    @abstractmethod
    def process(self, amount: Decimal) -> Dict:
        pass

    @abstractmethod
    def refund(self, transaction_id: str, amount: Decimal) -> Dict:
        pass

    @abstractmethod
    def get_status(self, transaction_id: str) -> Dict:
        pass


class CreditCardPayment(PaymentMethod):
    """Credit card payment implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = self._init_client()

    def _init_client(self):
        # Initialize credit card client
        return None

    def process(self, amount: Decimal) -> Dict:
        logging.info(f"Processing credit card payment: ${amount}")
        return {"status": "success", "transaction_id": "cc_123"}

    def refund(self, transaction_id: str, amount: Decimal) -> Dict:
        logging.info(f"Refunding credit card: {transaction_id}")
        return {"status": "success"}

    def get_status(self, transaction_id: str) -> Dict:
        return {"transaction_id": transaction_id, "status": "completed"}


class PayPalPayment(PaymentMethod):
    """PayPal payment implementation."""

    def __init__(self, client_id: str, secret: str):
        self.client_id = client_id
        self.secret = secret

    def process(self, amount: Decimal) -> Dict:
        logging.info(f"Processing PayPal payment: ${amount}")
        return {"status": "success", "transaction_id": "pp_456"}

    def refund(self, transaction_id: str, amount: Decimal) -> Dict:
        logging.info(f"Refunding PayPal: {transaction_id}")
        return {"status": "success"}

    def get_status(self, transaction_id: str) -> Dict:
        return {"transaction_id": transaction_id, "status": "completed"}


class StripePayment(PaymentMethod):
    """Stripe payment implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def process(self, amount: Decimal) -> Dict:
        logging.info(f"Processing Stripe payment: ${amount}")
        return {"status": "success", "transaction_id": "st_789"}

    def refund(self, transaction_id: str, amount: Decimal) -> Dict:
        logging.info(f"Refunding Stripe: {transaction_id}")
        return {"status": "success"}

    def get_status(self, transaction_id: str) -> Dict:
        return {"transaction_id": transaction_id, "status": "completed"}


class BitcoinPayment(PaymentMethod):
    """Bitcoin payment implementation - NEVER USED!"""

    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address

    def process(self, amount: Decimal) -> Dict:
        logging.info(f"Processing Bitcoin payment: ${amount}")
        return {"status": "success", "transaction_id": "btc_abc"}

    def refund(self, transaction_id: str, amount: Decimal) -> Dict:
        logging.info(f"Bitcoin refunds not implemented yet")
        return {"status": "error", "message": "Refunds not supported"}

    def get_status(self, transaction_id: str) -> Dict:
        return {"transaction_id": transaction_id, "status": "pending"}


class ApplePayPayment(PaymentMethod):
    """Apple Pay implementation - NEVER USED!"""

    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id

    def process(self, amount: Decimal) -> Dict:
        logging.info(f"Processing Apple Pay: ${amount}")
        return {"status": "success", "transaction_id": "ap_def"}

    def refund(self, transaction_id: str, amount: Decimal) -> Dict:
        return {"status": "error", "message": "Not implemented"}

    def get_status(self, transaction_id: str) -> Dict:
        return {"transaction_id": transaction_id, "status": "unknown"}


class PaymentProcessor:
    """Universal payment processor with multiple payment methods."""

    def __init__(self):
        self.methods: Dict[str, PaymentMethod] = {
            "credit_card": CreditCardPayment(api_key="test_key"),
            "paypal": PayPalPayment(client_id="test_id", secret="test_secret"),
            "stripe": StripePayment(api_key="test_key"),
            "bitcoin": BitcoinPayment(wallet_address="test_wallet"),
            "apple_pay": ApplePayPayment(merchant_id="test_merchant"),
        }
        self.default_method = "credit_card"

    def process_payment(
        self,
        method: Optional[str] = None,
        amount: Decimal = Decimal("0.00")
    ) -> Dict:
        """Process payment using specified method."""
        method = method or self.default_method
        payment_method = self.methods.get(method)

        if not payment_method:
            raise ValueError(f"Unknown payment method: {method}")

        return payment_method.process(amount)

    def refund_payment(
        self,
        transaction_id: str,
        amount: Decimal,
        method: Optional[str] = None
    ) -> Dict:
        """Refund payment."""
        method = method or self.default_method
        payment_method = self.methods.get(method)

        if not payment_method:
            raise ValueError(f"Unknown payment method: {method}")

        return payment_method.refund(transaction_id, amount)

    def add_payment_method(self, name: str, method: PaymentMethod) -> None:
        """Add a new payment method."""
        self.methods[name] = method

    def remove_payment_method(self, name: str) -> None:
        """Remove a payment method."""
        if name in self.methods:
            del self.methods[name]

    def get_available_methods(self) -> List[str]:
        """Get list of available payment methods."""
        return list(self.methods.keys())


# Usage
processor = PaymentProcessor()
result = processor.process_payment(method="credit_card", amount=Decimal("100.00"))
```

### Why It's Problematic

- **Speculative implementations**: Built Bitcoin and Apple Pay payment methods that are never used
- **Unnecessary abstraction**: Abstract base class for only one currently used payment method
- **Complex architecture**: Multiple payment classes and processor when only credit card is needed
- **Testing burden**: All payment methods must be tested even when unused
- **Maintenance overhead**: Unused code still requires maintenance and updates
- **Confusing for new developers**: Must understand entire system to use one feature

### How to Fix

**Refactoring Steps:**
1. Identify which payment methods are actually used (only credit card)
2. Remove abstract base class and unused payment methods (Bitcoin, Apple Pay)
3. Implement a simple function for credit card payment processing
4. Add other payment methods only when they become actual requirements
5. Keep the implementation simple and direct

### GOOD Example

```python
from decimal import Decimal
import logging


def process_credit_card_payment(
    card_number: str,
    amount: Decimal,
    cvv: Optional[str] = None,
    expiry: Optional[str] = None
) -> Dict:
    """
    Process a credit card payment.
    Only implemented what's needed now.
    """
    if not card_number or len(card_number) < 13:
        return {"status": "error", "message": "Invalid card number"}

    if not amount or amount <= 0:
        return {"status": "error", "message": "Invalid amount"}

    logging.info(f"Processing payment of ${amount} for card ending in {card_number[-4:]}")

    # Actual payment processing with payment gateway
    transaction_id = f"cc_{hash(card_number) % 10000}"

    return {
        "status": "success",
        "amount": float(amount),
        "transaction_id": transaction_id
    }


def refund_credit_card_payment(transaction_id: str, amount: Decimal) -> Dict:
    """
    Refund a credit card payment.
    """
    logging.info(f"Refunding ${amount} for transaction {transaction_id}")

    return {
        "status": "success",
        "transaction_id": transaction_id,
        "refunded_amount": float(amount)
    }


# Usage
result = process_credit_card_payment(
    card_number="4111111111111111",
    amount=Decimal("100.00")
)
```

**Key Changes:**
- Removed abstract base class and unused payment methods
- Simplified from 200+ lines to 40 lines
- Only implements credit card payment (actual requirement)
- Clear, direct functions instead of complex class hierarchy
- Can add PayPal/Stripe when actually needed
- Much easier to test and maintain

---

## Anti-Pattern 2: Gold Plating

### Description

Gold plating involves adding unnecessary features, polish, or enhancements beyond current requirements. In Python, this manifests as extensive validation, rich error handling, logging, caching, or configuration systems for simple functionality.

### BAD Example

```python
from typing import Any, Dict, List, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import re
import logging


class ValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class Validator:
    """Universal validator with extensive rule support."""

    def __init__(self):
        self.rules: Dict[str, List[Callable]] = {}
        self.pre_processors: List[Callable] = []
        self.post_processors: List[Callable] = []
        self.error_messages: Dict[str, str] = {}
        self.severity_levels: Dict[str, ValidationSeverity] = {}

    def add_rule(
        self,
        field: str,
        validator: Callable,
        error_message: str = "Validation failed",
        severity: ValidationSeverity = ValidationSeverity.ERROR
    ) -> None:
        """Add a validation rule."""
        if field not in self.rules:
            self.rules[field] = []
        self.rules[field].append(validator)
        self.error_messages[f"{field}_{validator.__name__}"] = error_message
        self.severity_levels[f"{field}_{validator.__name__}"] = severity

    def add_pre_processor(self, processor: Callable) -> None:
        """Add a pre-processor to normalize input."""
        self.pre_processors.append(processor)

    def add_post_processor(self, processor: Callable) -> None:
        """Add a post-processor for validation results."""
        self.post_processors.append(processor)

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate data against all rules."""
        result = ValidationResult(is_valid=True)

        # Pre-process data
        for processor in self.pre_processors:
            data = processor(data)

        # Validate each field
        for field, validators in self.rules.items():
            value = data.get(field)

            for validator in validators:
                try:
                    if not validator(value):
                        result.is_valid = False
                        error_key = f"{field}_{validator.__name__}"
                        error_msg = self.error_messages.get(error_key, "Validation failed")
                        severity = self.severity_levels.get(error_key, ValidationSeverity.ERROR)

                        if severity == ValidationSeverity.ERROR:
                            result.errors.append(error_msg)
                        elif severity == ValidationSeverity.WARNING:
                            result.warnings.append(error_msg)

                except Exception as e:
                    result.is_valid = False
                    result.errors.append(f"Validation error for {field}: {str(e)}")

        result.context["validated_fields"] = list(self.rules.keys())

        # Post-process results
        for processor in self.post_processors:
            result = processor(result)

        return result


class UserValidator(Validator):
    """Comprehensive user data validator."""

    def __init__(self):
        super().__init__()
        self._setup_rules()

    def _setup_rules(self) -> None:
        """Set up all validation rules."""

        # Email validation
        def validate_email(email: Any) -> bool:
            if not email:
                return False
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, str(email)))

        def validate_email_domain(email: Any) -> bool:
            """Check for disposable email domains - NEVER USED!"""
            if not email:
                return True
            disposable_domains = ["tempmail.com", "throwaway.com"]
            domain = str(email).split("@")[-1].lower()
            return domain not in disposable_domains

        # Password validation
        def validate_password_length(password: Any) -> bool:
            if not password:
                return False
            return len(str(password)) >= 8

        def validate_password_uppercase(password: Any) -> bool:
            if not password:
                return False
            return any(c.isupper() for c in str(password))

        def validate_password_lowercase(password: Any) -> bool:
            if not password:
                return False
            return any(c.islower() for c in str(password))

        def validate_password_digit(password: Any) -> bool:
            if not password:
                return False
            return any(c.isdigit() for c in str(password))

        def validate_password_special(password: Any) -> bool:
            """Check for special characters - NEVER USED!"""
            if not password:
                return False
            special_chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/"
            return any(c in special_chars for c in str(password))

        def validate_password_common(password: Any) -> bool:
            """Check against common passwords - NEVER USED!"""
            if not password:
                return True
            common_passwords = ["password", "123456", "qwerty"]
            return str(password).lower() not in common_passwords

        # Username validation
        def validate_username_length(username: Any) -> bool:
            if not username:
                return False
            return 3 <= len(str(username)) <= 20

        def validate_username_characters(username: Any) -> bool:
            if not username:
                return False
            return bool(re.match(r'^[a-zA-Z0-9_]+$', str(username)))

        # Add rules
        self.add_rule(
            "email",
            validate_email,
            "Email must be a valid email address",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "email",
            validate_email_domain,
            "Disposable email domains are not allowed",
            ValidationSeverity.WARNING
        )

        self.add_rule(
            "password",
            validate_password_length,
            "Password must be at least 8 characters",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "password",
            validate_password_uppercase,
            "Password must contain at least one uppercase letter",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "password",
            validate_password_lowercase,
            "Password must contain at least one lowercase letter",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "password",
            validate_password_digit,
            "Password must contain at least one digit",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "password",
            validate_password_special,
            "Password must contain at least one special character",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "password",
            validate_password_common,
            "Password is too common",
            ValidationSeverity.WARNING
        )

        self.add_rule(
            "username",
            validate_username_length,
            "Username must be between 3 and 20 characters",
            ValidationSeverity.ERROR
        )

        self.add_rule(
            "username",
            validate_username_characters,
            "Username can only contain letters, numbers, and underscores",
            ValidationSeverity.ERROR
        )


# Usage
validator = UserValidator()
user_data = {
    "email": "user@example.com",
    "password": "SecurePass123",
    "username": "john_doe"
}
result = validator.validate(user_data)
```

### Why It's Problematic

- **Over-validation**: Implements 10+ validation rules when only basic validation is needed
- **Unused features**: Email domain checking, special character validation, and common password checking never used
- **Complex architecture**: Pre-processors, post-processors, and severity levels for simple validation
- **High maintenance**: Every validation rule must be maintained and tested
- **Performance impact**: All rules run on every validation even when unnecessary
- **Over-engineered**: 200+ lines of code for what could be 30 lines

### How to Fix

**Refactoring Steps:**
1. Identify the actual validation requirements (email format, password length)
2. Remove unused validation rules (domain check, special characters, common passwords)
3. Remove pre-processors, post-processors, and severity levels
4. Implement simple, direct validation functions
5. Keep the code focused on current requirements

### GOOD Example

```python
import re
from typing import Dict, Optional


def validate_user_data(user_data: Dict) -> Dict:
    """
    Validate user registration data.
    Only validates what's actually needed.
    """
    errors = {}

    # Validate email
    email = user_data.get("email")
    if not email:
        errors["email"] = "Email is required"
    elif not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        errors["email"] = "Invalid email format"

    # Validate password
    password = user_data.get("password")
    if not password:
        errors["password"] = "Password is required"
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"

    # Validate username
    username = user_data.get("username")
    if not username:
        errors["username"] = "Username is required"
    elif len(username) < 3:
        errors["username"] = "Username must be at least 3 characters"
    elif not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors["username"] = "Username can only contain letters, numbers, and underscores"

    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }


# Usage
user_data = {
    "email": "user@example.com",
    "password": "SecurePass123",
    "username": "john_doe"
}
result = validate_user_data(user_data)
```

**Key Changes:**
- Removed complex Validator class with pre/post processors
- Removed unused validation rules (domain check, special chars, common passwords)
- Simplified from 200+ lines to 35 lines
- Direct, clear validation logic
- Easy to understand and modify
- Can add more validation when actually needed

---

## Anti-Pattern 3: Premature Abstraction

### Description

Premature abstraction involves creating abstract base classes, interfaces, or design patterns before there's clear need for them. In Python, this manifests as using ABCs, factory patterns, or complex inheritance hierarchies for single implementations.

### BAD Example

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging


class DataSource(ABC):
    """Abstract base class for all data sources."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to data source."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to data source."""
        pass

    @abstractmethod
    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute query and return results."""
        pass

    @abstractmethod
    def insert(self, table: str, data: Dict) -> int:
        """Insert record into table."""
        pass

    @abstractmethod
    def update(self, table: str, id: int, data: Dict) -> bool:
        """Update record in table."""
        pass

    @abstractmethod
    def delete(self, table: str, id: int) -> bool:
        """Delete record from table."""
        pass

    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin a transaction."""
        pass

    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit current transaction."""
        pass

    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        pass


class PostgreSQLDataSource(DataSource):
    """PostgreSQL data source implementation."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None
        self._in_transaction = False

    def connect(self) -> None:
        """Connect to PostgreSQL database."""
        import psycopg2
        self.connection = psycopg2.connect(self.connection_string)
        logging.info("Connected to PostgreSQL")

    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self.connection:
            self.connection.close()
            logging.info("Disconnected from PostgreSQL")

    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute query and return results."""
        cursor = self.connection.cursor()
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        return results

    def insert(self, table: str, data: Dict) -> int:
        """Insert record into table."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
        cursor = self.connection.cursor()
        cursor.execute(query, list(data.values()))
        result_id = cursor.fetchone()[0]
        self.connection.commit()
        cursor.close()
        return result_id

    def update(self, table: str, id: int, data: Dict) -> bool:
        """Update record in table."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE id = %s"
        cursor = self.connection.cursor()
        cursor.execute(query, list(data.values()) + [id])
        self.connection.commit()
        cursor.close()
        return cursor.rowcount > 0

    def delete(self, table: str, id: int) -> bool:
        """Delete record from table."""
        query = f"DELETE FROM {table} WHERE id = %s"
        cursor = self.connection.cursor()
        cursor.execute(query, [id])
        self.connection.commit()
        cursor.close()
        return cursor.rowcount > 0

    def begin_transaction(self) -> None:
        """Begin a transaction."""
        self.connection.autocommit = False
        self._in_transaction = True

    def commit_transaction(self) -> None:
        """Commit current transaction."""
        self.connection.commit()
        self.connection.autocommit = True
        self._in_transaction = False

    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        self.connection.rollback()
        self.connection.autocommit = True
        self._in_transaction = False


class MySQLDataSource(DataSource):
    """MySQL data source implementation - NEVER USED!"""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None

    def connect(self) -> None:
        """Connect to MySQL database."""
        import mysql.connector
        self.connection = mysql.connector.connect(self.connection_string)
        logging.info("Connected to MySQL")

    def disconnect(self) -> None:
        """Close MySQL connection."""
        if self.connection:
            self.connection.close()
            logging.info("Disconnected from MySQL")

    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute query and return results."""
        cursor = self.connection.cursor(dictionary=True)
        cursor.execute(query, params)
        results = cursor.fetchall()
        cursor.close()
        return results

    def insert(self, table: str, data: Dict) -> int:
        """Insert record into table."""
        # MySQL implementation - never called
        return 0

    def update(self, table: str, id: int, data: Dict) -> bool:
        """Update record in table."""
        # MySQL implementation - never called
        return False

    def delete(self, table: str, id: int) -> bool:
        """Delete record from table."""
        # MySQL implementation - never called
        return False

    def begin_transaction(self) -> None:
        """Begin a transaction."""
        # MySQL implementation - never called
        pass

    def commit_transaction(self) -> None:
        """Commit current transaction."""
        # MySQL implementation - never called
        pass

    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        # MySQL implementation - never called
        pass


class MongoDBDataSource(DataSource):
    """MongoDB data source implementation - NEVER USED!"""

    def __init__(self, connection_string: str, database: str):
        self.connection_string = connection_string
        self.database = database
        self.client = None

    def connect(self) -> None:
        """Connect to MongoDB."""
        import pymongo
        self.client = pymongo.MongoClient(self.connection_string)
        logging.info("Connected to MongoDB")

    def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logging.info("Disconnected from MongoDB")

    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute query and return results."""
        # MongoDB implementation - never called
        return []

    def insert(self, table: str, data: Dict) -> int:
        """Insert document into collection."""
        # MongoDB implementation - never called
        return 0

    def update(self, table: str, id: int, data: Dict) -> bool:
        """Update document in collection."""
        # MongoDB implementation - never called
        return False

    def delete(self, table: str, id: int) -> bool:
        """Delete document from collection."""
        # MongoDB implementation - never called
        return False

    def begin_transaction(self) -> None:
        """Begin a transaction."""
        # MongoDB implementation - never called
        pass

    def commit_transaction(self) -> None:
        """Commit current transaction."""
        # MongoDB implementation - never called
        pass

    def rollback_transaction(self) -> None:
        """Rollback current transaction."""
        # MongoDB implementation - never called
        pass


class DataSourceFactory:
    """Factory for creating data sources."""

    @staticmethod
    def create_data_source(
        db_type: str,
        connection_string: str,
        **kwargs
    ) -> DataSource:
        """Create a data source of the specified type."""
        if db_type == "postgresql":
            return PostgreSQLDataSource(connection_string)
        elif db_type == "mysql":
            return MySQLDataSource(connection_string)
        elif db_type == "mongodb":
            return MongoDBDataSource(connection_string, kwargs.get("database", "default"))
        else:
            raise ValueError(f"Unsupported database type: {db_type}")


class Repository:
    """Generic repository using data source abstraction."""

    def __init__(self, data_source: DataSource, table: str):
        self.data_source = data_source
        self.table = table

    def find_by_id(self, id: int) -> Optional[Dict]:
        """Find record by ID."""
        results = self.data_source.query(
            f"SELECT * FROM {self.table} WHERE id = %s",
            {"id": id}
        )
        return results[0] if results else None

    def find_all(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Find all records with optional filters."""
        if filters:
            where_clause = " AND ".join([f"{k} = %s" for k in filters.keys()])
            query = f"SELECT * FROM {self.table} WHERE {where_clause}"
            return self.data_source.query(query, filters)
        else:
            return self.data_source.query(f"SELECT * FROM {self.table}")

    def create(self, data: Dict) -> int:
        """Create new record."""
        return self.data_source.insert(self.table, data)

    def update(self, id: int, data: Dict) -> bool:
        """Update record."""
        return self.data_source.update(self.table, id, data)

    def delete(self, id: int) -> bool:
        """Delete record."""
        return self.data_source.delete(self.table, id)


# Usage
data_source = DataSourceFactory.create_data_source(
    "postgresql",
    "postgresql://user:pass@localhost/mydb"
)
user_repository = Repository(data_source, "users")
```

### Why It's Problematic

- **Unnecessary abstraction**: Abstract base class for only one actual implementation
- **Speculative implementations**: MySQL and MongoDB data sources created but never used
- **Factory pattern overhead**: Factory class for creating single type of data source
- **Generic repository**: Generic repository pattern for simple CRUD operations
- **Complex inheritance**: Three levels of abstraction for direct database operations
- **Unused features**: Transaction management that's never used

### How to Fix

**Refactoring Steps:**
1. Remove abstract base class and unused data source implementations
2. Implement direct PostgreSQL database class
3. Remove factory pattern
4. Simplify repository to concrete implementation
5. Keep only the functionality that's actually used

### GOOD Example

```python
import psycopg2
from typing import Dict, List, Optional


class Database:
    """
    Direct PostgreSQL database implementation.
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

    def query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute query and return results."""
        cursor = self.connection.cursor()
        cursor.execute(query, params or ())
        columns = [desc[0] for desc in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        cursor.close()
        return results

    def insert(self, table: str, data: Dict) -> int:
        """Insert record into table."""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id"
        cursor = self.connection.cursor()
        cursor.execute(query, list(data.values()))
        result_id = cursor.fetchone()[0]
        self.connection.commit()
        cursor.close()
        return result_id

    def update(self, table: str, id: int, data: Dict) -> bool:
        """Update record in table."""
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE id = %s"
        cursor = self.connection.cursor()
        cursor.execute(query, list(data.values()) + [id])
        self.connection.commit()
        cursor.close()
        return cursor.rowcount > 0

    def delete(self, table: str, id: int) -> bool:
        """Delete record from table."""
        query = f"DELETE FROM {table} WHERE id = %s"
        cursor = self.connection.cursor()
        cursor.execute(query, [id])
        self.connection.commit()
        cursor.close()
        return cursor.rowcount > 0


class UserRepository:
    """User repository with direct database operations."""

    def __init__(self, db: Database):
        self.db = db

    def find_by_id(self, id: int) -> Optional[Dict]:
        """Find user by ID."""
        results = self.db.query(
            "SELECT * FROM users WHERE id = %s",
            (id,)
        )
        return results[0] if results else None

    def find_by_email(self, email: str) -> Optional[Dict]:
        """Find user by email."""
        results = self.db.query(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )
        return results[0] if results else None

    def create(self, data: Dict) -> int:
        """Create new user."""
        return self.db.insert("users", data)

    def update(self, id: int, data: Dict) -> bool:
        """Update user."""
        return self.db.update("users", id, data)

    def delete(self, id: int) -> bool:
        """Delete user."""
        return self.db.delete("users", id)


# Usage
db = Database("postgresql://user:pass@localhost/mydb")
user_repo = UserRepository(db)
```

**Key Changes:**
- Removed abstract base class and unused MySQL/MongoDB implementations
- Removed factory pattern
- Direct PostgreSQL implementation
- Concrete UserRepository instead of generic Repository
- Simplified from 300+ lines to 80 lines
- Easy to understand and modify

---

## Anti-Pattern 4: Over-Generalization

### Description

Over-generalization involves creating overly general solutions for specific problems. In Python, this manifests as building "universal" handlers, creating configuration systems for future flexibility, or writing functions that handle cases not currently required.

### BAD Example

```python
from typing import Any, Dict, List, Optional, Callable, Union
from pathlib import Path
import json
import yaml
import toml
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod


class ConfigLoader(ABC):
    """Abstract base class for configuration loaders."""

    @abstractmethod
    def load(self, path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        pass

    @abstractmethod
    def save(self, path: str, data: Dict[str, Any]) -> None:
        """Save configuration to file."""
        pass

    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate configuration data."""
        pass


class JSONConfigLoader(ConfigLoader):
    """JSON configuration loader."""

    def load(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return json.load(f)

    def save(self, path: str, data: Dict[str, Any]) -> None:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def validate(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, dict)


class YAMLConfigLoader(ConfigLoader):
    """YAML configuration loader."""

    def load(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def save(self, path: str, data: Dict[str, Any]) -> None:
        with open(path, 'w') as f:
            yaml.dump(data, f)

    def validate(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, dict)


class TOMLConfigLoader(ConfigLoader):
    """TOML configuration loader - NEVER USED!"""

    def load(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return toml.load(f)

    def save(self, path: str, data: Dict[str, Any]) -> None:
        with open(path, 'w') as f:
            toml.dump(data, f)

    def validate(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, dict)


class XMLConfigLoader(ConfigLoader):
    """XML configuration loader - NEVER USED!"""

    def load(self, path: str) -> Dict[str, Any]:
        tree = ET.parse(path)
        root = tree.getroot()
        return self._xml_to_dict(root)

    def save(self, path: str, data: Dict[str, Any]) -> None:
        root = self._dict_to_xml(data)
        tree = ET.ElementTree(root)
        tree.write(path, encoding='utf-8', xml_declaration=True)

    def validate(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, dict)

    def _xml_to_dict(self, element: ET.Element) -> Dict:
        result = {element.tag: {} if element.attrib else None}
        children = list(element)
        if children:
            dd = {}
            for dc in map(self._xml_to_dict, children):
                for k, v in dc.items():
                    dd[k] = v
            result = {element.tag: dd}
        if element.attrib:
            result[element.tag].update(('@' + k, v) for k, v in element.attrib.items())
        if element.text:
            text = element.text.strip()
            if children or element.attrib:
                if text:
                    result[element.tag]['#text'] = text
            else:
                result[element.tag] = text
        return result

    def _dict_to_xml(self, data: Dict) -> ET.Element:
        root = ET.Element(list(data.keys())[0])
        return root


class ConfigManager:
    """
    Universal configuration manager with multiple features.
    Over-engineered for simple configuration needs.
    """

    def __init__(self):
        self.loaders: Dict[str, ConfigLoader] = {
            "json": JSONConfigLoader(),
            "yaml": YAMLConfigLoader(),
            "yml": YAMLConfigLoader(),
            "toml": TOMLConfigLoader(),
            "xml": XMLConfigLoader(),
        }
        self.config: Dict[str, Any] = {}
        self.cache: Dict[str, Any] = {}
        self.watchers: Dict[str, List[Callable]] = {}
        self.validators: Dict[str, Callable] = {}
        self.transformers: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []

    def load_config(self, path: str, use_cache: bool = True) -> Dict[str, Any]:
        """Load configuration from file."""
        if use_cache and path in self.cache:
            return self.cache[path]

        file_path = Path(path)
        extension = file_path.suffix.lstrip('.')

        if extension not in self.loaders:
            raise ValueError(f"Unsupported config format: {extension}")

        loader = self.loaders[extension]
        data = loader.load(path)

        if not loader.validate(data):
            raise ValueError(f"Invalid configuration in {path}")

        # Apply transformers
        for key, transformer in self.transformers.items():
            if key in data:
                data[key] = transformer(data[key])

        # Apply middleware
        for middleware in self.middleware:
            data = middleware(data)

        self.config.update(data)
        self.cache[path] = data

        # Notify watchers
        self._notify_watchers(path, data)

        return data

    def save_config(self, path: str) -> None:
        """Save configuration to file."""
        file_path = Path(path)
        extension = file_path.suffix.lstrip('.')

        if extension not in self.loaders:
            raise ValueError(f"Unsupported config format: {extension}")

        loader = self.loaders[extension]
        loader.save(path, self.config)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def add_validator(self, key: str, validator: Callable[[Any], bool]) -> None:
        """Add a validator for a configuration key."""
        self.validators[key] = validator

    def add_transformer(self, key: str, transformer: Callable[[Any], Any]) -> None:
        """Add a transformer for a configuration key."""
        self.transformers[key] = transformer

    def add_middleware(self, middleware: Callable[[Dict], Dict]) -> None:
        """Add middleware for configuration processing."""
        self.middleware.append(middleware)

    def add_watcher(self, path: str, callback: Callable[[Dict], None]) -> None:
        """Add a watcher for configuration changes."""
        if path not in self.watchers:
            self.watchers[path] = []
        self.watchers[path].append(callback)

    def remove_watcher(self, path: str, callback: Callable[[Dict], None]) -> None:
        """Remove a watcher."""
        if path in self.watchers and callback in self.watchers[path]:
            self.watchers[path].remove(callback)

    def _notify_watchers(self, path: str, data: Dict) -> None:
        """Notify all watchers of configuration changes."""
        if path in self.watchers:
            for callback in self.watchers[path]:
                callback(data)

    def clear_cache(self) -> None:
        """Clear configuration cache."""
        self.cache.clear()

    def reload_all(self, paths: List[str]) -> None:
        """Reload all configuration files."""
        for path in paths:
            self.load_config(path, use_cache=False)


# Usage
config_manager = ConfigManager()
config = config_manager.load_config("config.json")
```

### Why It's Problematic

- **Over-generalized system**: Supports JSON, YAML, TOML, and XML when only JSON is used
- **Unnecessary features**: Caching, watching, validators, transformers, and middleware never used
- **Complex architecture**: Abstract base class, multiple loaders, and manager pattern for simple needs
- **High cognitive load**: Developers must understand entire system to use basic functionality
- **Testing burden**: All features must be tested even when unused
- **Maintenance overhead**: Every loader and feature must be maintained

### How to Fix

**Refactoring Steps:**
1. Identify which configuration format is actually used (JSON)
2. Remove unused loaders (YAML, TOML, XML)
3. Remove caching, watching, validators, transformers, and middleware
4. Implement simple JSON configuration loading
5. Keep code focused on current requirements

### GOOD Example

```python
import json
from typing import Dict, Any
from pathlib import Path


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load JSON configuration file.
    Simple and direct implementation.
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open() as f:
        return json.load(f)


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Get configuration value with optional default using dot notation.
    """
    keys = key.split('.')
    value = config

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value


# Usage
config = load_config("config.json")
database_url = get_config_value(config, "database.url", "postgresql://localhost/mydb")
```

**Key Changes:**
- Removed abstract base class and unused loaders (YAML, TOML, XML)
- Removed caching, watching, validators, transformers, middleware
- Simplified from 250+ lines to 30 lines
- Simple, direct functions
- Easy to understand and test
- Can add features when actually needed

---

## Anti-Pattern 5: Unused Functionality

### Description

Unused functionality accumulates when developers add features that are never actually used or called. In Python, this includes methods that are never invoked, utility functions that are never imported, or class methods that serve no purpose in the current implementation.

### BAD Example

```python
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import hashlib
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
    XML = "xml"  # Never used!
    HTML = "html"  # Never used!


class Logger:
    """
    Comprehensive logging system with many unused features.
    """

    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        self.level = LogLevel(self.config.get("level", "info"))
        self.format_type = self.config.get("format", "text")
        self.context: Dict[str, Any] = {}
        self.handlers: List[Callable] = []
        self.filters: List[Callable] = []
        self.formatters: Dict[str, Callable] = {
            "text": self._format_text,
            "json": self._format_json,
            "xml": self._format_xml,  # Never used!
            "html": self._format_html,  # Never used!
        }
        self.metrics = {
            "log_counts": {level.value: 0 for level in LogLevel},
            "total_logs": 0,
            "errors": 0
        }

    def set_level(self, level: LogLevel) -> None:
        """Set the logging level."""
        self.level = level

    def set_format(self, format_type: str) -> None:
        """Set the log format type."""
        self.format_type = format_type

    def set_context(self, key: str, value: Any) -> None:
        """Set a context value."""
        self.context[key] = value

    def clear_context(self) -> None:
        """Clear all context values."""
        self.context.clear()

    def add_handler(self, handler: Callable) -> None:
        """Add a log handler."""
        self.handlers.append(handler)

    def add_filter(self, filter_func: Callable) -> None:
        """Add a log filter."""
        self.filters.append(filter_func)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log(LogLevel.ERROR, message, **kwargs)
        self.metrics["errors"] += 1

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **kwargs)

    def _log(self, level: LogLevel, message: str, **kwargs) -> None:
        """Internal logging method."""
        if not self._should_log(level):
            return

        # Apply filters
        if not self._apply_filters(message):
            return

        # Format message
        log_message = self._format_message(level, message, **kwargs)

        # Update metrics
        self.metrics["log_counts"][level.value] += 1
        self.metrics["total_logs"] += 1

        # Write to handlers
        for handler in self.handlers:
            handler(log_message)

        # Also use standard logging
        getattr(logging, level.value)(log_message)

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level."""
        level_order = ["debug", "info", "warning", "error", "critical"]
        return level_order.index(level.value) >= level_order.index(self.level.value)

    def _apply_filters(self, message: str) -> bool:
        """Apply all filters to message."""
        for filter_func in self.filters:
            if not filter_func(message):
                return False
        return True

    def _format_message(self, level: LogLevel, message: str, **kwargs) -> str:
        """Format log message."""
        formatter = self.formatters.get(self.format_type, self._format_text)
        return formatter(level, message, **kwargs)

    def _format_text(self, level: LogLevel, message: str, **kwargs) -> str:
        """Format as text."""
        context_str = ""
        if self.context or kwargs:
            all_context = {**self.context, **kwargs}
            context_str = f" | Context: {json.dumps(all_context)}"

        timestamp = datetime.now().isoformat()
        return f"{timestamp} - {self.name} - {level.value.upper()} - {message}{context_str}"

    def _format_json(self, level: LogLevel, message: str, **kwargs) -> str:
        """Format as JSON."""
        return json.dumps({
            "timestamp": datetime.now().isoformat(),
            "logger": self.name,
            "level": level.value,
            "message": message,
            "context": {**self.context, **kwargs}
        })

    def _format_xml(self, level: LogLevel, message: str, **kwargs) -> str:
        """Format as XML - NEVER USED!"""
        context_xml = ""
        if self.context or kwargs:
            all_context = {**self.context, **kwargs}
            context_items = "".join([f"<{k}>{v}</{k}>" for k, v in all_context.items()])
            context_xml = f"<context>{context_items}</context>"

        return f"""<log>
    <timestamp>{datetime.now().isoformat()}</timestamp>
    <logger>{self.name}</logger>
    <level>{level.value}</level>
    <message>{message}</message>
    {context_xml}
</log>"""

    def _format_html(self, level: LogLevel, message: str, **kwargs) -> str:
        """Format as HTML - NEVER USED!"""
        context_html = ""
        if self.context or kwargs:
            all_context = {**self.context, **kwargs}
            context_items = "".join([f"<li>{k}: {v}</li>" for k, v in all_context.items()])
            context_html = f"<ul>{context_items}</ul>"

        return f"""<div class="log-entry" data-level="{level.value}">
    <span class="timestamp">{datetime.now().isoformat()}</span>
    <span class="logger">{self.name}</span>
    <span class="level">{level.value}</span>
    <span class="message">{message}</span>
    {context_html}
</div>"""

    def get_metrics(self) -> Dict[str, Any]:
        """Get logging metrics."""
        return self.metrics.copy()

    def reset_metrics(self) -> None:
        """Reset logging metrics."""
        self.metrics = {
            "log_counts": {level.value: 0 for level in LogLevel},
            "total_logs": 0,
            "errors": 0
        }

    def export_logs(self, format_type: str = "json") -> str:
        """Export logs in specified format - NEVER USED!"""
        return self._format_message(LogLevel.INFO, "Export", format_type=format_type)

    def search_logs(self, query: str, level: Optional[LogLevel] = None) -> List[str]:
        """Search logs - NEVER USED!"""
        return []

    def create_child_logger(self, name: str) -> "Logger":
        """Create child logger - NEVER USED!"""
        child = Logger(f"{self.name}.{name}", self.config)
        child.context = self.context.copy()
        return child

    def rotate_logs(self, max_size: int, backup_count: int = 5) -> None:
        """Rotate log files - NEVER USED!"""
        pass

    def compress_logs(self, compression_type: str = "gzip") -> None:
        """Compress old log files - NEVER USED!"""
        pass

    def aggregate_logs(self, period: timedelta) -> Dict[str, Any]:
        """Aggregate logs over time period - NEVER USED!"""
        return {}

    def get_error_rate(self, period: timedelta = timedelta(hours=1)) -> float:
        """Calculate error rate - NEVER USED!"""
        return 0.0


# Usage
logger = Logger("myapp")
logger.info("Application started")
logger.error("Something went wrong", error_code=500)
```

### Why It's Problematic

- **Unused methods**: 15+ methods that are never called (XML/HTML formatters, export_logs, search_logs, etc.)
- **Feature bloat**: XML and HTML logging formats never used
- **Complex metrics**: Metrics tracking that's never accessed
- **Child loggers**: Child logger functionality never used
- **Log rotation/compression**: Features never implemented or used
- **High maintenance**: All features must be maintained even when unused

### How to Fix

**Refactoring Steps:**
1. Identify which logging features are actually used (basic text logging)
2. Remove unused formatters (XML, HTML)
3. Remove unused methods (export_logs, search_logs, create_child_logger, etc.)
4. Remove metrics tracking
5. Simplify to basic logging functionality

### GOOD Example

```python
import logging


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """
    Simple logging configuration.
    Only what's actually needed.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Usage
logger = setup_logging("myapp")
logger.info("Application started")
logger.error("Something went wrong")
```

**Key Changes:**
- Removed custom Logger class with 200+ lines
- Removed unused formatters (XML, HTML)
- Removed unused methods (export_logs, search_logs, child logger, etc.)
- Removed metrics tracking
- Uses Python's built-in logging
- Simple, direct implementation
- Easy to understand and use

---

## Anti-Pattern 6: Dead Code Accumulation

### Description

Dead code accumulates when developers keep commented out code, old implementations, or unused functions "just in case" they might be needed later. In Python, this includes unused imports, commented code blocks, and outdated method versions.

### BAD Example

```python
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


class OrderProcessor:
    """
    Order processing with accumulated dead code.
    """

    def __init__(self):
        self.repository = OrderRepository()
        self.cache = {}  # Cache that's never used

    def process_order(self, order: Dict) -> Dict:
        """Process an order."""
        # Current implementation
        if order.get("status") == "pending":
            order["status"] = "processing"
        elif order.get("status") == "processing":
            order["status"] = "shipped"

        order["updated_at"] = datetime.now().isoformat()
        self.repository.save(order)

        return order

    # ========== DEAD CODE - Remove! ==========

    def validate_order_v1(self, order: Dict) -> bool:
        """Old validation - replaced by v2."""
        return order.get("items") is not None and len(order["items"]) > 0

    def validate_order_v2(self, order: Dict) -> bool:
        """Old validation - replaced by current."""
        required_fields = ["user_id", "items", "total"]
        return all(field in order for field in required_fields)

    def calculate_discount_v1(self, order: Dict) -> float:
        """Old discount logic - moved to separate service."""
        return 0.0

    def calculate_tax_v1(self, order: Dict) -> float:
        """Old tax calculation - replaced by external service."""
        return order.get("total", 0) * 0.1

    def notify_customer_v1(self, order: Dict, message: str) -> None:
        """Old notification - replaced by event system."""
        pass

    def process_order_v2(self, order: Dict) -> Dict:
        """Previous implementation - replaced by current."""
        state_machine = OrderStateMachine(order)
        state_machine.advance()
        return order

    def process_order_v3(self, order: Dict) -> Dict:
        """Previous implementation - replaced by current."""
        if order.get("status") == "pending":
            order["status"] = "processing"
            order["updated_at"] = datetime.now().isoformat()
            self.repository.save(order)
        elif order.get("status") == "processing":
            order["status"] = "shipped"
            order["updated_at"] = datetime.now().isoformat()
            self.repository.save(order)
        return order

    # Unused notification methods
    def send_email_notification(self, to: str, subject: str, body: str) -> None:
        """Email sending - moved to NotificationService."""
        pass

    def send_sms_notification(self, to: str, message: str) -> None:
        """SMS sending - never implemented!"""
        pass

    def send_push_notification(self, to: str, message: str) -> None:
        """Push notifications - never implemented!"""
        pass

    # Unused invoice methods
    def generate_invoice_pdf(self, order: Dict) -> bytes:
        """PDF generation - never implemented!"""
        return b""

    def generate_invoice_html(self, order: Dict) -> str:
        """HTML invoice - never implemented!"""
        return ""

    def send_invoice(self, order: Dict, format: str = "pdf") -> None:
        """Send invoice - never implemented!"""
        pass

    # Unused shipping methods
    def track_shipment(self, order: Dict) -> Dict:
        """Shipment tracking - never implemented!"""
        return {}

    def get_shipping_estimate(self, order: Dict) -> float:
        """Shipping estimates - never implemented!"""
        return 0.0

    def schedule_delivery(self, order: Dict, delivery_date: datetime) -> None:
        """Delivery scheduling - never implemented!"""
        pass

    # Unused payment methods
    def refund_order(self, order: Dict, amount: float) -> bool:
        """Order refund - never implemented!"""
        return False

    def process_return(self, order: Dict, reason: str) -> bool:
        """Order return - never implemented!"""
        return False

    # Cached order lookup - never used
    def get_cached_order(self, order_id: int) -> Optional[Dict]:
        """Get order from cache - cache is never populated!"""
        return self.cache.get(order_id)

    def cache_order(self, order_id: int, order: Dict) -> None:
        """Cache order - never called!"""
        self.cache[order_id] = order

    # Commented code - keep just in case
    # def process_bulk_orders(self, orders: List[Dict]) -> List[Dict]:
    #     """Process multiple orders - future feature."""
    #     results = []
    #     for order in orders:
    #         result = self.process_order(order)
    #         results.append(result)
    #     return results

    # TODO: Add international shipping support
    # TODO: Add gift wrapping options
    # TODO: Add order cancellation flow
    # TODO: Add order modification flow

    # Analytics - never used
    def track_analytics(self, event: str, data: Dict) -> None:
        """Track analytics events - never called!"""
        pass

    def get_order_analytics(self, order_id: int) -> Dict:
        """Get order analytics - never called!"""
        return {}


class OrderRepository:
    """Simple order repository."""

    def save(self, order: Dict) -> None:
        """Save order to database."""
        pass


class OrderStateMachine:
    """Order state machine - never used!"""

    def __init__(self, order: Dict):
        self.order = order

    def advance(self) -> None:
        """Advance order state."""
        pass


# Usage
processor = OrderProcessor()
order = {"id": 1, "status": "pending", "user_id": 123, "items": [], "total": 100}
processed = processor.process_order(order)
```

### Why It's Problematic

- **Multiple versions**: v1, v2, v3 implementations all present
- **Unused methods**: 20+ methods never called or only return empty values
- **Commented code**: Commented out code blocks "just in case"
- **TODO comments**: Features that may never be implemented
- **Dead classes**: OrderStateMachine created but never used
- **Version control ignored**: History exists in git, not in code

### How to Fix

**Refactoring Steps:**
1. Remove all old versions (v1, v2, v3)
2. Remove unused methods (notifications, invoices, shipping, etc.)
3. Remove commented out code blocks
4. Remove TODO comments unless they represent confirmed future work
5. Remove unused classes and utilities
6. Trust version control to preserve history

### GOOD Example

```python
from typing import Dict
from datetime import datetime


class OrderProcessor:
    """
    Clean order processing implementation.
    Only current, active code.
    """

    def __init__(self):
        self.repository = OrderRepository()

    def process_order(self, order: Dict) -> Dict:
        """
        Process order through simple state transition.
        """
        if order.get("status") == "pending":
            order["status"] = "processing"
        elif order.get("status") == "processing":
            order["status"] = "shipped"

        order["updated_at"] = datetime.now().isoformat()
        self.repository.save(order)

        return order


class OrderRepository:
    """Simple order repository."""

    def save(self, order: Dict) -> None:
        """Save order to database."""
        pass


# Usage
processor = OrderProcessor()
order = {"id": 1, "status": "pending", "user_id": 123, "items": [], "total": 100}
processed = processor.process_order(order)
```

**Key Changes:**
- Removed all dead code (300+ lines)
- No unused methods
- No old versions (v1, v2, v3)
- No commented code
- No TODO comments
- Clean, focused implementation
- Old versions safely stored in version control

---

## Anti-Pattern 7: Framework Overkill

### Description

Framework overkill occurs when developers use complex frameworks, libraries, or architectural patterns for simple problems. In Python, this includes using ORMs when SQL is sufficient, task queues for simple async operations, or microservices architectures for small applications.

### BAD Example

```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from celery import Celery
from redis import Redis
import logging

# Database setup with SQLAlchemy ORM
DATABASE_URL = "postgresql://user:pass@localhost/mydb"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis cache
redis_client = Redis(host="localhost", port=6379, db=0)

# Celery task queue
celery_app = Celery('tasks', broker='redis://localhost:6379/1')

# FastAPI app
app = FastAPI()

# Models
class User(BaseModel):
    id: Optional[int] = None
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    balance: float = Field(default=0.0, ge=0)

class Product(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1)
    price: float = Field(..., gt=0)
    stock: int = Field(default=0, ge=0)

class Order(BaseModel):
    id: Optional[int] = None
    user_id: int
    product_id: int
    quantity: int = Field(..., gt=0)
    total: float
    status: str = Field(default="pending")

# SQLAlchemy ORM models
class UserORM(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(255), unique=True, index=True)
    balance = Column(Float, default=0.0)

class ProductORM(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    price = Column(Float)
    stock = Column(Integer, default=0)

class OrderORM(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    product_id = Column(Integer, index=True)
    quantity = Column(Integer)
    total = Column(Float)
    status = Column(String(50))

# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Celery tasks
@celery_app.task
def send_order_confirmation_email(order_id: int):
    """Send order confirmation email - overkill for simple app."""
    logging.info(f"Sending confirmation email for order {order_id}")
    # Email sending logic

@celery_app.task
def update_inventory(product_id: int, quantity: int):
    """Update inventory in background - overkill for simple app."""
    logging.info(f"Updating inventory for product {product_id}")
    # Inventory update logic

@celery_app.task
def calculate_order_statistics():
    """Calculate order statistics - never used!"""
    logging.info("Calculating order statistics")
    # Statistics calculation

# Cache middleware
async def cache_middleware(request, call_next):
    """Redis caching middleware - overkill for simple app."""
    cache_key = f"{request.method}:{request.url.path}"

    # Try to get from cache
    cached = redis_client.get(cache_key)
    if cached:
        return cached

    # Process request
    response = await call_next(request)

    # Cache response
    redis_client.setex(cache_key, 300, response)

    return response

# API endpoints
@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user with cache."""
    cache_key = f"user:{user_id}"
    cached = redis_client.get(cache_key)

    if cached:
        return User.parse_raw(cached)

    user = db.query(UserORM).filter(UserORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_dict = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "balance": user.balance
    }
    redis_client.setex(cache_key, 300, json.dumps(user_dict))

    return User(**user_dict)

@app.post("/users", response_model=User)
async def create_user(user: User, db: Session = Depends(get_db)):
    """Create user."""
    # Invalidate cache
    redis_client.delete("users:all")

    db_user = UserORM(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return User(**user.dict())

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get product."""
    product = db.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return Product(
        id=product.id,
        name=product.name,
        price=product.price,
        stock=product.stock
    )

@app.post("/products", response_model=Product)
async def create_product(product: Product, db: Session = Depends(get_db)):
    """Create product."""
    db_product = ProductORM(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return Product(**product.dict())

@app.post("/orders", response_model=Order)
async def create_order(order: Order, db: Session = Depends(get_db)):
    """Create order with background tasks."""
    # Check user exists
    user = db.query(UserORM).filter(UserORM.id == order.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check product exists
    product = db.query(ProductORM).filter(ProductORM.id == order.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check stock
    if product.stock < order.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    # Create order
    db_order = OrderORM(**order.dict())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    # Trigger background tasks (overkill!)
    send_order_confirmation_email.delay(db_order.id)
    update_inventory.delay(order.product_id, order.quantity)

    # Invalidate cache
    redis_client.delete("orders:all")

    return Order(**order.dict())


# Additional microservice architecture suggestions - NEVER USED!
# - user_service/app.py
# - product_service/app.py
# - order_service/app.py
# - notification_service/app.py
# - inventory_service/app.py
# - analytics_service/app.py
# Each with Docker, Kubernetes, service discovery, etc.
```

### Why It's Problematic

- **Framework overkill**: FastAPI + SQLAlchemy ORM + Celery + Redis for simple CRUD
- **ORM overhead**: SQLAlchemy ORM when simple SQL would suffice
- **Task queue**: Celery for tasks that don't need async processing
- **Cache layer**: Redis caching for low-traffic application
- **Complex deployment**: Multiple services and dependencies for simple app
- **Unused features**: Background tasks, caching, and complex query patterns never needed

### How to Fix

**Refactoring Steps:**
1. Remove Celery task queue (tasks don't need async processing)
2. Remove Redis cache (low traffic, not needed)
3. Simplify database to simple functions or simple ORM
4. Keep only essential API endpoints
5. Remove microservice architecture comments
6. Start simple, add complexity when needed

### GOOD Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from contextlib import contextmanager

# Simple SQLite database
DATABASE = "myapp.db"

@contextmanager
def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

# Initialize database
def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                balance REAL DEFAULT 0.0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """)

# FastAPI app
app = FastAPI()

# Models
class User(BaseModel):
    id: Optional[int] = None
    username: str
    email: str
    balance: float = 0.0

class Product(BaseModel):
    id: Optional[int] = None
    name: str
    price: float
    stock: int = 0

class Order(BaseModel):
    id: Optional[int] = None
    user_id: int
    product_id: int
    quantity: int
    total: float
    status: str = "pending"

# API endpoints
@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    """Get user."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        return User(**dict(row))

@app.post("/users", response_model=User)
async def create_user(user: User):
    """Create user."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, email, balance) VALUES (?, ?, ?)",
            (user.username, user.email, user.balance)
        )
        user_id = cursor.lastrowid

        return User(id=user_id, **user.dict())

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int):
    """Get product."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Product not found")

        return Product(**dict(row))

@app.post("/products", response_model=Product)
async def create_product(product: Product):
    """Create product."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
            (product.name, product.price, product.stock)
        )
        product_id = cursor.lastrowid

        return Product(id=product_id, **product.dict())

@app.post("/orders", response_model=Order)
async def create_order(order: Order):
    """Create order."""
    with get_db() as conn:
        # Check user exists
        cursor = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (order.user_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        # Check product exists and has stock
        cursor = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (order.product_id,)
        )
        product_row = cursor.fetchone()

        if not product_row:
            raise HTTPException(status_code=404, detail="Product not found")

        if product_row["stock"] < order.quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")

        # Create order
        cursor = conn.execute(
            "INSERT INTO orders (user_id, product_id, quantity, total, status) VALUES (?, ?, ?, ?, ?)",
            (order.user_id, order.product_id, order.quantity, order.total, order.status)
        )
        order_id = cursor.lastrowid

        # Update stock
        conn.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (order.quantity, order.product_id)
        )

        return Order(id=order_id, **order.dict())

# Initialize database on startup
init_db()
```

**Key Changes:**
- Removed Celery task queue (not needed)
- Removed Redis cache (low traffic)
- Simplified to SQLite with direct SQL
- Removed ORM abstraction layer
- Simple, direct API implementation
- Easy to deploy and maintain
- Can add features when actually needed

---

## Anti-Pattern 8: Configuration Overload

### Description

Configuration overload occurs when developers create extensive configuration systems with dozens of options for features that are never used or always left at default values. In Python, this manifests as complex config files, environment variable mappings, or configuration classes with many unused options.

### BAD Example

```python
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import os
import json
import yaml


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DatabaseType(Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    type: DatabaseType = DatabaseType.POSTGRESQL
    host: str = "localhost"
    port: int = 5432
    database: str = "myapp"
    username: str = "postgres"
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False
    ssl_mode: str = "prefer"
    connect_timeout: int = 10
    statement_timeout: int = 30000
    query_timeout: int = 60000


@dataclass
class CacheConfig:
    """Cache configuration - NEVER USED!"""
    type: str = "redis"
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    default_ttl: int = 3600
    max_connections: int = 50
    connection_timeout: int = 5
    key_prefix: str = "myapp"
    serialize: bool = True
    compression: bool = False


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: LogLevel = LogLevel.INFO
    format: str = "text"
    file: Optional[str] = None
    max_size: int = 10485760
    backup_count: int = 5
    rotation: str = "daily"
    compression: str = "gzip"
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    enable_console: bool = True
    enable_file: bool = False
    enable_syslog: bool = False  # Never used!
    syslog_address: str = "/dev/log"  # Never used!


@dataclass
class APIConfig:
    """API configuration."""
    host: str = "0.0.0.0"
    port: int = 3000
    workers: int = 4
    timeout: int = 30
    max_request_size: int = 10485760
    cors_enabled: bool = True
    cors_origins: str = "*"
    cors_methods: str = "GET,POST,PUT,DELETE,OPTIONS"
    cors_headers: str = "Content-Type,Authorization"
    cors_max_age: int = 3600
    enable_compression: bool = True
    compression_level: int = 6
    enable_trust_proxy: bool = False  # Never used!
    proxy_ip_header: str = "X-Forwarded-For"  # Never used!


@dataclass
class SecurityConfig:
    """Security configuration - NEVER USED!"""
    secret_key: str = "change-me"
    encryption_enabled: bool = True
    encryption_algorithm: str = "AES256"
    jwt_enabled: bool = False  # Never used!
    jwt_secret: str = ""  # Never used!
    jwt_expiry: int = 3600  # Never used!
    rate_limiting_enabled: bool = False  # Never used!
    rate_limit: int = 100  # Never used!
    rate_limit_period: int = 60  # Never used!


@dataclass
class PerformanceConfig:
    """Performance configuration - NEVER USED!"""
    enable_cache: bool = False
    enable_compression: bool = True
    minify_json: bool = False  # Never used!
    gzip_level: int = 6
    brotli_enabled: bool = False  # Never used!
    brotli_level: int = 4  # Never used!
    enable_connection_pooling: bool = True
    keep_alive_timeout: int = 75
    graceful_shutdown_timeout: int = 30


@dataclass
class FeatureFlags:
    """Feature flags - NEVER USED!"""
    enable_registration: bool = True
    enable_login: bool = True
    enable_email_verification: bool = False  # Never used!
    enable_two_factor: bool = False  # Never used!
    enable_social_login: bool = False  # Never used!
    enable_analytics: bool = False  # Never used!
    enable_notifications: bool = False  # Never used!
    beta_features_enabled: bool = False  # Never used!


@dataclass
class AnalyticsConfig:
    """Analytics configuration - NEVER USED!"""
    provider: str = "google"
    tracking_id: str = ""
    enable_anonymous_tracking: bool = True
    enable_user_tracking: bool = False  # Never used!
    sampling_rate: float = 1.0
    flush_interval: int = 60
    batch_size: int = 20


@dataclass
class NotificationConfig:
    """Notification configuration - NEVER USED!"""
    email_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    sms_enabled: bool = False  # Never used!
    sms_provider: str = ""  # Never used!
    push_enabled: bool = False  # Never used!
    push_provider: str = ""  # Never used!


@dataclass
class Config:
    """
    Master configuration class with all sections.
    Over 100 configuration options for simple app!
    """
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    api: APIConfig = field(default_factory=APIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)

    @classmethod
    def from_file(cls, path: str) -> "Config":
        """Load configuration from file."""
        if path.endswith(".json"):
            with open(path) as f:
                data = json.load(f)
        elif path.endswith(".yaml") or path.endswith(".yml"):
            with open(path) as f:
                data = yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported config format: {path}")

        return cls._from_dict(data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config = cls()

        # Database config from env
        config.database.host = os.getenv("DB_HOST", config.database.host)
        config.database.port = int(os.getenv("DB_PORT", str(config.database.port)))
        config.database.database = os.getenv("DB_NAME", config.database.database)
        config.database.username = os.getenv("DB_USER", config.database.username)
        config.database.password = os.getenv("DB_PASSWORD", config.database.password)

        # API config from env
        config.api.host = os.getenv("API_HOST", config.api.host)
        config.api.port = int(os.getenv("API_PORT", str(config.api.port)))
        config.api.workers = int(os.getenv("API_WORKERS", str(config.api.workers)))

        # Logging config from env
        logging_level = os.getenv("LOG_LEVEL", config.logging.level.value)
        config.logging.level = LogLevel(logging_level)

        # Cache config from env - never used!
        config.cache.host = os.getenv("CACHE_HOST", config.cache.host)
        config.cache.port = int(os.getenv("CACHE_PORT", str(config.cache.port)))

        # Security config from env - never used!
        config.security.secret_key = os.getenv("SECRET_KEY", config.security.secret_key)

        # And 50+ more env variable mappings...

        return config

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        config = cls()

        if "database" in data:
            config.database = DatabaseConfig(**data["database"])
        if "cache" in data:
            config.cache = CacheConfig(**data["cache"])
        if "logging" in data:
            config.logging = LoggingConfig(**data["logging"])
        if "api" in data:
            config.api = APIConfig(**data["api"])
        if "security" in data:
            config.security = SecurityConfig(**data["security"])
        if "performance" in data:
            config.performance = PerformanceConfig(**data["performance"])
        if "features" in data:
            config.features = FeatureFlags(**data["features"])
        if "analytics" in data:
            config.analytics = AnalyticsConfig(**data["analytics"])
        if "notifications" in data:
            config.notifications = NotificationConfig(**data["notifications"])

        return config

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "database": self.database.__dict__,
            "cache": self.cache.__dict__,
            "logging": self.logging.__dict__,
            "api": self.api.__dict__,
            "security": self.security.__dict__,
            "performance": self.performance.__dict__,
            "features": self.features.__dict__,
            "analytics": self.analytics.__dict__,
            "notifications": self.notifications.__dict__,
        }

    def validate(self) -> bool:
        """Validate configuration."""
        # Validate database
        if not self.database.host:
            raise ValueError("Database host is required")

        # Validate API
        if not 1 <= self.api.port <= 65535:
            raise ValueError("Invalid API port")

        # Validate security - never used!
        if self.security.encryption_enabled and not self.security.secret_key:
            raise ValueError("Secret key is required for encryption")

        # And 50+ more validations...

        return True


# config.yaml with 100+ lines of configuration
# Most never changed from defaults
"""
database:
  type: postgresql
  host: localhost
  port: 5432
  database: myapp
  username: postgres
  password: ""
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30
  pool_recycle: 3600
  echo: false
  ssl_mode: prefer
  connect_timeout: 10
  statement_timeout: 30000
  query_timeout: 60000

cache:
  type: redis
  host: localhost
  port: 6379
  db: 0
  password: ""
  default_ttl: 3600
  max_connections: 50
  connection_timeout: 5
  key_prefix: myapp
  serialize: true
  compression: false

logging:
  level: info
  format: text
  file: null
  max_size: 10485760
  backup_count: 5
  rotation: daily
  compression: gzip

api:
  host: 0.0.0.0
  port: 3000
  workers: 4
  timeout: 30
  max_request_size: 10485760
  cors_enabled: true
  cors_origins: "*"
  cors_methods: "GET,POST,PUT,DELETE,OPTIONS"
  cors_headers: "Content-Type,Authorization"

security:
  secret_key: "change-me"
  encryption_enabled: true
  encryption_algorithm: "AES256"

performance:
  enable_cache: false
  enable_compression: true
  gzip_level: 6

features:
  enable_registration: true
  enable_login: true

analytics:
  provider: google
  tracking_id: ""
  enable_anonymous_tracking: true
  sampling_rate: 1.0

notifications:
  email_enabled: false
  smtp_host: localhost
  smtp_port: 587
"""

# Usage
config = Config.from_env()
# or
config = Config.from_file("config.yaml")
```

### Why It's Problematic

- **Configuration bloat**: 100+ configuration options for simple app
- **Unused sections**: Cache, security, performance, features, analytics, notifications never used
- **Complex loading**: Multiple config formats and env variable mappings
- **High cognitive load**: Developers must understand all options
- **Most values never changed**: 90% of options stay at defaults
- **Testing burden**: All config paths must be tested

### How to Fix

**Refactoring Steps:**
1. Identify which configuration values are actually used
2. Remove unused configuration sections (cache, security, performance, etc.)
3. Simplify to only essential values (database URL, API port, log level)
4. Use environment variables directly
5. Keep configuration simple and focused

### GOOD Example

```python
import os
from dataclasses import dataclass


@dataclass
class Config:
    """
    Minimal configuration with only what's needed.
    """
    database_url: str
    api_port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql://localhost:5432/myapp"
            ),
            api_port=int(os.getenv("PORT", "3000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Usage
config = Config.from_env()
print(f"Database: {config.database_url}")
print(f"API Port: {config.api_port}")
print(f"Log Level: {config.log_level}")
```

**Key Changes:**
- Removed all unused configuration sections (cache, security, performance, etc.)
- Simplified from 100+ options to 3 essential values
- Removed complex config file loading
- Direct environment variable configuration
- Simple dataclass
- Easy to understand and extend

---

## Anti-Pattern 9: Crystal Ball Syndrome

### Description

Crystal ball syndrome occurs when developers try to predict future requirements and implement them now. In Python, this manifests as building "extensible" systems, adding configuration options for potential scenarios, or creating hooks/callbacks that might be used someday.

### BAD Example

```python
from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class PluginType(Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    LOGGING = "logging"
    CACHING = "caching"  # Never used!
    VALIDATION = "validation"  # Never used!
    TRANSFORMATION = "transformation"  # Never used!


class Event(ABC):
    """Abstract base class for events."""

    @abstractmethod
    def get_event_type(self) -> str:
        pass

    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        pass


class UserEvent(Event):
    """User-related events."""

    def __init__(self, event_type: str, user_id: int, data: Dict[str, Any]):
        self.event_type = event_type
        self.user_id = user_id
        self.data = data

    def get_event_type(self) -> str:
        return self.event_type

    def get_data(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            **self.data
        }


class SystemEvent(Event):
    """System-related events."""

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data

    def get_event_type(self) -> str:
        return self.event_type

    def get_data(self) -> Dict[str, Any]:
        return self.data


class Plugin(ABC):
    """Abstract base class for plugins."""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin."""
        pass

    @abstractmethod
    def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Handle an event."""
        pass

    def on_enable(self) -> None:
        """Called when plugin is enabled."""
        pass

    def on_disable(self) -> None:
        """Called when plugin is disabled."""
        pass

    def get_dependencies(self) -> List[str]:
        """Return list of plugin dependencies."""
        return []

    def get_compatibility(self) -> str:
        """Return plugin version compatibility."""
        return "1.0.0"


class PluginManager:
    """
    Extensible plugin system for future features.
    Over-engineered for current needs.
    """

    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.event_handlers: Dict[str, List[Plugin]] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        self.middleware: List[Callable] = []
        self.filters: List[Callable] = []
        self.config: Dict[str, Any] = {}

    def register_plugin(self, plugin: Plugin, config: Optional[Dict] = None) -> None:
        """Register a new plugin."""
        plugin.initialize(config or {})
        self.plugins[plugin.name] = plugin

        # Register event handlers
        if isinstance(plugin, EventHandlingPlugin):
            for event_type in plugin.get_supported_events():
                if event_type not in self.event_handlers:
                    self.event_handlers[event_type] = []
                self.event_handlers[event_type].append(plugin)

    def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.on_disable()
            del self.plugins[plugin_name]

            # Remove event handlers
            for event_handlers in self.event_handlers.values():
                if plugin in event_handlers:
                    event_handlers.remove(plugin)

    def enable_plugin(self, plugin_name: str) -> None:
        """Enable a plugin."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.enabled = True
            plugin.on_enable()

    def disable_plugin(self, plugin_name: str) -> None:
        """Disable a plugin."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.enabled = False
            plugin.on_disable()

    def add_hook(self, hook_name: str, callback: Callable) -> None:
        """Add a hook callback."""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)

    def remove_hook(self, hook_name: str, callback: Callable) -> None:
        """Remove a hook callback."""
        if hook_name in self.hooks and callback in self.hooks[hook_name]:
            self.hooks[hook_name].remove(callback)

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware."""
        self.middleware.append(middleware)

    def add_filter(self, filter_func: Callable) -> None:
        """Add a filter."""
        self.filters.append(filter_func)

    def emit_event(self, event: Event) -> Dict[str, Any]:
        """Emit an event to all interested plugins."""
        event_type = event.get_event_type()
        results = []

        # Run hooks before event
        if "before_emit" in self.hooks:
            for hook in self.hooks["before_emit"]:
                hook(event)

        # Run middleware
        modified_event = event
        for middleware in self.middleware:
            modified_event = middleware(modified_event)

        # Run filters
        for filter_func in self.filters:
            if not filter_func(modified_event):
                return {"filtered": True}

        # Handle event
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                if handler.enabled:
                    result = handler.handle_event(modified_event)
                    if result:
                        results.append(result)

        # Run hooks after event
        if "after_emit" in self.hooks:
            for hook in self.hooks["after_emit"]:
                hook(modified_event, results)

        return {"results": results}

    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self.plugins.get(plugin_name)

    def list_plugins(self) -> List[str]:
        """List all registered plugins."""
        return list(self.plugins.keys())

    def get_plugin_status(self, plugin_name: str) -> Dict[str, Any]:
        """Get plugin status."""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            return {"exists": False}

        return {
            "exists": True,
            "enabled": plugin.enabled,
            "dependencies": plugin.get_dependencies(),
            "compatibility": plugin.get_compatibility()
        }


class EventHandlingPlugin(Plugin):
    """Plugin that can handle events."""

    @abstractmethod
    def get_supported_events(self) -> List[str]:
        """Return list of event types this plugin handles."""
        pass


class AuthenticationPlugin(EventHandlingPlugin):
    """Authentication plugin - only one actually used."""

    def __init__(self):
        super().__init__("authentication")

    def initialize(self, config: Dict[str, Any]) -> None:
        self.secret_key = config.get("secret_key", "default")

    def get_supported_events(self) -> List[str]:
        return ["user.login", "user.logout", "user.register"]

    def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        event_type = event.get_event_type()
        data = event.get_data()

        if event_type == "user.login":
            return self._handle_login(data)
        elif event_type == "user.logout":
            return self._handle_logout(data)
        elif event_type == "user.register":
            return self._handle_register(data)

        return None

    def _handle_login(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user login."""
        print(f"User {data.get('user_id')} logged in")
        return {"success": True}

    def _handle_logout(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user logout."""
        print(f"User {data.get('user_id')} logged out")
        return {"success": True}

    def _handle_register(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user registration."""
        print(f"User {data.get('username')} registered")
        return {"success": True}


class LoggingPlugin(EventHandlingPlugin):
    """Logging plugin - actually used."""

    def __init__(self):
        super().__init__("logging")

    def initialize(self, config: Dict[str, Any]) -> None:
        self.log_level = config.get("log_level", "INFO")

    def get_supported_events(self) -> List[str]:
        return ["*"]  # Log all events

    def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        print(f"[LOG] {event.get_event_type()}: {event.get_data()}")
        return None


class CachingPlugin(EventHandlingPlugin):
    """Caching plugin - NEVER USED!"""

    def __init__(self):
        super().__init__("caching")

    def initialize(self, config: Dict[str, Any]) -> None:
        self.cache = {}

    def get_supported_events(self) -> List[str]:
        return ["data.fetch", "data.update"]

    def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Handle caching events."""
        return None


class ValidationPlugin(EventHandlingPlugin):
    """Validation plugin - NEVER USED!"""

    def __init__(self):
        super().__init__("validation")

    def initialize(self, config: Dict[str, Any]) -> None:
        self.rules = config.get("rules", [])

    def get_supported_events(self) -> List[str]:
        return ["*"]

    def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Validate events."""
        return {"valid": True}


class TransformationPlugin(EventHandlingPlugin):
    """Transformation plugin - NEVER USED!"""

    def __init__(self):
        super().__init__("transformation")

    def initialize(self, config: Dict[str, Any]) -> None:
        self.transformers = config.get("transformers", [])

    def get_supported_events(self) -> List[str]:
        return ["data.fetch", "data.save"]

    def handle_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Transform data."""
        return None


# Usage
plugin_manager = PluginManager()
plugin_manager.register_plugin(AuthenticationPlugin())
plugin_manager.register_plugin(LoggingPlugin())

# Future plugins that might never be needed:
# plugin_manager.register_plugin(CachingPlugin())
# plugin_manager.register_plugin(ValidationPlugin())
# plugin_manager.register_plugin(TransformationPlugin())

# Emit event
event = UserEvent("user.login", user_id=123, data={"timestamp": "2024-01-01"})
plugin_manager.emit_event(event)
```

### Why It's Problematic

- **Future-proofing**: Built plugin system for hypothetical future plugins
- **Over-abstraction**: Abstract base classes for only 2 actual plugins
- **Unused features**: Middleware, filters, and hooks never used
- **Complex system**: Plugin manager with registration, enable/disable, hooks for simple needs
- **Empty implementations**: Caching, validation, transformation plugins with placeholder code
- **High cognitive load**: Developers must understand entire plugin system

### How to Fix

**Refactoring Steps:**
1. Identify which functionality is actually needed (authentication, logging)
2. Remove plugin system and abstract base classes
3. Implement direct authentication and logging functionality
4. Remove middleware, filters, and hooks
5. Add plugins only when actually needed

### GOOD Example

```python
from typing import Dict, Any


def log_event(event_type: str, data: Dict[str, Any]) -> None:
    """
    Log events.
    Only what's actually needed.
    """
    print(f"[LOG] {event_type}: {data}")


def handle_authentication(event_type: str, user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle authentication events.
    Only what's actually needed.
    """
    if event_type == "user.login":
        print(f"User {user_id} logged in")
        return {"success": True}
    elif event_type == "user.logout":
        print(f"User {user_id} logged out")
        return {"success": True}
    elif event_type == "user.register":
        username = data.get("username")
        print(f"User {username} registered")
        return {"success": True}

    return {"success": False}


# Usage
log_event("user.login", {"user_id": 123, "timestamp": "2024-01-01"})
handle_authentication("user.login", 123, {"timestamp": "2024-01-01"})
```

**Key Changes:**
- Removed entire plugin system (300+ lines)
- Removed abstract base classes
- Removed unused plugins (caching, validation, transformation)
- Removed middleware, filters, and hooks
- Simple, direct functions
- Easy to understand and modify
- Can add plugin system if/when needed

---

## Anti-Pattern 10: Premature Optimization

### Description

Premature optimization occurs when developers add performance optimizations, caching, or complex data structures before there's an actual performance problem. In Python, this often manifests as implementing memoization, object pooling, or caching for operations that are fast enough in their simple form.

### BAD Example

```python
import functools
import hashlib
import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
import time
import threading


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    value: Any
    timestamp: float
    access_count: int = 0
    ttl: Optional[float] = None


class LRUCache:
    """LRU cache implementation - overkill for simple caching."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                entry.access_count += 1
                self.cache.move_to_end(key)
                self.hits += 1

                # Check TTL
                if entry.ttl and time.time() - entry.timestamp > entry.ttl:
                    del self.cache[key]
                    self.misses += 1
                    return None

                return entry.value
            else:
                self.misses += 1
                return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    self.cache.popitem(last=False)

            self.cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=ttl
            )

    def clear(self) -> None:
        """Clear cache."""
        with self.lock:
            self.cache.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self.lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self.cache),
                "hit_rate": self.hits / (self.hits + self.misses) if self.hits + self.misses > 0 else 0
            }


class MemoizedCalculator:
    """
    Calculator with memoization and caching.
    Overkill for simple calculations.
    """

    def __init__(self):
        self.fib_cache: Dict[int, int] = {}
        self.factorial_cache: Dict[int, int] = {}
        self.general_cache: LRUCache = LRUCache(max_size=1000)
        self.cache_stats = {"fib": 0, "factorial": 0, "general": 0}

    def fibonacci(self, n: int) -> int:
        """Calculate Fibonacci number with memoization."""
        cache_key = f"fib_{n}"

        # Check cache
        if n in self.fib_cache:
            self.cache_stats["fib"] += 1
            return self.fib_cache[n]

        # Calculate
        if n <= 1:
            result = n
        else:
            result = self.fibonacci(n - 1) + self.fibonacci(n - 2)

        # Cache result
        self.fib_cache[n] = result
        return result

    def factorial(self, n: int) -> int:
        """Calculate factorial with memoization."""
        cache_key = f"fact_{n}"

        # Check cache
        if n in self.factorial_cache:
            self.cache_stats["factorial"] += 1
            return self.factorial_cache[n]

        # Calculate
        if n <= 1:
            result = 1
        else:
            result = n * self.factorial(n - 1)

        # Cache result
        self.factorial_cache[n] = result
        return result

    def calculate(self, operation: str, *args) -> Any:
        """Calculate with caching."""
        cache_key = self._generate_cache_key(operation, args)

        # Check cache
        cached = self.general_cache.get(cache_key)
        if cached is not None:
            self.cache_stats["general"] += 1
            return cached

        # Calculate
        if operation == "add":
            result = sum(args)
        elif operation == "multiply":
            result = 1
            for arg in args:
                result *= arg
        elif operation == "power":
            result = args[0] ** args[1]
        else:
            raise ValueError(f"Unknown operation: {operation}")

        # Cache result
        self.general_cache.set(cache_key, result, ttl=300)
        return result

    def _generate_cache_key(self, operation: str, args: tuple) -> str:
        """Generate cache key from operation and args."""
        data = {"operation": operation, "args": args}
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            **self.cache_stats,
            "general_cache": self.general_cache.get_stats(),
            "fib_cache_size": len(self.fib_cache),
            "factorial_cache_size": len(self.factorial_cache)
        }

    def clear_caches(self) -> None:
        """Clear all caches."""
        self.fib_cache.clear()
        self.factorial_cache.clear()
        self.general_cache.clear()


class ObjectPool:
    """
    Generic object pool for resource management.
    Overkill for most use cases.
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        max_size: int = 10,
        reset_func: Optional[Callable[[Any], None]] = None
    ):
        self.factory = factory
        self.max_size = max_size
        self.reset_func = reset_func
        self.pool: List[Any] = []
        self.lock = threading.Lock()
        self.created_count = 0
        self.reused_count = 0

    def acquire(self) -> Any:
        """Acquire an object from the pool."""
        with self.lock:
            if self.pool:
                obj = self.pool.pop()
                self.reused_count += 1
                return obj
            else:
                obj = self.factory()
                self.created_count += 1
                return obj

    def release(self, obj: Any) -> None:
        """Release an object back to the pool."""
        with self.lock:
            if len(self.pool) < self.max_size:
                if self.reset_func:
                    self.reset_func(obj)
                self.pool.append(obj)

    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        with self.lock:
            return {
                "pool_size": len(self.pool),
                "created_count": self.created_count,
                "reused_count": self.reused_count,
                "reuse_rate": self.reused_count / self.created_count if self.created_count > 0 else 0
            }


class OptimizedDataProcessor:
    """
    Data processor with caching and optimization.
    Overkill for simple processing.
    """

    def __init__(self):
        self.cache = LRUCache(max_size=500)
        self.batch_cache: Dict[str, List[Any]] = {}
        self.result_cache: LRUCache = LRUCache(max_size=200)
        self.optimization_enabled = True

    def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single item with caching."""
        cache_key = self._generate_item_cache_key(item)

        # Check cache
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Process
        result = self._actually_process_item(item)

        # Cache result
        self.cache.set(cache_key, result, ttl=600)

        return result

    def process_batch(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process batch of items with batch caching."""
        batch_key = self._generate_batch_cache_key(items)

        # Check batch cache
        if batch_key in self.batch_cache:
            return self.batch_cache[batch_key]

        # Process items
        results = [self.process_item(item) for item in items]

        # Cache batch result
        self.batch_cache[batch_key] = results

        return results

    def _actually_process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Actually process item (without caching)."""
        return {
            "id": item.get("id"),
            "processed": True,
            "value": item.get("value", 0) * 2
        }

    def _generate_item_cache_key(self, item: Dict[str, Any]) -> str:
        """Generate cache key for item."""
        item_str = json.dumps(item, sort_keys=True)
        return hashlib.md5(item_str.encode()).hexdigest()

    def _generate_batch_cache_key(self, items: List[Dict[str, Any]]) -> str:
        """Generate cache key for batch."""
        batch_str = json.dumps(items, sort_keys=True)
        return hashlib.md5(batch_str.encode()).hexdigest()

    def aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate results with caching."""
        cache_key = f"aggregate_{len(results)}_{hash(tuple(r.get('id') for r in results))}"

        # Check cache
        cached = self.result_cache.get(cache_key)
        if cached is not None:
            return cached

        # Aggregate
        aggregated = {
            "count": len(results),
            "sum": sum(r.get("value", 0) for r in results),
            "avg": sum(r.get("value", 0) for r in results) / len(results)
        }

        # Cache result
        self.result_cache.set(cache_key, aggregated, ttl=900)

        return aggregated

    def clear_all_caches(self) -> None:
        """Clear all caches."""
        self.cache.clear()
        self.batch_cache.clear()
        self.result_cache.clear()

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        return {
            "item_cache": self.cache.get_stats(),
            "batch_cache_size": len(self.batch_cache),
            "result_cache": self.result_cache.get_stats(),
            "optimization_enabled": self.optimization_enabled
        }


# Usage
calculator = MemoizedCalculator()
print(calculator.fibonacci(10))
print(calculator.factorial(5))
print(calculator.calculate("add", 1, 2, 3))

processor = OptimizedDataProcessor()
result = processor.process_item({"id": 1, "value": 10})
print(result)

stats = calculator.get_cache_stats()
print(f"Cache stats: {stats}")
```

### Why It's Problematic

- **Unnecessary caching**: LRU cache, memoization, and result caching for simple operations
- **Complex implementation**: Thread-safe caches, TTL, and statistics for simple needs
- **Over-optimization**: Object pooling without measured performance needs
- **High complexity**: Multiple cache layers and optimization strategies
- **No performance measurements**: Optimizations added without profiling
- **Maintenance burden**: All caching logic must be maintained

### How to Fix

**Refactoring Steps:**
1. Remove all caching and memoization infrastructure
2. Implement simple, direct calculations
3. Remove object pooling (not needed for most cases)
4. Remove batch and result caching
5. Add optimizations only if profiling shows actual performance issues

### GOOD Example

```python
from typing import Any, Dict, List


def fibonacci(n: int) -> int:
    """Calculate Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def factorial(n: int) -> int:
    """Calculate factorial."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def calculate(operation: str, *args) -> Any:
    """Calculate result."""
    if operation == "add":
        return sum(args)
    elif operation == "multiply":
        result = 1
        for arg in args:
            result *= arg
        return result
    elif operation == "power":
        return args[0] ** args[1]
    else:
        raise ValueError(f"Unknown operation: {operation}")


def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single item."""
    return {
        "id": item.get("id"),
        "processed": True,
        "value": item.get("value", 0) * 2
    }


def process_batch(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process batch of items."""
    return [process_item(item) for item in items]


def aggregate_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results."""
    return {
        "count": len(results),
        "sum": sum(r.get("value", 0) for r in results),
        "avg": sum(r.get("value", 0) for r in results) / len(results)
    }


# Usage
print(fibonacci(10))
print(factorial(5))
print(calculate("add", 1, 2, 3))

result = process_item({"id": 1, "value": 10})
print(result)
```

**Key Changes:**
- Removed all caching and memoization (LRU cache, memoization, result cache)
- Removed object pooling
- Removed complex cache statistics
- Simplified from 300+ lines to 60 lines
- Direct, simple implementations
- Easy to understand and test
- Can add optimizations if profiling shows they're needed

---

## Detection Checklist

Use this checklist to identify YAGNI violations in Python code:

### Code Review Questions

- [ ] Does this code implement features that aren't being used?
- [ ] Are there commented out code blocks or TODO comments for future features?
- [ ] Is there a complex configuration system for simple functionality?
- [ ] Are there unused methods, functions, or classes?
- [ ] Is there caching or optimization without performance measurements?
- [ ] Are there abstract base classes for single implementations?
- [ ] Is there over-generalization for specific use cases?
- [ ] Are there skeleton implementations with "not implemented" or placeholder code?

### Automated Detection

- **Unused code detection**: Use `flake8` with `F841` (unused variable), `F811` (redefinition)
- **Import analysis**: Use `autoflake` or `flake8` with `F401` (unused imports)
- **Code complexity**: Use `radon` to detect high cyclomatic complexity
- **Dead code analysis**: Use `vulture` to find unused code
- **Linting**: Use `pylint` with comprehensive rules
- **Type checking**: Use `mypy` to identify unused variables and imports

### Manual Inspection Techniques

1. **Future-Tense Test**: Read code comments. If you see "future", "later", "eventually", or "maybe", it's likely a YAGNI violation
2. **Import Analysis**: Look at imports. If a file imports complex utilities but only uses basic features, it's over-engineered
3. **Method Count**: Classes with 10+ methods often have dead code or unnecessary features
4. **ABC Count**: Abstract base classes with only one implementation are unnecessary
5. **Configuration Count**: Configuration objects with 8+ options suggest gold plating
6. **Cache Usage**: Caching without performance measurements is likely premature optimization

### Common Symptoms

- **"Just in case" comments**: Comments explaining code is for future use
- **Skeleton implementations**: Methods that log "not implemented" or pass without returning values
- **Complex config objects**: Many configuration options that are never changed
- **Abstract base classes**: ABCs with only one concrete implementation
- **Multiple versions**: v1, v2, v3 implementations all present in same file
- **Commented code blocks**: Large sections of code that's disabled
- **TODO comments**: Multiple TODOs for features not in current scope

---

## Language-Specific Notes

### Idioms and Patterns

**EAFP vs LBYL**:
- **EAFP** (Easier to Ask Forgiveness than Permission) is more Pythonic: Try to do something and catch exceptions
- **LBYL** (Look Before You Leap) is less Pythonic: Check conditions beforehand
- EAFP helps avoid over-defensive programming and unnecessary checks

```python
# EAFP (Pythonic)
try:
    value = data['key']
except KeyError:
    value = default

# LBYL (less Pythonic, can lead to over-checking)
if 'key' in data:
    value = data['key']
else:
    value = default
```

**Duck Typing**:
- Python's dynamic typing enables simpler code without premature interface definitions
- Don't create abstract base classes until multiple implementations exist
- Use duck typing: if it walks like a duck and quacks like a duck, it's a duck

```python
# Good - duck typing
def process(data):
    return data.process()

# Bad - premature interface
class Processor(ABC):
    @abstractmethod
    def process(self):
        pass

class MyProcessor(Processor):
    def process(self):
        return "done"
```

**Context Managers**:
- Use `with` statements for resource management instead of building complex wrappers
- Python's contextlib provides tools for creating context managers

```python
# Good - using context manager
with open('file.txt') as f:
    data = f.read()

# Bad - building complex wrapper
class FileWrapper:
    def __init__(self, path):
        self.f = open(path)
    def read(self):
        return self.f.read()
    def close(self):
        self.f.close()
```

**Simple Data Structures**:
- Prefer dicts, lists, tuples, and dataclasses over custom classes until behavior is needed
- Use `namedtuple` or `dataclass` for simple data containers
- Don't create classes for data structures that don't need methods

```python
# Good - simple dataclass
@dataclass
class User:
    id: int
    name: str
    email: str

# Bad - over-engineered class
class User:
    def __init__(self, id, name, email):
        self._id = id
        self._name = name
        self._email = email

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def email(self):
        return self._email
```

### Language Features that Help

**Dynamic typing**:
- Allows deferring type abstractions until needed
- Enables duck typing without explicit interfaces
- Reduces need for generic code

**List/dict comprehensions**:
- Simple, powerful data transformations without helper functions
- More readable than map/filter chains
- Built-in and optimized

```python
# Good - comprehension
squares = [x**2 for x in range(10)]

# Bad - unnecessary helper function
def square_list(numbers):
    return [x**2 for x in numbers]

squares = square_list(range(10))
```

**Decorators**:
- Can add functionality (logging, caching) without changing implementation
- Built-in decorators like `@property`, `@staticmethod`, `@classmethod`
- Create custom decorators when you need cross-cutting concerns

**First-class functions**:
- Enable passing functions directly, avoiding premature abstraction
- Higher-order functions like `map`, `filter`, `reduce`
- Lambda functions for simple operations

**Standard Library**:
- Rich standard library reduces need for external dependencies
- Use built-in modules before adding dependencies
- `itertools`, `functools`, `collections` provide powerful utilities

### Language Features that Hinder

**Abstract base classes (ABC)**:
- Easy to overuse creating interfaces for single implementations
- Only use when you need to enforce an interface across multiple implementations
- Prefer duck typing in most cases

**Type hints**:
- Can lead to over-engineering when every function has complex type annotations
- Use type hints judiciously - not every function needs detailed typing
- Simple hints are good; complex generics can signal over-abstraction

**Properties**:
- Sometimes overused to add getters/setters that aren't needed
- Use properties when you need computed data or validation
- Don't use properties just to expose attributes

**Metaclasses**:
- Powerful but often unnecessary complexity
- Rarely needed in production code
- Consider simpler alternatives (decorators, class decorators) first

**Multiple inheritance**:
- Can lead to complex class hierarchies
- Composition is often simpler than complex inheritance
- Use inheritance carefully and sparingly

### Framework Considerations

**Django**:
- ORM and models encourage good separation, but be careful with over-customizing admin and forms
- Don't create custom model managers unless you need them
- Use Django's built-in features before creating custom solutions

**FastAPI**:
- Type hints and Pydantic models are great, but don't create overly complex schemas upfront
- Use dependency injection judiciously - not every function needs it
- Keep API models simple and focused

**Flask**:
- Minimal framework encourages simplicity - keep it that way
- Don't add extensions unless you actually need them
- Use blueprints for organization, not complexity

**SQLAlchemy**:
- Use base models, but don't create abstract base classes before needed
- Don't overuse relationship definitions
- Keep queries simple and direct

**Asyncio**:
- Don't make everything async just because you can
- Use async only when you need concurrent I/O operations
- Async adds complexity - use it judiciously

### Common Pitfalls

1. **Over-using class inheritance**: Composition is often simpler than complex inheritance hierarchies
2. **Creating base classes**: Don't create base classes until multiple similar classes exist
3. **Premature factory patterns**: Direct instantiation is simpler until multiple types are needed
4. **Over-configuration**: Don't make everything configurable - hardcode sensible defaults
5. **Exception hierarchies**: Use built-in exceptions until custom ones provide clear value
6. **Singleton pattern**: Rarely needed in Python - use module-level variables instead
7. **Over-using `__init__`**: Don't do heavy initialization in constructors
8. **Over-engineering imports**: Don't create `__init__.py` with complex logic
9. **Over-documenting**: Document public APIs, not every internal function
10. **Over-testing**: Test important paths, not every possible scenario

### Tooling Support

**Linting**:
- **flake8**: Detects unused imports, variables, and code style issues
- **pylint**: More comprehensive analysis, can detect dead code
- **black**: Code formatting - keeps code clean and readable

**Type checking**:
- **mypy**: Static type checking, catches unused variables and imports
- **pyright**: Faster type checker, good for large codebases

**Dead code detection**:
- **vulture**: Finds unused code in Python projects
- **autoflake**: Removes unused imports and variables

**Code complexity**:
- **radon**: Measures code complexity, identifies complex functions
- **xenon**: Enforces maximum complexity thresholds

**Testing**:
- **coverage.py**: Identifies untested code (potentially unused)
- **pytest**: Testing framework with simple, readable syntax
