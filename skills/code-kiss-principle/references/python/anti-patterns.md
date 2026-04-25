# KISS Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Premature Optimization](#premature-optimization)
- [Unnecessary Abstraction](#unnecessary-abstraction)
- [Over-Engineering](#over-engineering)
- [YAGNI Violations](#yagni-violations)
- [Dead Code](#dead-code)
- [Global Mutable State](#global-mutable-state)
- [Lasagna Architecture](#lasagna-architecture)
- [False Abstraction](#false-abstraction)
- [Framework Fever](#framework-fever)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the KISS principle in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

---

## Premature Optimization

### Description

Optimizing code for performance before measuring actual bottlenecks. This is one of the most common violations of the KISS principle in Python.

### BAD Example

```python
class OptimizedDataProcessor:
    def __init__(self):
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def calculate_average_optimized(self, data: list[float]) -> float:
        cache_key = tuple(data)
        
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        total = 0.0
        i = 0
        length = len(data)
        
        while i < length:
            total += data[i]
            i += 1
        
        average = total / length
        self.cache[cache_key] = average
        return average
    
    def filter_positive_optimized(self, data: list[int]) -> list[int]:
        result = []
        for i in range(len(data)):
            if data[i] > 0:
                result.append(data[i])
        return result
```

### Why It's Problematic

- **Cache inefficiency**: Caching based on entire list tuple is memory-intensive and rarely beneficial
- **Manual optimization**: Using while loop with manual index instead of Python's optimized for loop
- **Unnecessary complexity**: Adds caching logic for operations that are already fast
- **Maintenance burden**: More code to maintain with little or no performance gain
- **Unmeasured optimization**: No benchmarks to prove the optimization is needed

### How to Fix

**Refactoring Steps:**
1. Remove caching infrastructure
2. Use Python's built-in functions and comprehensions
3. Write simple, readable code first
4. Profile to find actual bottlenecks
5. Optimize only when measurements show need

### GOOD Example

```python
def calculate_average(data: list[float]) -> float:
    """Calculate the average of a list of numbers."""
    return sum(data) / len(data)

def filter_positive(data: list[int]) -> list[int]:
    """Filter positive numbers from a list."""
    return [x for x in data if x > 0]
```

**Key Changes:**
- Uses built-in `sum()` function which is optimized in C
- Simple list comprehension for filtering
- No caching complexity
- Clear, readable code
- Pythonic and performant

---

## Unnecessary Abstraction

### Description

Creating abstractions (interfaces, base classes, patterns) that don't provide real value or simplify anything. This is common in Python where developers bring patterns from statically-typed languages.

### BAD Example

```python
from abc import ABC, abstractmethod
from typing import Any

class DatabaseRepository(ABC):
    @abstractmethod
    def get_by_id(self, id: int) -> dict:
        pass
    
    @abstractmethod
    def save(self, entity: dict) -> dict:
        pass
    
    @abstractmethod
    def delete(self, id: int) -> bool:
        pass

class UserRepository(DatabaseRepository):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def get_by_id(self, id: int) -> dict:
        import sqlite3
        conn = sqlite3.connect(self.connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}
    
    def save(self, entity: dict) -> dict:
        import sqlite3
        conn = sqlite3.connect(self.connection_string)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)",
            (entity['name'], entity['email'])
        )
        conn.commit()
        entity['id'] = cursor.lastrowid
        conn.close()
        return entity
    
    def delete(self, id: int) -> bool:
        import sqlite3
        conn = sqlite3.connect(self.connection_string)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return cursor.rowcount > 0

class UserService:
    def __init__(self, repository: DatabaseRepository):
        self.repository = repository
    
    def get_user(self, user_id: int) -> dict:
        return self.repository.get_by_id(user_id)
```

### Why It's Problematic

- **Single implementation**: Abstract base class has only one subclass
- **No polymorphism benefit**: Type checking happens at runtime, not compile-time
- **Indirection without value**: Adds layer that doesn't simplify anything
- **Pythonic violation**: Python prefers duck typing over explicit interfaces
- **Maintenance overhead**: Extra code to maintain with no benefit

### How to Fix

**Refactoring Steps:**
1. Remove the abstract base class
2. Use concrete classes directly
3. Consider adding abstract base class only when you actually need multiple implementations
4. Use type hints for documentation instead of abstract classes

### GOOD Example

```python
class UserRepository:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def get_by_id(self, id: int) -> dict:
        import sqlite3
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
            row = cursor.fetchone()
            return dict(row) if row else {}
    
    def save(self, entity: dict) -> dict:
        import sqlite3
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email) VALUES (?, ?)",
                (entity['name'], entity['email'])
            )
            conn.commit()
            entity['id'] = cursor.lastrowid
            return entity
    
    def delete(self, id: int) -> bool:
        import sqlite3
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount > 0

class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository
    
    def get_user(self, user_id: int) -> dict:
        return self.repository.get_by_id(user_id)
```

**Key Changes:**
- Removed abstract base class
- Uses context managers for database connections
- Simpler, more direct implementation
- Still maintains the same interface
- Easier to understand and maintain

---

## Over-Engineering

### Description

Building systems with more complexity than the problem requires, often in the name of flexibility, extensibility, or elegance. This is particularly common in enterprise Python applications.

### BAD Example

```python
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import json

class ConfigFormat(Enum):
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"

@dataclass
class ConfigurationValue:
    key: str
    value: Any
    source: str
    is_encrypted: bool = False

class ConfigurationProvider(ABC):
    def __init__(self):
        self.cache: Dict[str, ConfigurationValue] = {}
    
    @abstractmethod
    def load(self) -> Dict[str, ConfigurationValue]:
        pass

class FileConfigurationProvider(ConfigurationProvider):
    def __init__(self, file_path: str, format: ConfigFormat):
        super().__init__()
        self.file_path = file_path
        self.format = format
    
    def load(self) -> Dict[str, ConfigurationValue]:
        with open(self.file_path, 'r') as f:
            if self.format == ConfigFormat.JSON:
                data = json.load(f)
            elif self.format == ConfigFormat.YAML:
                import yaml
                data = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported format: {self.format}")
        
        return {
            key: ConfigurationValue(
                key=key,
                value=value,
                source=self.file_path
            )
            for key, value in data.items()
        }

class ConfigurationService:
    def __init__(self, providers: List[ConfigurationProvider]):
        self.providers = providers
        self.config: Dict[str, ConfigurationValue] = {}
    
    def load_all(self):
        for provider in self.providers:
            self.config.update(provider.load())
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, ConfigurationValue(key, default, 'default')).value

class ConfigurationManager:
    def __init__(self):
        self.providers: List[ConfigurationProvider] = []
        self.service: Optional[ConfigurationService] = None
    
    def add_provider(self, provider: ConfigurationProvider):
        self.providers.append(provider)
    
    def initialize(self):
        self.service = ConfigurationService(self.providers)
        self.service.load_all()
    
    def get_config(self) -> ConfigurationService:
        if not self.service:
            self.initialize()
        return self.service
```

### Why It's Problematic

- **Multiple layers**: Providers, service, manager - all for loading a config file
- **Over-abstraction**: ConfigurationValue dataclass wraps simple key-value pairs
- **Enum for formats**: Unnecessary complexity for format selection
- **Cache that's not needed**: Loading config once is sufficient
- **Manager pattern**: Adds indirection without benefit
- **Hard to use**: Simple operation requires understanding multiple classes

### How to Fix

**Refactoring Steps:**
1. Remove all the wrapper classes
2. Use a simple function to load configuration
3. Use a dict to store configuration values
4. Load from environment variables and optional file
5. Keep it simple and direct

### GOOD Example

```python
import json
import os
from pathlib import Path

def load_config(config_path: str | None = None) -> dict:
    """Load configuration from file and environment variables."""
    config = {}
    
    if config_path and Path(config_path).exists():
        config.update(json.loads(Path(config_path).read_text()))
    
    config.update({
        'database_url': os.getenv('DATABASE_URL'),
        'api_key': os.getenv('API_KEY'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
    })
    
    return config

def get_config_value(config: dict, key: str, default=None):
    """Get a value from configuration with default."""
    return config.get(key, default)
```

**Key Changes:**
- Simple function replaces multiple classes
- Direct dict operations
- Environment variables as primary source
- File as optional override
- Easy to understand and use
- One-tenth the code

---

## YAGNI Violations

### Description

YAGNI = "You Aren't Gonna Need It." This anti-pattern is building features or infrastructure for hypothetical future needs that never materialize.

### BAD Example

```python
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import datetime

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"

class SubscriptionLevel(Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"

@dataclass
class User:
    id: int
    name: str
    email: str
    status: UserStatus = UserStatus.PENDING
    subscription_level: SubscriptionLevel = SubscriptionLevel.FREE
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_login: Optional[datetime.datetime] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    referral_code: Optional[str] = None
    referred_by: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'status': self.status.value,
            'subscription_level': self.subscription_level.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'phone': self.phone,
            'address': self.address,
            'preferences': self.preferences,
            'tags': self.tags,
            'referral_code': self.referral_code,
            'referred_by': self.referred_by,
        }
    
    def upgrade_subscription(self, new_level: SubscriptionLevel):
        """Upgrade user subscription level."""
        old_level = self.subscription_level
        self.subscription_level = new_level
        self.updated_at = datetime.datetime.now()
        # Email notification would go here
        # Analytics tracking would go here
        # Webhook would go here
    
    def add_referral(self, referral_code: str):
        """Add referral code."""
        self.referral_code = referral_code
        self.updated_at = datetime.datetime.now()

class UserService:
    def __init__(self):
        self.users: Dict[int, User] = {}
        self.next_id = 1
    
    def create_user(self, name: str, email: str) -> User:
        user = User(
            id=self.next_id,
            name=name,
            email=email
        )
        self.users[user.id] = user
        self.next_id += 1
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)
    
    def delete_user(self, user_id: int) -> bool:
        if user_id in self.users:
            self.users[user_id].status = UserStatus.DELETED
            self.users[user_id].updated_at = datetime.datetime.now()
            return True
        return False
    
    def export_users(self, format: str = 'json') -> str:
        """Export users in various formats (JSON, CSV, XML)."""
        if format == 'json':
            return json.dumps([u.to_dict() for u in self.users.values()])
        elif format == 'csv':
            # CSV export for bulk import/export
            pass
        elif format == 'xml':
            # XML export for third-party integration
            pass
        else:
            raise ValueError(f"Unsupported format: {format}")
```

### Why It's Problematic

- **Unused fields**: phone, address, referral_code, tags, preferences - never used
- **Unused methods**: upgrade_subscription, export_users - features not needed yet
- **Complex enums**: Multiple status and subscription levels for simple user creation
- **Future-proofing**: Building features that might be needed "someday"
- **Maintenance burden**: More code to maintain without benefit
- **Opportunity cost**: Time spent on unused features instead of actual needs

### How to Fix

**Refactoring Steps:**
1. Remove all unused fields and methods
2. Keep only what's needed now
3. Use simple types (strings, booleans) instead of enums when not needed
4. Add complexity only when requirements demand it
5. Trust that you can add features later

### GOOD Example

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class User:
    id: int
    name: str
    email: str
    created_at: datetime.datetime

class UserService:
    def __init__(self):
        self.users: dict[int, User] = {}
        self.next_id = 1
    
    def create_user(self, name: str, email: str) -> User:
        user = User(
            id=self.next_id,
            name=name,
            email=email,
            created_at=datetime.now()
        )
        self.users[user.id] = user
        self.next_id += 1
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)
```

**Key Changes:**
- Removed all unused fields
- Removed unused methods
- Removed enums (use simple types when needed later)
- Simple, clean dataclass
- Only what's needed right now
- Easy to extend when requirements change

---

## Dead Code

### Description

Code that exists but is never executed or used. This includes unused functions, unreachable code, and commented-out code.

### BAD Example

```python
import hashlib
import json
import csv
from typing import List, Dict, Any, Optional

class DataProcessor:
    def __init__(self):
        self.cache: Dict[str, Any] = {}
    
    def process_data_v1(self, data: List[Dict]) -> List[Dict]:
        """Old version, not used anymore."""
        results = []
        for item in data:
            processed = {
                'id': item.get('id'),
                'name': item.get('name'),
                'value': item.get('value', 0) * 2
            }
            results.append(processed)
        return results
    
    def process_data_v2(self, data: List[Dict]) -> List[Dict]:
        """Also not used anymore."""
        return [
            {
                'id': item.get('id'),
                'name': item.get('name'),
                'value': item.get('value', 0) * 2
            }
            for item in data
        ]
    
    def process_data_v3(self, data: List[Dict]) -> List[Dict]:
        """This is the one actually used."""
        return [
            {
                'id': item.get('id'),
                'name': item.get('name'),
                'value': item.get('value', 0) * 2
            }
            for item in data
        ]
    
    def process_data_v4(self, data: List[Dict]) -> List[Dict]:
        """Not yet implemented, but added for future."""
        raise NotImplementedError("This will be implemented next quarter")
    
    def calculate_hash(self, data: str) -> str:
        """Calculate SHA256 hash - never called."""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def export_to_csv(self, data: List[Dict], filename: str):
        """Export to CSV - never called."""
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    
    def export_to_xml(self, data: List[Dict], filename: str):
        """Export to XML - never called."""
        # Implementation for future XML export requirement
        pass
    
    def send_notification(self, message: str):
        """Send email notification - never called."""
        # Email service integration
        pass
    
    def log_to_external_service(self, data: Dict):
        """Log to external monitoring service - never called."""
        # External API call
        pass
    
    def _unused_helper_method(self, value: int) -> int:
        """Helper method that's never called."""
        return value * 2 + 1
    
    # def old_processing_method(self, data):
    #     """Commented out code kept for reference."""
    #     return [item['value'] * 2 for item in data]
    
    # def another_old_method(self, data):
    #     """More commented out code."""
    #     pass
```

### Why It's Problematic

- **Confusion**: Developers wonder which version to use
- **Maintenance burden**: Dead code gets maintained for no benefit
- **Hidden complexity**: Makes codebase appear larger than it is
- **Code rot**: Dead code becomes outdated and misleading
- **Version control already handles history**: No need to keep old code
- **Cognitive load**: Developers must understand code that's never used

### How to Fix

**Refactoring Steps:**
1. Use static analysis tools to find unused code
2. Delete unused functions and methods aggressively
3. Remove commented-out code (git has your back)
4. Keep only active implementations
5. Add features when needed, not before

### GOOD Example

```python
from typing import List, Dict

def process_data(data: List[Dict]) -> List[Dict]:
    """Process data by doubling values."""
    return [
        {
            'id': item.get('id'),
            'name': item.get('name'),
            'value': item.get('value', 0) * 2
        }
        for item in data
    ]
```

**Key Changes:**
- Removed all old versions
- Removed unused helper methods
- Removed commented-out code
- Single, clear implementation
- Easy to understand and maintain

---

## Global Mutable State

### Description

Using global variables or mutable state that can be accessed and modified from anywhere in the codebase. This creates hidden dependencies and makes code unpredictable.

### BAD Example

```python
from typing import Dict, Optional
import datetime

# Global state
current_user: Optional[Dict] = None
user_permissions: Dict[str, bool] = {}
database_connection = None
application_config: Dict = {}
request_context: Dict = {}
cache: Dict[str, any] = {}

def initialize_app(config: Dict):
    """Initialize application with global state."""
    global application_config, database_connection
    application_config = config
    database_connection = create_connection(config['database_url'])

def login(user_id: int):
    """Login user and set global state."""
    global current_user, user_permissions, request_context
    
    current_user = get_user_from_db(user_id)
    user_permissions = get_permissions(current_user['role'])
    request_context = {
        'user_id': user_id,
        'login_time': datetime.datetime.now(),
        'ip_address': '127.0.0.1'
    }

def logout():
    """Clear global user state."""
    global current_user, user_permissions, request_context
    current_user = None
    user_permissions = {}
    request_context = {}

def is_logged_in() -> bool:
    """Check if user is logged in using global state."""
    return current_user is not None

def has_permission(permission: str) -> bool:
    """Check permission using global state."""
    return user_permissions.get(permission, False)

def get_current_user() -> Optional[Dict]:
    """Get current user from global state."""
    return current_user

def get_config_value(key: str):
    """Get config value from global state."""
    return application_config.get(key)

def cache_data(key: str, value: any):
    """Cache data in global cache."""
    cache[key] = value

def get_cached_data(key: str):
    """Get data from global cache."""
    return cache.get(key)

def create_order(order_data: Dict) -> Dict:
    """Create order - depends on global user state."""
    if not is_logged_in():
        raise ValueError("User not logged in")
    
    if not has_permission('create_order'):
        raise ValueError("Permission denied")
    
    order_data['user_id'] = current_user['id']
    order_data['created_at'] = datetime.datetime.now()
    
    # Insert into database using global connection
    database_connection.insert('orders', order_data)
    
    return order_data
```

### Why It's Problematic

- **Hidden dependencies**: Functions don't declare their dependencies
- **Hard to test**: Difficult to set up and isolate tests
- **Concurrency issues**: Global state causes race conditions
- **Unpredictable behavior**: Order of function calls matters
- **Side effects**: Functions have hidden side effects
- **Poor reusability**: Can't use functions in different contexts

### How to Fix

**Refactoring Steps:**
1. Pass dependencies as function parameters
2. Use dependency injection
3. Encapsulate state in objects
4. Make state explicit in function signatures
5. Use context managers for request-scoped state

### GOOD Example

```python
from dataclasses import dataclass
from typing import Dict, Optional
import datetime

@dataclass
class UserSession:
    user: Dict
    permissions: Dict[str, bool]
    login_time: datetime.datetime

@dataclass
class AppContext:
    config: Dict
    cache: Dict[str, any]
    database_connection
    
    def get_config_value(self, key: str):
        return self.config.get(key)
    
    def cache_data(self, key: str, value: any):
        self.cache[key] = value
    
    def get_cached_data(self, key: str):
        return self.cache.get(key)

class UserService:
    def __init__(self, db_connection):
        self.db = db_connection
    
    def login(self, user_id: int) -> UserSession:
        """Create a user session."""
        user = self.db.get_user(user_id)
        permissions = self.db.get_permissions(user['role'])
        return UserSession(
            user=user,
            permissions=permissions,
            login_time=datetime.datetime.now()
        )

def create_order(session: UserSession, db, order_data: Dict) -> Dict:
    """Create order with explicit dependencies."""
    if 'create_order' not in session.permissions:
        raise ValueError("Permission denied")
    
    order_data['user_id'] = session.user['id']
    order_data['created_at'] = datetime.datetime.now()
    
    return db.insert('orders', order_data)
```

**Key Changes:**
- Removed all global state
- Session object encapsulates user state
- AppContext for application-wide state
- Explicit dependencies in function signatures
- Easy to test (mock sessions and context)
- No hidden side effects

---

## Lasagna Architecture

### Description

Architecture with too many layers of indirection, named after lasagna because of its many layers. Each layer adds complexity without necessarily adding value.

### BAD Example

```python
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

# Layer 1: DTOs
@dataclass
class UserDTO:
    id: int
    name: str
    email: str

@dataclass
class OrderDTO:
    id: int
    user_id: int
    total: float

# Layer 2: Entities
@dataclass
class UserEntity:
    id: int
    name: str
    email: str
    created_at: str

@dataclass
class OrderEntity:
    id: int
    user_id: int
    total: float
    status: str
    created_at: str

# Layer 3: Models
@dataclass
class UserModel:
    id: int
    name: str
    email: str
    role: str

# Layer 4: Mappers
class UserMapper:
    @staticmethod
    def dto_to_entity(dto: UserDTO) -> UserEntity:
        return UserEntity(
            id=dto.id,
            name=dto.name,
            email=dto.email,
            created_at=datetime.now().isoformat()
        )
    
    @staticmethod
    def entity_to_model(entity: UserEntity) -> UserModel:
        return UserModel(
            id=entity.id,
            name=entity.name,
            email=entity.email,
            role='user'
        )

class OrderMapper:
    @staticmethod
    def dto_to_entity(dto: OrderDTO) -> OrderEntity:
        return OrderEntity(
            id=dto.id,
            user_id=dto.user_id,
            total=dto.total,
            status='pending',
            created_at=datetime.now().isoformat()
        )

# Layer 5: Repositories (Interface)
class IUserRepository(ABC):
    @abstractmethod
    def find_by_id(self, id: int) -> Optional[UserEntity]:
        pass

class IOrderRepository(ABC):
    @abstractmethod
    def save(self, entity: OrderEntity) -> OrderEntity:
        pass

# Layer 6: Repositories (Implementation)
class UserRepository(IUserRepository):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def find_by_id(self, id: int) -> Optional[UserEntity]:
        import sqlite3
        conn = sqlite3.connect(self.connection_string)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        return UserEntity(*row) if row else None

class OrderRepository(IOrderRepository):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def save(self, entity: OrderEntity) -> OrderEntity:
        import sqlite3
        conn = sqlite3.connect(self.connection_string)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO orders (user_id, total, status) VALUES (?, ?, ?)",
            (entity.user_id, entity.total, entity.status)
        )
        conn.commit()
        entity.id = cursor.lastrowid
        conn.close()
        return entity

# Layer 7: Services (Interface)
class IUserService(ABC):
    @abstractmethod
    def get_user(self, id: int) -> Optional[UserDTO]:
        pass

class IOrderService(ABC):
    @abstractmethod
    def create_order(self, user_id: int, total: float) -> OrderDTO:
        pass

# Layer 8: Services (Implementation)
class UserService(IUserService):
    def __init__(self, repository: IUserRepository, mapper: UserMapper):
        self.repository = repository
        self.mapper = mapper
    
    def get_user(self, id: int) -> Optional[UserDTO]:
        entity = self.repository.find_by_id(id)
        if not entity:
            return None
        model = self.mapper.entity_to_model(entity)
        return UserDTO(id=model.id, name=model.name, email=model.email)

class OrderService(IOrderService):
    def __init__(self, order_repo: IOrderRepository, user_repo: IUserRepository, order_mapper: OrderMapper):
        self.order_repo = order_repo
        self.user_repo = user_repo
        self.mapper = order_mapper
    
    def create_order(self, user_id: int, total: float) -> OrderDTO:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        dto = OrderDTO(id=0, user_id=user_id, total=total)
        entity = self.mapper.dto_to_entity(dto)
        saved_entity = self.order_repo.save(entity)
        return OrderDTO(id=saved_entity.id, user_id=saved_entity.user_id, total=saved_entity.total)

# Layer 9: Controllers
class OrderController:
    def __init__(self, order_service: IOrderService, user_service: IUserService):
        self.order_service = order_service
        self.user_service = user_service
    
    def create_order(self, user_id: int, total: float) -> OrderDTO:
        user = self.user_service.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        return self.order_service.create_order(user_id, total)

# Layer 10: Factories
class ServiceFactory:
    @staticmethod
    def create_order_service(connection_string: str) -> OrderService:
        user_repo = UserRepository(connection_string)
        order_repo = OrderRepository(connection_string)
        user_mapper = UserMapper()
        order_mapper = OrderMapper()
        user_service = UserService(user_repo, user_mapper)
        return OrderService(order_repo, user_repo, order_mapper)

# Layer 11: Application
class Application:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.service_factory = ServiceFactory()
    
    def run(self):
        order_service = self.service_factory.create_order_service(self.connection_string)
        controller = OrderController(order_service, None)
        order = controller.create_order(1, 100.0)
        return order
```

### Why It's Problematic

- **11 layers** for creating a simple order
- **Multiple transformations**: DTO → Entity → Model → DTO
- **Indirection everywhere**: Can't trace execution easily
- **Change requires touching many layers**: Simple change affects multiple files
- **High cognitive load**: Must understand entire architecture
- **Development slowed**: Simple tasks take too long
- **Interfaces for single implementations**: No polymorphism benefit

### How to Fix

**Refactoring Steps:**
1. Map the actual flow through the system
2. Identify which layers add real value
3. Remove layers that just pass through data
4. Combine related layers
5. Simplify to what's actually needed

### GOOD Example

```python
from dataclasses import dataclass
from typing import Optional
import sqlite3

@dataclass
class User:
    id: int
    name: str
    email: str

@dataclass
class Order:
    id: int
    user_id: int
    total: float

class Database:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    def get_user(self, user_id: int) -> Optional[User]:
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return User(*row) if row else None
    
    def create_order(self, user_id: int, total: float) -> Order:
        with sqlite3.connect(self.connection_string) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO orders (user_id, total) VALUES (?, ?)",
                (user_id, total)
            )
            conn.commit()
            return Order(id=cursor.lastrowid, user_id=user_id, total=total)

def create_order(db: Database, user_id: int, total: float) -> Order:
    """Create an order for a user."""
    user = db.get_user(user_id)
    if not user:
        raise ValueError("User not found")
    return db.create_order(user_id, total)
```

**Key Changes:**
- Reduced from 11 layers to 3
- Direct data structures (no DTO/Entity/Model dance)
- Simple functions instead of complex service hierarchies
- Clear data flow
- Easy to understand and modify
- Fast to implement features

---

## False Abstraction

### Description

Creating abstractions that hide complexity rather than reduce it. The complexity still exists but is now harder to see and understand.

### BAD Example

```python
from typing import Any, Dict, List

class DataProcessor:
    """Abstracts data processing - but what does it actually do?"""
    
    def __init__(self):
        self.processors: List[callable] = []
    
    def add_processor(self, processor: callable):
        """Add a processor function."""
        self.processors.append(processor)
    
    def process(self, data: Any) -> Any:
        """Process data through all processors."""
        result = data
        for processor in self.processors:
            result = processor(result)
        return result
    
    def clear(self):
        """Clear all processors."""
        self.processors.clear()

class OrderProcessingService:
    """Service that processes orders - abstracted away."""
    
    def __init__(self, data_processor: DataProcessor):
        self.data_processor = data_processor
    
    def process_order(self, order_data: Dict) -> Dict:
        """Process an order - but what happens?"""
        return self.data_processor.process(order_data)

def setup_order_processing():
    """Setup order processing pipeline - complex logic hidden."""
    processor = DataProcessor()
    
    def validate_order(data: Dict) -> Dict:
        if not data.get('user_id'):
            raise ValueError("Missing user_id")
        if not data.get('total', 0) > 0:
            raise ValueError("Total must be positive")
        return data
    
    def enrich_order(data: Dict) -> Dict:
        import datetime
        data['created_at'] = datetime.datetime.now().isoformat()
        data['status'] = 'pending'
        return data
    
    def calculate_tax(data: Dict) -> Dict:
        tax = data.get('total', 0) * 0.1
        data['tax'] = round(tax, 2)
        data['total_with_tax'] = data['total'] + tax
        return data
    
    def apply_discount(data: Dict) -> Dict:
        if data.get('total', 0) > 100:
            data['discount'] = 10
            data['total'] = data['total'] - data['discount']
        return data
    
    def save_to_database(data: Dict) -> Dict:
        database.insert('orders', data)
        return data
    
    def send_confirmation_email(data: Dict) -> Dict:
        email_service.send(data['user_id'], 'Order confirmed')
        return data
    
    processor.add_processor(validate_order)
    processor.add_processor(enrich_order)
    processor.add_processor(calculate_tax)
    processor.add_processor(apply_discount)
    processor.add_processor(save_to_database)
    processor.add_processor(send_confirmation_email)
    
    return processor

def process_order(order_data: Dict) -> Dict:
    """Process an order - one function call, but what happens?"""
    processor = setup_order_processing()
    service = OrderProcessingService(processor)
    return service.process_order(order_data)
```

### Why It's Problematic

- **Hidden complexity**: You can't tell what `process_order()` does without tracing
- **Coupled operations**: Validation, enrichment, tax, discount, database, email all hidden
- **Hard to debug**: When something fails, you don't know where
- **Hard to test**: Can't test individual steps easily
- **Side effects hidden**: Database operations and emails are hidden
- **No visibility**: Order processing flow is unclear
- **Complexity not reduced**: It's just hidden behind abstraction

### How to Fix

**Refactoring Steps:**
1. Identify what the abstraction is actually hiding
2. Separate unrelated concerns into independent functions
3. Make each piece do one thing well
4. Keep complexity visible and manageable
5. Call operations explicitly

### GOOD Example

```python
import datetime
from typing import Dict

def validate_order(order_data: Dict) -> Dict:
    """Validate order data."""
    if not order_data.get('user_id'):
        raise ValueError("Missing user_id")
    if not order_data.get('total', 0) > 0:
        raise ValueError("Total must be positive")
    return order_data

def enrich_order(order_data: Dict) -> Dict:
    """Enrich order with metadata."""
    order_data['created_at'] = datetime.datetime.now().isoformat()
    order_data['status'] = 'pending'
    return order_data

def calculate_tax(order_data: Dict) -> Dict:
    """Calculate tax for order."""
    tax = order_data['total'] * 0.1
    order_data['tax'] = round(tax, 2)
    order_data['total_with_tax'] = order_data['total'] + tax
    return order_data

def apply_discount(order_data: Dict) -> Dict:
    """Apply discount if applicable."""
    if order_data['total'] > 100:
        order_data['discount'] = 10
        order_data['total'] = order_data['total'] - order_data['discount']
    return order_data

def save_order(order_data: Dict) -> Dict:
    """Save order to database."""
    order_id = database.insert('orders', order_data)
    order_data['id'] = order_id
    return order_data

def send_confirmation(order_data: Dict) -> Dict:
    """Send confirmation email."""
    email_service.send(order_data['user_id'], 'Order confirmed')
    return order_data

def process_order(order_data: Dict) -> Dict:
    """Process an order through all steps."""
    order_data = validate_order(order_data)
    order_data = enrich_order(order_data)
    order_data = calculate_tax(order_data)
    order_data = apply_discount(order_data)
    order_data = save_order(order_data)
    order_data = send_confirmation(order_data)
    return order_data
```

**Key Changes:**
- Clear, separate functions for each step
- Easy to understand what happens
- Easy to debug and test
- Complexity is visible
- Can reorder or skip steps as needed
- No hidden abstractions

---

## Framework Fever

### Description

Using heavyweight frameworks when simple libraries or vanilla code would suffice. Often occurs when developers are excited about a framework or want to use "enterprise" solutions.

### BAD Example

```python
from flask import Flask, request, jsonify
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token
from flask_cors import CORS
from flask_restful import Api, Resource

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['JWT_SECRET_KEY'] = 'secret-key'

db = SQLAlchemy(app)
ma = Marshmallow(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
cors = CORS(app)
api = Api(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False)

# Schemas
class UserSchema(ma.Schema):
    class Meta:
        fields = ('id', 'name', 'email')

class OrderSchema(ma.Schema):
    class Meta:
        fields = ('id', 'user_id', 'total')

user_schema = UserSchema()
users_schema = UserSchema(many=True)
order_schema = OrderSchema()
orders_schema = OrderSchema(many=True)

# Resources
class UserResource(Resource):
    def get(self, user_id):
        user = User.query.get_or_404(user_id)
        return jsonify(user_schema.dump(user))
    
    def put(self, user_id):
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        user.name = data.get('name', user.name)
        user.email = data.get('email', user.email)
        db.session.commit()
        return jsonify(user_schema.dump(user))

class UserListResource(Resource):
    def get(self):
        users = User.query.all()
        return jsonify(users_schema.dump(users))
    
    def post(self):
        data = request.get_json()
        user = User(name=data['name'], email=data['email'])
        db.session.add(user)
        db.session.commit()
        return jsonify(user_schema.dump(user)), 201

class OrderResource(Resource):
    def get(self, order_id):
        order = Order.query.get_or_404(order_id)
        return jsonify(order_schema.dump(order))

class OrderListResource(Resource):
    def post(self):
        data = request.get_json()
        order = Order(user_id=data['user_id'], total=data['total'])
        db.session.add(order)
        db.session.commit()
        return jsonify(order_schema.dump(order)), 201

# Routes
api.add_resource(UserResource, '/api/users/<int:user_id>')
api.add_resource(UserListResource, '/api/users')
api.add_resource(OrderResource, '/api/orders/<int:order_id>')
api.add_resource(OrderListResource, '/api/orders')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
```

### Why It's Problematic

- **Overkill for simple CRUD**: 7+ frameworks for basic operations
- **Steep learning curve**: Requires understanding all frameworks
- **Complex configuration**: Multiple configuration layers
- **Heavy dependencies**: Large dependency tree
- **Overhead**: Frameworks add startup and runtime overhead
- **Vendor lock-in**: Hard to change components
- **Simple tasks become complex**: Creating an endpoint requires understanding multiple frameworks

### How to Fix

**Refactoring Steps:**
1. Evaluate if each framework is necessary
2. Consider simpler alternatives (FastAPI, plain libraries)
3. Use libraries instead of frameworks when possible
4. Build only what you need
5. Keep dependencies minimal

### GOOD Example

```python
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from typing import Optional

class SimpleAPI(BaseHTTPRequestHandler):
    """Simple HTTP API without frameworks."""
    
    def do_GET(self):
        if self.path.startswith('/users/'):
            user_id = int(self.path.split('/')[-1])
            user = self.get_user(user_id)
            if user:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(user).encode())
            else:
                self.send_response(404)
        
        elif self.path == '/users':
            users = self.get_all_users()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(users).encode())
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(content_length))
        
        if self.path == '/users':
            user = self.create_user(data)
            self.send_response(201)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(user).encode())
    
    def get_user(self, user_id: int) -> Optional[dict]:
        with sqlite3.connect('app.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return {'id': row[0], 'name': row[1], 'email': row[2]} if row else None
    
    def get_all_users(self) -> list[dict]:
        with sqlite3.connect('app.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email FROM users")
            return [{'id': row[0], 'name': row[1], 'email': row[2]} for row in cursor.fetchall()]
    
    def create_user(self, data: dict) -> dict:
        with sqlite3.connect('app.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email) VALUES (?, ?)",
                (data['name'], data['email'])
            )
            conn.commit()
            return {'id': cursor.lastrowid, 'name': data['name'], 'email': data['email']}

if __name__ == '__main__':
    # Initialize database
    with sqlite3.connect('app.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                total REAL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()
    
    server = HTTPServer(('localhost', 8000), SimpleAPI)
    server.serve_forever()
```

**Key Changes:**
- No frameworks - just Python standard library
- Clear, straightforward code
- Easy to understand and modify
- Minimal dependencies
- Direct control over behavior
- Lightweight and fast

---

## Detection Checklist

Use this checklist to identify KISS violations in Python code:

### Code Review Questions

- Does this class have multiple responsibilities?
- Is there unnecessary abstraction (interfaces with one implementation)?
- Are you optimizing code before measuring performance?
- Is there code that's never executed (dead code)?
- Are you building features for hypothetical future needs (YAGNI)?
- Are there global mutable variables?
- Does the architecture have too many layers?
- Are you using heavy frameworks for simple problems?
- Is the complexity hidden rather than reduced?
- Could this be simpler while still meeting requirements?

### Automated Detection

- **pylint**: Checks for code complexity and unused code
- **flake8**: Style and complexity analysis
- **radon**: Cyclomatic complexity measurement
- **vulture**: Finds dead code
- **bandit**: Security issues (often from unnecessary complexity)
- **mypy**: Type checking (overly complex types indicate over-engineering)

### Manual Inspection Techniques

1. **Trace the flow**: Can you trace execution easily through the code?
2. **Count layers**: How many layers does data pass through?
3. **Check unused code**: Look for functions/classes never called
4. **Identify "future" features**: Look for code that might be needed someday
5. **Question abstractions**: Does each abstraction simplify or add complexity?
6. **Count dependencies**: Are you importing things you never use?

### Common Symptoms

- **"How does this work?"**: Code is hard to understand
- **"Where is the actual logic?"**: Buried under layers of abstraction
- **"Why are there so many files?"**: Excessive file/module count
- **"What does this do?"**: Unclear function/class purposes
- **Multiple implementations**: Old versions kept "just in case"
- **Complex imports**: Many dependencies for simple functionality
- **Long inheritance chains**: Deep class hierarchies
- **Comments explaining "why"**: Often indicate complexity that should be removed

---

## Language-Specific Notes

### Common Causes in Python

- **Copying from other languages**: Bringing Java/C# patterns to Python
- **"Best practice" dogma**: Applying patterns without context
- **Framework excitement**: New framework, apply it everywhere
- **Learning curve**: Using new features just learned
- **Resume-driven development**: Complex code looks more impressive

### Language Features that Enable Anti-Patterns

- **Dynamic typing**: Makes it easy to create complex object hierarchies
- **Decorators**: Can add hidden complexity to functions
- **Metaclasses**: Powerful but easily abused
- **Multiple inheritance**: Can create complex class hierarchies
- **Dynamic attributes**: Can make code hard to follow

### Framework-Specific Anti-Patterns

- **Django**: Overusing signals, excessive middleware
- **Flask**: Over-engineering with blueprints for simple apps
- **FastAPI**: Over-complicating dependency injection
- **Celery**: Creating complex task chains for simple jobs
- **SQLAlchemy**: Over-abstracting simple queries

### Tooling Support

**Refactoring Tools:**
- **rope**: Refactoring support
- **Rope**: Advanced Python refactoring
- **black**: Code formatting (enforces simplicity)
- **isort**: Import organization

**Analysis Tools:**
- **pylint**: Code complexity analysis
- **flake8**: Style and complexity
- **radon**: Code metrics
- **vulture**: Dead code detection
- **pylint**: Complexity analysis
