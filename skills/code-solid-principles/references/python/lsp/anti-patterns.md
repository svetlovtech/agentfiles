# LSP Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern A: Exception-Throwing Override](#anti-pattern-a-exception-throwing-override)
- [Anti-Pattern B: Covariant Return Types](#anti-pattern-b-covariant-return-types)
- [Anti-Pattern C: Tightening Preconditions](#anti-pattern-c-tightening-preconditions)
- [Anti-Pattern D: Loosening Postconditions](#anti-pattern-d-loosening-postconditions)
- [Anti-Pattern E: Unused Method Override](#anti-pattern-e-unused-method-override)
- [Anti-Pattern F: Invariant Violation](#anti-pattern-f-invariant-violation)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the LSP (Liskov Substitution Principle) principle in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

## Anti-Pattern A: Exception-Throwing Override

### Description

This anti-pattern occurs when a subclass overrides a method from its parent class but throws an exception indicating the operation is not supported. This violates the principle that subclasses should be substitutable for their base classes.

### BAD Example

```python
class Database:
    def connect(self):
        pass

    def execute_query(self, query):
        pass

    def begin_transaction(self):
        print("Beginning transaction")

    def commit_transaction(self):
        print("Committing transaction")


class SQLiteDatabase(Database):
    def begin_transaction(self):
        raise NotImplementedError("SQLite doesn't support transactions")

    def commit_transaction(self):
        raise NotImplementedError("SQLite doesn't support transactions")


def process_with_transaction(db):
    db.begin_transaction()
    db.execute_query("INSERT INTO users VALUES (1)")
    db.commit_transaction()


process_with_transaction(SQLiteDatabase())
```

### Why It's Problematic

- **Runtime exceptions**: Code breaks unexpectedly when using SQLiteDatabase
- **Type checking required**: Client must check database type before calling transaction methods
- **Not substitutable**: SQLiteDatabase cannot be used where Database is expected
- **Broken polymorphism**: Base class contract is not honored

### How to Fix

**Refactoring Steps:**
1. Create a separate interface for transactional databases
2. Remove transaction methods from base Database class
3. Have SQLiteDatabase implement only Database interface
4. Have transactional databases implement both interfaces

### GOOD Example

```python
from abc import ABC, abstractmethod


class Database(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def execute_query(self, query):
        pass


class TransactionalDatabase(Database):
    @abstractmethod
    def begin_transaction(self):
        pass

    @abstractmethod
    def commit_transaction(self):
        pass


class PostgreSQLDatabase(TransactionalDatabase):
    def connect(self):
        print("Connected to PostgreSQL")

    def execute_query(self, query):
        print(f"Executed: {query}")

    def begin_transaction(self):
        print("Transaction started")

    def commit_transaction(self):
        print("Transaction committed")


class SQLiteDatabase(Database):
    def connect(self):
        print("Connected to SQLite")

    def execute_query(self, query):
        print(f"Executed: {query}")


def process_with_transaction(db):
    db.begin_transaction()
    db.execute_query("INSERT INTO users VALUES (1)")
    db.commit_transaction()


process_with_transaction(PostgreSQLDatabase())
```

**Key Changes:**
- Separate TransactionalDatabase interface
- SQLiteDatabase only implements methods it supports
- No exceptions thrown for unsupported operations
- Full substitutability within each interface

---

## Anti-Pattern B: Covariant Return Types

### Description

This anti-pattern occurs when a subclass overrides a method to return a more specific type than the base class declares. While Python allows this, it can break client code that expects the base type.

### BAD Example

```python
class Animal:
    def create_offspring(self):
        return Animal()


class Dog(Animal):
    def create_offspring(self):
        return Dog()


def process_animal(animal_factory):
    offspring = animal_factory.create_offspring()
    offspring.breed = "unknown"


class Cat(Animal):
    def create_offspring(self):
        return Cat()


process_animal(Animal())
process_animal(Dog())
process_animal(Cat())
```

### Why It's Problematic

- **Type assumptions broken**: Client code may assume base type behavior
- **Inconsistent behavior**: Different subclasses return different concrete types
- **Brittle client code**: Adding new subclasses may break existing code
- **Hidden dependencies**: Code implicitly depends on specific subclass types

### How to Fix

**Refactoring Steps:**
1. Ensure all return types match the declared base type
2. If specific behavior needed, use factory pattern
3. Keep return types consistent across hierarchy
4. Use interfaces for polymorphic behavior

### GOOD Example

```python
from abc import ABC, abstractmethod


class Animal(ABC):
    @abstractmethod
    def get_species(self):
        pass

    @abstractmethod
    def create_offspring(self):
        pass


class Dog(Animal):
    def get_species(self):
        return "Dog"

    def create_offspring(self):
        return Dog()


class Cat(Animal):
    def get_species(self):
        return "Cat"

    def create_offspring(self):
        return Cat()


def process_animal(animal_factory):
    offspring = animal_factory.create_offspring()
    print(f"Created {offspring.get_species()}")


process_animal(Dog())
process_animal(Cat())
```

**Key Changes:**
- All return types are Animal or its subclasses (consistent with base)
- Client code uses polymorphic methods
- No type-specific assumptions
- Factory pattern explicit and clear

---

## Anti-Pattern C: Tightening Preconditions

### Description

This anti-pattern occurs when a subclass makes preconditions stricter than the base class. For example, accepting a narrower range of input values or requiring additional validation that the base class doesn't specify.

### BAD Example

```python
class NumberProcessor:
    def process(self, number):
        print(f"Processing: {number}")


class PositiveNumberProcessor(NumberProcessor):
    def process(self, number):
        if number < 0:
            raise ValueError("Only positive numbers allowed")
        print(f"Processing: {number}")


def process_numbers(processor, numbers):
    for num in numbers:
        processor.process(num)


processor = PositiveNumberProcessor()
process_numbers(processor, [1, 2, 3, -1, 5])
```

### Why It's Problematic

- **Contract violation**: Base class accepts any number, subclass rejects negatives
- **Unexpected failures**: Client code passes valid inputs per base class contract
- **Not substitutable**: PositiveNumberProcessor cannot replace NumberProcessor
- **Broken invariants**: Code expecting base class behavior fails

### How to Fix

**Refactoring Steps:**
1. Create separate interface for constrained processing
2. Keep base class contract broad
3. Add explicit type validation at base level if needed
4. Document preconditions clearly

### GOOD Example

```python
from abc import ABC, abstractmethod


class NumberProcessor(ABC):
    @abstractmethod
    def process(self, number):
        pass


class UnconstrainedProcessor(NumberProcessor):
    def process(self, number):
        print(f"Processing: {number}")


class ConstrainedProcessor(NumberProcessor):
    def __init__(self, validator):
        self.validator = validator

    def process(self, number):
        if not self.validator(number):
            raise ValueError("Number doesn't meet constraints")
        print(f"Processing: {number}")


def validate_positive(number):
    return number >= 0


def process_numbers(processor, numbers):
    for num in numbers:
        processor.process(num)


processor = ConstrainedProcessor(validate_positive)
process_numbers(processor, [1, 2, 3, 5])

unconstrained = UnconstrainedProcessor()
process_numbers(unconstrained, [1, 2, 3, -1, 5])
```

**Key Changes:**
- Base class contract remains broad
- Constraints injected via validator function
- Each processor can have different validation
- Substitutability maintained within same type

---

## Anti-Pattern D: Loosening Postconditions

### Description

This anti-pattern occurs when a subclass weakens or removes guarantees that the base class makes. For example, returning None when base class always returns a value, or returning a different type.

### BAD Example

```python
class DataFetcher:
    def fetch_data(self):
        return {"status": "success", "data": [1, 2, 3]}


class CachedDataFetcher(DataFetcher):
    def __init__(self):
        self.cache = None

    def fetch_data(self):
        if self.cache is None:
            self.cache = {"status": "success", "data": [1, 2, 3]}
        return self.cache


class EmptyDataFetcher(DataFetcher):
    def fetch_data(self):
        return None


def use_data(fetcher):
    result = fetcher.fetch_data()
    if result["status"] == "success":
        print(f"Got data: {result['data']}")


use_data(DataFetcher())
use_data(CachedDataFetcher())
use_data(EmptyDataFetcher())
```

### Why It's Problematic

- **Broken contract**: Base class promises data, subclass returns None
- **Type errors**: Client expects dictionary, gets None
- **Runtime failures**: Attribute access fails on None
- **Not substitutable**: Cannot use EmptyDataFetcher where DataFetcher expected

### How to Fix

**Refactoring Steps:**
1. Maintain consistent return types across hierarchy
2. Use sentinel values or exceptions for edge cases
3. Document postconditions clearly
4. Ensure all subclasses honor base class guarantees

### GOOD Example

```python
from abc import ABC, abstractmethod


class DataFetcher(ABC):
    @abstractmethod
    def fetch_data(self):
        pass


class APIDataFetcher(DataFetcher):
    def fetch_data(self):
        return {"status": "success", "data": [1, 2, 3]}


class CachedDataFetcher(DataFetcher):
    def __init__(self):
        self.cache = None

    def fetch_data(self):
        if self.cache is None:
            self.cache = {"status": "success", "data": [1, 2, 3]}
        return self.cache


class EmptyDataFetcher(DataFetcher):
    def fetch_data(self):
        return {"status": "empty", "data": []}


def use_data(fetcher):
    result = fetcher.fetch_data()
    if result["status"] == "success":
        print(f"Got data: {result['data']}")
    else:
        print(f"Status: {result['status']}")


use_data(APIDataFetcher())
use_data(CachedDataFetcher())
use_data(EmptyDataFetcher())
```

**Key Changes:**
- All fetchers return consistent dictionary structure
- Empty data indicated via status field, not None
- Client code handles all valid return types
- Full substitutability maintained

---

## Anti-Pattern E: Unused Method Override

### Description

This anti-pattern occurs when a subclass overrides a method but does nothing useful, essentially making it a no-op. This often happens when the subclass doesn't support the operation but inherits the method signature.

### BAD Example

```python
class File:
    def read(self):
        pass

    def write(self, content):
        pass

    def delete(self):
        pass


class ReadOnlyFile(File):
    def write(self, content):
        pass

    def delete(self):
        pass


def process_file(file):
    file.write("Hello")
    file.read()
    file.delete()


process_file(File())
process_file(ReadOnlyFile())
```

### Why It's Problematic

- **Silent failures**: Operations appear to succeed but do nothing
- **Misleading behavior**: Client assumes operations executed
- **Contract violation**: Base class implies write/delete work
- **Difficult debugging**: No error indication when operations fail

### How to Fix

**Refactoring Steps:**
1. Create separate interfaces for different capabilities
2. Remove unsupported methods from applicable classes
3. Throw exceptions if operation truly not supported
4. Use composition to combine capabilities

### GOOD Example

```python
from abc import ABC, abstractmethod


class ReadableFile(ABC):
    @abstractmethod
    def read(self):
        pass


class WritableFile(ReadableFile):
    @abstractmethod
    def write(self, content):
        pass


class DeletableFile(WritableFile):
    @abstractmethod
    def delete(self):
        pass


class ReadWriteFile(DeletableFile):
    def read(self):
        print("Reading content")

    def write(self, content):
        print(f"Writing: {content}")

    def delete(self):
        print("Deleting file")


class ReadOnlyFile(ReadableFile):
    def read(self):
        print("Reading content")


def process_file(file):
    file.read()
    if hasattr(file, 'write'):
        file.write("Hello")
    if hasattr(file, 'delete'):
        file.delete()


process_file(ReadWriteFile())
process_file(ReadOnlyFile())
```

**Key Changes:**
- Separate interfaces for different capabilities
- ReadOnlyFile only implements ReadableFile
- Client checks for capabilities before use
- No silent failures

---

## Anti-Pattern F: Invariant Violation

### Description

This anti-pattern occurs when a subclass breaks invariants that the base class maintains. An invariant is a condition that should always be true after any operation.

### BAD Example

```python
class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def set_dimensions(self, width, height):
        self.width = width
        self.height = height

    def get_area(self):
        return self.width * self.height


class Square(Rectangle):
    def __init__(self, side):
        super().__init__(side, side)

    def set_dimensions(self, width, height):
        self.width = width
        self.height = width


def resize_rectangle(rect, width, height):
    rect.set_dimensions(width, height)
    area = rect.get_area()
    assert area == width * height


square = Square(10)
resize_rectangle(square, 15, 20)
```

### Why It's Problematic

- **Broken invariants**: Square violates rectangle's width/height independence
- **Assertion failures**: Client code expecting rectangle behavior fails
- **Not substitutable**: Square cannot be used where Rectangle expected
- **Hidden side effects**: Setting one dimension affects the other

### How to Fix

**Refactoring Steps:**
1. Create separate base classes for different shapes
2. Use composition instead of inheritance
3. Maintain invariants specific to each class
4. Define common interface if needed

### GOOD Example

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

    def set_dimensions(self, width, height):
        self.width = width
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


def resize_shape(shape, factor):
    shape.scale(factor)
    area = shape.get_area()
    print(f"New area: {area}")


resize_shape(Rectangle(10, 20), 2)
resize_shape(Square(10), 2)
```

**Key Changes:**
- Rectangle and Square independent, share only Shape interface
- Each maintains its own invariants
- Client code works with any shape
- No violation of rectangle's independence invariant

---

## Detection Checklist

Use this checklist to identify LSP violations in Python code:

### Code Review Questions

- [ ] Do any subclasses throw NotImplementedError for inherited methods?
- [ ] Do subclasses have different method signatures than their parents?
- [ ] Do subclasses validate inputs more strictly than base class?
- [ ] Do subclasses return different types than base class declares?
- [ ] Do subclasses leave inherited methods empty or as no-ops?
- [ ] Do subclasses break invariants that base class maintains?
- [ ] Is there isinstance/type checking before using polymorphic references?
- [ ] Do subclasses weaken postconditions of base class?

### Automated Detection

- **mypy**: Use strict mode to catch type incompatibilities
- **pylint**: Look for W0223 (abstract method not overridden) and W0237 (arguments differ)
- **unittest.mock**: Test substitution by mocking base class with subclass
- **pytest-subtests**: Verify all subclasses pass same tests

### Manual Inspection Techniques

1. **Substitution test**: Try replacing base class with each subclass in client code
2. **Contract analysis**: Document preconditions/postconditions and verify subclasses maintain them
3. **Behavioral verification**: Run same operation on all subclasses and compare results
4. **Invariant checking**: Add assertions for invariants and verify they hold for all subclasses

### Common Symptoms

- **Runtime TypeError**: When method signature incompatible
- **NotImplementedError**: Thrown when calling method on subclass
- **AttributeError**: When client expects attribute/method that subclass doesn't have
- **Assertion failures**: When invariants broken in specific subclasses
- **Type checking in client code**: isinstance checks before using polymorphic references

---

## Language-Specific Notes

### Common Causes in Python

- **Duck typing**: Implicit contracts can mask violations until runtime
- **Convenience methods**: Adding helpful methods in subclasses that change behavior
- **Partial implementations**: Subclasses implementing only part of interface
- **Legacy code**: Gradual addition of features without proper interface design
- **Quick fixes**: Adding exceptions or empty overrides instead of proper refactoring

### Language Features that Enable Anti-Patterns

- **Dynamic typing**: No compile-time checking of method signatures
- **Flexible inheritance**: Multiple inheritance can create complex hierarchies
- **No formal interfaces**: Reliance on duck typing over explicit contracts
- **Optional type hints**: Not enforced at runtime without tools like mypy
- **Monkey patching**: Can modify behavior at runtime, masking violations

### Framework-Specific Anti-Patterns

- **Django models**: Deep inheritance hierarchies often violate LSP
- **SQLAlchemy**: Session objects with different backends may have inconsistent behavior
- **Pydantic**: Subclasses changing validation rules more strictly
- **pytest fixtures**: Fixture inheritance can create substitution issues

### Tooling Support

- **mypy**: Static type checking catches many signature violations
- **pyright**: Enhanced type checking with strict mode
- **pylint**: Detects abstract method issues and signature problems
- **bandit**: Security-focused linter can catch dangerous inheritance patterns
- **unittest.mock**: Helps test substitutability through mocking
