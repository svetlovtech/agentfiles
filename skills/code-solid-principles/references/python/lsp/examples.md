# LSP Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Shape Hierarchy Problem](#example-1-shape-hierarchy-problem)
- [Example 2: Database Connection Hierarchy](#example-2-database-connection-hierarchy)
- [Example 3: Bird Hierarchy](#example-3-bird-hierarchy)
- [Example 4: Collection with Empty Return](#example-4-collection-with-empty-return)
- [Example 5: Payment Processors](#example-5-payment-processors)
- [Example 6: Stack Inheritance](#example-6-stack-inheritance)
- [Example 7: Logging Hierarchy](#example-7-logging-hierarchy)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the LSP (Liskov Substitution Principle) principle in Python. Each example demonstrates a common violation and the corrected implementation.

## Example 1: Shape Hierarchy Problem

### BAD Example: Rectangle and Square Inheritance

```python
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def set_width(self, width):
        self.width = width

    def set_height(self, height):
        self.height = height

    def get_area(self):
        return self.width * self.height


class Square(Rectangle):
    def set_width(self, width):
        self.width = width
        self.height = width

    def set_height(self, height):
        self.width = height
        self.height = height


def enlarge_rectangle(rect, factor):
    rect.set_width(rect.width * factor)
    rect.set_height(rect.height * factor)
    assert rect.get_area() == rect.width * rect.height


rect = Rectangle(10, 20)
enlarge_rectangle(rect, 2)

square = Square(10)
enlarge_rectangle(square, 2)
```

**Problems:**
- Square can't maintain its invariant when used as Rectangle
- Client code expecting Rectangle behavior breaks with Square
- Modifying one dimension unexpectedly affects the other
- Subclass violates base class contract

### GOOD Example: Composition-Based Shape Design

```python
from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def get_area(self):
        pass

    @abstractmethod
    def scale(self, factor):
        pass


class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def set_width(self, width):
        self.width = width

    def set_height(self, height):
        self.height = height

    def get_area(self):
        return self.width * self.height

    def scale(self, factor):
        self.width *= factor
        self.height *= factor


class Square(Shape):
    def __init__(self, side):
        self.side = side

    def set_side(self, side):
        self.side = side

    def get_area(self):
        return self.side * self.side

    def scale(self, factor):
        self.side *= factor


def enlarge_shape(shape, factor):
    shape.scale(factor)
```

**Improvements:**
- Rectangle and Square share common interface but independent implementations
- Each shape maintains its own invariants
- Client code works with any shape without knowing specifics
- Substitutability preserved

### Explanation

The BAD example violates LSP because Square cannot be substituted for Rectangle without breaking client expectations. When client code modifies width and height independently, Square's behavior violates the Rectangle contract. The GOOD example uses composition with a common abstract base class, allowing each shape to implement its own behavior while maintaining substitutability through the Shape interface.

---

## Example 2: Database Connection Hierarchy

### BAD Example: Forced Transaction Methods

```python
class DatabaseConnection:
    def __init__(self, connection_string):
        self.connect(connection_string)

    def connect(self, connection_string):
        pass

    def execute_query(self, query):
        pass

    def disconnect(self):
        pass

    def begin_transaction(self):
        pass

    def commit_transaction(self):
        pass


class MySQLConnection(DatabaseConnection):
    def begin_transaction(self):
        print("BEGIN TRANSACTION")

    def commit_transaction(self):
        print("COMMIT")


class PostgreSQLConnection(DatabaseConnection):
    def begin_transaction(self):
        raise NotImplementedError("PostgreSQL uses autocommit")

    def commit_transaction(self):
        raise NotImplementedError("PostgreSQL uses autocommit")


def process_with_transaction(conn):
    conn.begin_transaction()
    conn.execute_query("INSERT INTO users VALUES (1, 'John')")
    conn.commit_transaction()
```

**Problems:**
- PostgreSQLConnection throws exceptions for inherited methods
- Client code must check implementation type
- Cannot use DatabaseConnection polymorphically
- Base class assumes all databases support transactions

### GOOD Example: Interface Segregation for Transactions

```python
from abc import ABC, abstractmethod


class DatabaseConnection(ABC):
    @abstractmethod
    def connect(self, connection_string):
        pass

    @abstractmethod
    def execute_query(self, query):
        pass

    @abstractmethod
    def disconnect(self):
        pass


class TransactionalConnection(DatabaseConnection):
    @abstractmethod
    def begin_transaction(self):
        pass

    @abstractmethod
    def commit_transaction(self):
        pass


class MySQLConnection(TransactionalConnection):
    def connect(self, connection_string):
        print(f"Connecting to MySQL: {connection_string}")

    def execute_query(self, query):
        print(f"Executing: {query}")

    def disconnect(self):
        print("Disconnecting MySQL")

    def begin_transaction(self):
        print("BEGIN TRANSACTION")

    def commit_transaction(self):
        print("COMMIT")


class PostgreSQLConnection(DatabaseConnection):
    def connect(self, connection_string):
        print(f"Connecting to PostgreSQL: {connection_string}")

    def execute_query(self, query):
        print(f"Executing: {query}")

    def disconnect(self):
        print("Disconnecting PostgreSQL")


def process_with_transaction(conn):
    conn.begin_transaction()
    conn.execute_query("INSERT INTO users VALUES (1, 'John')")
    conn.commit_transaction()
```

**Improvements:**
- Separate interface for transactional databases
- PostgreSQL doesn't inherit unused methods
- Client code can safely use TransactionalConnection type
- No exception throwing for unsupported features

### Explanation

The BAD example forces all database connections to implement transaction methods, even when they don't support them, leading to runtime exceptions. The GOOD example creates a separate TransactionalConnection interface that extends the base, allowing PostgreSQL to implement only what it needs while maintaining LSP compliance through proper interface design.

---

## Example 3: Bird Hierarchy

### BAD Example: All Birds Fly

```python
class Bird:
    def fly(self):
        print("Flying...")

    def make_sound(self):
        print("Tweet!")


class Duck(Bird):
    pass


class Penguin(Bird):
    def fly(self):
        raise NotImplementedError("Penguins can't fly!")


def make_birds_fly(birds):
    for bird in birds:
        bird.fly()


birds = [Duck(), Penguin()]
make_birds_fly(birds)
```

**Problems:**
- Penguin throws exception for inherited fly method
- Cannot process list of birds polymorphically
- Base class assumes all birds can fly
- Client code breaks with certain subclasses

### GOOD Example: Capability-Based Interfaces

```python
from abc import ABC, abstractmethod


class Flyable(ABC):
    @abstractmethod
    def fly(self):
        pass


class SoundMaker(ABC):
    @abstractmethod
    def make_sound(self):
        pass


class Duck(Flyable, SoundMaker):
    def fly(self):
        print("Duck flying...")

    def make_sound(self):
        print("Quack!")


class Penguin(SoundMaker):
    def fly(self):
        pass

    def make_sound(self):
        print("Squawk!")


def make_flyable_fly(flyables):
    for flyable in flyables:
        flyable.fly()


make_flyable_fly([Duck()])
```

**Improvements:**
- Separate interfaces for different capabilities
- Penguin doesn't implement Flyable
- Client code can safely process any Flyable
- No runtime exceptions from unsupported operations

### Explanation

The BAD example assumes all birds can fly, causing runtime errors when processing a list that includes flightless birds. The GOOD example uses capability-based interfaces (composition over inheritance), allowing Duck to implement both Flyable and SoundMaker while Penguin only implements SoundMaker, maintaining LSP compliance.

---

## Example 4: Collection with Empty Return

### BAD Example: Violating Postcondition with Empty List

```python
class DataProcessor:
    def process_data(self, data_source):
        items = data_source.get_items()
        return items


class DatabaseDataSource:
    def get_items(self):
        return [{"id": 1, "name": "Item 1"}]


class EmptyDataSource:
    def get_items(self):
        return []


def display_items(processor):
    items = processor.process_data(DatabaseDataSource())
    for item in items:
        print(f"Item: {item}")

    items = processor.process_data(EmptyDataSource())
    for item in items:
        print(f"Item: {item}")


display_items(DataProcessor())
```

**Problems:**
- EmptyDataSource returns empty list when data expected
- Client code assumes non-empty results
- Postcondition violated without indication
- Silent failure difficult to debug

### GOOD Example: Exception for Empty Data

```python
from abc import ABC, abstractmethod


class EmptyDataSourceError(Exception):
    pass


class DataSource(ABC):
    @abstractmethod
    def get_items(self):
        pass


class DatabaseDataSource(DataSource):
    def get_items(self):
        return [{"id": 1, "name": "Item 1"}]


class EmptyDataSource(DataSource):
    def get_items(self):
        raise EmptyDataSourceError("No data available")


def display_items(processor):
    try:
        items = processor.process_data(DatabaseDataSource())
        for item in items:
            print(f"Item: {item}")
    except EmptyDataSourceError as e:
        print(f"Error: {e}")

    try:
        items = processor.process_data(EmptyDataSource())
        for item in items:
            print(f"Item: {item}")
    except EmptyDataSourceError as e:
        print(f"Error: {e}")


display_items(DataProcessor())
```

**Improvements:**
- Empty data signaled via exception
- Client code can handle expected error condition
- Contract maintained (data or explicit failure)
- Clear error handling path

### Explanation

The BAD example silently returns an empty list, violating the implicit postcondition that data will be available. The GOOD example uses exceptions to signal the absence of data, maintaining the contract and allowing client code to handle the error condition explicitly, which is LSP-compliant.

---

## Example 5: Payment Processors

### BAD Example: Inconsistent Error Handling

```python
class PaymentProcessor:
    def process(self, amount):
        pass


class CreditCardProcessor(PaymentProcessor):
    def process(self, amount):
        if amount > 10000:
            raise ValueError("Credit card limit exceeded")
        print(f"Processing ${amount}")


class PayPalProcessor(PaymentProcessor):
    def process(self, amount):
        print(f"Processing ${amount}")


def handle_payment(processor, amount):
    try:
        processor.process(amount)
        print("Payment successful")
    except ValueError as e:
        if isinstance(processor, CreditCardProcessor):
            print(f"Credit card declined: {e}")
        else:
            raise


handle_payment(CreditCardProcessor(), 15000)
handle_payment(PayPalProcessor(), 15000)
```

**Problems:**
- Different error behavior across implementations
- Client code must check processor type
- Not all processors can handle all amounts
- Violates principle of least surprise

### GOOD Example: Consistent Result Objects

```python
from dataclasses import dataclass


@dataclass
class PaymentResult:
    success: bool
    error: str = None


class PaymentProcessor:
    def process(self, amount) -> PaymentResult:
        pass


class CreditCardProcessor(PaymentProcessor):
    def process(self, amount) -> PaymentResult:
        if amount > 10000:
            return PaymentResult(success=False, error="Credit card limit exceeded")
        print(f"Processing ${amount}")
        return PaymentResult(success=True)


class PayPalProcessor(PaymentProcessor):
    def process(self, amount) -> PaymentResult:
        print(f"Processing ${amount}")
        return PaymentResult(success=True)


def handle_payment(processor, amount):
    result = processor.process(amount)
    if result.success:
        print("Payment successful")
    else:
        print(f"Payment failed: {result.error}")


handle_payment(CreditCardProcessor(), 15000)
handle_payment(PayPalProcessor(), 15000)
```

**Improvements:**
- Consistent return type across all processors
- Error handling uniform across implementations
- No need to check processor type
- Clear success/failure indication

### Explanation

The BAD example has inconsistent error handling, with CreditCardProcessor throwing exceptions while PayPalProcessor does not. The GOOD example uses a consistent PaymentResult return type, allowing all implementations to be substitutable and client code to handle errors uniformly without type checking.

---

## Example 6: Stack Inheritance

### BAD Example: Stack Inherits from List

```python
class Stack(list):
    def push(self, item):
        self.append(item)

    def pop(self):
        if not self:
            raise IndexError("Stack is empty")
        return super().pop()


def use_stack(container):
    container.push(1)
    container.push(2)
    container.push(3)
    item = container.pop()
    print(f"Popped: {item}")


stack = Stack()
use_stack(stack)

stack.insert(0, 99)
stack.reverse()
use_stack(stack)
```

**Problems:**
- Stack inherits all list methods it shouldn't have
- Clients can modify stack with list methods
- LIFO invariant can be violated
- Behavior unpredictable for stack users

### GOOD Example: Composition-Based Stack

```python
from collections import deque


class Stack:
    def __init__(self):
        self._items = deque()

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            raise IndexError("Stack is empty")
        return self._items.pop()

    def is_empty(self):
        return len(self._items) == 0


def use_stack(stack):
    stack.push(1)
    stack.push(2)
    stack.push(3)
    item = stack.pop()
    print(f"Popped: {item}")


stack = Stack()
use_stack(stack)
```

**Improvements:**
- Stack only exposes stack-specific operations
- LIFO invariant enforced
- No way to break stack semantics
- Clear, predictable behavior

### Explanation

The BAD example uses inheritance from list, exposing all list methods that can break the stack's LIFO invariant. The GOOD example uses composition with a deque internally, exposing only stack-specific methods and maintaining the contract that Stack clients expect.

---

## Example 7: Logging Hierarchy

### BAD Example: Overloaded Log Method

```python
class Logger:
    def log(self, message, level="INFO"):
        print(f"[{level}] {message}")


class FileLogger(Logger):
    def log(self, message, level="INFO", filepath="app.log"):
        with open(filepath, "a") as f:
            f.write(f"[{level}] {message}\n")


def write_log(logger):
    logger.log("Application started")
    logger.log("Error occurred", "ERROR")


write_log(Logger())
write_log(FileLogger())
```

**Problems:**
- FileLogger changes method signature
- Not substitutable for base Logger
- Client code breaks with FileLogger
- violates method contract

### GOOD Example: Consistent Interface

```python
from abc import ABC, abstractmethod


class Logger(ABC):
    @abstractmethod
    def log(self, message, level):
        pass


class ConsoleLogger(Logger):
    def log(self, message, level):
        print(f"[{level}] {message}")


class FileLogger(Logger):
    def __init__(self, filepath):
        self.filepath = filepath

    def log(self, message, level):
        with open(self.filepath, "a") as f:
            f.write(f"[{level}] {message}\n")


def write_log(logger):
    logger.log("Application started", "INFO")
    logger.log("Error occurred", "ERROR")


write_log(ConsoleLogger())
write_log(FileLogger("app.log"))
```

**Improvements:**
- All loggers have consistent interface
- FileLogger uses constructor for filepath
- Fully substitutable
- Client code works with any logger

### Explanation

The BAD example violates LSP by changing the method signature in FileLogger, adding a third parameter with a default value that breaks substitutability. The GOOD example maintains the same interface across all loggers, using the constructor for configuration and ensuring any Logger implementation can be used interchangeably.

---

## Language-Specific Notes

### Idioms and Patterns

- **ABC (Abstract Base Classes)**: Use `abc.ABC` and `@abstractmethod` to define contracts that subclasses must implement
- **Duck typing**: Python's duck typing allows implicit interfaces, but explicit ABCs improve LSP compliance
- **Composition over inheritance**: Prefer composition to avoid inheritance-related LSP violations
- **Protocol classes**: Use `typing.Protocol` for structural subtyping when ABCs are too rigid

### Language Features

**Features that help:**
- **ABC module**: Provides formal way to define abstract interfaces
- **Multiple inheritance**: Allows mixin-based capability interfaces
- **Type hints**: Help catch LSP violations at static analysis time
- **Protocol**: Enables structural subtyping for flexible interface compliance

**Features that hinder:**
- **Duck typing**: Can mask LSP violations until runtime
- **Dynamic typing**: Subtle contract violations only caught at runtime
- **Implicit interfaces**: No formal contract enforcement without ABCs
- **Method overloading**: Python doesn't support overloading, reducing some LSP issues

### Framework Considerations

- **Django**: ORM models often violate LSP through deep inheritance hierarchies
- **Pyramid/Flask**: Dependency injection patterns help maintain LSP
- **pytest**: Mock objects help test LSP compliance
- **mypy**: Static type checking catches many LSP violations

### Common Pitfalls

1. **Overriding with incompatible signatures**: Always maintain the same method signature
2. **Tightening preconditions**: Never make input validation stricter in subclasses
3. **Loosening postconditions**: Never weaken output guarantees in subclasses
4. **Throwing unexpected exceptions**: Only throw exceptions that base class declares
5. **Inheriting from concrete classes**: Prefer inheriting from abstract bases
