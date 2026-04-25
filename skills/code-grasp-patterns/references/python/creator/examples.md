# Creator Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Domain Object Creation](#example-1-domain-object-creation)
- [Example 2: Factory Method Pattern](#example-2-factory-method-pattern)
- [Example 3: Repository Creation](#example-3-repository-creation)
- [Example 4: Service Object Creation](#example-4-service-object-creation)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the Creator pattern in Python. Each example demonstrates a common violation and the corrected implementation following GRASP principles.

## Example 1: Domain Object Creation

### BAD Example: Creator Responsibility Violation

```python
class OrderController:
    def create_order(self, request):
        customer_id = request['customer_id']
        items = request['items']
        
        # BAD: Creating Order with direct instantiation
        order = Order(
            customer_id=customer_id,
            items=[],
            status='PENDING',
            created_at=datetime.now()
        )
        
        # BAD: Creating OrderItems manually
        for item_data in items:
            product = Product.objects.get(id=item_data['product_id'])
            order_item = OrderItem(
                product_id=product.id,
                quantity=item_data['quantity'],
                price=product.price
            )
            order.items.append(order_item)
        
        # BAD: Validation logic scattered
        if not order.items:
            raise ValueError("Order must have items")
        
        order.total = sum(item.price * item.quantity for item in order.items)
        order.save()
        
        return order
```

**Problems:**
- No centralized creation logic
- Validation logic scattered
- Constructor called directly with manual setup
- Hard to ensure object invariants
- Duplicate creation code across codebase
- No single place for creation rules

### GOOD Example: Creator Pattern with Factory Methods

```python
class Order:
    @classmethod
    def create(cls, customer_id: int) -> 'Order':
        return cls(
            customer_id=customer_id,
            items=[],
            status='PENDING',
            created_at=datetime.now()
        )
    
    def add_item(self, product: Product, quantity: int) -> 'OrderItem':
        item = OrderItem.create(product, quantity)
        self.items.append(item)
        return item
    
    def validate(self):
        if not self.items:
            raise ValueError("Order must have items")
    
    def calculate_total(self) -> float:
        self.total = sum(item.price * item.quantity for item in self.items)
        return self.total


class OrderItem:
    @classmethod
    def create(cls, product: Product, quantity: int) -> 'OrderItem':
        return cls(
            product_id=product.id,
            quantity=quantity,
            price=product.price
        )


class OrderController:
    def create_order(self, request):
        # GOOD: Create through factory method
        order = Order.create(request['customer_id'])
        
        for item_data in request['items']:
            product = Product.objects.get(id=item_data['product_id'])
            order.add_item(product, item_data['quantity'])
        
        # GOOD: Validation in domain object
        order.validate()
        order.calculate_total()
        order.save()
        
        return order
```

**Improvements:**
- Centralized creation logic in factory methods
- Validation encapsulated in domain object
- Object invariants enforced on creation
- Clear creator responsibility
- Reusable across codebase
- Consistent object initialization

### Explanation

The GOOD example follows the Creator pattern by using class methods as factory methods. `Order.create()` encapsulates the creation logic, ensuring all orders are created with consistent initial state. `OrderItem.create()` handles item creation with proper initialization. This provides a single point of control for object creation and ensures invariants are maintained.

---

## Example 2: Factory Method Pattern

### BAD Example: Direct Instantiation with Type Checking

```python
class PaymentProcessor:
    def process_payment(self, payment_type: str, amount: float, details: dict):
        # BAD: Type checking and direct instantiation
        if payment_type == 'credit_card':
            processor = CreditCardPaymentProcessor()
        elif payment_type == 'paypal':
            processor = PayPalPaymentProcessor()
        elif payment_type == 'bank_transfer':
            processor = BankTransferPaymentProcessor()
        else:
            raise ValueError(f'Unknown payment type: {payment_type}')
        
        return processor.process(amount, details)


class OrderService:
    def create_order_processor(self, order_type: str):
        # BAD: Duplicate type checking logic
        if order_type == 'standard':
            return StandardOrderProcessor()
        elif order_type == 'express':
            return ExpressOrderProcessor()
        elif order_type == 'international':
            return InternationalOrderProcessor()
        else:
            raise ValueError(f'Unknown order type: {order_type}')
```

**Problems:**
- Type checking scattered throughout codebase
- Violates Open/Closed Principle
- Adding new types requires modifying multiple places
- Duplicate creation logic
- No centralized factory
- Hard to maintain

### GOOD Example: Factory Method Pattern

```python
class PaymentProcessorFactory:
    _processors = {
        'credit_card': CreditCardPaymentProcessor,
        'paypal': PayPalPaymentProcessor,
        'bank_transfer': BankTransferPaymentProcessor
    }
    
    @classmethod
    def create_processor(cls, payment_type: str) -> PaymentProcessor:
        processor_class = cls._processors.get(payment_type)
        if not processor_class:
            raise ValueError(f'Unknown payment type: {payment_type}')
        return processor_class()
    
    @classmethod
    def register_processor(cls, payment_type: str, processor_class: type):
        cls._processors[payment_type] = processor_class


class OrderProcessorFactory:
    _processors = {
        'standard': StandardOrderProcessor,
        'express': ExpressOrderProcessor,
        'international': InternationalOrderProcessor
    }
    
    @classmethod
    def create_processor(cls, order_type: str) -> OrderProcessor:
        processor_class = cls._processors.get(order_type)
        if not processor_class:
            raise ValueError(f'Unknown order type: {order_type}')
        return processor_class()


class PaymentService:
    def __init__(self, processor_factory: PaymentProcessorFactory):
        self.factory = processor_factory
    
    def process_payment(self, payment_type: str, amount: float, details: dict):
        # GOOD: Create through factory
        processor = self.factory.create_processor(payment_type)
        return processor.process(amount, details)


class OrderService:
    def __init__(self, processor_factory: OrderProcessorFactory):
        self.factory = processor_factory
    
    def create_order_processor(self, order_type: str) -> OrderProcessor:
        # GOOD: Create through factory
        return self.factory.create_processor(order_type)
```

**Improvements:**
- Centralized creation logic in factories
- Type checking consolidated
- Open/Closed Principle followed
- Easy to add new processor types
- Reusable factory pattern
- Clear separation of concerns

### Explanation

The GOOD example implements the Factory Method pattern using factory classes. `PaymentProcessorFactory` and `OrderProcessorFactory` encapsulate object creation logic, consolidating type checking in one place. This follows the Creator pattern by assigning creation responsibility to dedicated factory classes. New processor types can be added without modifying existing code (Open/Closed Principle).

---

## Example 3: Repository Creation

### BAD Example: Repository Instantiation in Controllers

```python
class UserController:
    def get_user(self, user_id: int):
        # BAD: Creating repository directly
        user_repo = UserRepository()
        return user_repo.find_by_id(user_id)


class OrderController:
    def create_order(self, request):
        # BAD: Creating repository directly
        user_repo = UserRepository()
        product_repo = ProductRepository()
        order_repo = OrderRepository()
        
        customer = user_repo.find_by_id(request['customer_id'])
        order = order_repo.create(customer)
        
        for item in request['items']:
            product = product_repo.find_by_id(item['product_id'])
            order.add_item(product, item['quantity'])
        
        return order


class ProductController:
    def search_products(self, query: str):
        # BAD: Creating repository directly
        product_repo = ProductRepository()
        return product_repo.search(query)
```

**Problems:**
- Repositories created in multiple places
- No dependency injection
- Hard to test (can't mock repositories)
- Tight coupling to concrete implementations
- Violates Low Coupling principle
- Difficult to swap implementations

### GOOD Example: Repository Creation via Dependency Injection

```python
class RepositoryFactory:
    _repositories = {}
    
    @classmethod
    def register_repository(cls, interface: type, implementation: type):
        cls._repositories[interface] = implementation
    
    @classmethod
    def create_repository(cls, interface: type):
        implementation = cls._repositories.get(interface)
        if not implementation:
            raise ValueError(f'No implementation registered for {interface}')
        return implementation()


class UserController:
    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository
    
    def get_user(self, user_id: int):
        return self.user_repo.find_by_id(user_id)


class OrderController:
    def __init__(self, 
                 user_repository: UserRepository,
                 product_repository: ProductRepository,
                 order_repository: OrderRepository):
        self.user_repo = user_repository
        self.product_repo = product_repository
        self.order_repo = order_repository
    
    def create_order(self, request):
        customer = self.user_repo.find_by_id(request['customer_id'])
        order = self.order_repo.create(customer)
        
        for item in request['items']:
            product = self.product_repo.find_by_id(item['product_id'])
            order.add_item(product, item['quantity'])
        
        return order


class ProductController:
    def __init__(self, product_repository: ProductRepository):
        self.product_repo = product_repository
    
    def search_products(self, query: str):
        return self.product_repo.search(query)


# Bootstrap/application setup
RepositoryFactory.register_repository(UserRepository, DjangoUserRepository)
RepositoryFactory.register_repository(ProductRepository, DjangoProductRepository)
RepositoryFactory.register_repository(OrderRepository, DjangoOrderRepository)
```

**Improvements:**
- Repositories injected via constructors
- Dependency injection enables testing
- Loose coupling to implementations
- Factory manages repository lifecycle
- Easy to swap implementations
- Follows Creator pattern

### Explanation

The GOOD example follows the Creator pattern by using dependency injection and a factory for repository creation. Repositories are injected into controllers, reducing coupling. The `RepositoryFactory` manages repository creation and implementation registration. This allows easy testing with mocks and swapping implementations (e.g., from Django ORM to SQLAlchemy).

---

## Example 4: Service Object Creation

### BAD Example: Service Instantiation Scattered

```python
class OrderController:
    def create_order(self, request):
        # BAD: Creating services inline
        inventory_service = InventoryService()
        payment_service = PaymentService()
        email_service = EmailService()
        
        order = Order.create(request['customer_id'])
        
        for item in request['items']:
            product = Product.objects.get(id=item['product_id'])
            inventory_service.reserve_stock(product.id, item['quantity'])
        
        payment_service.process_payment(order)
        email_service.send_confirmation(order)
        
        return order


class NotificationController:
    def send_notification(self, request):
        # BAD: Creating service inline
        email_service = EmailService()
        sms_service = SMSService()
        push_service = PushNotificationService()
        
        notification = Notification.create(request)
        
        if notification.via_email:
            email_service.send(notification)
        if notification.via_sms:
            sms_service.send(notification)
        if notification.via_push:
            push_service.send(notification)
        
        return notification
```

**Problems:**
- Services instantiated in multiple places
- No centralized configuration
- Hard to manage service dependencies
- Violates DRY (duplicate creation code)
- No lifecycle management
- Difficult to test

### GOOD Example: Service Container Pattern

```python
class ServiceContainer:
    _services = {}
    _singletons = {}
    
    @classmethod
    def register_service(cls, name: str, factory: callable, singleton: bool = True):
        cls._services[name] = {'factory': factory, 'singleton': singleton}
    
    @classmethod
    def get_service(cls, name: str):
        if name not in cls._services:
            raise ValueError(f'Service {name} not registered')
        
        service_config = cls._services[name]
        
        if service_config['singleton']:
            if name not in cls._singletons:
                cls._singletons[name] = service_config['factory']()
            return cls._singletons[name]
        else:
            return service_config['factory']()
    
    @classmethod
    def reset(cls):
        cls._singletons.clear()


class OrderController:
    def __init__(self, inventory_service: InventoryService,
                 payment_service: PaymentService,
                 email_service: EmailService):
        self.inventory_service = inventory_service
        self.payment_service = payment_service
        self.email_service = email_service
    
    def create_order(self, request):
        order = Order.create(request['customer_id'])
        
        for item in request['items']:
            product = Product.objects.get(id=item['product_id'])
            self.inventory_service.reserve_stock(product.id, item['quantity'])
        
        self.payment_service.process_payment(order)
        self.email_service.send_confirmation(order)
        
        return order


class NotificationController:
    def __init__(self, email_service: EmailService,
                 sms_service: SMSService,
                 push_service: PushNotificationService):
        self.email_service = email_service
        self.sms_service = sms_service
        self.push_service = push_service
    
    def send_notification(self, request):
        notification = Notification.create(request)
        
        if notification.via_email:
            self.email_service.send(notification)
        if notification.via_sms:
            self.sms_service.send(notification)
        if notification.via_push:
            self.push_service.send(notification)
        
        return notification


# Bootstrap/application setup
ServiceContainer.register_service('inventory', lambda: InventoryService())
ServiceContainer.register_service('payment', lambda: PaymentService())
ServiceContainer.register_service('email', lambda: EmailService())
ServiceContainer.register_service('sms', lambda: SMSService())
ServiceContainer.register_service('push', lambda: PushNotificationService())
```

**Improvements:**
- Services managed by container
- Centralized configuration
- Dependency injection supported
- Singleton pattern for expensive services
- Easy to test with mocks
- Clear lifecycle management

### Explanation

The GOOD example implements a service container following the Creator pattern. The `ServiceContainer` manages service creation, supporting both singleton and transient lifecycles. Services are registered with factory functions and retrieved as needed. Controllers receive services via dependency injection, enabling easy testing and reducing coupling. This provides centralized control over object creation and configuration.

---

## Language-Specific Notes

### Idioms and Patterns

- **Class methods**: Use `@classmethod` for factory methods
- **`__init__` methods**: Keep constructors simple, delegate to factory methods
- **Dataclasses**: Use `@dataclass` with `field(default_factory=...)` for default values
- **Singleton pattern**: Use module-level instances or decorators
- **Dependency injection**: Use constructor injection or framework DI

### Language Features

**Features that help:**
- **Class methods**: Natural factory method support with `@classmethod`
- **Static methods**: Utility factory methods with `@staticmethod`
- **Dataclasses**: Clean value object definitions
- **Type hints**: Improve clarity of factory return types
- **Context managers**: Resource management during object creation

**Features that hinder:**
- **Dynamic instantiation**: `globals()[class_name]()` bypasses type checking
- **`eval()` and `exec()`**: Dangerous for object creation
- **Multiple inheritance**: Can complicate creation logic

### Framework Considerations

- **Django**: Use model managers as creators
- **FastAPI**: Use `Depends()` for dependency injection
- **SQLAlchemy**: Use scoped_session for session management
- **Pydantic**: Use model validators for creation logic

### Common Pitfalls

1. **Putting creation logic in `__init__`**: Makes constructors complex
   - Use factory methods for complex initialization

2. **Not using factory methods**: Direct instantiation everywhere
   - Centralize creation logic in factory methods

3. **Violating SRP in constructors**: Doing too much in `__init__`
   - Keep constructors simple, use builders for complex objects

4. **No validation during creation**: Objects created in invalid state
   - Validate in factory methods or `__post_init__`
