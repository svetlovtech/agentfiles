# OCP Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Payment Processing with Strategy](#example-1-payment-processing-with-strategy)
- [Example 2: Report Generation with Template Method](#example-2-report-generation-with-template-method)
- [Example 3: Validation with Duck Typing](#example-3-validation-with-duck-typing)
- [Example 4: Notification System with Decorator](#example-4-notification-system-with-decorator)
- [Example 5: Shape Calculation with ABCs](#example-5-shape-calculation-with-abcs)
- [Example 6: Data Processing Pipeline](#example-6-data-processing-pipeline)
- [Example 7: Tax Calculation with Registry](#example-7-tax-calculation-with-registry)
- [Example 8: Configuration Loading](#example-8-configuration-loading)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the Open/Closed Principle (OCP) in Python. Each example demonstrates a common violation and the corrected implementation.

## Example 1: Payment Processing with Strategy

### BAD Example: Switch Statement

```python
class PaymentProcessor:
    def process(self, payment_type, amount):
        if payment_type == "credit_card":
            return self._process_credit_card(amount)
        elif payment_type == "paypal":
            return self._process_paypal(amount)
        elif payment_type == "bitcoin":
            return self._process_bitcoin(amount)
        else:
            raise ValueError(f"Unknown payment type: {payment_type}")

    def _process_credit_card(self, amount):
        return f"Processing credit card payment of ${amount}"

    def _process_paypal(self, amount):
        return f"Processing PayPal payment of ${amount}"

    def _process_bitcoin(self, amount):
        return f"Processing Bitcoin payment of ${amount}"
```

**Problems:**
- Must modify class to add new payment methods
- Growing if-elif chain becomes unmaintainable
- Hard to test all payment types
- Violates single responsibility

### GOOD Example: Strategy Pattern

```python
from abc import ABC, abstractmethod

class PaymentStrategy(ABC):
    @abstractmethod
    def process(self, amount: float) -> str:
        pass

class CreditCardStrategy(PaymentStrategy):
    def process(self, amount: float) -> str:
        return f"Processing credit card payment of ${amount}"

class PayPalStrategy(PaymentStrategy):
    def process(self, amount: float) -> str:
        return f"Processing PayPal payment of ${amount}"

class BitcoinStrategy(PaymentStrategy):
    def process(self, amount: float) -> str:
        return f"Processing Bitcoin payment of ${amount}"

class PaymentProcessor:
    def __init__(self, strategy: PaymentStrategy):
        self.strategy = strategy

    def process(self, amount: float) -> str:
        return self.strategy.process(amount)
```

**Improvements:**
- New payment methods added without modifying PaymentProcessor
- Each strategy is independent and testable
- Can swap strategies at runtime
- Clear separation of concerns

### Explanation

The GOOD example uses the Strategy pattern to encapsulate payment algorithms. PaymentProcessor depends on the PaymentStrategy abstraction, making it open for extension (add new strategies) but closed for modification (no changes to PaymentProcessor needed).

---

## Example 2: Report Generation with Template Method

### BAD Example: Multiple Generation Methods

```python
class ReportGenerator:
    def generate_html(self, data):
        return f"<html><body>{data}</body></html>"

    def generate_pdf(self, data):
        return f"PDF: {data}"

    def generate_csv(self, data):
        return f"CSV,{data}"

    def generate(self, format_type, data):
        if format_type == "html":
            return self.generate_html(data)
        elif format_type == "pdf":
            return self.generate_pdf(data)
        elif format_type == "csv":
            return self.generate_csv(data)
```

**Problems:**
- Each new format requires modifying generate method
- Duplicate structure across formats
- No common base structure
- Hard to add common features (headers, footers)

### GOOD Example: Template Method Pattern

```python
from abc import ABC, abstractmethod

class ReportTemplate(ABC):
    def generate(self, data: str) -> str:
        header = self._create_header()
        body = self._create_body(data)
        footer = self._create_footer()
        return f"{header}\n{body}\n{footer}"

    def _create_header(self) -> str:
        return "=== HEADER ==="

    def _create_footer(self) -> str:
        return "=== FOOTER ==="

    @abstractmethod
    def _create_body(self, data: str) -> str:
        pass

class HTMLReport(ReportTemplate):
    def _create_body(self, data: str) -> str:
        return f"<body>{data}</body>"

class PDFReport(ReportTemplate):
    def _create_body(self, data: str) -> str:
        return f"PDF BODY: {data}"

class CSVReport(ReportTemplate):
    def _create_header(self) -> str:
        return "CSV_HEADER"
    
    def _create_body(self, data: str) -> str:
        return f"CSV,{data}"
```

**Improvements:**
- Common structure defined in base template
- New formats extend by subclassing
- No modification to existing code for new formats
- Template method enforces consistent structure

### Explanation

The GOOD example uses the Template Method pattern where the base class defines the algorithm structure (generate method) and subclasses override specific steps. Adding new formats requires only creating a new subclass, not modifying existing code.

---

## Example 3: Validation with Duck Typing

### BAD Example: Type-Based Validation

```python
class Validator:
    def validate(self, value, validation_type):
        if validation_type == "email":
            return "@" in value and "." in value
        elif validation_type == "phone":
            return value.isdigit() and len(value) == 10
        elif validation_type == "url":
            return value.startswith("http")
        elif validation_type == "age":
            return value.isdigit() and 0 < int(value) < 120
        else:
            raise ValueError(f"Unknown validation type: {validation_type}")
```

**Problems:**
- New validators require modifying class
- String-based type checking is error-prone
- Hard to reuse validators
- No composition or combination of validators

### GOOD Example: Duck Typing and Composition

```python
class EmailValidator:
    def validate(self, value: str) -> bool:
        return "@" in value and "." in value

class PhoneValidator:
    def validate(self, value: str) -> bool:
        return value.isdigit() and len(value) == 10

class URLValidator:
    def validate(self, value: str) -> bool:
        return value.startswith("http")

class CompositeValidator:
    def __init__(self):
        self.validators = []

    def add_validator(self, validator):
        self.validators.append(validator)

    def validate(self, value: str) -> bool:
        return all(v.validate(value) for v in self.validators)

class Validator:
    def __init__(self, validator):
        self.validator = validator

    def validate(self, value: str) -> bool:
        return self.validator.validate(value)
```

**Improvements:**
- Validators are duck-typed, need no interface
- Can compose multiple validators
- New validators added without changing existing code
- Each validator is independently testable

### Explanation

The GOOD example leverages Python's duck typing - any object with a validate method can be used. CompositeValidator allows combining validators without modifying the base class. New validators are simply new classes with validate methods.

---

## Example 4: Notification System with Decorator

### BAD Example: Method Overloading

```python
class Notifier:
    def send(self, message, channel="email"):
        if channel == "email":
            print(f"Sending email: {message}")
        elif channel == "sms":
            print(f"Sending SMS: {message}")
        elif channel == "push":
            print(f"Sending push: {message}")
        elif channel == "email_with_logging":
            print(f"LOG: Sending email: {message}")
            print(f"Sending email: {message}")
        elif channel == "sms_with_retry":
            print(f"Sending SMS: {message}")
            print(f"Retrying SMS: {message}")
```

**Problems:**
- Every combination requires new channel type
- Exponential growth of channel types with features
- Cannot dynamically add behaviors
- Feature duplication across channels

### GOOD Example: Decorator Pattern

```python
from functools import wraps

def logged(notifier):
    @wraps(notifier.send)
    def send_with_logging(message):
        print(f"LOG: Sending message: {message}")
        return notifier.send(message)
    return send_with_logging

def retry(notifier, max_retries=3):
    @wraps(notifier.send)
    def send_with_retry(message):
        for attempt in range(max_retries):
            try:
                return notifier.send(message)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                print(f"Retry {attempt + 1}...")
    return send_with_retry

class EmailNotifier:
    def send(self, message: str):
        print(f"Sending email: {message}")

class SMSNotifier:
    def send(self, message: str):
        print(f"Sending SMS: {message}")

class PushNotifier:
    def send(self, message: str):
        print(f"Sending push: {message}")
```

**Improvements:**
- Behaviors added through decorators
- Can stack decorators for combinations
- No modification to base notifiers
- Decorators reusable across all notifier types

### Explanation

The GOOD example uses Python decorators to add behaviors like logging and retry logic dynamically. Decorators wrap the send method, adding functionality without modifying the original notifier classes. This allows unlimited behavior combinations.

---

## Example 5: Shape Calculation with ABCs

### BAD Example: Type-Based Area Calculation

```python
class ShapeCalculator:
    def calculate_area(self, shape):
        if shape["type"] == "rectangle":
            return shape["width"] * shape["height"]
        elif shape["type"] == "circle":
            import math
            return math.pi * (shape["radius"] ** 2)
        elif shape["type"] == "triangle":
            return 0.5 * shape["base"] * shape["height"]
        else:
            raise ValueError(f"Unknown shape type: {shape['type']}")
```

**Problems:**
- Dictionary-based type checking is fragile
- New shapes require modifying calculator
- No encapsulation of shape-specific logic
- Hard to add shape-specific operations

### GOOD Example: Abstract Base Classes

```python
from abc import ABC, abstractmethod
import math

class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        pass

class Rectangle(Shape):
    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height

    def area(self) -> float:
        return self.width * self.height

class Circle(Shape):
    def __init__(self, radius: float):
        self.radius = radius

    def area(self) -> float:
        return math.pi * (self.radius ** 2)

class Triangle(Shape):
    def __init__(self, base: float, height: float):
        self.base = base
        self.height = height

    def area(self) -> float:
        return 0.5 * self.base * self.height

class ShapeCalculator:
    def calculate_total_area(self, shapes: list[Shape]) -> float:
        return sum(shape.area() for shape in shapes)
```

**Improvements:**
- Each shape encapsulates its area calculation
- New shapes added by subclassing Shape
- Type-safe with ABCs
- Easy to add other operations (perimeter, etc.)

### Explanation

The GOOD example defines an abstract Shape class with an area method. Each concrete shape implements its own area calculation. ShapeCalculator works with any Shape object, making it open for extension (new shapes) but closed for modification.

---

## Example 6: Data Processing Pipeline

### BAD Example: Hard-Coded Pipeline Steps

```python
class DataProcessor:
    def process(self, data, steps):
        result = data
        for step in steps:
            if step == "normalize":
                result = self._normalize(result)
            elif step == "clean":
                result = self._clean(result)
            elif step == "validate":
                result = self._validate(result)
            elif step == "transform":
                result = self._transform(result)
            else:
                raise ValueError(f"Unknown step: {step}")
        return result

    def _normalize(self, data):
        return data.strip().lower()

    def _clean(self, data):
        return data.replace(" ", "_")

    def _validate(self, data):
        return data if len(data) > 0 else None

    def _transform(self, data):
        return data.upper()
```

**Problems:**
- Each new step requires modifying process method
- Hard to reorder or compose steps
- Steps tightly coupled to processor
- No way to add custom steps

### GOOD Example: Callable Pipeline

```python
from typing import Callable

class DataPipeline:
    def __init__(self):
        self.steps = []

    def add_step(self, step: Callable[[str], str]):
        self.steps.append(step)

    def process(self, data: str) -> str:
        result = data
        for step in self.steps:
            result = step(result)
        return result

def normalize(data: str) -> str:
    return data.strip().lower()

def clean(data: str) -> str:
    return data.replace(" ", "_")

def validate(data: str) -> str:
    return data if len(data) > 0 else None

def transform(data: str) -> str:
    return data.upper()

def custom_step(data: str) -> str:
    return data + "_custom"
```

**Improvements:**
- Steps are callable objects
- Can add custom steps dynamically
- Easy to reorder pipeline
- No modification needed for new step types

### Explanation

The GOOD example treats each pipeline step as a callable. DataPipeline accepts any callable, making it open for extension. New steps are simply functions or callable objects added to the pipeline without modifying DataPipeline.

---

## Example 7: Tax Calculation with Registry

### BAD Example: Country-Based Tax Calculation

```python
class TaxCalculator:
    def calculate_tax(self, amount, country):
        if country == "USA":
            return amount * 0.07
        elif country == "UK":
            return amount * 0.20
        elif country == "Germany":
            return amount * 0.19
        elif country == "France":
            return amount * 0.20
        elif country == "Japan":
            return amount * 0.10
        else:
            raise ValueError(f"Unsupported country: {country}")
```

**Problems:**
- New countries require modifying class
- Tax logic scattered in method
- Hard to update rates dynamically
- No way to register countries at runtime

### GOOD Example: Strategy with Registry

```python
from typing import Dict

class TaxStrategy:
    def calculate(self, amount: float) -> float:
        pass

class USATaxStrategy(TaxStrategy):
    def calculate(self, amount: float) -> float:
        return amount * 0.07

class UKTaxStrategy(TaxStrategy):
    def calculate(self, amount: float) -> float:
        return amount * 0.20

class TaxCalculator:
    def __init__(self):
        self.strategies: Dict[str, TaxStrategy] = {}

    def register_country(self, country: str, strategy: TaxStrategy):
        self.strategies[country] = strategy

    def calculate_tax(self, amount: float, country: str) -> float:
        strategy = self.strategies.get(country)
        if not strategy:
            raise ValueError(f"Unsupported country: {country}")
        return strategy.calculate(amount)
```

**Improvements:**
- Countries registered at runtime
- New countries added without modification
- Strategies are independent and testable
- Tax rates can be updated dynamically

### Explanation

The GOOD example uses a registry pattern where countries are registered with their tax strategies. TaxCalculator is closed for modification but open for extension through the register_country method. New countries can be added by creating a strategy and registering it.

---

## Example 8: Configuration Loading

### BAD Example: Format-Based Loading

```python
class ConfigLoader:
    def load(self, filepath):
        if filepath.endswith(".json"):
            return self._load_json(filepath)
        elif filepath.endswith(".yaml"):
            return self._load_yaml(filepath)
        elif filepath.endswith(".toml"):
            return self._load_toml(filepath)
        elif filepath.endswith(".ini"):
            return self._load_ini(filepath)
        else:
            raise ValueError(f"Unsupported format: {filepath}")

    def _load_json(self, filepath):
        import json
        with open(filepath) as f:
            return json.load(f)

    def _load_yaml(self, filepath):
        import yaml
        with open(filepath) as f:
            return yaml.safe_load(f)
```

**Problems:**
- New formats require modifying class
- File extension parsing is brittle
- Format-specific code mixed with loader
- Hard to add custom format loaders

### GOOD Example: Protocol-Based Loading

```python
from typing import Protocol
import json

class ConfigFormat(Protocol):
    def load(self, filepath: str) -> dict:
        ...

class JSONFormat:
    def load(self, filepath: str) -> dict:
        with open(filepath) as f:
            return json.load(f)

class YAMLFormat:
    def load(self, filepath: str) -> dict:
        import yaml
        with open(filepath) as f:
            return yaml.safe_load(f)

class TOMLFormat:
    def load(self, filepath: str) -> dict:
        import tomli
        with open(filepath, "rb") as f:
            return tomli.load(f)

class ConfigLoader:
    def __init__(self):
        self.formatters = {}

    def register_format(self, extension: str, formatter: ConfigFormat):
        self.formatters[extension] = formatter

    def load(self, filepath: str) -> dict:
        extension = filepath.split(".")[-1]
        formatter = self.formatters.get(extension)
        if not formatter:
            raise ValueError(f"Unsupported format: {extension}")
        return formatter.load(filepath)
```

**Improvements:**
- Formats registered dynamically
- Protocol defines expected interface
- New formats added without modification
- Custom formatters easily integrated

### Explanation

The GOOD example uses Python's Protocol structural typing to define the ConfigFormat interface. ConfigLoader is a registry that maps file extensions to format loaders. New formats are added by implementing the protocol and registering it.

---

## Language-Specific Notes

### Idioms and Patterns

- **ABCs**: Use `abc.ABC` and `@abstractmethod` to define interfaces that must be implemented
- **Duck typing**: Rely on behavior ("if it walks like a duck") rather than explicit interfaces
- **Decorators**: Add cross-cutting concerns without modifying original functions
- **Callable protocol**: Treat functions and classes uniformly as callable objects
- **Context managers**: Use `__enter__` and `__exit__` for resource management
- **Descriptor protocol**: Define custom attribute access patterns

### Language Features

**Features that help:**
- `functools.singledispatch`: Method overloading based on type
- `abc` module: Abstract base classes for interface definition
- `typing.Protocol`: Structural typing for duck-typed interfaces
- Decorators: Composable behavior modification
- First-class functions: Functions as objects for strategies

**Features that hinder:**
- Dynamic typing: Runtime type errors instead of compile-time
- Monkey patching: Can violate encapsulation
- Lack of private keywords: Relies on convention (underscore prefix)
- Global state: Makes extension harder

### Framework Considerations

- **Django**: Mixins for extending model and view behavior
- **FastAPI**: Dependency injection for extending functionality
- **SQLAlchemy**: Abstract base classes for model extensions
- **pytest**: Plugins for extending test framework
- **Click**: Commands and groups for CLI extension

### Common Pitfalls

1. **Over-using inheritance**: Prefer composition to inheritance for flexibility
2. **Premature ABCs**: Create abstractions when you have multiple implementations
3. **Ignoring duck typing**: Don't create unnecessary interfaces
4. **God classes**: Too many responsibilities makes OCP harder
5. **Tight coupling**: Depend on abstractions, not concrete classes
