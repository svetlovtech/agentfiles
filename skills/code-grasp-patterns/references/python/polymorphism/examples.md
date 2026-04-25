# Polymorphism Examples - Python

## Introduction

This document provides paired examples of BAD and GOOD implementations of Polymorphism pattern in Python.

## Example 1: Type Checking

### BAD Example

```python
class PaymentService:
    def process_payment(self, payment_type, amount, details):
        # BAD: Type checking instead of polymorphism
        if payment_type == 'credit_card':
            self._process_credit_card(amount, details)
        elif payment_type == 'paypal':
            self._process_paypal(amount, details)
        elif payment_type == 'bank_transfer':
            self._process_bank_transfer(amount, details)
        else:
            raise ValueError('Unknown payment type')
```

### GOOD Example

```python
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float, details: dict) -> PaymentResult:
        pass

class CreditCardProcessor(PaymentProcessor):
    def process(self, amount: float, details: dict) -> PaymentResult:
        # Credit card specific logic
        pass

class PayPalProcessor(PaymentProcessor):
    def process(self, amount: float, details: dict) -> PaymentResult:
        # PayPal specific logic
        pass

class BankTransferProcessor(PaymentProcessor):
    def process(self, amount: float, details: dict) -> PaymentResult:
        # Bank transfer specific logic
        pass

class PaymentService:
    def __init__(self, processor: PaymentProcessor):
        self.processor = processor
    
    def process_payment(self, amount: float, details: dict) -> PaymentResult:
        # GOOD: Polymorphic call
        return self.processor.process(amount, details)

# Factory for creating appropriate processor
class PaymentProcessorFactory:
    _processors = {
        'credit_card': CreditCardProcessor,
        'paypal': PayPalProcessor,
        'bank_transfer': BankTransferProcessor
    }
    
    @classmethod
    def create(cls, payment_type: str) -> PaymentProcessor:
        processor_class = cls._processors.get(payment_type)
        if not processor_class:
            raise ValueError(f'Unknown payment type: {payment_type}')
        return processor_class()
```

**Improvements:**
- Polymorphic behavior
- Easy to add new payment types
- No type checking
- Open/Closed Principle

## Example 2: Shape Calculation

### BAD Example

```python
class ShapeCalculator:
    def calculate_area(self, shape_type, dimensions):
        # BAD: Type checking
        if shape_type == 'rectangle':
            return dimensions['width'] * dimensions['height']
        elif shape_type == 'circle':
            return 3.14 * dimensions['radius'] ** 2
        elif shape_type == 'triangle':
            return 0.5 * dimensions['base'] * dimensions['height']
```

### GOOD Example

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Dimensions:
    pass

class Shape(ABC):
    @abstractmethod
    def area(self) -> float:
        pass

@dataclass
class RectangleDimensions(Dimensions):
    width: float
    height: float

class Rectangle(Shape):
    def __init__(self, dimensions: RectangleDimensions):
        self.dimensions = dimensions
    
    def area(self) -> float:
        return self.dimensions.width * self.dimensions.height

@dataclass
class CircleDimensions(Dimensions):
    radius: float

class Circle(Shape):
    def __init__(self, dimensions: CircleDimensions):
        self.dimensions = dimensions
    
    def area(self) -> float:
        return 3.14 * self.dimensions.radius ** 2

# Polymorphic usage
shapes: List[Shape] = [
    Rectangle(RectangleDimensions(5, 10)),
    Circle(CircleDimensions(7))
]
for shape in shapes:
    print(f"Area: {shape.area()}")
```

**Improvements:**
- Each shape knows how to calculate area
- No type checking
- Easy to add new shapes
- Clear separation

## Language-Specific Notes

### Python Polymorphism Patterns

- **ABC**: Use `abc.ABC` for abstract base classes
- **Duck typing**: Type checking not required for polymorphism
- **Protocol**: Use `Protocol` for structural typing
- **Multiple inheritance**: Mixins for shared behavior
- **`super()`**: Call parent methods in inheritance
