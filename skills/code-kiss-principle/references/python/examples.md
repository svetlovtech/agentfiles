# KISS Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Function Design](#example-1-function-design)
- [Example 2: Class Design](#example-2-class-design)
- [Example 3: Algorithm Selection](#example-3-algorithm-selection)
- [Example 4: Data Structures](#example-4-data-structures)
- [Example 5: Error Handling](#example-5-error-handling)
- [Example 6: Async Code](#example-6-async-code)
- [Example 7: Configuration](#example-7-configuration)
- [Example 8: Testing](#example-8-testing)
- [Example 9: String Processing](#example-9-string-processing)
- [Example 10: API Client](#example-10-api-client)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the KISS principle in Python. Each example demonstrates a common violation and the corrected implementation, focusing on simplicity, readability, and avoiding over-engineering.

---

## Example 1: Function Design

### BAD Example: Over-Engineered Function

```python
from typing import Callable, Any, List, Dict, Optional
from functools import wraps
import time
from dataclasses import dataclass

@dataclass
class ExecutionContext:
    function_name: str
    start_time: float
    end_time: float
    execution_time: float
    result: Any

class FunctionExecutor:
    def __init__(self, timeout: Optional[float] = None, retries: int = 0):
        self.timeout = timeout
        self.retries = retries
        self.execution_history: List[ExecutionContext] = []

    def execute_with_tracking(
        self,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> ExecutionContext:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        context = ExecutionContext(
            function_name=func.__name__,
            start_time=start_time,
            end_time=end_time,
            execution_time=end_time - start_time,
            result=result
        )
        self.execution_history.append(context)
        return context

def get_average_from_list(data: List[float]) -> Optional[float]:
    executor = FunctionExecutor()
    if not data:
        return None
    
    total = 0
    count = 0
    
    context = executor.execute_with_tracking(
        lambda: sum(data)
    )
    total = context.result
    count = len(data)
    
    result_context = executor.execute_with_tracking(
        lambda: total / count
    )
    
    return result_context.result
```

**Problems:**
- Uses complex ExecutionContext dataclass unnecessarily
- Creates FunctionExecutor class for simple average calculation
- Introduces lambda wrappers for basic arithmetic operations
- Adds tracking functionality that's not needed
- Makes simple code harder to understand
- Over-abstraction with no actual benefit

### GOOD Example: Simple Function

```python
def get_average(values: list[float]) -> float | None:
    """Calculate the average of a list of numbers.
    
    Returns None if the list is empty.
    """
    if not values:
        return None
    return sum(values) / len(values)
```

**Improvements:**
- Uses Python's built-in `sum()` and `len()` functions
- Clear, readable implementation in one line
- Type hints using modern Python syntax
- Docstring explains behavior and edge case
- No unnecessary classes or tracking
- Easy to understand and maintain

### Explanation

The BAD example demonstrates over-engineering by creating an execution tracking system for a simple average calculation. The GOOD example leverages Python's built-in functions to solve the problem directly and clearly. KISS principle emphasizes using the simplest solution that meets requirements, which in this case is a straightforward arithmetic operation.

---

## Example 2: Class Design

### BAD Example: Over-Designed Class Hierarchy

```python
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable
from enum import Enum

class ValidatorType(Enum):
    RANGE = "range"
    PATTERN = "pattern"
    LENGTH = "length"

@runtime_checkable
class Validator(Protocol):
    def validate(self, value: Any) -> bool:
        ...

class AbstractValidator(ABC):
    def __init__(self, error_message: str):
        self.error_message = error_message
    
    @abstractmethod
    def validate(self, value: Any) -> bool:
        pass
    
    def get_error(self) -> str:
        return self.error_message

class RangeValidator(AbstractValidator):
    def __init__(self, min_val: float, max_val: float, error_message: str):
        super().__init__(error_message)
        self.min_val = min_val
        self.max_val = max_val
    
    def validate(self, value: Any) -> bool:
        try:
            return self.min_val <= float(value) <= self.max_val
        except (ValueError, TypeError):
            return False

class PatternValidator(AbstractValidator):
    def __init__(self, pattern: str, error_message: str):
        super().__init__(error_message)
        import re
        self.pattern = re.compile(pattern)
    
    def validate(self, value: Any) -> bool:
        return bool(self.pattern.match(str(value)))

class LengthValidator(AbstractValidator):
    def __init__(self, min_len: int, max_len: int, error_message: str):
        super().__init__(error_message)
        self.min_len = min_len
        self.max_len = max_len
    
    def validate(self, value: Any) -> bool:
        return self.min_len <= len(str(value)) <= self.max_len

class ValidatorFactory:
    @staticmethod
    def create_validator(validator_type: ValidatorType, **kwargs) -> AbstractValidator:
        if validator_type == ValidatorType.RANGE:
            return RangeValidator(
                kwargs['min_val'],
                kwargs['max_val'],
                kwargs.get('error_message', 'Value out of range')
            )
        elif validator_type == ValidatorType.PATTERN:
            return PatternValidator(
                kwargs['pattern'],
                kwargs.get('error_message', 'Invalid format')
            )
        elif validator_type == ValidatorType.LENGTH:
            return LengthValidator(
                kwargs['min_len'],
                kwargs['max_len'],
                kwargs.get('error_message', 'Invalid length')
            )
        else:
            raise ValueError(f"Unknown validator type: {validator_type}")
```

**Problems:**
- Creates abstract base class unnecessarily
- Uses Protocol for runtime checking that's never used
- Enum for validator types adds complexity
- Factory pattern for simple validator creation
- Too many classes for simple validation logic
- Makes it harder to understand and use

### GOOD Example: Simple Validation Functions

```python
import re

def validate_range(value: float, min_val: float, max_val: float) -> bool:
    """Check if a value is within the specified range."""
    try:
        return min_val <= float(value) <= max_val
    except (ValueError, TypeError):
        return False

def validate_pattern(value: str, pattern: str) -> bool:
    """Check if a value matches the given regex pattern."""
    return bool(re.match(pattern, str(value)))

def validate_length(value: str, min_len: int, max_len: int) -> bool:
    """Check if a string's length is within the specified bounds."""
    return min_len <= len(str(value)) <= max_len
```

**Improvements:**
- Simple functions for each validation type
- No unnecessary class hierarchy
- Clear function names that describe what they do
- Easy to test and use
- Pythonic approach using built-in and standard library functions
- Less code, more clarity

### Explanation

The BAD example over-engineers validation with multiple classes, protocols, enums, and factory patterns. The GOOD example uses simple functions that leverage Python's strengths. KISS favors straightforward solutions that are easy to understand and maintain over complex abstractions that don't provide real benefits.

---

## Example 3: Algorithm Selection

### BAD Example: Prematurely Optimized Algorithm

```python
from typing import List, Any

class OptimizedSearch:
    def __init__(self):
        self.cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
    
    def binary_search(self, arr: List[Any], target: Any) -> int:
        """Optimized binary search with caching."""
        cache_key = (tuple(arr), target)
        
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        left, right = 0, len(arr) - 1
        while left <= right:
            mid = (left + right) // 2
            mid_val = arr[mid]
            
            if mid_val == target:
                self.cache[cache_key] = mid
                return mid
            elif mid_val < target:
                left = mid + 1
            else:
                right = mid - 1
        
        self.cache[cache_key] = -1
        return -1
    
    def get_cache_stats(self) -> dict:
        return {
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
        }

def find_item(items: List[str], search_term: str) -> int:
    """Find an item in a list using optimized binary search."""
    items.sort()  # Sort for binary search
    searcher = OptimizedSearch()
    index = searcher.binary_search(items, search_term)
    return index
```

**Problems:**
- Uses binary search with unnecessary caching
- Caches based on entire array tuple (expensive memory usage)
- Sorts the array every time (destructive operation)
- Complex class for simple search operation
- Cache statistics that are never used
- Over-engineering for a problem that Python's `in` operator handles efficiently
- Assumes sorted data which may not be the case

### GOOD Example: Simple Search

```python
def find_item(items: list[str], search_term: str) -> int:
    """Find the index of an item in a list.
    
    Returns -1 if not found.
    """
    try:
        return items.index(search_term)
    except ValueError:
        return -1

# Or even simpler if you just need to check existence:
def contains_item(items: list[str], search_term: str) -> bool:
    """Check if an item exists in a list."""
    return search_term in items
```

**Improvements:**
- Uses Python's built-in `index()` method
- Clear and readable implementation
- No unnecessary caching or sorting
- Simpler is better - Python's `in` and `index()` are highly optimized
- Memory efficient (no caching)
- Handles unsorted lists correctly

### Explanation

The BAD example implements binary search with caching, which is premature optimization. Python's built-in list operations are already optimized in C and are fast for typical use cases. The GOOD example uses Python's built-in methods, which are both simple and performant. KISS emphasizes using the simplest solution that works well enough, not optimizing prematurely without measured need.

---

## Example 4: Data Structures

### BAD Example: Over-Complicated Data Management

```python
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import json

class DataType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"

@dataclass
class DataField:
    name: str
    value: Any
    data_type: DataType
    required: bool = True
    validator: Optional[callable] = None

@dataclass
class DataRecord:
    fields: List[DataField] = field(default_factory=list)
    
    def add_field(self, field: DataField):
        self.fields.append(field)
    
    def get_field(self, name: str) -> Optional[DataField]:
        for field in self.fields:
            if field.name == name:
                return field
        return None
    
    def get_value(self, name: str) -> Optional[Any]:
        field = self.get_field(name)
        return field.value if field else None
    
    def to_dict(self) -> Dict[str, Any]:
        return {field.name: field.value for field in self.fields}
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

class DataManager:
    def __init__(self):
        self.records: List[DataRecord] = []
    
    def create_record(self) -> DataRecord:
        record = DataRecord()
        self.records.append(record)
        return record
    
    def add_record(self, record: DataRecord):
        self.records.append(record)
    
    def find_record(self, index: int) -> Optional[DataRecord]:
        if 0 <= index < len(self.records):
            return self.records[index]
        return None

# Usage
def create_user_data():
    manager = DataManager()
    record = manager.create_record()
    
    record.add_field(DataField(
        name="name",
        value="John Doe",
        data_type=DataType.STRING
    ))
    
    record.add_field(DataField(
        name="age",
        value=30,
        data_type=DataType.INTEGER
    ))
    
    return record.to_json()
```

**Problems:**
- Creates complex DataField and DataRecord classes unnecessarily
- Uses enum for data types that's never validated
- DataManager class adds unnecessary indirection
- Too many layers of abstraction for simple data storage
- Verbose and hard to read
- Python has built-in dict and list that work perfectly

### GOOD Example: Simple Data Structures

```python
def create_user_data() -> dict:
    """Create a simple user data dictionary."""
    return {
        'name': 'John Doe',
        'age': 30
    }

def create_user(name: str, age: int, email: str | None = None) -> dict:
    """Create a user dictionary with common fields."""
    user = {'name': name, 'age': age}
    if email:
        user['email'] = email
    return user

def get_user_value(user: dict, key: str, default=None):
    """Get a value from user dict with default."""
    return user.get(key, default)
```

**Improvements:**
- Uses Python's built-in dict directly
- Simple, clear functions
- No unnecessary classes or enums
- Pythonic and idiomatic
- Easy to understand and modify
- Leverages Python's dict methods

### Explanation

The BAD example creates multiple classes to manage simple data that Python's built-in dict handles elegantly. The GOOD example uses dictionaries directly, which are Pythonic, simple, and perfectly suitable for this use case. KISS favors using language features and standard library functions rather than building custom abstractions.

---

## Example 5: Error Handling

### BAD Example: Over-Engineered Error Handling

```python
from typing import Optional, Type, Union, List
from dataclasses import dataclass
from enum import Enum
import traceback

class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class ErrorContext:
    function_name: str
    line_number: int
    file_name: str
    traceback_str: str

@dataclass
class ErrorResult:
    success: bool
    error: Optional[Exception] = None
    error_message: Optional[str] = None
    error_context: Optional[ErrorContext] = None
    severity: ErrorSeverity = ErrorSeverity.ERROR
    data: Optional[Any] = None

class ErrorHandler:
    def __init__(self, enable_logging: bool = True, log_file: Optional[str] = None):
        self.enable_logging = enable_logging
        self.log_file = log_file
        self.error_history: List[ErrorResult] = []
    
    def execute_with_handling(
        self,
        func: callable,
        *args,
        expected_exceptions: Optional[List[Type[Exception]]] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        **kwargs
    ) -> ErrorResult:
        try:
            result = func(*args, **kwargs)
            return ErrorResult(success=True, data=result)
        
        except Exception as e:
            if expected_exceptions and not any(isinstance(e, exc) for exc in expected_exceptions):
                raise
            
            tb = traceback.extract_tb(e.__traceback__)[-1]
            context = ErrorContext(
                function_name=tb.name,
                line_number=tb.lineno,
                file_name=tb.filename,
                traceback_str=traceback.format_exc()
            )
            
            error_result = ErrorResult(
                success=False,
                error=e,
                error_message=str(e),
                error_context=context,
                severity=severity
            )
            
            self.error_history.append(error_result)
            return error_result

def divide_numbers(a: float, b: float) -> float:
    """Divide two numbers with comprehensive error handling."""
    handler = ErrorHandler(enable_logging=True)
    
    result = handler.execute_with_handling(
        lambda: a / b,
        expected_exceptions=[ZeroDivisionError, TypeError],
        severity=ErrorSeverity.ERROR
    )
    
    if result.success:
        return result.data
    else:
        print(f"Error occurred: {result.error_message}")
        if result.error_context:
            print(f"Context: {result.error_context.function_name}")
        return None
```

**Problems:**
- Creates complex error handling infrastructure
- Uses enums and dataclasses for error metadata that's rarely needed
- Wraps simple operations in lambda functions
- Excessive error context collection for simple division
- Makes code harder to read and understand
- Most error details are never used in this simple case

### GOOD Example: Simple Error Handling

```python
def divide_numbers(a: float, b: float) -> float:
    """Divide two numbers. Raises ValueError for division by zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

# Or if you prefer to return None for errors:
def divide_numbers_safe(a: float, b: float) -> float | None:
    """Divide two numbers safely. Returns None on error."""
    try:
        return a / b
    except (TypeError, ZeroDivisionError):
        return None
```

**Improvements:**
- Simple, direct error handling
- Clear error messages
- Either raises exceptions or returns None based on use case
- No unnecessary classes or infrastructure
- Easy to understand and maintain
- Pythonic approach

### Explanation

The BAD example over-engineers error handling with custom classes, enums, and extensive context collection for a simple division operation. The GOOD example uses Python's built-in exception handling, which is clear, simple, and sufficient. KISS emphasizes using appropriate error handling without adding unnecessary complexity.

---

## Example 6: Async Code

### BAD Example: Over-Complicated Async Pattern

```python
import asyncio
from typing import List, Any, Callable, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
import time

@dataclass
class TaskResult:
    task_id: str
    success: bool
    result: Any
    execution_time: float
    error: Optional[Exception] = None

class AsyncTaskManager:
    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.results: List[TaskResult] = []
    
    async def execute_with_semaphore(
        self,
        task_id: str,
        coro: Callable,
        *args,
        **kwargs
    ) -> TaskResult:
        async with self.semaphore:
            start_time = time.time()
            try:
                result = await coro(*args, **kwargs)
                execution_time = time.time() - start_time
                
                task_result = TaskResult(
                    task_id=task_id,
                    success=True,
                    result=result,
                    execution_time=execution_time
                )
                self.results.append(task_result)
                return task_result
                
            except Exception as e:
                execution_time = time.time() - start_time
                task_result = TaskResult(
                    task_id=task_id,
                    success=False,
                    result=None,
                    execution_time=execution_time,
                    error=e
                )
                self.results.append(task_result)
                return task_result
    
    async def execute_batch(
        self,
        tasks: List[tuple[str, Callable, tuple, dict]]
    ) -> List[TaskResult]:
        return await asyncio.gather(
            *[self.execute_with_semaphore(tid, coro, *args, **kwargs)
              for tid, coro, args, kwargs in tasks],
            return_exceptions=True
        )

async def fetch_data(url: str, delay: float) -> dict:
    """Simulate fetching data from a URL with delay."""
    await asyncio.sleep(delay)
    return {'url': url, 'data': 'sample data'}

async def fetch_all_data(urls: List[str]) -> List[dict]:
    """Fetch data from multiple URLs with complex async management."""
    manager = AsyncTaskManager(max_concurrent=5)
    
    tasks = [
        (f'task_{i}', fetch_data, (url,), {'delay': 0.1})
        for i, url in enumerate(urls)
    ]
    
    results = await manager.execute_batch(tasks)
    
    successful_results = []
    for result in results:
        if result.success and isinstance(result, TaskResult):
            successful_results.append(result.result)
    
    return successful_results
```

**Problems:**
- Creates complex TaskManager class for simple async operations
- Uses dataclass for task results with metadata that's not needed
- Semaphore management adds unnecessary complexity
- Converts simple async tasks into tuples and dictionaries
- Makes code harder to read and understand
- asyncio.gather can handle concurrency directly

### GOOD Example: Simple Async Code

```python
import asyncio

async def fetch_data(url: str, delay: float) -> dict:
    """Simulate fetching data from a URL with delay."""
    await asyncio.sleep(delay)
    return {'url': url, 'data': 'sample data'}

async def fetch_all_data(urls: list[str]) -> list[dict]:
    """Fetch data from multiple URLs concurrently."""
    tasks = [fetch_data(url, 0.1) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out exceptions
    return [r for r in results if isinstance(r, dict)]

# If you need to limit concurrency:
async def fetch_all_data_limited(urls: list[str], max_concurrent: int = 5) -> list[dict]:
    """Fetch data from multiple URLs with concurrency limit."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def fetch_with_limit(url: str):
        async with semaphore:
            return await fetch_data(url, 0.1)
    
    tasks = [fetch_with_limit(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]
```

**Improvements:**
- Direct use of asyncio.gather for concurrent execution
- Simple, readable code
- Uses asyncio primitives directly
- Only adds complexity when actually needed (concurrency limit)
- Clear and maintainable
- Pythonic async/await patterns

### Explanation

The BAD example wraps simple async operations in a complex manager class with unnecessary metadata and tracking. The GOOD example uses asyncio's built-in concurrency features directly, which are simple and sufficient. KISS favors using language features directly rather than building complex wrappers around them.

---

## Example 7: Configuration

### BAD Example: Over-Engineered Configuration System

```python
import os
import json
import yaml
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

class ConfigSource(Enum):
    ENV = "environment"
    FILE = "file"
    DEFAULTS = "defaults"

@dataclass
class ConfigValue:
    value: Any
    source: ConfigSource
    is_overridden: bool = False

@dataclass
class ConfigSchema:
    key: str
    value_type: type
    required: bool = True
    default: Any = None
    validator: Optional[callable] = None

class ConfigLoader(ABC):
    @abstractmethod
    def load(self, source: str) -> Dict[str, Any]:
        pass

class JsonConfigLoader(ConfigLoader):
    def load(self, source: str) -> Dict[str, Any]:
        with open(source, 'r') as f:
            return json.load(f)

class YamlConfigLoader(ConfigLoader):
    def load(self, source: str) -> Dict[str, Any]:
        with open(source, 'r') as f:
            return yaml.safe_load(f)

class EnvironmentConfigLoader(ConfigLoader):
    def load(self, source: str) -> Dict[str, Any]:
        prefix = source
        return {k: v for k, v in os.environ.items() if k.startswith(prefix)}

class ConfigurationManager:
    def __init__(self, schema: List[ConfigSchema]):
        self.schema = schema
        self.config_values: Dict[str, ConfigValue] = {}
        self.loaders: Dict[str, ConfigLoader] = {
            'json': JsonConfigLoader(),
            'yaml': YamlConfigLoader(),
            'env': EnvironmentConfigLoader()
        }
    
    def add_loader(self, name: str, loader: ConfigLoader):
        self.loaders[name] = loader
    
    def load_from_source(self, source_type: str, source: str):
        loader = self.loaders.get(source_type)
        if not loader:
            raise ValueError(f"Unknown loader type: {source_type}")
        
        values = loader.load(source)
        for key, value in values.items():
            config_value = ConfigValue(
                value=value,
                source=ConfigSource.FILE
            )
            self.config_values[key] = config_value
    
    def load_from_env(self, prefix: str = ""):
        loader = EnvironmentConfigLoader()
        values = loader.load(prefix)
        for key, value in values.items():
            config_value = ConfigValue(
                value=value,
                source=ConfigSource.ENV
            )
            self.config_values[key] = config_value
    
    def get(self, key: str, default: Any = None) -> Any:
        config_value = self.config_values.get(key)
        if config_value:
            return config_value.value
        return default
    
    def get_with_source(self, key: str) -> Optional[ConfigValue]:
        return self.config_values.get(key)

# Usage
def initialize_config():
    schema = [
        ConfigSchema('database_url', str, True),
        ConfigSchema('debug', bool, False, False),
        ConfigSchema('timeout', int, False, 30)
    ]
    
    manager = ConfigurationManager(schema)
    manager.load_from_env('APP_')
    manager.load_from_source('yaml', 'config.yaml')
    
    return manager

def get_database_url(manager: ConfigurationManager) -> str:
    return manager.get('database_url', 'sqlite:///:memory:')
```

**Problems:**
- Complex configuration manager with abstract base classes
- Multiple loader types for simple config loading
- Schema validation that's not actually used
- Enum for config sources adds unnecessary complexity
- Over-abstraction for a simple need
- Makes it harder to understand and maintain

### GOOD Example: Simple Configuration

```python
import os
from pathlib import Path

def load_config(config_path: str | None = None) -> dict:
    """Load configuration from environment variables and optional file."""
    config = {
        'database_url': os.getenv('DATABASE_URL', 'sqlite:///:memory:'),
        'debug': os.getenv('DEBUG', 'false').lower() == 'true',
        'timeout': int(os.getenv('TIMEOUT', '30'))
    }
    
    if config_path:
        try:
            import json
            file_config = json.loads(Path(config_path).read_text())
            config.update(file_config)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    
    return config

def get_config() -> dict:
    """Get application configuration."""
    return load_config('config.json')
```

**Improvements:**
- Simple function-based configuration
- Environment variables as primary source
- Optional file override
- Clear and readable
- No unnecessary abstractions
- Easy to extend if needed

### Explanation

The BAD example creates an over-engineered configuration system with multiple classes, loaders, schemas, and validation. The GOOD example uses a simple function that reads from environment variables and an optional file, which is sufficient for most Python applications. KISS favors simple solutions that meet actual requirements over complex infrastructure.

---

## Example 8: Testing

### BAD Example: Over-Engineered Test Framework

```python
import unittest
from typing import List, Callable, Any, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum

class TestPhase(Enum):
    SETUP = "setup"
    EXECUTE = "execute"
    TEARDOWN = "teardown"
    ASSERT = "assert"

@dataclass
class TestResult:
    test_name: str
    phase: TestPhase
    success: bool
    duration: float
    error: Optional[Exception] = None
    message: str = ""

class TestCaseBase(ABC):
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.results: List[TestResult] = []
    
    @abstractmethod
    def setup(self):
        pass
    
    @abstractmethod
    def execute(self):
        pass
    
    @abstractmethod
    def teardown(self):
        pass
    
    def run(self) -> List[TestResult]:
        import time
        start_time = time.time()
        
        try:
            self.setup()
            self.results.append(TestResult(
                test_name=self.test_name,
                phase=TestPhase.SETUP,
                success=True,
                duration=time.time() - start_time
            ))
        except Exception as e:
            self.results.append(TestResult(
                test_name=self.test_name,
                phase=TestPhase.SETUP,
                success=False,
                duration=time.time() - start_time,
                error=e
            ))
            return self.results
        
        execute_start = time.time()
        try:
            self.execute()
            self.results.append(TestResult(
                test_name=self.test_name,
                phase=TestPhase.EXECUTE,
                success=True,
                duration=time.time() - execute_start
            ))
        except Exception as e:
            self.results.append(TestResult(
                test_name=self.test_name,
                phase=TestPhase.EXECUTE,
                success=False,
                duration=time.time() - execute_start,
                error=e
            ))
        
        try:
            self.teardown()
            self.results.append(TestResult(
                test_name=self.test_name,
                phase=TestPhase.TEARDOWN,
                success=True,
                duration=time.time() - start_time
            ))
        except Exception as e:
            self.results.append(TestResult(
                test_name=self.test_name,
                phase=TestPhase.TEARDOWN,
                success=False,
                duration=time.time() - start_time,
                error=e
            ))
        
        return self.results

class CalculatorTest(TestCaseBase):
    def __init__(self):
        super().__init__("CalculatorTest")
        self.calculator = None
    
    def setup(self):
        self.calculator = SimpleCalculator()
    
    def execute(self):
        result = self.calculator.add(2, 3)
        assert result == 5, f"Expected 5, got {result}"
        
        result = self.calculator.multiply(4, 5)
        assert result == 20, f"Expected 20, got {result}"
    
    def teardown(self):
        self.calculator = None

class SimpleCalculator:
    def add(self, a, b):
        return a + b
    
    def multiply(self, a, b):
        return a * b

def run_custom_tests():
    test = CalculatorTest()
    results = test.run()
    for result in results:
        print(f"{result.phase}: {result.success}")
    return all(r.success for r in results)
```

**Problems:**
- Creates custom test framework instead of using pytest/unittest
- Complex result tracking with enums and dataclasses
- Abstract base class for simple test cases
- Manual phase management (setup/execute/teardown)
- Verbose and hard to read
- Reinvents standard library functionality

### GOOD Example: Simple Tests

```python
import pytest

class Calculator:
    def add(self, a: float, b: float) -> float:
        return a + b
    
    def multiply(self, a: float, b: float) -> float:
        return a * b

def test_calculator_add():
    """Test calculator addition."""
    calc = Calculator()
    assert calc.add(2, 3) == 5
    assert calc.add(-1, 1) == 0
    assert calc.add(0, 0) == 0

def test_calculator_multiply():
    """Test calculator multiplication."""
    calc = Calculator()
    assert calc.multiply(4, 5) == 20
    assert calc.multiply(-2, 3) == -6
    assert calc.multiply(0, 100) == 0

@pytest.fixture
def calculator():
    """Fixture providing a calculator instance."""
    return Calculator()

def test_calculator_with_fixture(calculator):
    """Test calculator using pytest fixture."""
    assert calculator.add(2, 3) == 5
    assert calculator.multiply(4, 5) == 20
```

**Improvements:**
- Uses pytest, the standard Python testing framework
- Simple, clear test functions
- Uses fixtures for setup/teardown when needed
- Pythonic and idiomatic
- Easy to understand and maintain
- Leverages pytest's powerful features

### Explanation

The BAD example creates a custom test framework instead of using Python's standard testing tools. The GOOD example uses pytest, which is simple, powerful, and well-understood. KISS favors using established tools and libraries rather than building custom implementations.

---

## Example 9: String Processing

### BAD Example: Over-Engineered String Processing

```python
import re
from typing import List, Dict, Optional, Callable, Pattern
from dataclasses import dataclass
from enum import Enum

class StringOperation(Enum):
    TRIM = "trim"
    UPPER = "upper"
    LOWER = "lower"
    REPLACE = "replace"
    REMOVE_PATTERN = "remove_pattern"

@dataclass
class ProcessingRule:
    operation: StringOperation
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    enabled: bool = True

class StringProcessor:
    def __init__(self):
        self.rules: List[ProcessingRule] = []
        self.compiled_patterns: Dict[str, Pattern] = {}
    
    def add_rule(self, rule: ProcessingRule):
        self.rules.append(rule)
        if rule.pattern and rule.operation == StringOperation.REMOVE_PATTERN:
            self.compiled_patterns[rule.pattern] = re.compile(rule.pattern)
    
    def process(self, text: str) -> str:
        result = text
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            result = self._apply_rule(rule, result)
        
        return result
    
    def _apply_rule(self, rule: ProcessingRule, text: str) -> str:
        if rule.operation == StringOperation.TRIM:
            return text.strip()
        elif rule.operation == StringOperation.UPPER:
            return text.upper()
        elif rule.operation == StringOperation.LOWER:
            return text.lower()
        elif rule.operation == StringOperation.REPLACE:
            if rule.pattern and rule.replacement:
                return text.replace(rule.pattern, rule.replacement)
            return text
        elif rule.operation == StringOperation.REMOVE_PATTERN:
            if rule.pattern in self.compiled_patterns:
                return self.compiled_patterns[rule.pattern].sub('', text)
            return text
        return text

def normalize_user_input(input_text: str) -> str:
    """Normalize user input with complex processing rules."""
    processor = StringProcessor()
    
    processor.add_rule(ProcessingRule(operation=StringOperation.TRIM))
    processor.add_rule(ProcessingRule(operation=StringOperation.LOWER))
    processor.add_rule(ProcessingRule(
        operation=StringOperation.REMOVE_PATTERN,
        pattern=r'\s+',
        enabled=True
    ))
    processor.add_rule(ProcessingRule(
        operation=StringOperation.REPLACE,
        pattern='  ',
        replacement=' '
    ))
    
    return processor.process(input_text)
```

**Problems:**
- Creates complex StringProcessor class for simple string operations
- Uses enum for operation types
- Compiles regex patterns unnecessarily
- Rules system adds complexity without benefit
- Makes simple string transformations hard to understand
- Python has built-in string methods that handle most cases

### GOOD Example: Simple String Processing

```python
import re

def normalize_user_input(text: str) -> str:
    """Normalize user input: trim, lowercase, and clean whitespace."""
    text = text.strip().lower()
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    return text

def clean_email(email: str) -> str:
    """Clean and normalize email address."""
    return email.strip().lower()

def format_phone(phone: str) -> str:
    """Format phone number by removing non-digit characters."""
    return re.sub(r'\D', '', phone)
```

**Improvements:**
- Direct use of Python's string methods
- Simple, clear functions
- Uses regex only when needed
- Easy to understand and modify
- Pythonic and idiomatic
- Less code, more clarity

### Explanation

The BAD example creates a complex string processing system with rules, enums, and compiled patterns for simple string operations. The GOOD example uses Python's built-in string methods and simple regex when needed. KISS favors using language features directly rather than building complex processing systems.

---

## Example 10: API Client

### BAD Example: Over-Engineered API Client

```python
import requests
import json
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
import time

class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

class AuthType(Enum):
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"

@dataclass
class RequestConfig:
    url: str
    method: HttpMethod
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    data: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    auth_type: AuthType = AuthType.NONE
    auth_value: Optional[str] = None
    timeout: float = 30.0
    retries: int = 3
    retry_delay: float = 1.0

@dataclass
class Response:
    status_code: int
    data: Any
    headers: Dict[str, str]
    elapsed_time: float
    success: bool

class ApiClient:
    def __init__(self, base_url: str, default_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip('/')
        self.default_headers = default_headers or {}
        self.session = requests.Session()
        self.request_history: List[RequestConfig] = []
        self.response_history: List[Response] = []
    
    def execute(self, config: RequestConfig) -> Response:
        url = f"{self.base_url}/{config.url.lstrip('/')}"
        headers = {**self.default_headers, **config.headers}
        
        # Add authentication
        if config.auth_type == AuthType.BEARER:
            headers['Authorization'] = f"Bearer {config.auth_value}"
        elif config.auth_type == AuthType.API_KEY:
            headers['X-API-Key'] = config.auth_value
        
        start_time = time.time()
        
        # Retry logic
        last_exception = None
        for attempt in range(config.retries + 1):
            try:
                response = self.session.request(
                    method=config.method.value,
                    url=url,
                    headers=headers,
                    params=config.params,
                    data=config.data,
                    json=config.json_data,
                    timeout=config.timeout
                )
                
                elapsed = time.time() - start_time
                
                result = Response(
                    status_code=response.status_code,
                    data=response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
                    headers=dict(response.headers),
                    elapsed_time=elapsed,
                    success=200 <= response.status_code < 300
                )
                
                self.request_history.append(config)
                self.response_history.append(result)
                
                return result
                
            except Exception as e:
                last_exception = e
                if attempt < config.retries:
                    time.sleep(config.retry_delay)
                    continue
                else:
                    raise last_exception

class UserService:
    def __init__(self, client: ApiClient):
        self.client = client
    
    def get_user(self, user_id: str) -> Dict[str, Any]:
        config = RequestConfig(
            url=f'/users/{user_id}',
            method=HttpMethod.GET
        )
        response = self.client.execute(config)
        if response.success:
            return response.data
        else:
            raise Exception(f"Failed to fetch user: {response.status_code}")
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        config = RequestConfig(
            url='/users',
            method=HttpMethod.POST,
            json_data=user_data
        )
        response = self.client.execute(config)
        if response.success:
            return response.data
        else:
            raise Exception(f"Failed to create user: {response.status_code}")
```

**Problems:**
- Complex API client with multiple classes and enums
- RequestConfig dataclass with many fields
- Custom retry logic that requests library already handles
- Response wrapping adds unnecessary layer
- History tracking that's rarely used
- Makes simple API calls overly complex
- Requests library already provides most of this functionality

### GOOD Example: Simple API Client

```python
import requests

class ApiClient:
    """Simple API client using requests."""
    
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
    
    def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> requests.Response:
        """Make an API request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop('headers', {})
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=30,
            **kwargs
        )
        response.raise_for_status()
        return response

class UserService:
    """User API service."""
    
    def __init__(self, api_key: str):
        self.client = ApiClient('https://api.example.com', api_key)
    
    def get_user(self, user_id: str) -> dict:
        """Get user by ID."""
        response = self.client.request('GET', f'users/{user_id}')
        return response.json()
    
    def create_user(self, user_data: dict) -> dict:
        """Create a new user."""
        response = self.client.request(
            'POST',
            'users',
            json=user_data
        )
        return response.json()
```

**Improvements:**
- Simple API client that wraps requests directly
- Leverages requests' built-in features (timeout, error handling)
- Clear, readable code
- No unnecessary enums or dataclasses
- Easy to understand and extend
- Follows Python conventions

### Explanation

The BAD example over-engineers an API client with complex configuration, retry logic, and response wrapping. The GOOD example uses a simple wrapper around requests library, which already provides most needed functionality. KISS favors using well-designed libraries directly rather than building complex abstractions around them.

---

## Language-Specific Notes

### Idioms and Patterns

- **List comprehensions**: Use for simple transformations instead of map/filter
- **Context managers**: Use `with` for resource management
- **Decorators**: Use for cross-cutting concerns, not over-complicating functions
- **Generator expressions**: Use for lazy evaluation instead of creating lists
- **Dictionary comprehensions**: Use for creating dicts from other iterables

### Language Features

**Features that help:**
- **Built-in functions**: `sum()`, `len()`, `max()`, `min()` reduce complexity
- **List/dict comprehensions**: Expressive and readable for common operations
- `with` statement: Automatic resource cleanup
- **Type hints**: Make code clearer without adding complexity
- **f-strings**: Simple string formatting

**Features that hinder:**
- **Multiple inheritance**: Can create complex class hierarchies
- **Metaclasses**: Often overkill for most use cases
- **Complex decorators**: Can make code hard to follow
- **Dynamic attribute access**: Can make code unclear

### Framework Considerations

- **Django**: ORM abstraction can hide SQL, but often necessary for web apps
- **Flask**: Minimalist framework encourages simple approaches
- **FastAPI**: Type hints and dependency injection add clarity, not complexity
- **Pytest**: Powerful but simple to use for basic tests
- **SQLAlchemy**: ORM abstraction is appropriate for database work

### Common Pitfalls

1. **Overusing classes**: Functions are often sufficient in Python
2. **Premature abstraction**: Create abstractions only when you have multiple implementations
3. **Ignoring built-ins**: Python has many powerful built-in functions and libraries
4. **Complex type hints**: Keep type hints simple and readable
5. **Over-documenting simple code**: Code should be self-explanatory
6. **Reinventing the wheel**: Check standard library and popular packages first
7. **Over-engineering for "flexibility"**: Build for current needs, not hypothetical future ones
8. **Pattern obsession**: Use patterns when they solve actual problems
9. **Complex one-liners**: Prefer readability over cleverness
10. **Over-wrappering**: Wrapping everything in classes when functions would suffice

### Python-Specific Anti-Patterns

- **God classes**: Classes that do too much (violates single responsibility)
- **Utility classes**: Static method classes that should just be functions
- **Over-encapsulation**: Private methods and attributes when not needed
- **Complex inheritance**: Deep class hierarchies
- **Namespace pollution**: Importing too many things into module scope
- **Magic methods abuse**: Using dunder methods inappropriately
- **Property overuse**: Using properties when simple attributes would work
