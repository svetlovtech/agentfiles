# Controller Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern: Fat Controller](#anti-pattern-fat-controller)
- [Anti-Pattern: Business Logic in Controller](#anti-pattern-business-logic-in-controller)
- [Anti-Pattern: Direct Database Access](#anti-pattern-direct-database-access)
- [Anti-Pattern: Controller as Service Layer](#anti-pattern-controller-as-service-layer)
- [Anti-Pattern: God Controller](#anti-pattern-god-controller)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns that violate the Controller pattern in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

## Anti-Pattern: Fat Controller

### Description

Fat Controllers contain excessive business logic, calculations, and operations that should be delegated to domain objects or services. This happens when developers put all request handling logic in the controller for simplicity, resulting in methods with 50+ lines that are hard to understand, test, and maintain.

### BAD Example

```python
class OrderController:
    def create_order(self, request):
        # 80+ lines of business logic in controller
        if not request.get('customer_id'):
            return {'error': 'Customer required'}, 400
        
        customer = Customer.objects.get(id=request['customer_id'])
        
        total = 0
        items = []
        for item_data in request['items']:
            product = Product.objects.get(id=item_data['product_id'])
            
            # Business logic: Stock validation
            if product.stock < item_data['quantity']:
                return {'error': f'Product {product.id} out of stock'}, 400
            
            # Business logic: Bulk discount calculation
            item_total = product.price * item_data['quantity']
            if item_data['quantity'] >= 10:
                item_total *= 0.85  # 15% bulk discount
            elif item_data['quantity'] >= 5:
                item_total *= 0.90  # 10% bulk discount
            
            total += item_total
            items.append({
                'product_id': product.id,
                'quantity': item_data['quantity'],
                'price': product.price,
                'discounted_price': item_total / item_data['quantity']
            })
        
        # Business logic: Customer discount
        if customer.total_orders > 10:
            total *= 0.95  # 5% loyal customer discount
        elif customer.total_orders > 50:
            total *= 0.90  # 10% VIP customer discount
        
        # Business logic: Shipping calculation
        shipping = 0
        if total < 50:
            shipping = 9.99
        elif total < 100:
            shipping = 4.99
        total += shipping
        
        # Business logic: Tax calculation
        tax = total * 0.08
        total += tax
        
        # Create order
        order = Order.objects.create(
            customer_id=customer.id,
            subtotal=total - shipping - tax,
            shipping=shipping,
            tax=tax,
            total=total,
            status='PENDING'
        )
        
        # Create order items
        for item in items:
            OrderItem.objects.create(
                order_id=order.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                price=item['price']
            )
            
            # Update stock
            Product.objects.filter(id=item['product_id']).update(
                stock=F('stock') - item['quantity']
            )
        
        # Send email
        send_email(
            to=customer.email,
            subject=f'Order #{order.id} Confirmed',
            body=f'Total: ${total:.2f}'
        )
        
        return {'order_id': order.id, 'total': total}, 201
```

### Why It's Problematic

- **Hard to test**: Business logic tightly coupled to HTTP request handling
- **Hard to understand**: 80+ line method with multiple concerns mixed together
- **Code duplication**: Similar logic likely repeated in other controllers
- **Violates SRP**: Controller handles validation, calculations, persistence, and notifications
- **Violates Information Expert**: Domain objects should contain business logic
- **Tight coupling**: Direct database access prevents swapping implementations
- **Not reusable**: Business logic trapped in HTTP context

### How to Fix

**Refactoring Steps:**
1. Extract validation logic into dedicated validator class
2. Extract calculations to domain objects (Order, Product)
3. Extract persistence to repository classes
4. Extract notifications to email service
5. Create service class to orchestrate domain objects
6. Make controller thin (5-15 lines)

### GOOD Example

```python
class OrderController:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service
    
    def create_order(self, request):
        try:
            create_order_request = CreateOrderRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        order = self.order_service.create_order(create_order_request)
        return OrderResponse.from_order(order), 201


class OrderService:
    def __init__(self, order_repo: OrderRepository,
                 product_repo: ProductRepository,
                 email_service: EmailService):
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.email_service = email_service
    
    def create_order(self, request: CreateOrderRequest) -> Order:
        customer = self.product_repo.get_customer(request.customer_id)
        
        order = Order.create(customer.id)
        for item_data in request.items:
            product = self.product_repo.get_product(item_data.product_id)
            order.add_item(product, item_data.quantity)
            product.reserve_stock(item_data.quantity)
        
        order.apply_customer_discount(customer.tier)
        order.calculate_totals()
        
        self.order_repo.save(order)
        self.product_repo.update_stock_batch(order.items)
        self.email_service.send_confirmation(order)
        
        return order


class Order:
    @classmethod
    def create(cls, customer_id: int) -> 'Order':
        return cls(customer_id=customer_id, items=[])
    
    def add_item(self, product: Product, quantity: int):
        item = OrderItem(product.id, quantity, product.price)
        item.apply_bulk_discount(quantity)
        self.items.append(item)
    
    def apply_customer_discount(self, tier: str):
        multiplier = {'BRONZE': 1.0, 'SILVER': 0.95, 'GOLD': 0.90}.get(tier, 1.0)
        self.customer_discount_multiplier = multiplier
    
    def calculate_totals(self):
        subtotal = sum(item.total() for item in self.items)
        subtotal *= self.customer_discount_multiplier
        
        self.shipping = self._calculate_shipping(subtotal)
        self.tax = subtotal * 0.08
        self.total = subtotal + self.shipping + self.tax
    
    def _calculate_shipping(self, subtotal: float) -> float:
        if subtotal < 50:
            return 9.99
        elif subtotal < 100:
            return 4.99
        return 0.0


class OrderItem:
    def __init__(self, product_id: int, quantity: int, price: float):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price
        self.discount_multiplier = 1.0
    
    def apply_bulk_discount(self, quantity: int):
        if quantity >= 10:
            self.discount_multiplier = 0.85
        elif quantity >= 5:
            self.discount_multiplier = 0.90
    
    def total(self) -> float:
        return self.price * self.quantity * self.discount_multiplier
```

**Key Changes:**
- Controller reduced to 5 lines of orchestration
- Business logic moved to Order and OrderItem domain objects
- Persistence abstracted through repositories
- Email logic in dedicated service
- Each class has single responsibility
- Easy to test independently

---

## Anti-Pattern: Business Logic in Controller

### Description

Business logic like calculations, validations, and domain rules placed in controllers instead of domain objects or services. This anti-pattern emerges when developers don't understand that controllers should only coordinate, not calculate.

### BAD Example

```python
class PaymentController:
    def process_payment(self, request):
        payment_method = request.get('payment_method')
        amount = request.get('amount')
        
        # Business logic: Payment method validation
        if payment_method not in ['credit_card', 'paypal', 'bank_transfer']:
            return {'error': 'Invalid payment method'}, 400
        
        # Business logic: Minimum amount validation
        if amount < 10:
            return {'error': 'Minimum amount is $10'}, 400
        
        # Business logic: Maximum amount validation
        if amount > 10000:
            return {'error': 'Maximum amount is $10000'}, 400
        
        # Business logic: Credit card specific validation
        if payment_method == 'credit_card':
            card = request.get('card')
            if not card or not card.get('number') or not card.get('cvv'):
                return {'error': 'Invalid card details'}, 400
            
            # Business logic: Luhn algorithm
            if not self._luhn_check(card['number']):
                return {'error': 'Invalid card number'}, 400
            
            # Business logic: Card expiration validation
            exp_month, exp_year = card.get('expiry', '/').split('/')
            if datetime.now() > datetime(int(exp_year), int(exp_month), 1):
                return {'error': 'Card expired'}, 400
        
        # Process payment
        payment = Payment.objects.create(
            method=payment_method,
            amount=amount,
            status='PROCESSING'
        )
        
        return {'payment_id': payment.id}, 201
```

### Why It's Problematic

- **Domain rules scattered**: Validation rules not with domain entities
- **Hard to reuse**: Can't use validation logic outside HTTP context
- **Hard to test**: Validation mixed with HTTP concerns
- **Violates Information Expert**: Payment object should validate itself
- **Duplicated logic**: Same validation likely needed elsewhere

### How to Fix

**Refactoring Steps:**
1. Create Payment entity with validation methods
2. Create payment processor classes for each method
3. Extract validation to domain objects
4. Use factory for processor selection
5. Make controller thin

### GOOD Example

```python
class PaymentController:
    def __init__(self, payment_service: PaymentService):
        self.payment_service = payment_service
    
    def process_payment(self, request):
        try:
            payment_request = PaymentRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        payment = self.payment_service.process_payment(payment_request)
        return PaymentResponse.from_payment(payment), 201


class PaymentService:
    def __init__(self, processor_factory: PaymentProcessorFactory,
                 payment_repo: PaymentRepository):
        self.processor_factory = processor_factory
        self.payment_repo = payment_repo
    
    def process_payment(self, request: PaymentRequest) -> Payment:
        processor = self.processor_factory.get_processor(request.payment_method)
        result = processor.process(request.amount, request.payment_details)
        
        payment = Payment.create(request.payment_method, request.amount, result)
        self.payment_repo.save(payment)
        return payment


class CreditCardProcessor(PaymentProcessor):
    def validate_details(self, details: CreditCardDetails):
        if not details.number or len(details.number) < 13:
            raise InvalidCardError('Invalid card number')
        
        if not self._luhn_check(details.number):
            raise InvalidCardError('Card number failed validation')
        
        if datetime.now() > details.expiry_date:
            raise CardExpiredError(details.expiry_date)
    
    def _luhn_check(self, card_number: str) -> bool:
        # Luhn algorithm implementation
        pass


class Payment:
    @classmethod
    def create(cls, method: str, amount: float, result: PaymentResult) -> 'Payment':
        cls._validate_amount(amount)
        return cls(
            method=method,
            amount=amount,
            status=result.status,
            transaction_id=result.transaction_id
        )
    
    @staticmethod
    def _validate_amount(amount: float):
        if amount < 10:
            raise InvalidAmountError('Minimum amount is $10')
        if amount > 10000:
            raise InvalidAmountError('Maximum amount is $10000')
```

**Key Changes:**
- Validation logic in domain objects
- Payment processors encapsulate method-specific logic
- Controller only orchestrates
- Validation rules centralized
- Easy to test validation independently

---

## Anti-Pattern: Direct Database Access

### Description

Controllers directly querying and manipulating databases instead of using repository abstractions. This creates tight coupling to database implementation and makes testing difficult.

### BAD Example

```python
class UserController:
    def get_user(self, user_id):
        # Direct database access
        user = User.objects.get(id=user_id)
        return {'id': user.id, 'email': user.email}, 200
    
    def update_user(self, user_id, request):
        # Direct database access
        user = User.objects.get(id=user_id)
        user.email = request.get('email', user.email)
        user.name = request.get('name', user.name)
        user.save()
        return {'id': user.id, 'email': user.email}, 200
    
    def delete_user(self, user_id):
        # Direct database access
        User.objects.filter(id=user_id).delete()
        return {}, 204
```

### Why It's Problematic

- **Tight coupling**: Controller depends on ORM specifics
- **Hard to test**: Can't mock database easily
- **No abstraction**: Can't swap database implementation
- **Violates Pure Fabrication**: Should use repositories
- **Scattered queries**: Business data access logic spread across controllers

### How to Fix

**Refactoring Steps:**
1. Create repository interface
2. Implement repository with database logic
3. Inject repository into controller
4. Use repository methods instead of direct queries

### GOOD Example

```python
class UserController:
    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository
    
    def get_user(self, user_id):
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return {'error': 'User not found'}, 404
        return UserResponse.from_user(user), 200
    
    def update_user(self, user_id, request):
        user = self.user_repo.find_by_id(user_id)
        if not user:
            return {'error': 'User not found'}, 404
        
        user.update_email(request.get('email'))
        user.update_name(request.get('name'))
        self.user_repo.save(user)
        return UserResponse.from_user(user), 200
    
    def delete_user(self, user_id):
        if not self.user_repo.exists(user_id):
            return {'error': 'User not found'}, 404
        self.user_repo.delete(user_id)
        return {}, 204


class UserRepository(ABC):
    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[User]:
        pass
    
    @abstractmethod
    def save(self, user: User) -> None:
        pass
    
    @abstractmethod
    def delete(self, user_id: int) -> None:
        pass
    
    @abstractmethod
    def exists(self, user_id: int) -> bool:
        pass


class DjangoUserRepository(UserRepository):
    def find_by_id(self, user_id: int) -> Optional[User]:
        try:
            user_django = User.objects.get(id=user_id)
            return User.from_django_model(user_django)
        except User.DoesNotExist:
            return None
    
    def save(self, user: User) -> None:
        user_django = User.objects.get(id=user.id)
        user_django.email = user.email
        user_django.name = user.name
        user_django.save()
```

**Key Changes:**
- Repository interface abstracts data access
- Controller depends on abstraction, not implementation
- Easy to mock for testing
- Database logic centralized in repository
- Can swap implementations (Django, SQLAlchemy, etc.)

---

## Anti-Pattern: Controller as Service Layer

### Description

Controllers treating themselves as service layers, containing business logic that should be in services or domain objects. This happens when developers think "controllers handle requests, so they should contain all request processing logic."

### BAD Example

```python
class OrderController:
    def create_order(self, request):
        # Controller acting as service layer
        customer = self._get_or_create_customer(request)
        order = self._create_order(customer, request)
        self._process_payment(order, request)
        self._reserve_inventory(order)
        self._send_notifications(order)
        return order
    
    def _get_or_create_customer(self, request):
        email = request['customer']['email']
        customer = Customer.objects.filter(email=email).first()
        if not customer:
            customer = Customer.objects.create(
                email=email,
                name=request['customer']['name']
            )
        return customer
    
    def _create_order(self, customer, request):
        order = Order.objects.create(customer=customer)
        for item in request['items']:
            OrderItem.objects.create(
                order=order,
                product_id=item['product_id'],
                quantity=item['quantity']
            )
        return order
    
    def _process_payment(self, order, request):
        payment = Payment.objects.create(
            order=order,
            amount=order.total,
            method=request['payment']['method']
        )
        # Payment processing logic
        return payment
    
    def _reserve_inventory(self, order):
        for item in order.items:
            product = Product.objects.get(id=item.product_id)
            product.stock -= item.quantity
            product.save()
    
    def _send_notifications(self, order):
        send_email(order.customer.email, 'Order created')
        send_sms(order.customer.phone, 'Order created')
```

### Why It's Problematic

- **Blurred boundaries**: Controller and service layer mixed
- **Hard to test**: Business logic tied to HTTP context
- **Not reusable**: Service methods can't be called from other contexts
- **Violates separation of concerns**: Each layer has multiple responsibilities

### How to Fix

**Refactoring Steps:**
1. Extract business logic to OrderService
2. Move private methods to service class
3. Make controller thin (single method call)
4. Use domain objects for business rules

### GOOD Example

```python
class OrderController:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service
    
    def create_order(self, request):
        try:
            create_order_request = CreateOrderRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        order = self.order_service.create_order(create_order_request)
        return OrderResponse.from_order(order), 201


class OrderService:
    def __init__(self, customer_service: CustomerService,
                 payment_service: PaymentService,
                 inventory_service: InventoryService,
                 notification_service: NotificationService,
                 order_repo: OrderRepository):
        self.customer_service = customer_service
        self.payment_service = payment_service
        self.inventory_service = inventory_service
        self.notification_service = notification_service
        self.order_repo = order_repo
    
    def create_order(self, request: CreateOrderRequest) -> Order:
        customer = self.customer_service.get_or_create(request.customer)
        order = self._create_order(customer, request.items)
        self.payment_service.process_payment(order, request.payment)
        self.inventory_service.reserve_stock(order)
        self.notification_service.send_order_notifications(order)
        self.order_repo.save(order)
        return order
    
    def _create_order(self, customer: Customer, items: List) -> Order:
        order = Order.create(customer.id)
        for item in items:
            order.add_item(item.product_id, item.quantity)
        return order


class CustomerService:
    def get_or_create(self, customer_data: CustomerData) -> Customer:
        existing = self.customer_repo.find_by_email(customer_data.email)
        if existing:
            return existing
        return self.customer_repo.create(customer_data)
```

**Key Changes:**
- Clear service layer with business logic
- Controller only handles HTTP concerns
- Services can be reused in non-HTTP contexts
- Each service has single responsibility
- Easy to test independently

---

## Anti-Pattern: God Controller

### Description

A single controller handling too many responsibilities and operations, often dozens of methods covering multiple unrelated use cases. This creates a maintenance nightmare and violates the Single Responsibility Principle.

### BAD Example

```python
class ApiController:
    # User management
    def register_user(self, request): pass
    def login_user(self, request): pass
    def update_user(self, request): pass
    def delete_user(self, request): pass
    def get_user_profile(self, request): pass
    def change_password(self, request): pass
    def reset_password(self, request): pass
    def upload_avatar(self, request): pass
    
    # Order management
    def create_order(self, request): pass
    def get_order(self, request): pass
    def cancel_order(self, request): pass
    def refund_order(self, request): pass
    def get_order_history(self, request): pass
    
    # Product management
    def create_product(self, request): pass
    def update_product(self, request): pass
    def delete_product(self, request): pass
    def get_product(self, request): pass
    def search_products(self, request): pass
    
    # Payment management
    def process_payment(self, request): pass
    def refund_payment(self, request): pass
    def get_payment_status(self, request): pass
    
    # Notification management
    def send_email(self, request): pass
    def send_sms(self, request): pass
    def get_notifications(self, request): pass
    
    # Admin operations
    def get_dashboard_stats(self, request): pass
    def generate_report(self, request): pass
    def manage_settings(self, request): pass
    
    # And 20+ more methods...
```

### Why It's Problematic

- **Violates SRP**: Single class handling multiple unrelated concerns
- **Hard to maintain**: Changes affect many unrelated methods
- **Hard to test**: Massive test suite required
- **Hard to understand**: Too many methods to comprehend
- **Team conflicts**: Multiple developers stepping on each other
- **Deployment issues**: Changes in one area force redeployment of all

### How to Fix

**Refactoring Steps:**
1. Group related operations by feature/bounded context
2. Create separate controllers for each group
3. Ensure each controller has single responsibility
4. Use facade for cross-cutting concerns if needed

### GOOD Example

```python
# User feature
class UserController:
    def __init__(self, user_service: UserService):
        self.user_service = user_service
    
    def register(self, request): pass
    def get_profile(self, request): pass
    def update_profile(self, request): pass
    def change_password(self, request): pass

# Orders feature
class OrderController:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service
    
    def create(self, request): pass
    def get(self, request): pass
    def cancel(self, request): pass
    def get_history(self, request): pass

# Products feature
class ProductController:
    def __init__(self, product_service: ProductService):
        self.product_service = product_service
    
    def create(self, request): pass
    def get(self, request): pass
    def update(self, request): pass
    def search(self, request): pass

# Payments feature
class PaymentController:
    def __init__(self, payment_service: PaymentService):
        self.payment_service = payment_service
    
    def process(self, request): pass
    def refund(self, request): pass
    def get_status(self, request): pass

# Notifications feature
class NotificationController:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
    
    def send(self, request): pass
    def get_history(self, request): pass

# Admin feature
class AdminController:
    def __init__(self, admin_service: AdminService):
        self.admin_service = admin_service
    
    def get_dashboard_stats(self, request): pass
    def generate_report(self, request): pass
    def manage_settings(self, request): pass
```

**Key Changes:**
- Controllers organized by feature/bounded context
- Each controller has 3-5 related methods
- Clear single responsibility per controller
- Easy to understand and maintain
- Teams can work on different controllers independently
- Can deploy changes per feature

---

## Detection Checklist

Use this checklist to identify Controller pattern violations in Python code:

### Code Review Questions

- [ ] Does the controller method exceed 20 lines?
- [ ] Does the controller contain business logic calculations?
- [ ] Does the controller directly access the database (ORM queries)?
- [ ] Does the controller send emails or notifications directly?
- [ ] Does the controller validate complex business rules?
- [ ] Does the controller handle file processing or transformations?
- [ ] Does the controller have more than 5 public methods?
- [ ] Does the controller handle unrelated operations?

### Automated Detection

- **Method length**: Flag methods over 20 lines in controller files
- **ORM queries**: Check for `Model.objects.get/filter` in controllers
- **Import statements**: Look for business logic imports in controller files
- **Cyclomatic complexity**: Flag methods with complexity > 3
- **Line count**: Check controller files over 300 lines

### Manual Inspection Techniques

1. **Read controller method**: If it takes more than 30 seconds to understand, it's too complex
2. **Check dependencies**: Count injected services (should be 1-3, not 10+)
3. **Look for private methods**: Many private methods suggest business logic in controller
4. **Follow the flow**: If method does validation, calculation, persistence, and notification, it's too much

### Common Symptoms

- **Fat views**: View functions with 50+ lines of logic
- **Direct ORM usage**: `User.objects.get()` in view/controller code
- **Mixed concerns**: Controllers handling both HTTP and business logic
- **Hard to test**: Can't unit test without full HTTP context
- **God classes**: Single controller with 20+ methods
- **Copy-paste**: Same validation logic repeated across controllers

---

## Language-Specific Notes

### Common Causes in Python

- **Framework defaults**: Django's `views.py` encourages putting logic in views
- **Rapid prototyping**: Quick to put everything in one place initially
- **Lack of service layer**: Django doesn't enforce service layer
- **ORM convenience**: Direct ORM queries are very convenient
- **Flask simplicity**: Flask makes it easy to add logic to route handlers

### Language Features that Enable Anti-Patterns

- **Dynamic typing**: No compile-time checks for business logic placement
- **Decorators**: Can hide logic that should be in services
- **Context managers**: May lead to resource management in controllers
- **List comprehensions**: Can hide complex calculations in one-liners

### Framework-Specific Anti-Patterns

- **Django**: Fat views with ORM queries mixed with business logic
- **Flask**: Route handlers with all logic inline
- **FastAPI**: Endpoint functions with logic not in services
- **Pyramid**: Views acting as service layer

### Tooling Support

- **Pylint**: Detects long methods, high cyclomatic complexity
- **Flake8**: Flags long lines and complexity
- **Pytest**: Use mocking to identify tight coupling
- **Sourcery**: AI-powered refactoring suggestions
- **Black**: Formatting helps spot long methods
