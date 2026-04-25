# YAGNI Real-World Scenarios - Python

## Table of Contents

- [Introduction](#introduction)
- [Scenario 1: API Client Design](#scenario-1-api-client-design)
- [Scenario 2: Django/Flask Application Architecture](#scenario-2-djangoflask-application-architecture)
- [Scenario 3: Data Processing Pipeline](#scenario-3-data-processing-pipeline)
- [Scenario 4: Configuration Management](#scenario-4-configuration-management)
- [Scenario 5: Authentication System](#scenario-5-authentication-system)
- [Scenario 6: Type Hints and Data Classes](#scenario-6-type-hints-and-data-classes)
- [Migration Guide](#migration-guide)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document presents real-world scenarios where the YAGNI principle is applied in Python. Each scenario includes a practical problem, analysis of violations, and step-by-step solution with code examples.

## Scenario 1: API Client Design

### Context

A team is building a Python application that needs to consume a REST API for user management. The API currently has only two endpoints: create user and get user by ID.

### Problem Description

The developer creates a comprehensive API client with retry logic, caching, authentication providers, request/response interceptors, and extensive configuration options. This adds significant complexity for current simple requirements.

### Analysis of Violations

**Current Issues:**
- **Speculative generality**: Built full retry, caching, auth, and interceptor infrastructure that aren't used
- **Over-engineered configuration**: 10+ configuration options for features that will never be used
- **Crystal ball syndrome**: Anticipated authentication, caching, and retry logic before requirements exist
- **Complex class hierarchy**: Created base classes and abstract interfaces for single implementation

**Impact:**
- **Code complexity**: 300+ lines for simple GET/POST operations
- **Maintenance burden**: Multiple abstractions increase cognitive load
- **Testing difficulty**: Many edge cases and configurations to test
- **Development velocity**: Time spent on infrastructure delays feature delivery

### BAD Approach

```python
import requests
import time
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


class AuthProvider(ABC):
    """Abstract authentication provider - never actually used!"""
    @abstractmethod
    def get_auth_header(self) -> Dict[str, str]:
        pass


class ApiKeyAuthProvider(AuthProvider):
    """API key authentication - never implemented!"""
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_auth_header(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key}


class BearerTokenAuthProvider(AuthProvider):
    """Bearer token authentication - never implemented!"""
    def __init__(self, token: str):
        self.token = token

    def get_auth_header(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class CacheProvider(ABC):
    """Abstract cache provider - never actually used!"""
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        pass


class InMemoryCache(CacheProvider):
    """In-memory cache implementation - never used!"""
    def __init__(self):
        self.cache: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        value, expiry = self.cache[key]
        if expiry and time.time() > expiry:
            del self.cache[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = time.time() + ttl if ttl else None
        self.cache[key] = (value, expiry)


@dataclass
class ApiClientConfig:
    """Configuration with many unused options"""
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    auth_provider: Optional[AuthProvider] = None
    cache_provider: Optional[CacheProvider] = None


class ApiClient:
    """Over-engineered API client with unused features"""

    def __init__(self, config: ApiClientConfig):
        self.config = config
        self.session = requests.Session()

    def _execute_with_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Execute request with retry logic - never needed!"""
        last_error: Exception
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.config.timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                last_error = e
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
        raise last_error

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET request with caching - never needed!"""
        url = f"{self.config.base_url}{endpoint}"
        if self.config.cache_provider:
            cache_key = f"GET:{url}:{json.dumps(params, sort_keys=True)}"
            cached = self.config.cache_provider.get(cache_key)
            if cached is not None:
                return cached

        response = self._execute_with_retry("GET", url, params=params)
        data = response.json()

        if self.config.cache_provider:
            self.config.cache_provider.set(cache_key, data, ttl=300)

        return data

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """POST request - never uses auth or retry features!"""
        url = f"{self.config.base_url}{endpoint}"
        response = self._execute_with_retry("POST", url, json=data)
        return response.json()


config = ApiClientConfig(base_url="https://api.example.com/v1", cache_provider=InMemoryCache())
client = ApiClient(config)
```

**Why This Approach Fails:**
- Built authentication providers and caching that aren't used
- Abstract base classes for single implementation
- 100+ lines for simple GET/POST operations
- Configuration with 7 options, most never changed

### GOOD Approach

**Solution Strategy:**
1. Remove all unused features (auth, caching, retry logic)
2. Simplify to direct HTTP calls with basic error handling
3. Use requests library directly without complex wrappers
4. Implement only the two endpoints that are actually needed
5. Add features when actual requirements emerge

```python
import requests
from typing import Dict


class UserApiClient:
    """Simple API client with only what's needed now"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout

    def get_user(self, user_id: int) -> Dict:
        """Get user by ID"""
        response = requests.get(f"{self.base_url}/users/{user_id}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def create_user(self, name: str, email: str) -> Dict:
        """Create a new user"""
        response = requests.post(f"{self.base_url}/users", json={"name": name, "email": email}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


user_api = UserApiClient("https://api.example.com/v1")
```

**Benefits:**
- Reduced from 100+ lines to 25 lines
- Simple and easy to understand
- Only implements current requirements
- Easy to extend with auth, caching, or retry logic when needed

### Implementation Steps

1. **Identify current requirements**: List only the endpoints actually needed (get_user, create_user)
2. **Create minimal client**: Implement UserApiClient with only baseUrl and timeout
3. **Remove unused code**: Delete authentication providers, caching, abstract base classes
4. **Test and verify**: Test both endpoints with real API

### Testing the Solution

```python
import pytest
from unittest.mock import Mock, patch


def test_get_user_success():
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "name": "John"}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = UserApiClient("https://api.example.com/v1")
        user = client.get_user(1)
        assert user["id"] == 1


def test_create_user_success():
    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = {"id": 2, "name": "Jane"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        client = UserApiClient("https://api.example.com/v1")
        user = client.create_user("Jane", "jane@example.com")
        assert user["id"] == 2
```

## Scenario 2: Django/Flask Application Architecture

### Context

A team is building a simple web application for managing a list of books. The application has basic CRUD operations: create, read, update, and delete books. No authentication, no user management.

### Problem Description

The developer creates a complex microservices architecture with separate services for books, users, authentication, notifications, and analytics. Each service has its own database, API gateway, message queues, caching layers.

### Analysis of Violations

**Current Issues:**
- **Architectural overkill**: Microservices for a simple CRUD application
- **Speculative scalability**: Built for scale that may never be needed
- **Infrastructure complexity**: Service discovery, message queues, and API gateway for simple needs

**Impact:**
- **Deployment complexity**: Multiple services to deploy and coordinate
- **Development velocity**: Slow feature delivery due to distributed complexity
- **Monitoring burden**: Distributed tracing and logging across services

### BAD Approach

```python
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import redis
import pika
import json
import os


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://localhost/books')
db = SQLAlchemy(app)

redis_client = redis.Redis(host=os.getenv('REDIS_HOST', 'localhost'), port=6379, db=0)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.queue_declare(queue='book_events')


class Book(db.Model):
    """Book model with many fields - most never used"""
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    published_date = db.Column(db.Date)
    description = db.Column(db.Text)
    pages = db.Column(db.Integer)
    genre = db.Column(db.String(100))
    publisher = db.Column(db.String(255))
    status = db.Column(db.String(20), default='active')


class BookCache:
    """Cache manager for books - never needed!"""
    @staticmethod
    def get(book_id: int):
        key = f"book:{book_id}"
        cached = redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None

    @staticmethod
    def set(book_id: int, book_data):
        key = f"book:{book_id}"
        redis_client.setex(key, 3600, json.dumps(book_data))


class EventPublisher:
    """Event publisher - never needed!"""
    @staticmethod
    def publish_book_created(book_id: int, book_data):
        channel.basic_publish(exchange='', routing_key='book_events', body=json.dumps({"book_id": book_id}))


@app.route('/books/<int:book_id>', methods=['GET'])
def get_book(book_id: int):
    """Get book by ID with caching - never needed!"""
    cached = BookCache.get(book_id)
    if cached:
        return jsonify(cached)

    book = Book.query.filter_by(id=book_id).first()
    if not book:
        return jsonify({'error': 'Book not found'}), 404

    book_data = {'id': book.id, 'title': book.title, 'author': book.author, 'isbn': book.isbn}
    BookCache.set(book.id, book_data)
    return jsonify(book_data)


@app.route('/books', methods=['POST'])
def create_book():
    """Create a new book - never needed!"""
    data = request.get_json()
    book = Book(title=data['title'], author=data['author'], isbn=data['isbn'])
    db.session.add(book)
    db.session.commit()

    book_data = {'id': book.id, 'title': book.title, 'author': book.author, 'isbn': book.isbn}
    BookCache.set(book.id, book_data)
    EventPublisher.publish_book_created(book.id, book_data)
    return jsonify(book_data), 201


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
```

**Why This Approach Fails:**
- Microservices architecture for simple CRUD operations
- Redis caching and RabbitMQ message queues for low traffic
- Complex Book model with 10+ fields, most never used
- 90+ lines for basic operations

### GOOD Approach

**Solution Strategy:**
1. Use simple monolithic Flask application
2. Remove microservices, Redis, RabbitMQ
3. Simplify Book model to only essential fields
4. Remove event publishing

```python
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
db = SQLAlchemy(app)


class Book(db.Model):
    """Simple book model with only what's needed"""
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)


@app.route('/books', methods=['GET'])
def get_books():
    books = Book.query.all()
    return jsonify([{'id': b.id, 'title': b.title, 'author': b.author, 'isbn': b.isbn} for b in books])


@app.route('/books/<int:book_id>', methods=['GET'])
def get_book(book_id: int):
    book = Book.query.get_or_404(book_id)
    return jsonify({'id': book.id, 'title': book.title, 'author': book.author, 'isbn': book.isbn})


@app.route('/books', methods=['POST'])
def create_book():
    data = request.get_json()
    book = Book(title=data['title'], author=data['author'], isbn=data['isbn'])
    db.session.add(book)
    db.session.commit()
    return jsonify({'id': book.id, 'title': book.title, 'author': book.author, 'isbn': book.isbn}), 201


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

**Benefits:**
- Reduced from 90+ lines to 45 lines
- Simple monolithic application
- Direct database queries
- Easy to deploy and debug

### Implementation Steps

1. **Identify requirements**: Confirm only CRUD for books, no complex features
2. **Create simple Flask app**: Set up with SQLite, simple Book model, CRUD endpoints
3. **Remove infrastructure**: Delete Redis, RabbitMQ, event publishing

### Testing the Solution

```python
import pytest
from app import app, db, Book
import json


@pytest.fixture
def client():
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.drop_all()


def test_create_book(client):
    response = client.post('/books', data=json.dumps({'title': 'Test', 'author': 'Author', 'isbn': '123'}), content_type='application/json')
    assert response.status_code == 201
```

## Scenario 3: Data Processing Pipeline

### Context

A team is building a data processing pipeline to read CSV files, transform data (calculate totals, averages), and write results to a database. The pipeline runs once per day processing 10,000 rows.

### Problem Description

The developer creates a comprehensive pipeline with abstract base classes for data loaders, writers, transformers, validators, multiple data formats, parallel processing, batch processing, and complex configuration options.

### Analysis of Violations

**Current Issues:**
- **Speculative scaling**: Built for distributed processing when single-machine is sufficient
- **Over-engineered architecture**: Added message queues, worker pools, and batch processing
- **Complex configuration**: 20+ configuration options for features never used

**Impact:**
- **Deployment complexity**: Multiple services to coordinate
- **Development overhead**: Time spent on infrastructure delays feature delivery

### BAD Approach

```python
import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class DataType(Enum):
    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class DataLoader(ABC):
    """Abstract data loader - overkill for CSV reading"""
    @abstractmethod
    def load(self, source: str) -> pd.DataFrame:
        pass


class CsvDataLoader(DataLoader):
    """CSV loader with many features - most never used"""
    def __init__(self, delimiter: str = ",", encoding: str = "utf-8"):
        self.delimiter = delimiter
        self.encoding = encoding

    def load(self, source: str) -> pd.DataFrame:
        return pd.read_csv(source, delimiter=self.delimiter, encoding=self.encoding)


class JsonDataLoader(DataLoader):
    """JSON loader - never used!"""
    def load(self, source: str) -> pd.DataFrame:
        import json
        with open(source, 'r') as f:
            data = json.load(f)
        return pd.DataFrame(data)


class DataWriter(ABC):
    """Abstract data writer - overkill for database writes"""
    @abstractmethod
    def write(self, data: pd.DataFrame, destination: str) -> None:
        pass


class DatabaseDataWriter(DataWriter):
    """Database writer - never used!"""
    def __init__(self, connection_string: str, table_name: str):
        self.connection_string = connection_string
        self.table_name = table_name

    def write(self, data: pd.DataFrame, destination: str) -> None:
        from sqlalchemy import create_engine
        engine = create_engine(self.connection_string)
        data.to_sql(self.table_name, engine, if_exists='append', index=False)


class DataProcessor:
    """Over-engineered data processor"""

    def __init__(self, loader: DataLoader, writer: DataWriter):
        self.loader = loader
        self.writer = writer

    def execute(self, source: str, destination: str) -> Dict[str, Any]:
        """Execute the pipeline"""
        data = self.loader.load(source)
        self.writer.write(data, destination)
        return {'input_rows': len(data), 'output_rows': len(data)}


# Usage - actual requirement is simple: read CSV, calculate sum, write to DB
loader = CsvDataLoader(delimiter=",")
writer = DatabaseDataWriter("sqlite:///results.db", "processed_data")
processor = DataProcessor(loader, writer)
results = processor.execute("data.csv", "output.csv")
```

**Why This Approach Fails:**
- Created abstract classes for loaders and writers that are never used
- Built validation rules that are never needed
- 80+ lines for simple CSV processing

### GOOD Approach

**Solution Strategy:**
1. Remove abstract classes and framework code
2. Implement simple CSV reading with pandas
3. Add simple transformation (calculate totals/averages)
4. Write directly to database without batching

```python
import pandas as pd
from sqlalchemy import create_engine


def process_data(input_csv: str, db_connection_string: str, table_name: str):
    """Simple data processing pipeline"""
    data = pd.read_csv(input_csv)
    numeric_columns = data.select_dtypes(include=['number']).columns
    results = pd.DataFrame({
        'metric': [f'{col}_total' for col in numeric_columns] + [f'{col}_average' for col in numeric_columns],
        'value': list(data[numeric_columns].sum()) + list(data[numeric_columns].mean())
    })
    engine = create_engine(db_connection_string)
    results.to_sql(table_name, engine, if_exists='replace', index=False)


process_data('data.csv', 'sqlite:///results.db', 'processed_data')
```

**Benefits:**
- Reduced from 80+ lines to 18 lines
- Simple and easy to understand
- Direct pandas operations
- Fast enough for 10,000 rows

### Implementation Steps

1. **Identify requirements**: Confirm only CSV reading and simple calculations are needed
2. **Create simple pipeline**: Use pandas to read CSV, implement simple calculations
3. **Remove unnecessary code**: Delete abstract classes, validation, parallel processing

### Testing the Solution

```python
import pytest
import pandas as pd
import tempfile
import os
import sqlite3


@pytest.fixture
def sample_csv():
    data = pd.DataFrame({'name': ['Alice', 'Bob'], 'value1': [10, 20], 'value2': [100, 200]})
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        data.to_csv(f.name, index=False)
        yield f.name
    os.unlink(f.name)


def test_process_data(sample_csv):
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
        db_path = db_file.name
    try:
        process_data(sample_csv, f'sqlite:///{db_path}', 'test_results')
        conn = sqlite3.connect(db_path)
        results = pd.read_sql_query("SELECT * FROM test_results", conn)
        conn.close()
        assert len(results) == 4
    finally:
        os.unlink(db_path)
```

## Scenario 4: Configuration Management

### Context

A team is building a Python application that needs configuration for database connection and API keys. The application has three settings: database URL, API key, and port number.

### Problem Description

The developer creates a comprehensive configuration management system with support for multiple formats (YAML, JSON, TOML, INI, ENV), environment variable interpolation, schema validation, hierarchical configuration, configuration watchers for hot reloading.

### Analysis of Violations

**Current Issues:**
- **Over-engineered configuration**: Built for formats never used (YAML, TOML, XML)
- **Speculative features**: Schema validation and hot reloading not needed
- **Complex hierarchy**: Multi-environment configuration for simple app

**Impact:**
- **Configuration complexity**: 150+ lines of code for 3 settings
- **Maintenance burden**: Multiple configuration files to manage
- **Deployment overhead**: Complex environment setup

### BAD Approach

```python
import os
import yaml
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod


class ConfigFormat(Enum):
    YAML = "yaml"
    JSON = "json"
    ENV = "env"


class ConfigLoader(ABC):
    """Abstract configuration loader - overkill"""
    @abstractmethod
    def load(self, path: str) -> Dict[str, Any]:
        pass


class YamlConfigLoader(ConfigLoader):
    """YAML configuration loader - never used!"""
    def load(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}


class JsonConfigLoader(ConfigLoader):
    """JSON configuration loader - never used!"""
    def load(self, path: str) -> Dict[str, Any]:
        with open(path, 'r') as f:
            return json.load(f)


class EnvironmentLoader(ConfigLoader):
    """Environment variable loader"""
    def load(self, path: Optional[str] = None) -> Dict[str, Any]:
        prefix = path if path else ""
        env_vars = {}
        for key, value in os.environ.items():
            if key.startswith(prefix):
                env_vars[key[len(prefix):].lower()] = value
        return env_vars


class ConfigManager:
    """Over-engineered configuration manager"""

    def __init__(self, sources: Optional[List[Dict]] = None):
        self.sources = sources or []
        self.loaders: Dict[ConfigFormat, ConfigLoader] = {
            ConfigFormat.YAML: YamlConfigLoader(),
            ConfigFormat.JSON: JsonConfigLoader(),
            ConfigFormat.ENV: EnvironmentLoader(),
        }
        self.config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """Load configuration from all sources"""
        merged_config = {}
        for source in self.sources:
            if source['type'] == 'file':
                source_config = self._load_from_file(source)
                merged_config = {**merged_config, **source_config}
            elif source['type'] == 'env':
                source_config = self.loaders[ConfigFormat.ENV].load(source.get('prefix'))
                merged_config = {**merged_config, **source_config}
        self.config = merged_config
        return self.config

    def _load_from_file(self, source: Dict) -> Dict[str, Any]:
        format_type = ConfigFormat(source['format'])
        return self.loaders[format_type].load(source['path'])


# Usage - actual requirement is 3 simple settings
config_manager = ConfigManager(sources=[{'type': 'file', 'path': 'config.yaml', 'format': 'yaml'}])
config = config_manager.load()
```

**Why This Approach Fails:**
- Created abstract loader classes for 3 different formats when only 1 is used
- Built interpolation system that's never needed
- 80+ lines for 3 simple settings

### GOOD Approach

**Solution Strategy:**
1. Remove all configuration format loaders except environment variables
2. Eliminate validation, watching, and hot reloading
3. Use simple dataclass or environment variables directly

```python
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Simple configuration with only what's needed"""
    database_url: str
    api_key: str
    port: int

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///app.db"),
            api_key=os.getenv("API_KEY", ""),
            port=int(os.getenv("PORT", "3000"))
        )


config = Config.from_env()
```

**Benefits:**
- Reduced from 80+ lines to 15 lines
- Simple and easy to understand
- Only environment variable support
- No unnecessary features

### Implementation Steps

1. **Identify requirements**: Confirm only 3 settings needed, prefer environment variables
2. **Create simple Config dataclass**: Define with only required fields, implement from_env
3. **Remove unnecessary code**: Delete loader classes, validation, watchers

### Testing the Solution

```python
import pytest
import os
from unittest.mock import patch


def test_config_from_env():
    with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://localhost/mydb', 'API_KEY': 'test_key', 'PORT': '8080'}):
        config = Config.from_env()
        assert config.database_url == 'postgresql://localhost/mydb'
        assert config.api_key == 'test_key'
        assert config.port == 8080
```

## Scenario 5: Authentication System

### Context

A team is building a simple internal tool that needs basic authentication. The tool has 10 users and requires email/password login. No social login, no multi-factor authentication.

### Problem Description

The developer creates a comprehensive authentication system with support for multiple providers (local, OAuth, SAML, LDAP), two-factor authentication (TOTP, SMS, email), role-based access control (RBAC), session management with Redis, audit logging, password policies.

### Analysis of Violations

**Current Issues:**
- **Speculative features**: Built for OAuth, SAML, and LDAP when only local auth is needed
- **Over-engineered security**: Two-factor auth and RBAC for 10 users
- **Infrastructure overhead**: Redis session store and audit logging for simple app

**Impact:**
- **Code complexity**: 300+ lines for simple password authentication
- **Maintenance burden**: Multiple authentication providers to maintain
- **Development velocity**: Time spent on auth infrastructure delays features

### BAD Approach

```python
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod


class AuthProviderType(Enum):
    LOCAL = "local"
    OAUTH = "oauth"
    SAML = "saml"


class UserRole(Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


@dataclass
class User:
    """User model with many fields - most never used"""
    id: int
    email: str
    password_hash: str
    role: UserRole = UserRole.USER
    two_factor_enabled: bool = False
    is_active: bool = True
    is_verified: bool = False
    last_login: Optional[datetime] = None


class AuthProvider(ABC):
    """Abstract authentication provider - overkill"""
    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[User]:
        pass

    @abstractmethod
    def register(self, user_data: Dict[str, Any]) -> User:
        pass


class LocalAuthProvider(AuthProvider):
    """Local password authentication"""
    def __init__(self):
        import bcrypt
        self.bcrypt = bcrypt

    def hash_password(self, password: str) -> str:
        return self.bcrypt.hashpw(password.encode('utf-8'), self.bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password: str, hash: str) -> bool:
        return self.bcrypt.checkpw(password.encode('utf-8'), hash.encode('utf-8'))

    def authenticate(self, credentials: Dict[str, Any]) -> Optional[User]:
        email = credentials.get("email")
        password = credentials.get("password")
        if not email or not password:
            return None
        user = self._get_user_by_email(email)
        if not user or not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        user.last_login = datetime.utcnow()
        return user

    def _get_user_by_email(self, email: str) -> Optional[User]:
        return None


class OAuthProvider(AuthProvider):
    """OAuth authentication - never used!"""
    def authenticate(self, credentials: Dict[str, Any]) -> Optional[User]:
        return None

    def register(self, user_data: Dict[str, Any]) -> User:
        return None


class AuthService:
    """Over-engineered authentication service"""

    def __init__(self, providers: Dict[AuthProviderType, AuthProvider], secret_key: str):
        self.providers = providers
        self.secret_key = secret_key

    def login(self, provider_type: AuthProviderType, credentials: Dict[str, Any]) -> Dict[str, Any]:
        provider = self.providers.get(provider_type)
        if not provider:
            raise ValueError(f"Provider {provider_type} not found")
        user = provider.authenticate(credentials)
        if not user:
            raise ValueError("Invalid credentials")
        token = self._generate_jwt_token(user)
        return {"user": user, "token": token}

    def _generate_jwt_token(self, user: User) -> str:
        payload = {"user_id": user.id, "email": user.email, "exp": datetime.utcnow() + timedelta(hours=24)}
        return jwt.encode(payload, self.secret_key, algorithm="HS256")


# Usage - actual requirement is simple email/password login
providers = {AuthProviderType.LOCAL: LocalAuthProvider(), AuthProviderType.OAUTH: OAuthProvider()}
auth_service = AuthService(providers=providers, secret_key="super_secret_key")
```

**Why This Approach Fails:**
- Created abstract auth providers for OAuth and SAML when only local auth is needed
- Built two-factor authentication system that's never used
- 130+ lines for simple password authentication

### GOOD Approach

**Solution Strategy:**
1. Remove all authentication providers except local
2. Eliminate two-factor authentication, RBAC, and permissions
3. Use simple password hashing with bcrypt
4. Generate simple JWT tokens for authentication

```python
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass


@dataclass
class User:
    """Simple user model with only what's needed"""
    id: int
    email: str
    password_hash: str


class AuthService:
    """Simple authentication service"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def hash_password(self, password: str) -> str:
        """Hash password with bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password: str, hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hash.encode('utf-8'))

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = self._get_user_by_email(email)
        if not user:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    def generate_token(self, user: User) -> str:
        """Generate JWT token for user"""
        payload = {"user_id": user.id, "email": user.email, "exp": datetime.utcnow() + timedelta(hours=24)}
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _get_user_by_email(self, email: str) -> Optional[User]:
        return None


auth_service = AuthService(secret_key="your_secret_key_here")
```

**Benefits:**
- Reduced from 130+ lines to 55 lines
- Simple and easy to understand
- Only password authentication
- No unnecessary features

### Implementation Steps

1. **Identify requirements**: Confirm only email/password authentication needed
2. **Create simple AuthService**: Implement password hashing, authenticate method, JWT tokens
3. **Remove unnecessary code**: Delete all authentication providers except local

### Testing the Solution

```python
import pytest


def test_hash_and_verify_password():
    service = AuthService("secret_key")
    password = "test_password_123"
    hash = service.hash_password(password)
    assert service.verify_password(password, hash)
    assert not service.verify_password("wrong_password", hash)


def test_generate_and_verify_token():
    service = AuthService("secret_key")
    user = User(id=1, email="test@example.com", password_hash="hash")
    token = service.generate_token(user)
    payload = jwt.decode(token, service.secret_key, algorithms=["HS256"])
    assert payload is not None
    assert payload["user_id"] == 1
```

## Scenario 6: Type Hints and Data Classes

### Context

A team is building a Python application that manages a library of books. The application has simple data structures: Book (id, title, author, isbn) and Library (list of books, add_book, remove_book methods).

### Problem Description

The developer creates over-annotated type hints with generics, Union types, Literal types, TypedDict with complex nested structures, and Protocol classes for interfaces that don't exist. They also create abstract base classes and over-parameterized dataclasses.

### Analysis of Violations

**Current Issues:**
- **Over-typing**: Complex type hints that are harder to read than the code
- **Speculative generics**: Generic types for single implementations
- **Abstract overkill**: Protocol classes and ABCs for simple functions
- **Over-parameterization**: Dataclass with 10+ optional parameters when 4 are needed

**Impact:**
- **Code readability**: Type hints are more complex than the code they document
- **Development velocity**: Time spent on perfect type hints delays features
- **Onboarding difficulty**: New developers struggle with complex type system

### BAD Approach

```python
from typing import TypeVar, Generic, Optional, Dict, Any, Protocol, TypedDict
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum


T = TypeVar('T')


class BookStatus(Enum):
    """Book status - never used!"""
    AVAILABLE = "available"
    BORROWED = "borrowed"
    RESERVED = "reserved"


class BookMetadata(TypedDict, total=False):
    """Book metadata - never used!"""
    subtitle: Optional[str]
    language: str
    page_count: Optional[int]
    tags: list


class BookRepository(Protocol):
    """Book repository protocol - never used!"""
    def find_by_id(self, book_id: int) -> Optional['Book']: ...
    def save(self, book: 'Book') -> 'Book': ...


class Searchable(Protocol):
    """Searchable protocol - never used!"""
    def search(self, query: str, fields: list) -> list[T]: ...


@dataclass
class Book:
    """Over-parameterized dataclass"""
    id: int
    title: str
    author: str
    isbn: str
    status: BookStatus = BookStatus.AVAILABLE
    metadata: BookMetadata = field(default_factory=dict)
    publication_date: Optional[str] = None
    tags: list = field(default_factory=list)
    notes: Optional[str] = None
    custom_fields: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary - never used!"""
        return {'id': self.id, 'title': self.title, 'author': self.author, 'isbn': self.isbn}

    @classmethod
    def from_dict(cls, data: dict) -> 'Book':
        """Create from dictionary - never used!"""
        return cls(id=data.get('id', 0), title=data.get('title', ''), author=data.get('author', ''), isbn=data.get('isbn', ''))


class Library(Generic[T]):
    """Generic library with over-engineered types"""

    def __init__(self, name: str, items: Optional[list] = None):
        self.name = name
        self.items: list[T] = items or []

    def add_item(self, item) -> T:
        """Add item or items"""
        self.items.append(item)
        return item

    def remove_item(self, item: T) -> bool:
        """Remove item"""
        try:
            self.items.remove(item)
            return True
        except ValueError:
            return False

    def find_by_id(self, item_id: int) -> Optional[T]:
        """Find item by ID"""
        for item in self.items:
            if hasattr(item, 'id') and item.id == item_id:
                return item
        return None


# Usage - actual requirement is simple Book and Library
library: Library[Book] = Library(name="My Library")
book1 = Book(id=1, title="Book 1", author="Author 1", isbn="1234567890")
library.add_item(book1)
```

**Why This Approach Fails:**
- Created Protocol classes for interfaces that don't exist
- Over-parameterized dataclass with 10+ fields when 4 are needed
- Generic Library class for single Book type
- 90+ lines for simple data structures

### GOOD Approach

**Solution Strategy:**
1. Remove all Protocol classes and ABCs
2. Simplify Book dataclass to only essential fields
3. Use simple Library class without generics
4. Remove complex TypedDict structures

```python
from typing import list, Optional
from dataclasses import dataclass


@dataclass
class Book:
    """Simple book model with only what's needed"""
    id: int
    title: str
    author: str
    isbn: str


class Library:
    """Simple library for managing books"""

    def __init__(self, name: str):
        self.name = name
        self.books: list[Book] = []

    def add_book(self, book: Book) -> None:
        """Add a book to the library"""
        self.books.append(book)

    def remove_book(self, book_id: int) -> bool:
        """Remove a book by ID"""
        for i, book in enumerate(self.books):
            if book.id == book_id:
                self.books.pop(i)
                return True
        return False

    def find_by_id(self, book_id: int) -> Optional[Book]:
        """Find a book by ID"""
        for book in self.books:
            if book.id == book_id:
                return book
        return None

    def list_all(self) -> list[Book]:
        """Get all books"""
        return self.books.copy()


# Usage
library = Library(name="My Library")
book1 = Book(id=1, title="Book 1", author="Author 1", isbn="1234567890")
library.add_book(book1)
```

**Benefits:**
- Reduced from 90+ lines to 40 lines
- Simple and easy to understand
- Only essential fields and methods
- Clear type hints without over-engineering

### Implementation Steps

1. **Identify requirements**: Confirm only Book with 4 fields needed, simple Library CRUD
2. **Create simple dataclass and class**: Define Book with essential fields, implement Library with basic methods
3. **Remove unnecessary code**: Delete Protocol classes, TypedDict structures

### Testing the Solution

```python
import pytest


def test_library_add_and_list_books():
    library = Library(name="Test Library")
    book1 = Book(id=1, title="Book 1", author="Author 1", isbn="1234567890")
    library.add_book(book1)

    books = library.list_all()
    assert len(books) == 1
    assert books[0].title == "Book 1"


def test_library_find_by_id():
    library = Library(name="Test Library")
    book = Book(id=1, title="Book 1", author="Author 1", isbn="1234567890")
    library.add_book(book)

    found = library.find_by_id(1)
    assert found is not None
    assert found.title == "Book 1"


def test_library_remove_book():
    library = Library(name="Test Library")
    book = Book(id=1, title="Book 1", author="Author 1", isbn="1234567890")
    library.add_book(book)

    assert library.remove_book(1) is True
    assert len(library.list_all()) == 0
```

## Migration Guide

### Refactoring Existing Python Codebases

When refactoring existing Python code to follow YAGNI:

**Phase 1: Assessment**
- Use `vulture` or `dead` to find unused code
- Search for "TODO", "FUTURE", or "LATER" comments indicating speculative features
- Identify modules, classes, and functions with low usage
- Check for abstract base classes with single implementations

**Phase 2: Planning**
- Create a list of violations prioritized by impact
- Plan incremental refactoring to avoid breaking changes
- Document what's actually used vs what exists

**Phase 3: Implementation**
- Start with the lowest-impact, highest-value removals
- Remove unused imports, functions, and classes
- Simplify complex type hints to what's actually needed
- Delete speculative features and dead code
- Remove abstract base classes with single implementations

**Phase 4: Verification**
- Run full test suite
- Check that no unused code remains
- Verify that application still works correctly

### Incremental Refactoring Strategies

**Strategy 1: Type Simplification**
- Description: Gradually simplify complex type hints by removing unused generics and optional parameters
- When to use: When type hints are complex but hard to refactor all at once
- Example: Replace `Optional[Union[str, int, None]]` with `str | int`

**Strategy 2: Dead Code Elimination**
- Description: Use automated tools to identify and remove unused code incrementally
- When to use: When codebase has accumulated many unused utilities and functions
- Example: Run `vulture`, verify each unused function, then remove in batches

**Strategy 3: Abstract Class Removal**
- Description: Gradually remove abstract base classes when only one implementation exists
- When to use: When ABCs exist with single concrete implementations
- Example: Convert ABC to concrete class, update all references, then delete ABC

### Common Refactoring Patterns

1. **Pattern 1: Remove Abstract Base Classes**
   - Use `inspect` to find ABCs with single implementation
   - Replace ABC with concrete class
   - How it helps: Reduces abstraction complexity

2. **Pattern 2: Simplify Type Hints**
   - Use `mypy --warn-redundant-casts` to find over-specified types
   - Replace complex Union types with simpler alternatives
   - How it helps: Makes type hints more readable

3. **Pattern 3: Collapse Dataclasses**
   - Remove unused optional fields from dataclasses
   - How it helps: Simplifies data structures

### Testing During Refactoring

**Regression Testing:**
- Run full test suite after each refactoring batch
- Use type checking with `mypy` or `pyright` to catch type-related issues
- Tools: `pytest`, `unittest`, `mypy`

**Integration Testing:**
- Test that refactored code works with other systems
- Verify that API integrations still work
- Tools: integration test suites

## Language-Specific Notes

### Common Real-World Challenges in Python

- **Dynamic typing**: Allows deferring abstractions but can lead to runtime errors
- **Framework ecosystems**: Django, Flask, FastAPI encourage complex patterns
- **Type hints**: Can lead to over-engineering when every function has complex annotations
- **Duck typing**: Encourages simplicity but can be overused

### Framework-Specific Scenarios

- **Django**: Over-customizing admin, forms, and views; creating abstract base models unnecessarily
- **Flask**: Creating blueprints and extensions for simple apps; over-engineering route handlers
- **FastAPI**: Creating complex dependency injection for simple endpoints; over-specifying Pydantic models
- **SQLAlchemy**: Creating abstract base classes and mixins before needed

### Ecosystem Tools

**Refactoring Tools:**
- **vulture**: Find unused code in Python
- **dead**: Find dead code
- **pyflakes**: Check for unused imports and variables
- **autoflake**: Remove unused imports and variables
- **ruff**: Fast Python linter with many YAGNI checks

**Analysis Tools:**
- **mypy**: Static type checker
- **pyright**: Fast type checker
- **radon**: Code complexity metrics

**IDE Extensions:**
- **Pylance**: VS Code extension with type checking
- **PyCharm**: Built-in code inspection for dead code
- **black**: Code formatter (enforces simplicity)

### Best Practices for Python

1. **Start simple**: Use simple types and functions, add complexity only when needed
2. **Avoid over-abstracting**: Don't create base classes or ABCs until multiple implementations exist
3. **Use dataclasses**: Prefer dataclasses over custom classes for simple data structures
4. **Type hints**: Use simple, clear type hints; avoid complex generics unless necessary
5. **EAFP over LBYL**: Use try/except for cleaner code
6. **Remove dead code**: Regularly audit and remove unused code; use version control for history

### Python Idioms Supporting YAGNI

- **EAFP**: "Easier to Ask Forgiveness than Permission" - try/except instead of checking conditions
- **Duck typing**: "If it walks like a duck and quacks like a duck" - don't create unnecessary interfaces
- **Context managers**: Use `with` statements for resource management
- **List/dict comprehensions**: Simple, powerful data transformations

### Case Studies

**Case Study 1: Django E-commerce API**
- Context: Django REST API for e-commerce platform
- Problem: Over-engineered serializers, viewsets, and permissions for simple CRUD
- Solution: Removed custom serializers, used generic views, simplified permissions
- Results: 40% less code, faster API responses, easier onboarding

**Case Study 2: FastAPI Microservice**
- Context: FastAPI service for data processing
- Problem: Complex dependency injection, middleware, and Pydantic models for simple endpoints
- Solution: Simplified dependencies, removed unused middleware, flattened Pydantic models
- Results: 50% less code, 30% faster startup, easier testing

**Case Study 3: Data Science Pipeline**
- Context: Python data pipeline with pandas and NumPy
- Problem: Over-engineered abstraction layers, caching, and parallelization for simple transformations
- Solution: Removed abstractions, used pandas directly, eliminated unnecessary caching
- Results: 60% less code, faster development, easier debugging

**Case Study 4: Flask Web Application**
- Context: Flask web app for internal tooling
- Problem: Complex blueprints, extensions, and custom decorators for simple routes
- Solution: Consolidated blueprints, removed unused extensions, simplified routing
- Results: 45% less code, easier navigation, faster development
