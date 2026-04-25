# Polymorphism Anti-Patterns - Python

## Anti-Pattern: Type Checking

### BAD Example

```python
def process_shape(shape_type, dimensions):
    if shape_type == 'rectangle':
        return dimensions['width'] * dimensions['height']
    elif shape_type == 'circle':
        return 3.14 * dimensions['radius'] ** 2
```

### GOOD Example

```python
class Shape(ABC):
    @abstractmethod
    def area(self) -> float: pass

class Rectangle(Shape):
    def area(self) -> float:
        return self.width * self.height
```

## Detection Checklist

- [ ] Type checking with `if type ==`
- [ ] Not using ABC/Protocol
- [ ] Violating Open/Closed Principle
- [ ] Hard to add new types
