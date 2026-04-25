# Creator Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern: Constructor Overload](#anti-pattern-constructor-overload)
- [Anti-Pattern: God Constructor](#anti-pattern-god-constructor)
- [Anti-Pattern: Direct Instantiation Everywhere](#anti-pattern-direct-instantiation-everywhere)
- [Anti-Pattern: Factory Method Misuse](#anti-pattern-factory-method-misuse)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the Creator pattern in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

## Anti-Pattern: Constructor Overload

### Description

Python doesn't support method overloading, so developers try to simulate it with complex constructors that handle multiple optional parameters and conditional logic. This makes constructors hard to understand and use.

### BAD Example

```python
class Order:
    def __init__(self, customer_id=None, items=None, status=None, 
                 total=None, discount=None, shipping=None, 
                 created_at=None, updated_at=None, notes=None):
        # BAD: Constructor with 10 optional parameters
        self.customer_id = customer_id
        self.items = items or []
        self.status = status or 'PENDING'
        self.total = total or 0.0
        self.discount = discount or 0.0
        self.shipping = shipping or 0.0
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.notes = notes or ''
        
        # BAD: Complex conditional logic
        if status == 'COMPLETED' and not total:
            raise ValueError('Completed orders must have a total')
        
        if items and len(items) > 0:
            self.total = sum(item.price * item.quantity for item in items)
            self.apply_discount()
            self.calculate_shipping()


class OrderService:
    def create_order_from_cart(self, cart):
        # BAD: Constructor call with many arguments
        return Order(
            customer_id=cart.customer_id,
            items=cart.items,
            status='PENDING',
            total=cart.total,
            discount=cart.discount,
            shipping=cart.shipping,
            created_at=datetime.now()
        )
    
    def create_order_from_api(self, api_data):
        # BAD: Different order of arguments
        return Order(
            status=api_data.get('status', 'PENDING'),
            customer_id=api_data['customer_id'],
            items=api_data['items'],
            total=api_data.get('total', 0),
            discount=api_data.get('discount', 0),
            notes=api_data.get('notes', '')
        )
```

### Why It's Problematic

- **Hard to use**: Unclear which parameters are required
- **Error-prone**: Easy to pass arguments in wrong order
- **Violates clarity**: Constructor does too much
- **Hard to extend**: Adding new parameters breaks existing calls
- **No type safety**: Parameters can be None in unexpected ways
- **Hard to test**: Many branches to cover

### How to Fix

**Refactoring Steps:**
1. Create factory methods for common creation scenarios
2. Use builder pattern for complex objects
3. Keep constructor simple with required parameters only
4. Use dataclasses for simple value objects
5. Create named constructors for different contexts

### GOOD Example

```python
class Order:
    def __init__(self, customer_id: int):
        # GOOD: Simple constructor with required parameters
        self.customer_id = customer_id
        self.items = []
        self.status = 'PENDING'
        self.total = 0.0
        self.discount = 0.0
        self.shipping = 0.0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.notes = ''
    
    @classmethod
    def from_cart(cls, cart: ShoppingCart) -> 'Order':
        # GOOD: Named constructor for cart conversion
        order = cls(customer_id=cart.customer_id)
        order.items = cart.items.copy()
        order.total = cart.total
        order.discount = cart.discount
        order.calculate_totals()
        return order
    
    @classmethod
    def from_api_request(cls, request: CreateOrderRequest) -> 'Order':
        # GOOD: Named constructor for API requests
        order = cls(customer_id=request.customer_id)
        
        for item in request.items:
            order.add_item(item.product_id, item.quantity)
        
        if request.notes:
            order.notes = request.notes
        
        return order
    
    @classmethod
    def create_completed(cls, customer_id: int, items: List[OrderItem]) -> 'Order':
        # GOOD: Named constructor for specific state
        order = cls(customer_id=customer_id)
        order.items = items
        order.status = 'COMPLETED'
        order.calculate_totals()
        return order


class OrderBuilder:
    def __init__(self, customer_id: int):
        self.customer_id = customer_id
        self.items = []
        self.status = 'PENDING'
        self.discount = 0.0
        self.notes = ''
    
    def with_items(self, items: List[OrderItem]) -> 'OrderBuilder':
        self.items = items
        return self
    
    def with_status(self, status: str) -> 'OrderBuilder':
        self.status = status
        return self
    
    def with_discount(self, discount: float) -> 'OrderBuilder':
        self.discount = discount
        return self
    
    def with_notes(self, notes: str) -> 'OrderBuilder':
        self.notes = notes
        return self
    
    def build(self) -> Order:
        order = Order(self.customer_id)
        order.items = self.items
        order.status = self.status
        order.discount = self.discount
        order.notes = self.notes
        order.calculate_totals()
        return order


# Usage
order = Order.from_cart(cart)
order = Order.from_api_request(request)
order = OrderBuilder(customer_id=1).with_items(items).with_discount(0.1).build()
```

**Key Changes:**
- Constructor simple with single required parameter
- Factory methods for common scenarios
- Builder pattern for flexible construction
- Clear named constructors
- Easy to test and extend

---

## Anti-Pattern: God Constructor

### Description

Constructors that perform extensive work like database queries, API calls, file I/O, or complex calculations. This violates the principle that constructors should only initialize objects to a valid state.

### BAD Example

```python
class OrderService:
    def __init__(self):
        # BAD: Database connection in constructor
        self.db_connection = psycopg2.connect(
            host='localhost',
            database='orders',
            user='user',
            password='password'
        )
        
        # BAD: Loading configuration in constructor
        self.config = self._load_config()
        
        # BAD: Initializing multiple services in constructor
        self.payment_service = PaymentService(self.config['payment'])
        self.email_service = EmailService(self.config['email'])
        self.sms_service = SMSService(self.config['sms'])
        
        # BAD: Loading data in constructor
        self.product_cache = self._load_all_products()
        self.customer_cache = self._load_all_customers()
        
        # BAD: Starting background threads in constructor
        self.notification_thread = threading.Thread(
            target=self._start_notification_worker
        )
        self.notification_thread.start()
    
    def _load_config(self):
        # BAD: File I/O in constructor
        with open('config.json') as f:
            return json.load(f)
    
    def _load_all_products(self):
        # BAD: Database query in constructor
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT * FROM products')
        return {row['id']: row for row in cursor.fetchall()}
    
    def _load_all_customers(self):
        # BAD: Another database query in constructor
        cursor = self.db_connection.cursor()
        cursor.execute('SELECT * FROM customers')
        return {row['id']: row for row in cursor.fetchall()}
```

### Why It's Problematic

- **Hard to test**: Can't mock database, files, or API calls
- **Slow instantiation**: Objects take time to create
- **Side effects**: Constructor has unexpected side effects
- **Violates SRP**: Constructor does too much
- **Hard to debug**: Hard to tell where errors come from
- **Resource leaks**: Connections not properly managed

### How to Fix

**Refactoring Steps:**
1. Inject dependencies via constructor
2. Move expensive operations to lazy initialization
3. Separate configuration loading
4. Don't perform I/O in constructors
5. Use factory for complex initialization

### GOOD Example

```python
class OrderService:
    def __init__(self,
                 db_connection: DatabaseConnection,
                 config: Config,
                 payment_service: PaymentService,
                 email_service: EmailService,
                 sms_service: SMSService):
        # GOOD: Only inject dependencies
        self.db = db_connection
        self.config = config
        self.payment_service = payment_service
        self.email_service = email_service
        self.sms_service = sms_service
        
        # GOOD: Lazy initialization for caches
        self._product_cache = None
        self._customer_cache = None
    
    @property
    def product_cache(self):
        # GOOD: Lazy loading
        if self._product_cache is None:
            self._product_cache = self._load_products()
        return self._product_cache
    
    @property
    def customer_cache(self):
        # GOOD: Lazy loading
        if self._customer_cache is None:
            self._customer_cache = self._load_customers()
        return self._customer_cache
    
    def _load_products(self):
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM products')
        return {row['id']: row for row in cursor.fetchall()}
    
    def _load_customers(self):
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM customers')
        return {row['id']: row for row in cursor.fetchall()}


class OrderServiceFactory:
    # GOOD: Factory for complex initialization
    @staticmethod
    def create_from_config() -> OrderService:
        config = OrderServiceFactory._load_config()
        db = DatabaseConnection(config.database)
        payment = PaymentService(config.payment)
        email = EmailService(config.email)
        sms = SMSService(config.sms)
        
        return OrderService(db, config, payment, email, sms)
    
    @staticmethod
    def create_for_test(mock_db: DatabaseConnection) -> OrderService:
        config = Config.default()
        payment = MockPaymentService()
        email = MockEmailService()
        sms = MockSMSService()
        
        return OrderService(mock_db, config, payment, email, sms)


# Usage in production
service = OrderServiceFactory.create_from_config()

# Usage in tests
mock_db = MockDatabaseConnection()
service = OrderServiceFactory.create_for_test(mock_db)
```

**Key Changes:**
- Dependencies injected, not created
- Lazy initialization for expensive operations
- Factory handles complex setup
- No I/O in constructors
- Easy to test with mocks
- Clear separation of concerns

---

## Anti-Pattern: Direct Instantiation Everywhere

### Description

Using direct instantiation with `ClassName()` throughout the codebase instead of using factory methods or dependency injection. This creates tight coupling and makes testing difficult.

### BAD Example

```python
class OrderController:
    def create_order(self, request):
        # BAD: Direct instantiation
        order = Order(customer_id=request['customer_id'])
        return order


class OrderService:
    def process_order(self, order_id):
        # BAD: Direct instantiation
        order_repo = OrderRepository()
        order = order_repo.find_by_id(order_id)
        
        # BAD: Direct instantiation
        payment_service = PaymentService()
        payment_service.process_payment(order)
        
        # BAD: Direct instantiation
        email_service = EmailService()
        email_service.send_confirmation(order)
        
        return order


class PaymentController:
    def process_payment(self, request):
        # BAD: Direct instantiation
        processor = CreditCardPaymentProcessor()
        return processor.process(request['amount'], request['card'])


class NotificationService:
    def send_notification(self, notification):
        # BAD: Direct instantiation based on type
        if notification.type == 'email':
            sender = EmailSender()
        elif notification.type == 'sms':
            sender = SMSSender()
        elif notification.type == 'push':
            sender = PushSender()
        else:
            raise ValueError(f'Unknown type: {notification.type}')
        
        return sender.send(notification)
```

### Why It's Problematic

- **Tight coupling**: Can't swap implementations
- **Hard to test**: Can't mock dependencies
- **Violates DIP**: Depends on concrete classes
- **Duplicate code**: Same instantiation repeated
- **Hard to configure**: Can't customize objects

### How to Fix

**Refactoring Steps:**
1. Use dependency injection
2. Create factory classes
3. Use interfaces/protocols
4. Register dependencies in container

### GOOD Example

```python
class OrderController:
    def __init__(self, order_factory: OrderFactory):
        self.order_factory = order_factory
    
    def create_order(self, request):
        # GOOD: Create through factory
        order = self.order_factory.create_order(request['customer_id'])
        return order


class OrderService:
    def __init__(self,
                 order_repo: OrderRepository,
                 payment_service: PaymentService,
                 email_service: EmailService):
        # GOOD: Inject dependencies
        self.order_repo = order_repo
        self.payment_service = payment_service
        self.email_service = email_service
    
    def process_order(self, order_id):
        order = self.order_repo.find_by_id(order_id)
        self.payment_service.process_payment(order)
        self.email_service.send_confirmation(order)
        return order


class PaymentController:
    def __init__(self, payment_processor: PaymentProcessor):
        self.processor = payment_processor
    
    def process_payment(self, request):
        # GOOD: Use injected processor
        return self.processor.process(request['amount'], request['card'])


class NotificationFactory:
    _senders = {
        'email': EmailSender,
        'sms': SMSSender,
        'push': PushSender
    }
    
    def create_sender(self, notification_type: str) -> NotificationSender:
        sender_class = self._senders.get(notification_type)
        if not sender_class:
            raise ValueError(f'Unknown type: {notification_type}')
        return sender_class()


class NotificationService:
    def __init__(self, sender_factory: NotificationFactory):
        self.factory = sender_factory
    
    def send_notification(self, notification):
        # GOOD: Create through factory
        sender = self.factory.create_sender(notification.type)
        return sender.send(notification)


# Container setup
class Container:
    _instances = {}
    
    @classmethod
    def get(cls, interface: type):
        if interface not in cls._instances:
            cls._instances[interface] = cls._create(interface)
        return cls._instances[interface]
    
    @classmethod
    def _create(cls, interface: type):
        if interface == OrderController:
            return OrderController(cls.get(OrderFactory))
        if interface == OrderService:
            return OrderService(
                cls.get(OrderRepository),
                cls.get(PaymentService),
                cls.get(EmailService)
            )
        # ... other mappings
```

**Key Changes:**
- Dependencies injected via constructors
- Factories manage object creation
- Container manages lifecycle
- Easy to test with mocks
- Loose coupling through interfaces

---

## Anti-Pattern: Factory Method Misuse

### Description

Using factory methods inappropriately, such as creating factories for simple objects, or using factories when simple constructors would suffice. This adds unnecessary complexity.

### BAD Example

```python
class SimpleStringFactory:
    # BAD: Unnecessary factory for simple objects
    @staticmethod
    def create_string(value: str) -> str:
        return value


class IntegerFactory:
    # BAD: Factory for simple primitive
    @classmethod
    def create_integer(cls, value: int) -> int:
        return value


class DataFactory:
    # BAD: Factory just passes through
    @staticmethod
    def create_data(data: dict) -> dict:
        return data.copy()


class ProductFactory:
    # BAD: Factory doesn't add value
    @staticmethod
    def create_product(name: str, price: float) -> Product:
        return Product(name=name, price=price)


class OrderItemFactory:
    # BAD: Factory just calls constructor
    def create_order_item(self, product_id: int, quantity: int, price: float) -> OrderItem:
        return OrderItem(product_id, quantity, price)
```

### Why It's Problematic

- **Unnecessary indirection**: Adds layers without benefit
- **Code bloat**: Extra classes for no reason
- **Violates YAGNI**: Don't need factories for simple objects
- **Harder to read**: Indirection makes code less clear
- **Performance overhead**: Extra function calls

### How to Fix

**Refactoring Steps:**
1. Remove factories for simple objects
2. Use factory methods only when they add value
3. Keep constructors for straightforward cases
4. Use factories only for complex creation logic

### GOOD Example

```python
# GOOD: Simple objects use constructors directly
def create_simple_string(value: str) -> str:
    return value


def create_data(data: dict) -> dict:
    return data.copy()


# GOOD: Factory methods add value (encapsulation, validation)
class Product:
    @classmethod
    def create(cls, name: str, price: float) -> 'Product':
        cls._validate_price(price)
        cls._validate_name(name)
        return cls(name=name, price=price)
    
    @staticmethod
    def _validate_price(price: float):
        if price < 0:
            raise ValueError('Price cannot be negative')
    
    @staticmethod
    def _validate_name(name: str):
        if not name or len(name) > 100:
            raise ValueError('Invalid product name')


# GOOD: Factory handles complex initialization
class OrderItem:
    @classmethod
    def create_from_product(cls, product: Product, quantity: int) -> 'OrderItem':
        cls._validate_quantity(quantity)
        return cls(
            product_id=product.id,
            quantity=quantity,
            price=product.get_current_price()
        )
    
    @classmethod
    def create_from_api(cls, data: dict) -> 'OrderItem':
        cls._validate_data(data)
        return cls(
            product_id=data['product_id'],
            quantity=data['quantity'],
            price=data['price']
        )
    
    @staticmethod
    def _validate_quantity(quantity: int):
        if quantity <= 0:
            raise ValueError('Quantity must be positive')
    
    @staticmethod
    def _validate_data(data: dict):
        required = ['product_id', 'quantity', 'price']
        for field in required:
            if field not in data:
                raise ValueError(f'Missing required field: {field}')


# GOOD: Factory for polymorphic creation
class PaymentProcessorFactory:
    _processors = {
        'credit_card': CreditCardProcessor,
        'paypal': PayPalProcessor,
        'bank_transfer': BankTransferProcessor
    }
    
    @classmethod
    def create_processor(cls, payment_type: str) -> PaymentProcessor:
        processor_class = cls._processors.get(payment_type)
        if not processor_class:
            raise ValueError(f'Unknown payment type: {payment_type}')
        return processor_class()


# GOOD: Direct use when simple
user = User(name='John', email='john@example.com')
product = Product(name='Widget', price=9.99)
```

**Key Changes:**
- Removed unnecessary factories
- Factory methods only when they add value
- Direct constructors for simple cases
- Factory methods handle validation and complex logic
- Clear when to use factory vs constructor

---

## Detection Checklist

Use this checklist to identify Creator pattern violations in Python code:

### Code Review Questions

- [ ] Does the constructor have more than 5 parameters?
- [ ] Does the constructor perform I/O operations?
- [ ] Does the constructor make database queries or API calls?
- [ ] Does the constructor have complex conditional logic?
- [ ] Are objects created with direct `ClassName()` calls throughout codebase?
- [ ] Does a factory just pass through to a constructor without adding value?
- [ ] Is there duplication in object creation code?

### Automated Detection

- **Parameter count**: Flag constructors with >5 parameters
- **Cyclomatic complexity**: Flag constructors with complexity > 3
- **File/network access**: Check for file I/O or network calls in `__init__`
- **Duplication**: Look for repeated instantiation patterns
- **Factory analysis**: Flag factories that don't add logic

### Manual Inspection Techniques

1. **Read constructors**: If `__init__` is >20 lines, it's doing too much
2. **Check for `new` patterns**: Direct instantiation scattered throughout code
3. **Look for factories**: Determine if they add value or just add indirection
4. **Follow object creation**: Trace how objects are created across codebase

### Common Symptoms

- **Long constructors**: `__init__` methods with 50+ lines
- **Many parameters**: Constructors with 10+ optional arguments
- **I/O in constructors**: File reads, database queries, network calls
- **Scattered creation**: Same creation logic duplicated
- **Unnecessary factories**: Factory methods that just call `__init__`
- **Tight coupling**: Direct instantiation of concrete classes

---

## Language-Specific Notes

### Common Causes in Python

- **No overloading**: Developers try to simulate with many optional parameters
- **Flexible types**: No compile-time checking for constructor signatures
- **Easy instantiation**: `ClassName()` is very easy and tempting
- **Lack of DI containers**: Few Python frameworks enforce DI patterns

### Language Features that Enable Anti-Patterns

- **Optional parameters**: Easy to add many defaults
- **Dynamic typing**: Can pass anything as constructor arguments
- **`*args` and `**kwargs`**: Can hide complex initialization
- **Class methods**: Easy to create factory methods (can overuse)

### Framework-Specific Anti-Patterns

- **Django**: Creating model instances directly instead of using managers
- **FastAPI**: No framework-enforced DI (manual injection only)
- **SQLAlchemy**: Direct session usage instead of repository pattern

### Tooling Support

- **Pylint**: Detects long methods and many arguments
- **Mypy**: Type hints can catch some construction issues
- **Pytest**: Mocking reveals tight coupling issues
- **Sourcery**: Suggests factory methods for complex constructors
