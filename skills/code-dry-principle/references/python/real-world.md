# DRY Real-World Scenarios - Python

## Table of Contents

- [Introduction](#introduction)
- [Scenario 1: API Client Abstraction](#scenario-1-api-client-abstraction)
- [Scenario 2: Database Query Builder](#scenario-2-database-query-builder)
- [Scenario 3: Form Validation System](#scenario-3-form-validation-system)
- [Scenario 4: Data Transformation Pipeline](#scenario-4-data-transformation-pipeline)
- [Scenario 5: Configuration Management](#scenario-5-configuration-management)
- [Scenario 6: Logging Utility](#scenario-6-logging-utility)
- [Scenario 7: Authentication Wrapper](#scenario-7-authentication-wrapper)
- [Scenario 8: Email Notification Service](#scenario-8-email-notification-service)
- [Migration Guide](#migration-guide)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document presents real-world scenarios where DRY principle is applied in Python. Each scenario includes a practical problem, analysis of violations, and step-by-step solution with code examples.

## Scenario 1: API Client Abstraction

### Context

A growing e-commerce platform needs to integrate with multiple third-party APIs (Stripe for payments, SendGrid for emails, Twilio for SMS). Each API client is implemented separately with duplicated connection handling and error management.

### Problem Description

The development team has created separate client classes for each API, duplicating connection setup, retry logic, timeout handling, and error transformation. When a new requirement for consistent rate limiting is added, the team must modify three different files.

### Analysis of Violations

**Current Issues:**
- **Connection management duplicated**: Each client handles HTTP connections separately
- **Retry logic repeated**: Same retry pattern in all three clients
- **Error handling inconsistent**: Different error types and messages
- **Timeout handling scattered**: Each client implements timeouts differently

**Impact:**
- **Maintenance burden**: Bug fixes require updating multiple files
- **Inconsistent behavior**: Different APIs behave differently
- **Slow feature development**: New features require multiple implementations
- **Increased testing complexity**: Need to test similar logic multiple times

### BAD Approach

```python
import requests
import time

class StripeClient:
    BASE_URL = "https://api.stripe.com/v1"

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}'
        })

    def _request(self, method, endpoint, data=None, retries=3):
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(retries):
            try:
                response = self.session.request(method, url, json=data, timeout=30)
                if response.status_code >= 500:
                    raise Exception("Stripe server error")
                if response.status_code >= 400:
                    raise Exception(f"Stripe error: {response.text}")
                return response.json()
            except requests.Timeout:
                if attempt == retries - 1:
                    raise Exception("Stripe timeout")
                time.sleep(2 ** attempt)
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"Stripe request failed: {e}")
                time.sleep(2 ** attempt)

    def create_charge(self, amount, currency, source):
        return self._request('POST', '/charges', {
            'amount': amount,
            'currency': currency,
            'source': source
        })

class SendGridClient:
    BASE_URL = "https://api.sendgrid.com/v3"

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}'
        })

    def _request(self, method, endpoint, data=None, retries=3):
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(retries):
            try:
                response = self.session.request(method, url, json=data, timeout=30)
                if response.status_code >= 500:
                    raise Exception("SendGrid server error")
                if response.status_code >= 400:
                    raise Exception(f"SendGrid error: {response.text}")
                return response.json()
            except requests.Timeout:
                if attempt == retries - 1:
                    raise Exception("SendGrid timeout")
                time.sleep(2 ** attempt)
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"SendGrid request failed: {e}")
                time.sleep(2 ** attempt)

    def send_email(self, to, subject, content):
        return self._request('POST', '/mail/send', {
            'personalizations': [{'to': [{'email': to}]}],
            'from': {'email': 'noreply@example.com'},
            'subject': subject,
            'content': [{'type': 'text/plain', 'value': content}]
        })

class TwilioClient:
    BASE_URL = f"https://api.twilio.com/2010-04-01/Accounts"

    def __init__(self, account_sid, auth_token):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.session = requests.Session()
        self.session.auth = (account_sid, auth_token)

    def _request(self, method, endpoint, data=None, retries=3):
        url = f"{self.BASE_URL}/{self.account_sid}{endpoint}"
        for attempt in range(retries):
            try:
                response = self.session.request(method, url, data=data, timeout=30)
                if response.status_code >= 500:
                    raise Exception("Twilio server error")
                if response.status_code >= 400:
                    raise Exception(f"Twilio error: {response.text}")
                return response.json()
            except requests.Timeout:
                if attempt == retries - 1:
                    raise Exception("Twilio timeout")
                time.sleep(2 ** attempt)
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"Twilio request failed: {e}")
                time.sleep(2 ** attempt)

    def send_sms(self, to, body):
        return self._request('POST', '/Messages.json', {
            'To': to,
            'From': '+1234567890',
            'Body': body
        })
```

**Why This Approach Fails:**
- Retry logic duplicated 3 times with identical implementation
- Timeout handling repeated in each client
- Error messages are inconsistent
- Adding rate limiting requires modifying all three clients
- No single source of truth for API interaction patterns

### GOOD Approach

**Solution Strategy:**
1. Create a base HTTP client class with shared behavior
2. Use template method pattern for common request handling
3. Abstract error handling and retry logic
4. Allow subclasses to customize authentication and endpoints

```python
import requests
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

class APIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

@dataclass
class RetryConfig:
    max_attempts: int = 3
    backoff_base: float = 2.0
    initial_delay: float = 1.0

@dataclass
class RequestConfig:
    timeout: int = 30
    retry_config: RetryConfig = RetryConfig()

class BaseHTTPClient(ABC):
    """Base class for HTTP API clients with common patterns"""

    def __init__(self, base_url: str, request_config: Optional[RequestConfig] = None):
        self.base_url = base_url
        self.config = request_config or RequestConfig()
        self.session = self._create_session()

    @abstractmethod
    def _create_session(self) -> requests.Session:
        """Create and configure HTTP session"""
        pass

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint"""
        return f"{self.base_url}{endpoint}"

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retry logic and error handling"""
        url = self._build_url(endpoint)
        return self._execute_with_retry(method, url, **kwargs)

    def _execute_with_retry(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Execute request with exponential backoff retry"""
        retry = self.config.retry_config

        for attempt in range(retry.max_attempts):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=self.config.timeout,
                    **kwargs
                )
                return self._handle_response(response)

            except requests.Timeout as e:
                if attempt == retry.max_attempts - 1:
                    raise APIError(f"Request timeout after {retry.max_attempts} attempts")
                delay = retry.initial_delay * (retry.backoff_base ** attempt)
                time.sleep(delay)

            except requests.RequestException as e:
                if attempt == retry.max_attempts - 1:
                    raise APIError(f"Request failed: {str(e)}")
                delay = retry.initial_delay * (retry.backoff_base ** attempt)
                time.sleep(delay)

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle HTTP response and transform errors"""
        if response.status_code >= 500:
            raise APIError("Server error", response.status_code)

        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', response.text)
            except ValueError:
                error_message = response.text
            raise APIError(f"Client error: {error_message}", response.status_code)

        return response.json()

class StripeClient(BaseHTTPClient):
    """Stripe API client"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        super().__init__(
            base_url="https://api.stripe.com/v1",
            request_config=RequestConfig(timeout=30)
        )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.api_key}'
        })
        return session

    def create_charge(self, amount: int, currency: str, source: str) -> Dict[str, Any]:
        """Create a charge"""
        return self._make_request('POST', '/charges', json={
            'amount': amount,
            'currency': currency,
            'source': source
        })

    def refund_charge(self, charge_id: str, amount: Optional[int] = None) -> Dict[str, Any]:
        """Refund a charge"""
        data = {'charge': charge_id}
        if amount:
            data['amount'] = amount
        return self._make_request('POST', '/refunds', json=data)

class SendGridClient(BaseHTTPClient):
    """SendGrid API client"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        super().__init__(
            base_url="https://api.sendgrid.com/v3",
            request_config=RequestConfig(timeout=30)
        )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        })
        return session

    def send_email(
        self,
        to: str,
        subject: str,
        content: str,
        from_email: str = "noreply@example.com"
    ) -> Dict[str, Any]:
        """Send an email"""
        return self._make_request('POST', '/mail/send', json={
            'personalizations': [{'to': [{'email': to}]}],
            'from': {'email': from_email},
            'subject': subject,
            'content': [{'type': 'text/plain', 'value': content}]
        })

class TwilioClient(BaseHTTPClient):
    """Twilio API client"""

    def __init__(self, account_sid: str, auth_token: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        super().__init__(
            base_url=f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}",
            request_config=RequestConfig(timeout=30)
        )

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.auth = (self.account_sid, self.auth_token)
        return session

    def send_sms(self, to: str, body: str, from_number: str = "+1234567890") -> Dict[str, Any]:
        """Send an SMS message"""
        return self._make_request('POST', '/Messages.json', data={
            'To': to,
            'From': from_number,
            'Body': body
        })
```

**Benefits:**
- Single implementation of retry logic and error handling
- Consistent error handling across all APIs
- Easy to add new features (rate limiting, caching) in one place
- Each client focuses only on its specific API
- Reduced code from ~200 lines to ~180 with better organization

### Implementation Steps

1. **Step 1: Create Base Class**
   - Define `BaseHTTPClient` with abstract methods
   - Implement shared request handling
   - Add configuration dataclasses

2. **Step 2: Refactor Each Client**
   - Inherit from `BaseHTTPClient`
   - Implement `_create_session` for authentication
   - Remove duplicated retry and error handling

3. **Step 3: Test Integration**
   - Ensure each client works as before
   - Verify error handling is consistent
   - Check that retry logic works correctly

### Testing Solution

**Test Cases:**
- **Retry logic**: Verify retries on timeout and server errors
- **Error handling**: Confirm consistent APIError for all clients
- **Timeout**: Test timeout configuration per client
- **Authentication**: Verify each client's auth method works
- **Specific endpoints**: Test each client's specific methods

**Verification:**
- All three clients use same retry logic (single source of truth)
- Error handling is consistent across clients
- Adding new feature (rate limiting) requires only one code change
- Each client maintains its specific API methods

---

## Scenario 2: Database Query Builder

### Context

A SaaS application has multiple data access patterns across different services. Each service manually constructs SQL queries with similar patterns for filtering, sorting, and pagination.

### Problem Description

Developers copy-paste query construction code between services, leading to inconsistent SQL injection handling, repeated JOIN logic, and duplicated pagination code. When the team needs to add audit logging to all queries, they must modify 15+ files.

### Analysis of Violations

**Current Issues:**
- **Query building duplicated**: Similar WHERE, JOIN patterns repeated
- **Pagination logic scattered**: Same limit/offset code everywhere
- **SQL injection risk**: Manual string concatenation
- **Inconsistent ordering**: Different ORDER BY implementations

**Impact:**
- **Security risk**: Manual query building leads to SQL injection vulnerabilities
- **Maintenance nightmare**: Changes require updating many files
- **Inconsistent behavior**: Queries behave differently across services
- **Poor testability**: Hard to test query construction logic

### BAD Approach

```python
import psycopg2

def get_active_users(connection, min_age=None, max_age=None, limit=10, offset=0):
    query = "SELECT * FROM users WHERE status = 'active'"
    params = []

    if min_age is not None:
        query += f" AND age >= {min_age}"
    if max_age is not None:
        query += f" AND age <= {max_age}"
    if limit:
        query += f" LIMIT {limit}"
    if offset:
        query += f" OFFSET {offset}"

    cursor = connection.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()

def get_products(connection, category=None, min_price=None, max_price=None, limit=20, offset=0):
    query = "SELECT * FROM products WHERE stock > 0"
    params = []

    if category:
        query += f" AND category = '{category}'"
    if min_price is not None:
        query += f" AND price >= {min_price}"
    if max_price is not None:
        query += f" AND price <= {max_price}"
    query += " ORDER BY price ASC"
    if limit:
        query += f" LIMIT {limit}"
    if offset:
        query += f" OFFSET {offset}"

    cursor = connection.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()

def get_orders(connection, user_id=None, status=None, date_from=None, date_to=None, limit=50, offset=0):
    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if user_id:
        query += f" AND user_id = {user_id}"
    if status:
        query += f" AND status = '{status}'"
    if date_from:
        query += f" AND created_at >= '{date_from}'"
    if date_to:
        query += f" AND created_at <= '{date_to}'"
    query += " ORDER BY created_at DESC"
    if limit:
        query += f" LIMIT {limit}"
    if offset:
        query += f" OFFSET {offset}"

    cursor = connection.cursor()
    cursor.execute(query, params)
    return cursor.fetchall()
```

**Why This Approach Fails:**
- SQL injection vulnerabilities from string concatenation
- Pagination logic duplicated across all queries
- No single source of truth for query patterns
- Adding audit logging requires modifying every query function
- Hard to test query construction

### GOOD Approach

**Solution Strategy:**
1. Create a query builder class with fluent interface
2. Use parameterized queries to prevent SQL injection
3. Implement common patterns (WHERE, JOIN, pagination) once
4. Add hooks for cross-cutting concerns (logging, caching)

```python
from typing import Any, List, Tuple, Optional, Dict
from dataclasses import dataclass, field
import psycopg2
from psycopg2 import sql

@dataclass
class QueryConfig:
    """Configuration for query execution"""
    enable_logging: bool = True
    enable_caching: bool = False
    cache_ttl: int = 300

class QueryBuilder:
    """Fluent query builder for constructing SQL queries"""

    def __init__(self, table: str):
        self._table = sql.Identifier(table)
        self._select_fields = [sql.SQL("*")]
        self._joins: List[sql.Composable] = []
        self._where_clauses: List[sql.Composable] = []
        self._where_params: List[Any] = []
        self._order_by: List[sql.Composable] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._group_by: Optional[sql.Composable] = None

    def select(self, *fields: str) -> 'QueryBuilder':
        """Specify fields to select"""
        self._select_fields = [sql.Identifier(field) for field in fields]
        return self

    def join(self, table: str, on_condition: str, join_type: str = "INNER") -> 'QueryBuilder':
        """Add a JOIN clause"""
        self._joins.append(
            sql.SQL(f"{join_type} JOIN {table} ON {on_condition}")
        )
        return self

    def where(self, condition: str, *params: Any) -> 'QueryBuilder':
        """Add a WHERE clause"""
        self._where_clauses.append(sql.SQL(condition))
        self._where_params.extend(params)
        return self

    def where_eq(self, field: str, value: Any) -> 'QueryBuilder':
        """Add an equality condition"""
        self._where_clauses.append(sql.SQL(f"{field} = %s"))
        self._where_params.append(value)
        return self

    def where_in(self, field: str, values: List[Any]) -> 'QueryBuilder':
        """Add an IN condition"""
        placeholders = sql.SQL(', ').join([sql.Placeholder()] * len(values))
        self._where_clauses.append(sql.SQL(f"{field} IN ({placeholders})"))
        self._where_params.extend(values)
        return self

    def order_by(self, field: str, direction: str = "ASC") -> 'QueryBuilder':
        """Add an ORDER BY clause"""
        self._order_by.append(sql.SQL(f"{field} {direction}"))
        return self

    def limit(self, count: int) -> 'QueryBuilder':
        """Add a LIMIT clause"""
        self._limit = count
        return self

    def offset(self, count: int) -> 'QueryBuilder':
        """Add an OFFSET clause"""
        self._offset = count
        return self

    def group_by(self, field: str) -> 'QueryBuilder':
        """Add a GROUP BY clause"""
        self._group_by = sql.Identifier(field)
        return self

    def build(self) -> Tuple[sql.Composable, List[Any]]:
        """Build the SQL query and parameters"""
        # SELECT
        select_clause = sql.SQL(', ').join(self._select_fields)

        # FROM
        from_clause = self._table

        # JOINS
        join_clause = sql.SQL(' ').join(self._joins) if self._joins else sql.SQL('')

        # WHERE
        where_clause = sql.SQL('')
        if self._where_clauses:
            where_clause = sql.SQL('WHERE ') + sql.SQL(' AND ').join(self._where_clauses)

        # GROUP BY
        group_clause = sql.SQL('')
        if self._group_by:
            group_clause = sql.SQL('GROUP BY ') + self._group_by

        # ORDER BY
        order_clause = sql.SQL('')
        if self._order_by:
            order_clause = sql.SQL('ORDER BY ') + sql.SQL(', ').join(self._order_by)

        # LIMIT and OFFSET
        limit_clause = sql.SQL('') if self._limit is None else sql.SQL(f'LIMIT {self._limit}')
        offset_clause = sql.SQL('') if self._offset is None else sql.SQL(f'OFFSET {self._offset}')

        # Build full query
        query = sql.SQL(' ').join([
            sql.SQL('SELECT'),
            select_clause,
            sql.SQL('FROM'),
            from_clause,
            join_clause,
            where_clause,
            group_clause,
            order_clause,
            limit_clause,
            offset_clause
        ])

        return query, self._where_params

class DatabaseRepository:
    """Repository with query building and cross-cutting concerns"""

    def __init__(self, connection, config: Optional[QueryConfig] = None):
        self.connection = connection
        self.config = config or QueryConfig()
        self._cache = {}

    def execute_query(
        self,
        query: sql.Composable,
        params: List[Any],
        operation: str = "fetchall"
    ):
        """Execute query with logging and caching"""
        query_str = query.as_string(self.connection)

        # Check cache
        cache_key = (query_str, tuple(params))
        if self.config.enable_caching and cache_key in self._cache:
            return self._cache[cache_key]

        # Log query
        if self.config.enable_logging:
            print(f"Executing query: {query_str}")
            print(f"Parameters: {params}")

        # Execute
        cursor = self.connection.cursor()
        cursor.execute(query, params)

        result = None
        if operation == "fetchall":
            result = cursor.fetchall()
        elif operation == "fetchone":
            result = cursor.fetchone()
        elif operation == "execute":
            self.connection.commit()
            result = cursor.rowcount

        cursor.close()

        # Cache result
        if self.config.enable_caching:
            self._cache[cache_key] = result

        return result

# Usage examples
def get_active_users(repository, min_age=None, max_age=None, limit=10, offset=0):
    query = (
        QueryBuilder('users')
        .select('id', 'name', 'email', 'age', 'status')
        .where_eq('status', 'active')
    )

    if min_age is not None:
        query.where('age >= %s', min_age)
    if max_age is not None:
        query.where('age <= %s', max_age)

    query.limit(limit).offset(offset)

    sql_query, params = query.build()
    return repository.execute_query(sql_query, params)

def get_products(repository, category=None, min_price=None, max_price=None, limit=20, offset=0):
    query = (
        QueryBuilder('products')
        .select('id', 'name', 'category', 'price', 'stock')
        .where('stock > 0')
    )

    if category:
        query.where_eq('category', category)
    if min_price is not None:
        query.where('price >= %s', min_price)
    if max_price is not None:
        query.where('price <= %s', max_price)

    query.order_by('price', 'ASC').limit(limit).offset(offset)

    sql_query, params = query.build()
    return repository.execute_query(sql_query, params)

def get_orders(repository, user_id=None, status=None, date_from=None, date_to=None, limit=50, offset=0):
    query = (
        QueryBuilder('orders')
        .select('id', 'user_id', 'total', 'status', 'created_at')
    )

    if user_id:
        query.where_eq('user_id', user_id)
    if status:
        query.where_eq('status', status)
    if date_from:
        query.where('created_at >= %s', date_from)
    if date_to:
        query.where('created_at <= %s', date_to)

    query.order_by('created_at', 'DESC').limit(limit).offset(offset)

    sql_query, params = query.build()
    return repository.execute_query(sql_query, params)
```

**Benefits:**
- SQL injection prevention through parameterized queries
- Single implementation of pagination and filtering
- Fluent interface for readable query construction
- Easy to add cross-cutting concerns (logging, caching)
- Type-safe with psycopg2's sql module

### Implementation Steps

1. **Step 1: Create QueryBuilder Class**
   - Implement fluent interface methods (select, where, join, etc.)
   - Build SQL using psycopg2's sql module for safety
   - Support common query patterns

2. **Step 2: Create Repository Class**
   - Wrap query execution with logging/caching
   - Provide consistent query execution interface
   - Add configuration for features

3. **Step 3: Refactor Existing Functions**
   - Replace string concatenation with QueryBuilder
   - Remove duplicated pagination logic
   - Ensure all queries use parameterized queries

### Testing Solution

**Test Cases:**
- **SQL injection**: Verify parameters are properly escaped
- **Query building**: Test all builder methods produce correct SQL
- **Pagination**: Confirm limit and offset work correctly
- **Filtering**: Test WHERE clauses with various conditions
- **Cross-cutting**: Verify logging and caching work

**Verification:**
- All queries use parameterized queries (no string concatenation)
- Pagination logic exists only in QueryBuilder
- Adding audit logging requires one change (in Repository)
- Query construction is type-safe and testable

---

## Scenario 3: Form Validation System

### Context

A web application has multiple forms (registration, profile update, product creation, etc.). Each form handler implements validation separately with duplicated rules and error handling.

### Problem Description

Validation logic is scattered across form handlers, leading to inconsistent error messages, missing validation for common fields, and difficulty when business rules change. Email validation alone is implemented 8 times differently.

### Analysis of Violations

**Current Issues:**
- **Validation rules duplicated**: Same field validation repeated
- **Error messages inconsistent**: Different messages for same validation
- **Business rules scattered**: Email format defined 8 different ways
- **No reusable validators**: Can't compose validation logic

**Impact:**
- **Inconsistent UX**: Different error messages confuse users
- **Maintenance burden**: Business rule changes require many updates
- **Validation gaps**: Some forms miss required validations
- **Poor testability**: Hard to test validation logic in isolation

### BAD Approach

```python
def validate_registration(data):
    errors = []

    # Name validation
    if not data.get('name'):
        errors.append("Name is required")
    elif len(data['name']) < 2:
        errors.append("Name must be at least 2 characters")
    elif len(data['name']) > 100:
        errors.append("Name must be less than 100 characters")

    # Email validation
    email = data.get('email')
    if not email:
        errors.append("Email is required")
    elif '@' not in email:
        errors.append("Email must contain @ symbol")
    elif '.' not in email.split('@')[1]:
        errors.append("Email must contain a domain")

    # Password validation
    password = data.get('password')
    if not password:
        errors.append("Password is required")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters")
    elif not any(c.isupper() for c in password):
        errors.append("Password must contain an uppercase letter")
    elif not any(c.isdigit() for c in password):
        errors.append("Password must contain a digit")

    # Age validation
    age = data.get('age')
    if not age:
        errors.append("Age is required")
    elif age < 18:
        errors.append("You must be at least 18 years old")
    elif age > 120:
        errors.append("Please enter a valid age")

    if errors:
        raise ValueError(errors)
    return data

def validate_profile_update(data):
    errors = []

    # Name validation (different rules!)
    if data.get('name') and len(data['name']) < 3:
        errors.append("Name must be at least 3 characters")

    # Email validation (different implementation!)
    email = data.get('email')
    if email:
        import re
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            errors.append("Invalid email format")

    # Phone validation (new field)
    phone = data.get('phone')
    if phone and len(phone) != 10:
        errors.append("Phone number must be 10 digits")

    if errors:
        raise ValueError(errors)
    return data

def validate_product_creation(data):
    errors = []

    # Name validation (different again!)
    if not data.get('name'):
        errors.append("Product name is required")
    elif len(data['name']) > 200:
        errors.append("Product name too long")

    # Email validation (for contact email)
    email = data.get('contact_email')
    if email and '@' not in email:
        errors.append("Invalid email")

    # Price validation
    price = data.get('price')
    if not price:
        errors.append("Price is required")
    elif price <= 0:
        errors.append("Price must be positive")

    if errors:
        raise ValueError(errors)
    return data
```

**Why This Approach Fails:**
- Email validation implemented 3 different ways
- Name validation has different rules per form
- No reusable validation components
- Adding new validation rule requires updating many forms
- Error messages are inconsistent

### GOOD Approach

**Solution Strategy:**
1. Create reusable validator functions
2. Use composition to build validation rules
3. Create form validators that compose field validators
4. Centralize error messages

```python
from typing import Any, Callable, List, Dict, Optional
from dataclasses import dataclass, field
import re

@dataclass
class ValidationError:
    field: str
    message: str

class Validator:
    """Base validator class"""

    def __init__(self, message: str = None):
        self.message = message

    def validate(self, value: Any, field_name: str = "value") -> List[ValidationError]:
        """Validate a value and return errors"""
        errors = []
        if not self._is_valid(value):
            errors.append(ValidationError(
                field=field_name,
                message=self.message or self._default_message(field_name)
            ))
        return errors

    def _is_valid(self, value: Any) -> bool:
        raise NotImplementedError

    def _default_message(self, field_name: str) -> str:
        return f"Invalid {field_name}"

class RequiredValidator(Validator):
    def __init__(self, message: str = None):
        super().__init__(message or "{field} is required")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        return True

class MinLengthValidator(Validator):
    def __init__(self, min_length: int, message: str = None):
        self.min_length = min_length
        super().__init__(message or f"{{field}} must be at least {min_length} characters")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        return len(str(value)) >= self.min_length

class MaxLengthValidator(Validator):
    def __init__(self, max_length: int, message: str = None):
        self.max_length = max_length
        super().__init__(message or f"{{field}} must be less than {max_length} characters")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        return len(str(value)) <= self.max_length

class EmailValidator(Validator):
    EMAIL_PATTERN = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

    def __init__(self, message: str = None):
        super().__init__(message or "Invalid email format")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        return bool(self.EMAIL_PATTERN.match(str(value)))

class MinValueValidator(Validator):
    def __init__(self, min_value: float, message: str = None):
        self.min_value = min_value
        super().__init__(message or f"{{field}} must be at least {min_value}")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        try:
            return float(value) >= self.min_value
        except (ValueError, TypeError):
            return False

class MaxValueValidator(Validator):
    def __init__(self, max_value: float, message: str = None):
        self.max_value = max_value
        super().__init__(message or f"{{field}} must be at most {max_value}")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        try:
            return float(value) <= self.max_value
        except (ValueError, TypeError):
            return False

class RegexValidator(Validator):
    def __init__(self, pattern: str, message: str = None):
        self.pattern = re.compile(pattern)
        super().__init__(message or "Invalid format")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        return bool(self.pattern.match(str(value)))

class PasswordValidator(Validator):
    def __init__(self, message: str = None):
        super().__init__(message or "Password does not meet requirements")

    def _is_valid(self, value: Any) -> bool:
        if value is None:
            return True
        password = str(value)
        if len(password) < 8:
            return False
        if not any(c.isupper() for c in password):
            return False
        if not any(c.isdigit() for c in password):
            return False
        return True

@dataclass
class FieldValidation:
    """Validation rules for a single field"""
    field_name: str
    validators: List[Validator] = field(default_factory=list)

    def validate(self, data: Dict[str, Any]) -> List[ValidationError]:
        """Validate field in data"""
        value = data.get(self.field_name)
        errors = []
        for validator in self.validators:
            errors.extend(validator.validate(value, self.field_name))
        return errors

@dataclass
class FormValidator:
    """Validator for entire forms"""
    fields: List[FieldValidation] = field(default_factory=list)

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate entire form data"""
        all_errors = []

        for field_validation in self.fields:
            all_errors.extend(field_validation.validate(data))

        if all_errors:
            error_dict = {error.field: [] for error in all_errors}
            for error in all_errors:
                error_dict[error.field].append(error.message)
            raise ValidationError(error_dict)

        return data

    def add_field(self, field_name: str, validators: List[Validator]) -> 'FormValidator':
        """Add field with validators"""
        self.fields.append(FieldValidation(field_name, validators))
        return self

# Predefined field validators
def required_email_field(field_name: str = 'email') -> FieldValidation:
    """Email field with required validation"""
    return FieldValidation(
        field_name=field_name,
        validators=[
            RequiredValidator(),
            EmailValidator()
        ]
    )

def required_name_field(field_name: str = 'name', min_length: int = 2, max_length: int = 100) -> FieldValidation:
    """Name field with length validation"""
    return FieldValidation(
        field_name=field_name,
        validators=[
            RequiredValidator(),
            MinLengthValidator(min_length),
            MaxLengthValidator(max_length)
        ]
    )

def required_password_field(field_name: str = 'password') -> FieldValidation:
    """Password field with complexity validation"""
    return FieldValidation(
        field_name=field_name,
        validators=[
            RequiredValidator(),
            PasswordValidator()
        ]
    )

def optional_age_field(field_name: str = 'age', min_age: int = 18, max_age: int = 120) -> FieldValidation:
    """Optional age field with range validation"""
    return FieldValidation(
        field_name=field_name,
        validators=[
            MinValueValidator(min_age),
            MaxValueValidator(max_age)
        ]
    )

def required_price_field(field_name: str = 'price', min_price: float = 0.01) -> FieldValidation:
    """Price field with minimum value validation"""
    return FieldValidation(
        field_name=field_name,
        validators=[
            RequiredValidator(),
            MinValueValidator(min_price)
        ]
    )

# Form validators using composition
def validate_registration(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate registration form"""
    validator = FormValidator()
    validator.add_field('name', [
        RequiredValidator(),
        MinLengthValidator(2),
        MaxLengthValidator(100)
    ])
    validator.add_field('email', [
        RequiredValidator(),
        EmailValidator()
    ])
    validator.add_field('password', [
        RequiredValidator(),
        PasswordValidator()
    ])
    validator.add_field('age', [
        RequiredValidator(),
        MinValueValidator(18),
        MaxValueValidator(120)
    ])
    return validator.validate(data)

def validate_profile_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate profile update form"""
    validator = FormValidator()
    validator.add_field('name', [
        MinLengthValidator(3),
        MaxLengthValidator(100)
    ])
    validator.add_field('email', [
        EmailValidator()
    ])
    validator.add_field('phone', [
        RegexValidator(r'^\d{10}$', "Phone must be 10 digits")
    ])
    return validator.validate(data)

def validate_product_creation(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate product creation form"""
    validator = FormValidator()
    validator.add_field('name', [
        RequiredValidator(),
        MaxLengthValidator(200)
    ])
    validator.add_field('contact_email', [
        EmailValidator()
    ])
    validator.add_field('price', [
        RequiredValidator(),
        MinValueValidator(0.01)
    ])
    return validator.validate(data)
```

**Benefits:**
- Single implementation of each validation type
- Composable validators for flexible form validation
- Consistent error messages
- Easy to add new validators
- Reusable field validators

### Implementation Steps

1. **Step 1: Create Base Validator Class**
   - Define Validator interface
   - Implement _is_valid and message formatting

2. **Step 2: Implement Common Validators**
   - Create validators for common patterns (required, email, length, etc.)
   - Use inheritance for shared behavior

3. **Step 3: Create Composition Classes**
   - Implement FieldValidation for single fields
   - Implement FormValidator for entire forms
   - Add factory functions for common field types

4. **Step 4: Refactor Forms**
   - Replace manual validation with FormValidator
   - Use predefined field validators where possible
   - Ensure consistent error messages

### Testing Solution

**Test Cases:**
- **Required validation**: Test empty/None values
- **Email validation**: Verify email format validation
- **Length validation**: Test min/max length constraints
- **Password validation**: Check complexity requirements
- **Composition**: Test multiple validators on single field

**Verification:**
- Email validation exists only in EmailValidator class
- All forms use consistent error messages
- Adding new validation rule requires only one new validator class
- Validators are composable and reusable

---

## Scenario 4: Data Transformation Pipeline

### Context

A data analytics platform processes data from multiple sources (CSV, JSON, APIs) into a consistent format for analysis. Each source has its own transformation code with duplicated patterns.

### Problem Description

Data transformation logic is scattered across source-specific modules, duplicating common operations like date parsing, string cleaning, type conversion, and validation. Adding a new data source requires rewriting the same transformation logic.

### Analysis of Violations

**Current Issues:**
- **Transformation operations duplicated**: Same operations repeated across sources
- **No reusable transformers**: Can't compose transformations
- **Type handling scattered**: Date parsing, type conversion in multiple places
- **Validation logic repeated**: Similar validation everywhere

**Impact:**
- **Slow development**: New data sources require rewriting transformation logic
- **Inconsistent data**: Different sources produce slightly different outputs
- **Maintenance burden**: Bug fixes require updating multiple files
- **Poor testability**: Hard to test individual transformations

### BAD Approach

```python
import json
import csv
from datetime import datetime
import requests

def transform_csv_data(rows):
    """Transform CSV data"""
    processed = []
    for row in rows:
        processed_row = {
            'id': int(row['id']),
            'name': row['name'].strip().title(),
            'email': row['email'].lower().strip(),
            'age': int(row['age']),
            'created': datetime.strptime(row['created'], '%Y-%m-%d'),
            'active': row['status'].lower() == 'active',
            'price': float(row['price']),
        }
        processed.append(processed_row)
    return processed

def transform_json_data(data):
    """Transform JSON data"""
    processed = []
    for item in data:
        processed_item = {
            'id': item['id'],
            'name': item['name'].strip().title(),
            'email': item['email'].lower().strip(),
            'age': item['age'],
            'created': datetime.fromisoformat(item['created_at']),
            'active': item['status'] == 'active',
            'price': item['price'],
        }
        processed.append(processed_item)
    return processed

def transform_api_data(api_response):
    """Transform API response data"""
    processed = []
    for item in api_response['data']:
        processed_item = {
            'id': item['user_id'],
            'name': item['full_name'].strip().title(),
            'email': item['email_address'].lower().strip(),
            'age': item['user_age'],
            'created': datetime.strptime(item['registration_date'], '%Y-%m-%dT%H:%M:%S'),
            'active': item['is_active'],
            'price': float(item.get('subscription_fee', 0)),
        }
        processed.append(processed_item)
    return processed
```

**Why This Approach Fails:**
- String cleaning (strip, title, lower) duplicated 3 times
- Date parsing implemented 3 different ways
- Type conversion scattered
- No reusable transformation pipeline
- Field mapping hardcoded in each function

### GOOD Approach

**Solution Strategy:**
1. Create reusable transformation functions
2. Implement a pipeline builder for composing transformations
3. Define field mapping configuration
4. Support type-safe transformations

```python
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from functools import reduce

# Type definitions
Transformer = Callable[[Any], Any]
FieldMapping = Dict[str, str]

# Basic transformers
def identity(value: Any) -> Any:
    """Return value unchanged"""
    return value

def to_int(value: Any) -> Optional[int]:
    """Convert value to int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def to_float(value: Any) -> Optional[float]:
    """Convert value to float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def to_bool(value: Any) -> bool:
    """Convert value to bool"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1', 'active')
    return bool(value)

def strip_text(value: Any) -> str:
    """Strip whitespace from string"""
    return str(value).strip() if value is not None else ''

def to_lower(value: Any) -> str:
    """Convert string to lowercase"""
    return str(value).lower() if value is not None else ''

def to_title(value: Any) -> str:
    """Convert string to title case"""
    return str(value).title() if value is not None else ''

def parse_date_iso(value: Any) -> Optional[datetime]:
    """Parse ISO 8601 date"""
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None

def parse_date_format(value: Any, fmt: str = '%Y-%m-%d') -> Optional[datetime]:
    """Parse date with specific format"""
    try:
        return datetime.strptime(str(value), fmt)
    except (ValueError, TypeError):
        return None

# Composed transformers
def clean_name(value: Any) -> str:
    """Clean and format name"""
    return to_title(strip_text(value))

def clean_email(value: Any) -> str:
    """Clean and format email"""
    return to_lower(strip_text(value))

# Transformer composition
def compose(*transformers: Transformer) -> Transformer:
    """Compose multiple transformers into one"""
    def composed(value: Any) -> Any:
        return reduce(lambda acc, t: t(acc), transformers, value)
    return composed

@dataclass
class FieldConfig:
    """Configuration for transforming a single field"""
    source_field: str
    target_field: str
    transformer: Transformer = identity
    required: bool = True

@dataclass
class TransformationConfig:
    """Configuration for entire data transformation"""
    field_mappings: List[FieldConfig]

@dataclass
class TransformationResult:
    """Result of data transformation"""
    success: bool
    data: List[Dict[str, Any]]
    errors: List[str] = None

class DataTransformer:
    """Generic data transformer with configurable field mappings"""

    def __init__(self, config: TransformationConfig):
        self.config = config

    def transform(self, source_data: List[Dict[str, Any]]) -> TransformationResult:
        """Transform source data according to configuration"""
        result_data = []
        errors = []

        for idx, item in enumerate(source_data):
            try:
                processed_item = self._transform_item(item)
                result_data.append(processed_item)
            except Exception as e:
                errors.append(f"Error transforming item {idx}: {str(e)}")

        return TransformationResult(
            success=len(errors) == 0,
            data=result_data,
            errors=errors if errors else None
        )

    def _transform_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform single item according to field configuration"""
        processed = {}

        for field_config in self.config.field_mappings:
            source_value = item.get(field_config.source_field)

            if field_config.required and source_value is None:
                raise ValueError(f"Required field '{field_config.source_field}' is missing")

            if source_value is not None:
                processed[field_config.target_field] = field_config.transformer(source_value)
            else:
                processed[field_config.target_field] = None

        return processed

# Predefined configurations
def create_csv_transform_config() -> TransformationConfig:
    """Configuration for CSV data transformation"""
    return TransformationConfig([
        FieldConfig('id', 'id', to_int),
        FieldConfig('name', 'name', clean_name),
        FieldConfig('email', 'email', clean_email),
        FieldConfig('age', 'age', to_int),
        FieldConfig('created', 'created', lambda x: parse_date_format(x, '%Y-%m-%d')),
        FieldConfig('status', 'active', lambda x: to_bool(x) if x == 'active' else False),
        FieldConfig('price', 'price', to_float),
    ])

def create_json_transform_config() -> TransformationConfig:
    """Configuration for JSON data transformation"""
    return TransformationConfig([
        FieldConfig('id', 'id', identity),
        FieldConfig('name', 'name', clean_name),
        FieldConfig('email', 'email', clean_email),
        FieldConfig('age', 'age', identity),
        FieldConfig('created_at', 'created', parse_date_iso),
        FieldConfig('status', 'active', to_bool),
        FieldConfig('price', 'price', identity),
    ])

def create_api_transform_config() -> TransformationConfig:
    """Configuration for API data transformation"""
    return TransformationConfig([
        FieldConfig('user_id', 'id', identity),
        FieldConfig('full_name', 'name', clean_name),
        FieldConfig('email_address', 'email', clean_email),
        FieldConfig('user_age', 'age', identity),
        FieldConfig('registration_date', 'created', lambda x: parse_date_format(x, '%Y-%m-%dT%H:%M:%S')),
        FieldConfig('is_active', 'active', to_bool),
        FieldConfig('subscription_fee', 'price', lambda x: to_float(x) if x is not None else 0.0),
    ])

# Usage
def transform_csv_data(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform CSV data using configured transformer"""
    config = create_csv_transform_config()
    transformer = DataTransformer(config)
    result = transformer.transform(rows)
    return result.data

def transform_json_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform JSON data using configured transformer"""
    config = create_json_transform_config()
    transformer = DataTransformer(config)
    result = transformer.transform(data)
    return result.data

def transform_api_data(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Transform API data using configured transformer"""
    config = create_api_transform_config()
    transformer = DataTransformer(config)
    result = transformer.transform(api_response['data'])
    return result.data
```

**Benefits:**
- Single implementation of each transformation type
- Composable transformers for flexibility
- Configurable field mappings
- Type-safe transformations
- Easy to add new data sources

### Implementation Steps

1. **Step 1: Create Basic Transformers**
   - Implement simple transformers (to_int, to_float, etc.)
   - Add composed transformers for common operations

2. **Step 2: Create Configuration Classes**
   - Define FieldConfig for single field
   - Define TransformationConfig for entire transformation

3. **Step 3: Implement DataTransformer**
   - Build transformer that applies configuration
   - Handle errors gracefully
   - Support required/optional fields

4. **Step 4: Create Predefined Configs**
   - Define common transformation configurations
   - Refactor existing functions to use DataTransformer

### Testing Solution

**Test Cases:**
- **Type conversion**: Test int, float, bool, date conversions
- **String cleaning**: Verify strip, lower, title operations
- **Composition**: Test composed transformers work correctly
- **Field mapping**: Verify source to target mapping
- **Error handling**: Test handling of missing/invalid data

**Verification:**
- Each transformation type exists only once
- All data sources use same transformer implementations
- Adding new data source requires only new configuration
- Transformers are composable and testable

---

## Scenario 5: Configuration Management

### Context

A microservices application has multiple services (API, worker, scheduler) each with scattered configuration values (database URLs, API keys, feature flags). Configuration is duplicated across environment files and hardcoded in code.

### Problem Description

Configuration values are hardcoded in multiple files, duplicated across services, and difficult to change per environment. Database URLs appear in 6 different files, API keys in 4 files. Feature flags are inconsistently applied.

### Analysis of Violations

**Current Issues:**
- **Configuration values duplicated**: Same values in multiple files
- **Hardcoded values**: Database URLs, API keys in code
- **No single source of truth**: Config scattered everywhere
- **Environment switching difficult**: Hard to change environments

**Impact:**
- **Security risk**: Secrets in code repositories
- **Deployment complexity**: Need to update multiple files per environment
- **Configuration drift**: Different values in different places
- **Slow development**: Changing config requires hunting through files

### BAD Approach

```python
# api_service.py
def connect_to_database():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="myapp",
        user="admin",
        password="secret123"
    )

def connect_to_cache():
    return redis.Redis(host="localhost", port=6379)

def send_email():
    smtp = smtplib.SMTP("smtp.example.com", 587)
    smtp.login("noreply@example.com", "secret456")
    return smtp

FEATURE_ENABLED = True
MAX_BATCH_SIZE = 100
TIMEOUT_SECONDS = 30

# worker_service.py
def get_database_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="myapp",
        user="admin",
        password="secret123"
    )

def get_cache_connection():
    return redis.Redis(host="localhost", port=6379)

QUEUE_NAME = "tasks"
MAX_RETRIES = 3
FEATURE_ENABLED = True  # Duplicated!

# scheduler.py
def create_db_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="myapp",
        user="admin",
        password="secret123"
    )

CRON_SCHEDULE = "0 * * * *"
FEATURE_ENABLED = False  # Different value!
```

**Why This Approach Fails:**
- Database connection code duplicated 3 times
- Secrets hardcoded in code
- Feature flag has different values in different services
- No environment-specific configuration
- Changing a setting requires updating multiple files

### GOOD Approach

**Solution Strategy:**
1. Create centralized configuration dataclass
2. Support environment variable overrides
3. Validate configuration at startup
4. Use dependency injection for configuration

```python
import os
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import logging

class Environment(Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class DatabaseConfig:
    """Database configuration"""
    host: str
    port: int
    name: str
    user: str
    password: str
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class CacheConfig:
    """Cache configuration"""
    host: str
    port: int
    db: int = 0
    password: Optional[str] = None
    ttl: int = 3600

@dataclass
class EmailConfig:
    """Email configuration"""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str

@dataclass
class QueueConfig:
    """Queue configuration"""
    host: str
    port: int
    queue_name: str
    max_retries: int = 3

@dataclass
class FeatureConfig:
    """Feature flag configuration"""
    new_ui_enabled: bool = False
    api_v2_enabled: bool = False
    experimental_features: bool = False

@dataclass
class ApplicationConfig:
    """Main application configuration"""
    environment: Environment
    debug: bool
    database: DatabaseConfig
    cache: CacheConfig
    email: EmailConfig
    queue: QueueConfig
    features: FeatureConfig
    max_batch_size: int = 100
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> 'ApplicationConfig':
        """Load configuration from environment variables"""
        env = Environment(os.getenv('APP_ENV', 'development'))

        # Database
        database = DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            name=os.getenv('DB_NAME', 'myapp'),
            user=os.getenv('DB_USER', 'admin'),
            password=os.getenv('DB_PASSWORD', ''),
            pool_size=int(os.getenv('DB_POOL_SIZE', '10')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '20'))
        )

        # Cache
        cache = CacheConfig(
            host=os.getenv('CACHE_HOST', 'localhost'),
            port=int(os.getenv('CACHE_PORT', '6379')),
            db=int(os.getenv('CACHE_DB', '0')),
            password=os.getenv('CACHE_PASSWORD'),
            ttl=int(os.getenv('CACHE_TTL', '3600'))
        )

        # Email
        email = EmailConfig(
            smtp_host=os.getenv('SMTP_HOST', 'smtp.example.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_user=os.getenv('SMTP_USER', 'noreply@example.com'),
            smtp_password=os.getenv('SMTP_PASSWORD', ''),
            from_email=os.getenv('SMTP_FROM', 'noreply@example.com')
        )

        # Queue
        queue = QueueConfig(
            host=os.getenv('QUEUE_HOST', 'localhost'),
            port=int(os.getenv('QUEUE_PORT', '5672')),
            queue_name=os.getenv('QUEUE_NAME', 'tasks'),
            max_retries=int(os.getenv('QUEUE_MAX_RETRIES', '3'))
        )

        # Features
        features = FeatureConfig(
            new_ui_enabled=os.getenv('FEATURE_NEW_UI', 'false').lower() == 'true',
            api_v2_enabled=os.getenv('FEATURE_API_V2', 'false').lower() == 'true',
            experimental_features=os.getenv('FEATURE_EXPERIMENTAL', 'false').lower() == 'true'
        )

        # Main config
        config = cls(
            environment=env,
            debug=env != Environment.PRODUCTION,
            database=database,
            cache=cache,
            email=email,
            queue=queue,
            features=features,
            max_batch_size=int(os.getenv('MAX_BATCH_SIZE', '100')),
            timeout_seconds=int(os.getenv('TIMEOUT_SECONDS', '30'))
        )

        # Validate configuration
        config.validate()

        return config

    def validate(self) -> None:
        """Validate configuration"""
        if self.environment == Environment.PRODUCTION:
            if not self.database.password:
                raise ValueError("Database password required in production")
            if not self.email.smtp_password:
                raise ValueError("SMTP password required in production")
            if self.debug:
                logging.warning("Debug mode enabled in production")

# Singleton configuration instance
config = ApplicationConfig.from_env()

# Usage in services
class DatabaseConnection:
    """Database connection using configuration"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection = None

    def connect(self):
        if self._connection is None:
            self._connection = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.name,
                user=self.config.user,
                password=self.config.password
            )
        return self._connection

class CacheConnection:
    """Cache connection using configuration"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._client = None

    def connect(self):
        if self._client is None:
            self._client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                password=self.config.password
            )
        return self._client

class EmailService:
    """Email service using configuration"""

    def __init__(self, config: EmailConfig):
        self.config = config
        self._smtp = None

    def connect(self):
        if self._smtp is None:
            self._smtp = smtplib.SMTP(
                self.config.smtp_host,
                self.config.smtp_port
            )
            self._smtp.login(
                self.config.smtp_user,
                self.config.smtp_password
            )
        return self._smtp

# Initialize services with configuration
db = DatabaseConnection(config.database)
cache = CacheConnection(config.cache)
email = EmailService(config.email)

# Feature flag usage
def process_request():
    if config.features.api_v2_enabled:
        return process_request_v2()
    return process_request_v1()

def batch_process():
    for item in get_items(config.max_batch_size):
        process_item(item)
```

**Benefits:**
- Single source of truth for all configuration
- Environment variable support for flexibility
- Type-safe with dataclasses
- Configuration validation at startup
- Dependency injection for testability

### Implementation Steps

1. **Step 1: Create Configuration Dataclasses**
   - Define config classes for each component
   - Use dataclasses for type safety

2. **Step 2: Implement from_env Method**
   - Load from environment variables
   - Provide sensible defaults
   - Support different environments

3. **Step 3: Add Validation**
   - Validate required settings
   - Warn about potential issues
   - Fail fast on invalid config

4. **Step 4: Refactor Services**
   - Inject configuration via constructor
   - Remove hardcoded values
   - Use singleton config instance

### Testing Solution

**Test Cases:**
- **Environment loading**: Verify config loads from env vars
- **Default values**: Confirm defaults are applied
- **Validation**: Test validation catches missing required values
- **Type safety**: Verify type hints work correctly
- **Dependency injection**: Test with mock configuration

**Verification:**
- Configuration exists in one place only
- No hardcoded values in service code
- Environment variables control all settings
- Configuration is validated at startup
- Services receive config via injection

---

## Scenario 6: Logging Utility

### Context

An application has multiple components (API, workers, scheduled jobs) each implementing their own logging logic. Log formats are inconsistent, some logs go to stdout, others to files, and log levels are not standardized.

### Problem Description

Logging code is scattered across the application with different formats, levels, and destinations. Adding structured logging or log aggregation requires updating every component.

### Analysis of Violations

**Current Issues:**
- **Logging setup duplicated**: Same setup code in multiple files
- **Inconsistent formats**: Different log formats across components
- **Levels not standardized**: Mixed use of INFO, DEBUG, ERROR
- **No centralized configuration**: Each component configures logging independently

**Impact:**
- **Difficult debugging**: Inconsistent logs make issues hard to trace
- **Poor log aggregation**: Different formats break log parsers
- **Maintenance burden**: Changing log format requires many updates
- **Missing context**: Logs lack consistent metadata

### BAD Approach

```python
# api_service.py
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def handle_request():
    logger.info("Request received")
    try:
        process_request()
        logger.info("Request processed successfully")
    except Exception as e:
        logger.error(f"Request failed: {e}")

# worker.py
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger('worker')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('worker.log', maxBytes=10485760, backupCount=5)
handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

def process_task():
    logger.debug("Starting task processing")
    try:
        execute_task()
        logger.info("Task completed")
    except Exception as e:
        logger.error("Task failed", exc_info=True)

# scheduler.py
import sys

def log(message, level='INFO'):
    """Custom logging function"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prefix = f"[{timestamp}] [{level}]"
    print(f"{prefix} {message}", file=sys.stderr if level == 'ERROR' else sys.stdout)

def run_scheduled_job():
    log("Starting scheduled job")
    try:
        execute_job()
        log("Job completed")
    except Exception as e:
        log(f"Job failed: {e}", 'ERROR')
```

**Why This Approach Fails:**
- Logging setup duplicated in each component
- Three different logging implementations
- No consistent log format
- Difficult to aggregate logs
- No structured logging support

### GOOD Approach

**Solution Strategy:**
1. Create centralized logging configuration
2. Use structured logging with extra context
3. Support multiple handlers (console, file, remote)
4. Provide convenience methods for common patterns

```python
import logging
import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json

@dataclass
class LogConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    log_file: Optional[str] = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5
    json_format: bool = False
    include_context: bool = True

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra context
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        return json.dumps(log_data)

class Logger:
    """Centralized logger with structured logging support"""

    _loggers: Dict[str, logging.Logger] = {}
    _config: LogConfig = LogConfig()

    @classmethod
    def configure(cls, config: LogConfig):
        """Configure logging globally"""
        cls._config = config

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.level))

        # Remove existing handlers
        root_logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if config.json_format:
            console_handler.setFormatter(JSONFormatter(datefmt=config.date_format))
        else:
            console_handler.setFormatter(
                logging.Formatter(config.format, datefmt=config.date_format)
            )
        root_logger.addHandler(console_handler)

        # File handler if configured
        if config.log_file:
            file_handler = RotatingFileHandler(
                config.log_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count
            )
            if config.json_format:
                file_handler.setFormatter(JSONFormatter(datefmt=config.date_format))
            else:
                file_handler.setFormatter(
                    logging.Formatter(config.format, datefmt=config.date_format)
                )
            root_logger.addHandler(file_handler)

    @classmethod
    def get_logger(cls, name: str) -> 'Logger':
        """Get or create a logger instance"""
        if name not in cls._loggers:
            cls._loggers[name] = Logger(name)
        return cls._loggers[name]

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, message: str, **context):
        """Internal log method"""
        extra = {'extra': context} if context else None
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **context):
        self._log(logging.DEBUG, message, **context)

    def info(self, message: str, **context):
        self._log(logging.INFO, message, **context)

    def warning(self, message: str, **context):
        self._log(logging.WARNING, message, **context)

    def error(self, message: str, exc_info=None, **context):
        if exc_info:
            self._logger.error(message, exc_info=exc_info, extra={'extra': context})
        else:
            self._log(logging.ERROR, message, **context)

    def critical(self, message: str, exc_info=None, **context):
        if exc_info:
            self._logger.critical(message, exc_info=exc_info, extra={'extra': context})
        else:
            self._log(logging.CRITICAL, message, **context)

# Decorator for logging function calls
def log_execution(logger: Logger):
    """Decorator to log function execution"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(
                f"Calling {func.__name__}",
                function=func.__name__,
                args=len(args),
                kwargs=list(kwargs.keys())
            )

            try:
                result = func(*args, **kwargs)
                logger.info(
                    f"{func.__name__} completed successfully",
                    function=func.__name__
                )
                return result

            except Exception as e:
                logger.error(
                    f"{func.__name__} failed",
                    function=func.__name__,
                    error=str(e),
                    exc_info=True
                )
                raise

        return wrapper
    return decorator

# Context manager for request logging
class RequestLogContext:
    """Context manager for request-scoped logging"""

    def __init__(self, logger: Logger, request_id: str, **extra_context):
        self.logger = logger
        self.request_id = request_id
        self.extra_context = extra_context

    def __enter__(self):
        self.logger.info(
            "Request started",
            request_id=self.request_id,
            **self.extra_context
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(
                "Request failed",
                request_id=self.request_id,
                error=str(exc_val),
                **self.extra_context
            )
        else:
            self.logger.info(
                "Request completed",
                request_id=self.request_id,
                **self.extra_context
            )
        return False

# Initialize logging
log_config = LogConfig(
    level="INFO",
    log_file="application.log",
    json_format=True
)
Logger.configure(log_config)

# Usage examples
api_logger = Logger.get_logger('api_service')

@log_execution(api_logger)
def handle_request(request_id: str, user_id: int):
    with RequestLogContext(api_logger, request_id, user_id=user_id):
        process_request(request_id)
        api_logger.info("Request processed", user_id=user_id)

worker_logger = Logger.get_logger('worker')

def process_task(task_id: str):
    worker_logger.debug("Starting task", task_id=task_id)
    try:
        execute_task(task_id)
        worker_logger.info("Task completed", task_id=task_id)
    except Exception as e:
        worker_logger.error("Task failed", task_id=task_id, error=str(e))

scheduler_logger = Logger.get_logger('scheduler')

def run_scheduled_job(job_name: str):
    scheduler_logger.info(f"Starting {job_name}")
    try:
        execute_job(job_name)
        scheduler_logger.info(f"{job_name} completed")
    except Exception as e:
        scheduler_logger.error(f"{job_name} failed", job_name=job_name, error=str(e))
```

**Benefits:**
- Single configuration for all logging
- Consistent log formats across components
- Structured logging with JSON support
- Context-aware logging with extra fields
- Convenience decorators and context managers

### Implementation Steps

1. **Step 1: Create Logger Class**
   - Implement wrapper around logging module
   - Add support for structured logging
   - Provide convenience methods

2. **Step 2: Implement Configuration**
   - Create LogConfig dataclass
   - Support console and file handlers
   - Add JSON formatter option

3. **Step 3: Add Convenience Features**
   - Create log_execution decorator
   - Implement RequestLogContext context manager
   - Add factory method for getting loggers

4. **Step 4: Refactor Existing Code**
   - Replace all logging with Logger instances
   - Use decorators for common patterns
   - Add structured context to logs

### Testing Solution

**Test Cases:**
- **Configuration**: Verify logging configures correctly
- **Structured logging**: Test JSON format works
- **Context manager**: Verify request logging context
- **Decorator**: Test function execution logging
- **Multiple handlers**: Ensure console and file both work

**Verification:**
- Logging configured in one place only
- All components use same log format
- Structured logging supported
- Easy to add log aggregation (single config change)
- Context added consistently across logs

---

## Scenario 7: Authentication Wrapper

### Context

A web application has multiple views and API endpoints that need authentication. Each endpoint implements its own authentication logic, checking sessions, validating tokens, and handling errors separately.

### Problem Description

Authentication logic is duplicated across all protected endpoints, leading to inconsistent error handling, missing token validation in some places, and difficulty when authentication requirements change.

### Analysis of Violations

**Current Issues:**
- **Authentication checks duplicated**: Same logic in every protected view
- **Error handling inconsistent**: Different auth errors handled differently
- **Token validation repeated**: JWT parsing/validation code repeated
- **No centralized auth**: Hard to update authentication logic

**Impact:**
- **Security risk**: Inconsistent authentication leads to vulnerabilities
- **Maintenance burden**: Updating auth requires many changes
- **Inconsistent UX**: Different error messages confuse users
- **Development slows**: New endpoints require rewriting auth logic

### BAD Approach

```python
from flask import Flask, request, jsonify
import jwt

app = Flask(__name__)

SECRET_KEY = "secret"

def get_current_user():
    """Get current user from session"""
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

@app.route('/api/profile')
def get_profile():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Not authenticated'}), 401

    return jsonify({'user': user.to_dict()})

@app.route('/api/orders')
def get_orders():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401

    orders = Order.query.filter_by(user_id=user.id).all()
    return jsonify({'orders': [o.to_dict() for o in orders]})

@app.route('/api/create-order', methods=['POST'])
def create_order():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Please login'}), 401

    data = request.get_json()
    order = Order.create(user_id=user.id, **data)
    return jsonify({'order': order.to_dict()})

# API with JWT
@app.route('/api/v2/profile')
def get_profile_v2():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({'error': 'No token provided'}), 401

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

    user = User.query.get(payload['user_id'])
    return jsonify({'user': user.to_dict()})
```

**Why This Approach Fails:**
- Authentication check repeated in every endpoint
- JWT parsing/validation duplicated
- Different error messages for same auth failure
- No single place to update auth logic
- Easy to forget authentication in new endpoints

### GOOD Approach

**Solution Strategy:**
1. Create authentication decorators
2. Centralize JWT validation
3. Provide consistent error responses
4. Support multiple authentication methods

```python
from functools import wraps
from typing import Callable, Optional
from flask import Flask, request, jsonify, session, g
import jwt
from datetime import datetime, timedelta

class AuthenticationError(Exception):
    """Authentication error"""
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class JWTManager:
    """Centralized JWT token management"""

    def __init__(self, secret_key: str, algorithm: str = 'HS256'):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_token(self, user_id: int, expires_hours: int = 24) -> str:
        """Create JWT token"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expires_hours),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise AuthenticationError('Token expired', 401)

        except jwt.InvalidTokenError:
            raise AuthenticationError('Invalid token', 401)

def login_required(f: Callable) -> Callable:
    """Decorator to require session-based authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            raise AuthenticationError('Authentication required')

        g.user_id = session['user_id']
        return f(*args, **kwargs)

    return decorated_function

def token_required(f: Callable) -> Callable:
    """Decorator to require JWT token authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header or not auth_header.startswith('Bearer '):
            raise AuthenticationError('No token provided')

        token = auth_header.replace('Bearer ', '')

        try:
            payload = app.config['jwt_manager'].decode_token(token)
            g.user_id = payload['user_id']
            return f(*args, **kwargs)

        except AuthenticationError as e:
            raise e

    return decorated_function

def optional_auth(f: Callable) -> Callable:
    """Decorator for optional authentication"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.user_id = None

        # Try session auth first
        if 'user_id' in session:
            g.user_id = session['user_id']
            return f(*args, **kwargs)

        # Try token auth
        auth_header = request.headers.get('Authorization', '')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '')
            try:
                payload = app.config['jwt_manager'].decode_token(token)
                g.user_id = payload['user_id']
            except AuthenticationError:
                pass

        return f(*args, **kwargs)

    return decorated_function

def require_role(*roles: str):
    """Decorator factory to require specific user roles"""

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user_id') or g.user_id is None:
                raise AuthenticationError('Authentication required')

            user = User.query.get(g.user_id)
            if not user or user.role not in roles:
                raise AuthenticationError('Insufficient permissions', 403)

            return f(*args, **kwargs)

        return decorated_function
    return decorator

# Error handler
@app.errorhandler(AuthenticationError)
def handle_auth_error(error: AuthenticationError):
    """Handle authentication errors consistently"""
    return jsonify({'error': error.message}), error.status_code

# Flask app setup
app = Flask(__name__)
app.secret_key = "your-secret-key"
app.config['jwt_manager'] = JWTManager(app.secret_key)

# Routes using decorators
@app.route('/api/profile')
@login_required
def get_profile():
    """Get user profile (session auth)"""
    user = User.query.get(g.user_id)
    return jsonify({'user': user.to_dict()})

@app.route('/api/orders')
@login_required
def get_orders():
    """Get user orders (session auth)"""
    orders = Order.query.filter_by(user_id=g.user_id).all()
    return jsonify({'orders': [o.to_dict() for o in orders]})

@app.route('/api/create-order', methods=['POST'])
@login_required
@require_role('user', 'admin')
def create_order():
    """Create order (session auth, requires user or admin role)"""
    data = request.get_json()
    order = Order.create(user_id=g.user_id, **data)
    return jsonify({'order': order.to_dict()})

@app.route('/api/v2/profile')
@token_required
def get_profile_v2():
    """Get user profile (JWT auth)"""
    user = User.query.get(g.user_id)
    return jsonify({'user': user.to_dict()})

@app.route('/api/v2/orders')
@token_required
def get_orders_v2():
    """Get user orders (JWT auth)"""
    orders = Order.query.filter_by(user_id=g.user_id).all()
    return jsonify({'orders': [o.to_dict() for o in orders]})

@app.route('/api/public-data')
@optional_auth
def get_public_data():
    """Get public data (optional authentication)"""
    if g.user_id:
        user = User.query.get(g.user_id)
        return jsonify({'data': get_personalized_data(user)})
    else:
        return jsonify({'data': get_generic_data()})

@app.route('/api/admin/users')
@token_required
@require_role('admin')
def get_all_users():
    """Get all users (requires admin role)"""
    users = User.query.all()
    return jsonify({'users': [u.to_dict() for u in users]})

@app.route('/auth/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.get_json()
    user = User.authenticate(data['email'], data['password'])

    if not user:
        raise AuthenticationError('Invalid credentials', 401)

    session['user_id'] = user.id
    token = app.config['jwt_manager'].create_token(user.id)

    return jsonify({
        'user': user.to_dict(),
        'token': token
    })
```

**Benefits:**
- Single implementation of authentication logic
- Consistent error handling across all endpoints
- Support for multiple auth methods (session, JWT)
- Composable decorators for flexible requirements
- Easy to add new auth methods or requirements

### Implementation Steps

1. **Step 1: Create JWTManager Class**
   - Implement token creation and validation
   - Handle common JWT errors
   - Support configuration (algorithm, expiration)

2. **Step 2: Implement Auth Decorators**
   - Create login_required for session auth
   - Create token_required for JWT auth
   - Create optional_auth for flexible auth

3. **Step 3: Add Role-Based Access**
   - Implement require_role decorator factory
   - Support multiple roles
   - Return appropriate error codes

4. **Step 4: Refactor Endpoints**
   - Remove manual auth checks
   - Apply appropriate decorators
   - Use g.user_id for accessing user

### Testing Solution

**Test Cases:**
- **Session auth**: Verify login_required works
- **JWT auth**: Test token_required validates tokens
- **Optional auth**: Confirm optional_auth allows anonymous access
- **Role-based**: Test require_role enforces roles
- **Error handling**: Verify consistent error responses

**Verification:**
- Authentication logic exists in one place only
- All endpoints use decorators (no manual checks)
- Error responses are consistent
- Easy to add new authentication method
- Role checking centralized

---

## Scenario 8: Email Notification Service

### Context

An application sends various types of emails (welcome, password reset, order confirmation, marketing). Each email is sent from different parts of the code with duplicated template rendering and sending logic.

### Problem Description

Email sending code is scattered across the application with duplicated SMTP setup, template rendering, error handling, and logging. Adding a new email type requires rewriting the same boilerplate.

### Analysis of Violations

**Current Issues:**
- **SMTP setup duplicated**: Same connection code in multiple places
- **Template rendering repeated**: Similar template logic everywhere
- **Error handling inconsistent**: Different error handling per email type
- **No email queue**: All emails sent synchronously

**Impact:**
- **Slow page loads**: Synchronous email sending blocks requests
- **Maintenance burden**: SMTP changes require many updates
- **Inconsistent templates**: Similar emails look different
- **Poor error handling**: Some email errors silently fail

### BAD Approach

```python
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_welcome_email(user_email, user_name):
    smtp = smtplib.SMTP('smtp.example.com', 587)
    smtp.starttls()
    smtp.login('noreply@example.com', 'password123')

    msg = MIMEText(f'Welcome {user_name}!', 'plain')
    msg['Subject'] = 'Welcome to our service'
    msg['From'] = 'noreply@example.com'
    msg['To'] = user_email

    smtp.send_message(msg)
    smtp.quit()

def send_password_reset(user_email, reset_token):
    smtp = smtplib.SMTP('smtp.example.com', 587)
    smtp.starttls()
    smtp.login('noreply@example.com', 'password123')

    msg = MIMEText(f'Reset your password: {reset_token}', 'plain')
    msg['Subject'] = 'Password Reset'
    msg['From'] = 'noreply@example.com'
    msg['To'] = user_email

    smtp.send_message(msg)
    smtp.quit()

def send_order_confirmation(user_email, order_id, total):
    smtp = smtplib.SMTP('smtp.example.com', 587)
    smtp.starttls()
    smtp.login('noreply@example.com', 'password123')

    html = f'<h1>Order Confirmed</h1><p>Order ID: {order_id}</p><p>Total: ${total}</p>'
    msg = MIMEText(html, 'html')
    msg['Subject'] = f'Order {order_id} Confirmed'
    msg['From'] = 'noreply@example.com'
    msg['To'] = user_email

    smtp.send_message(msg)
    smtp.quit()

def send_marketing_email(user_email, subject, content):
    smtp = smtplib.SMTP('smtp.example.com', 587)
    smtp.starttls()
    smtp.login('noreply@example.com', 'password123')

    msg = MIMEText(content, 'plain')
    msg['Subject'] = subject
    msg['From'] = 'marketing@example.com'
    msg['To'] = user_email

    try:
        smtp.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
    finally:
        smtp.quit()
```

**Why This Approach Fails:**
- SMTP setup duplicated 4 times
- No template system (string formatting)
- Inconsistent error handling (some ignore errors)
- Synchronous sending (blocks execution)
- Hard to track email delivery

### GOOD Approach

**Solution Strategy:**
1. Create email service with template system
2. Support HTML and plain text emails
3. Implement email queue for async sending
4. Centralize SMTP configuration
5. Add logging and error handling

```python
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import logging
from jinja2 import Template
from queue import Queue
import threading

logger = logging.getLogger(__name__)

@dataclass
class EmailConfig:
    """Email configuration"""
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    from_email: str
    use_tls: bool = True
    max_retries: int = 3

@dataclass
class Email:
    """Email message"""
    to: str
    subject: str
    template_name: str
    template_data: Dict[str, Any] = field(default_factory=dict)
    from_email: Optional[str] = None
    reply_to: Optional[str] = None

class EmailTemplate:
    """Email template management"""

    def __init__(self):
        self._templates = {}

    def add_template(self, name: str, subject: str, html_template: str, text_template: str):
        """Add an email template"""
        self._templates[name] = {
            'subject': Template(subject),
            'html': Template(html_template),
            'text': Template(text_template)
        }

    def render(self, name: str, data: Dict[str, Any]) -> Dict[str, str]:
        """Render email template with data"""
        template = self._templates.get(name)
        if not template:
            raise ValueError(f"Template not found: {name}")

        return {
            'subject': template['subject'].render(**data),
            'html': template['html'].render(**data),
            'text': template['text'].render(**data)
        }

class EmailQueue:
    """Async email queue"""

    def __init__(self):
        self._queue = Queue()
        self._worker_thread = None
        self._running = False

    def start(self):
        """Start queue worker thread"""
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def stop(self):
        """Stop queue worker thread"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join()

    def enqueue(self, email: Email):
        """Add email to queue"""
        self._queue.put(email)

    def _worker(self):
        """Worker thread that processes queued emails"""
        while self._running:
            try:
                email = self._queue.get(timeout=1)
                email_service._send_email(email)
            except:
                continue

class EmailService:
    """Centralized email service"""

    def __init__(self, config: EmailConfig):
        self.config = config
        self.templates = EmailTemplate()
        self.queue = EmailQueue()
        self._init_default_templates()

    def _init_default_templates(self):
        """Initialize default email templates"""
        self.templates.add_template(
            'welcome',
            subject='Welcome to Our Service!',
            html_template='<h1>Welcome {{name}}!</h1><p>Thanks for joining us.</p>',
            text_template='Welcome {{name}}!\n\nThanks for joining us.'
        )

        self.templates.add_template(
            'password_reset',
            subject='Password Reset',
            html_template='<h1>Reset Your Password</h1><p>Use this token: {{token}}</p>',
            text_template='Reset Your Password\n\nUse this token: {{token}}'
        )

        self.templates.add_template(
            'order_confirmation',
            subject='Order {{order_id}} Confirmed',
            html_template='<h1>Order Confirmed</h1><p>Order ID: {{order_id}}</p><p>Total: ${{total}}</p>',
            text_template='Order Confirmed\n\nOrder ID: {{order_id}}\nTotal: ${{total}}'
        )

        self.templates.add_template(
            'marketing',
            subject='{{subject}}',
            html_template='<h1>{{subject}}</h1><p>{{content}}</p>',
            text_template='{{subject}}\n\n{{content}}'
        )

    def send(self, email: Email, async_send: bool = True):
        """Send email"""
        if async_send:
            self.queue.enqueue(email)
        else:
            self._send_email(email)

    def _send_email(self, email: Email):
        """Send email (internal method)"""
        try:
            # Render template
            rendered = self.templates.render(email.template_name, email.template_data)

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = rendered['subject']
            msg['From'] = email.from_email or self.config.from_email
            msg['To'] = email.to

            if email.reply_to:
                msg['Reply-To'] = email.reply_to

            # Add plain text part
            msg.attach(MIMEText(rendered['text'], 'plain'))

            # Add HTML part
            msg.attach(MIMEText(rendered['html'], 'html'))

            # Connect to SMTP and send
            for attempt in range(self.config.max_retries):
                try:
                    smtp = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)

                    if self.config.use_tls:
                        smtp.starttls()

                    smtp.login(self.config.smtp_username, self.config.smtp_password)
                    smtp.send_message(msg)
                    smtp.quit()

                    logger.info(f"Email sent to {email.to}")
                    return

                except Exception as e:
                    if attempt == self.config.max_retries - 1:
                        logger.error(f"Failed to send email to {email.to}: {e}")
                        raise
                    logger.warning(f"Retry {attempt + 1} for {email.to}")

        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            raise

# Convenience methods
def send_welcome_email(to: str, name: str, async_send: bool = True):
    email = Email(
        to=to,
        template_name='welcome',
        template_data={'name': name}
    )
    email_service.send(email, async_send)

def send_password_reset(to: str, token: str, async_send: bool = True):
    email = Email(
        to=to,
        template_name='password_reset',
        template_data={'token': token}
    )
    email_service.send(email, async_send)

def send_order_confirmation(to: str, order_id: int, total: float, async_send: bool = True):
    email = Email(
        to=to,
        template_name='order_confirmation',
        template_data={'order_id': order_id, 'total': total}
    )
    email_service.send(email, async_send)

def send_marketing_email(to: str, subject: str, content: str, async_send: bool = True):
    email = Email(
        to=to,
        template_name='marketing',
        template_data={'subject': subject, 'content': content},
        from_email='marketing@example.com'
    )
    email_service.send(email, async_send)

# Initialize service
email_config = EmailConfig(
    smtp_host='smtp.example.com',
    smtp_port=587,
    smtp_username='noreply@example.com',
    smtp_password='password123',
    from_email='noreply@example.com'
)
email_service = EmailService(email_config)
email_service.queue.start()
```

**Benefits:**
- Single SMTP configuration and sending logic
- Template system for consistent email rendering
- Async queue for non-blocking email sending
- Consistent error handling and logging
- Easy to add new email templates

### Implementation Steps

1. **Step 1: Create Email Config**
   - Define EmailConfig dataclass
   - Include all SMTP settings

2. **Step 2: Implement Template System**
   - Create EmailTemplate class using Jinja2
   - Add default templates
   - Support custom templates

3. **Step 3: Build Email Service**
   - Implement EmailService with SMTP handling
   - Add retry logic
   - Include error handling and logging

4. **Step 4: Add Async Queue**
   - Implement EmailQueue for async sending
   - Start worker thread
   - Graceful shutdown support

5. **Step 5: Create Convenience Methods**
   - Add helpers for common email types
   - Support sync/async sending

### Testing Solution

**Test Cases:**
- **Template rendering**: Verify templates render correctly
- **SMTP connection**: Test email sending works
- **Async queue**: Confirm queue processes emails
- **Error handling**: Test retries and error logging
- **Convenience methods**: Verify helper functions work

**Verification:**
- SMTP code exists in one place only
- All emails use template system
- Async queue prevents blocking
- Consistent error handling across all emails
- Easy to add new email types

---

## Migration Guide

### Refactoring Existing Codebases

When refactoring existing Python code to follow DRY:

**Phase 1: Assessment**
- Identify violations using tools (Pylint similarity checker, Ruff)
- Search for repeated patterns (same imports, similar function names)
- Prioritize by impact (high traffic code, frequently changing logic)
- Document current state and issues

**Phase 2: Planning**
- Create refactoring roadmap with milestones
- Design new architecture focused on single responsibility
- Plan incremental changes to avoid big rewrites
- Ensure comprehensive test coverage before refactoring

**Phase 3: Implementation**
- Implement changes incrementally
- Add comprehensive tests for new abstractions
- Maintain backwards compatibility where possible
- Run tests frequently to catch regressions

**Phase 4: Verification**
- Run all tests to ensure correctness
- Measure improvements (less code, fewer duplications)
- Update documentation
- Monitor production for issues

### Incremental Refactoring Strategies

**Strategy 1: Extract Method**
- Identify repeated code blocks
- Extract into separate methods
- Replace duplication with method calls
- Example: Extract validation logic into validator functions

**Strategy 2: Create Base Classes**
- Find classes with similar methods
- Create base class with common methods
- Subclasses inherit and specialize
- Example: BaseHTTPClient for API clients

**Strategy 3: Use Decorators**
- Identify cross-cutting concerns (auth, logging, caching)
- Create decorators for common patterns
- Apply decorators to functions/classes
- Example: @login_required decorator

**Strategy 4: Configuration Injection**
- Identify hardcoded values
- Create configuration classes
- Inject configuration via constructors
- Example: ApplicationConfig dataclass

### Common Refactoring Patterns

**1. Template Method Pattern**
- Define algorithm skeleton in base class
- Subclasses override specific steps
- Reduces duplication in algorithms
- How it helps: Share algorithm structure, vary implementation

**2. Strategy Pattern**
- Encapsulate interchangeable algorithms
- Pass strategy as parameter
- Eliminates conditional logic
- How it helps: Share behavior, vary algorithms

**3. Composition Over Inheritance**
- Build complex objects from simple ones
- Pass behavior as dependencies
- Avoids deep inheritance
- How it helps: Share through composition, not inheritance

**4. Dataclasses and NamedTuples**
- Define data structures concisely
- Reduce boilerplate
- Improve type safety
- How it helps: Single definition for data containers

### Testing During Refactoring

**Regression Testing:**
- Write tests before refactoring (test characterization)
- Run full test suite after each change
- Use mutation testing to catch missed edge cases
- Tools: pytest, pytest-cov, hypothesis

**Integration Testing:**
- Test new abstractions in real contexts
- Verify behavior is unchanged
- Check performance isn't degraded
- Tools: pytest, locust, pytest-benchmark

---

## Language-Specific Notes

### Common Real-World Challenges in Python

- **Dynamic typing**: Hard to catch duplication without tools
- **Duck typing**: Tempts over-generalization
- **Batteries included**: Rich stdlib leads to choice paralysis
- **Multiple paradigms**: OOP, functional, procedural mixed

**Solutions:**
- Use type hints (mypy) to catch inconsistencies
- Apply Rule of Three before abstracting
- Prefer explicit over clever
- Choose one paradigm per module and stick to it

### Framework-Specific Scenarios

- **Django**: Use mixins for shared view behavior, avoid massive utils.py
- **Flask**: Use blueprints and context processors to share logic
- **FastAPI**: Use dependency injection to avoid code duplication
- **Pydantic**: Create base models with shared validation

### Ecosystem Tools

**Refactoring Tools:**
- **Ruff**: Fast linter with duplication detection
- **Pylint**: Comprehensive code analysis with similarity checker
- **Black**: Code formatter that reveals patterns
- **isort**: Import organizer that reveals duplication

**Analysis Tools:**
- **Vulture**: Detects unused code (signs of over-abstraction)
- **Pydoctor**: Documentation generator for understanding code
- **gprof2dot**: Visualizes code relationships

**Testing Tools:**
- **pytest**: Testing framework with fixtures
- **pytest-cov**: Coverage measurement
- **hypothesis**: Property-based testing

### Best Practices for Python

1. **Use type hints**: Improves documentation and catches errors
2. **Prefer dataclasses over dicts**: For structured data
3. **Use context managers**: For resource management
4. **Apply decorators carefully**: For cross-cutting concerns only
5. **Follow PEP 8**: Consistent style makes patterns visible
6. **Use virtual environments**: Isolate dependencies
7. **Write docstrings**: Document abstractions
8. **Prefer composition over inheritance**: Unless inheritance is truly appropriate

### Case Studies

**Case Study 1: Django E-commerce Platform**
- **Context**: 50+ views with duplicate permission checking
- **Problem**: Adding new role required updating 50 files
- **Solution**: Created middleware + mixins for permissions
- **Results**: 90% reduction in permission code, new roles in one place

**Case Study 2: Flask API Service**
- **Context**: Multiple endpoints with duplicated validation
- **Problem**: Same validation in 15 endpoints
- **Solution**: Created validation decorator + schema library
- **Results**: 70% less validation code, consistent errors

**Case Study 3: Data Processing Pipeline**
- **Context**: 8 data sources with duplicate transformations
- **Problem**: Bug fix required updating 8 files
- **Solution**: Created DataTransformer with configuration
- **Results**: Single source of truth, new sources in config only
