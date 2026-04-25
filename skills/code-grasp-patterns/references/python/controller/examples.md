# Controller Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: E-commerce Order Creation](#example-1-ecommerce-order-creation)
- [Example 2: User Registration](#example-2-user-registration)
- [Example 3: API Gateway Facade](#example-3-api-gateway-facade)
- [Example 4: Payment Processing](#example-4-payment-processing)
- [Example 5: File Upload Handler](#example-5-file-upload-handler)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of the Controller pattern in Python. Each example demonstrates a common violation and the corrected implementation following GRASP principles.

## Example 1: E-commerce Order Creation

### BAD Example: Fat Controller with Business Logic

```python
class OrderController:
    def create_order(self, request):
        # BAD: Validation logic in controller
        if not request.get('customer_id'):
            return {'error': 'Customer ID required'}, 400
        
        if not request.get('items') or len(request['items']) == 0:
            return {'error': 'Items required'}, 400
        
        # BAD: Business logic calculation in controller
        customer = Customer.objects.get(id=request['customer_id'])
        total = 0
        for item in request['items']:
            product = Product.objects.get(id=item['product_id'])
            if product.stock < item['quantity']:
                return {'error': 'Insufficient stock'}, 400
            total += product.price * item['quantity']
        
        # BAD: Apply discount logic in controller
        if total > 1000:
            total *= 0.9  # 10% discount
        
        # BAD: Direct database access
        order = Order.objects.create(
            customer_id=customer.id,
            total=total,
            status='PENDING'
        )
        
        # BAD: Direct database operations
        for item in request['items']:
            OrderItem.objects.create(
                order_id=order.id,
                product_id=item['product_id'],
                quantity=item['quantity'],
                price=Product.objects.get(id=item['product_id']).price
            )
            # BAD: Direct stock update
            Product.objects.filter(id=item['product_id']).update(
                stock=F('stock') - item['quantity']
            )
        
        # BAD: Direct email sending
        send_email(
            to=customer.email,
            subject='Order Created',
            body=f'Your order {order.id} has been created'
        )
        
        return {'order_id': order.id, 'total': total}, 201
```

**Problems:**
- Validation logic should be in domain or service layer
- Business calculations belong in domain objects (Information Expert)
- Direct database access should use repositories (Pure Fabrication)
- Email sending should use dedicated service
- Controller has 50+ lines of business logic
- Hard to test due to tight coupling
- Violates Single Responsibility Principle

### GOOD Example: Thin Controller with Delegation

```python
class OrderController:
    def __init__(self, order_service: OrderService):
        self.order_service = order_service
    
    def create_order(self, request):
        # GOOD: Validate request DTO
        try:
            create_order_request = CreateOrderRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        # GOOD: Delegate all business logic to service
        try:
            order = self.order_service.create_order(create_order_request)
            return OrderResponse.from_order(order), 201
        except InsufficientStockError as e:
            return {'error': str(e)}, 400
        except CustomerNotFoundError as e:
            return {'error': str(e)}, 404


class OrderService:
    def __init__(self, order_repo: OrderRepository, 
                 product_repo: ProductRepository,
                 email_service: EmailService):
        self.order_repo = order_repo
        self.product_repo = product_repo
        self.email_service = email_service
    
    def create_order(self, request: CreateOrderRequest) -> Order:
        # GOOD: Business logic in service/domain
        customer = self.product_repo.get_customer(request.customer_id)
        if not customer:
            raise CustomerNotFoundError(request.customer_id)
        
        # GOOD: Create order through domain
        order = Order.create(customer.id)
        
        for item in request.items:
            product = self.product_repo.get_product(item.product_id)
            if not product:
                raise ProductNotFoundError(item.product_id)
            if product.stock < item.quantity:
                raise InsufficientStockError(product.id, item.quantity)
            
            # GOOD: Domain logic in Order entity
            order.add_item(product, item.quantity)
            product.reserve_stock(item.quantity)
        
        # GOOD: Apply discount in domain
        total = order.calculate_total()
        
        # GOOD: Repository for persistence
        self.order_repo.save(order)
        self.product_repo.update_stock_batch(order.items)
        
        # GOOD: Email service for notifications
        self.email_service.send_order_confirmation(order)
        
        return order


class Order:
    def __init__(self, customer_id: int):
        self.customer_id = customer_id
        self.items = []
        self.status = 'PENDING'
    
    @classmethod
    def create(cls, customer_id: int) -> 'Order':
        return cls(customer_id)
    
    def add_item(self, product: Product, quantity: int):
        item = OrderItem(product.id, quantity, product.price)
        self.items.append(item)
    
    def calculate_total(self) -> float:
        total = sum(item.price * item.quantity for item in self.items)
        # GOOD: Domain discount logic
        if total > 1000:
            total *= 0.9
        return total
```

**Improvements:**
- Controller is thin (5 lines of orchestration)
- Business logic delegated to OrderService and domain objects
- Repository pattern for data access
- Domain objects contain business rules (Information Expert)
- Clear separation of concerns
- Easy to test with mocks
- Follows dependency injection

### Explanation

The GOOD example demonstrates proper Controller pattern application. The controller only receives the request, validates it using a DTO, and delegates to the OrderService. The service orchestrates domain objects which contain business logic. The Order entity calculates totals and applies discounts (Information Expert pattern). Repositories handle persistence (Pure Fabrication), and a separate service handles email. This creates a clear separation between layers with low coupling and high cohesion.

---

## Example 2: User Registration

### BAD Example: Controller with All Logic

```python
class UserController:
    def register(self, request):
        # BAD: Validation in controller
        email = request.get('email')
        password = request.get('password')
        
        if not email or '@' not in email:
            return {'error': 'Invalid email'}, 400
        
        if not password or len(password) < 8:
            return {'error': 'Password too short'}, 400
        
        # BAD: Business logic in controller
        if User.objects.filter(email=email).exists():
            return {'error': 'Email already registered'}, 400
        
        # BAD: Password hashing in controller
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        
        # BAD: Direct database access
        user = User.objects.create(
            email=email,
            password=hashed_password,
            is_active=False
        )
        
        # BAD: Token generation in controller
        token = generate_random_token()
        VerificationToken.objects.create(user=user, token=token)
        
        # BAD: Email sending in controller
        send_verification_email(email, token)
        
        return {'user_id': user.id}, 201
```

**Problems:**
- Validation logic mixed with controller
- Business rules in controller
- Password hashing should be in service
- Direct database queries
- Token generation not isolated
- Email logic tightly coupled
- No reusable components

### GOOD Example: Thin Controller with Service Delegation

```python
class UserController:
    def __init__(self, user_service: UserService):
        self.user_service = user_service
    
    def register(self, request):
        # GOOD: Create request DTO
        try:
            register_request = RegisterRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        # GOOD: Delegate to service
        try:
            user = self.user_service.register_user(register_request)
            return UserResponse.from_user(user), 201
        except EmailAlreadyRegisteredError as e:
            return {'error': str(e)}, 409


class UserService:
    def __init__(self, user_repo: UserRepository,
                 password_hasher: PasswordHasher,
                 token_service: TokenService,
                 email_service: EmailService):
        self.user_repo = user_repo
        self.password_hasher = password_hasher
        self.token_service = token_service
        self.email_service = email_service
    
    def register_user(self, request: RegisterRequest) -> User:
        # GOOD: Business logic in service
        if self.user_repo.exists_by_email(request.email):
            raise EmailAlreadyRegisteredError(request.email)
        
        # GOOD: Delegate password hashing
        hashed_password = self.password_hasher.hash(request.password)
        
        # GOOD: Create user through repository
        user = User.create(request.email, hashed_password, is_active=False)
        self.user_repo.save(user)
        
        # GOOD: Token generation in separate service
        verification_token = self.token_service.create_verification_token(user.id)
        self.user_repo.save_verification_token(verification_token)
        
        # GOOD: Email in dedicated service
        self.email_service.send_verification_email(
            request.email, 
            verification_token.token
        )
        
        return user


class User:
    @classmethod
    def create(cls, email: str, password: str, is_active: bool) -> 'User':
        return cls(
            email=email,
            password=password,
            is_active=is_active,
            created_at=datetime.now()
        )
```

**Improvements:**
- Controller thin with single responsibility
- Business logic in service layer
- Password hashing extracted to dedicated service
- Token generation isolated in separate service
- Repository pattern for data access
- Email service for notifications
- Easy to test each component independently
- Each class has high cohesion

### Explanation

The GOOD example shows proper Controller pattern with clear separation of concerns. The UserController only handles HTTP concerns (request/response) and delegates to UserService. UserService orchestrates business logic using multiple specialized services (PasswordHasher, TokenService, EmailService). Each service has a single, clear responsibility. This design follows Low Coupling (services depend on abstractions) and High Cohesion (each service does one thing well).

---

## Example 3: API Gateway Facade

### BAD Example: Controller Tightly Coupled to Multiple Services

```python
class OrderController:
    def create_order(self, request):
        # BAD: Direct calls to multiple services without abstraction
        user_response = requests.get(f'http://user-service/{request["user_id"]}')
        if user_response.status_code != 200:
            return {'error': 'User not found'}, 404
        
        user = user_response.json()
        
        # BAD: Inventory service call in controller
        for item in request['items']:
            inv_response = requests.post(
                'http://inventory-service/check',
                json={'product_id': item['product_id'], 'quantity': item['quantity']}
            )
            if inv_response.json().get('available') != True:
                return {'error': 'Product not available'}, 400
        
        # BAD: Payment service call in controller
        payment_response = requests.post(
            'http://payment-service/process',
            json={
                'amount': request['amount'],
                'card': request['card_details']
            }
        )
        if payment_response.status_code != 200:
            return {'error': 'Payment failed'}, 400
        
        # BAD: Save order directly
        order = Order.objects.create(
            user_id=request['user_id'],
            payment_id=payment_response.json()['payment_id'],
            total=request['amount']
        )
        
        return {'order_id': order.id}, 201
```

**Problems:**
- Controller directly calls multiple services
- No abstraction over external services
- Error handling scattered
- Retry logic not centralized
- Service URLs hardcoded
- Hard to test
- No circuit breaker pattern
- Tight coupling to service implementations

### GOOD Example: Facade Controller with Service Abstractions

```python
class OrderFacadeController:
    def __init__(self, order_orchestration_service: OrderOrchestrationService):
        self.order_service = order_orchestration_service
    
    def create_order(self, request):
        # GOOD: Create request DTO
        try:
            create_order_request = CreateOrderRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        # GOOD: Single service call to orchestrate everything
        try:
            order = self.order_service.create_order(create_order_request)
            return OrderResponse.from_order(order), 201
        except ServiceUnavailableError as e:
            return {'error': 'Service unavailable', 'details': str(e)}, 503
        except PaymentFailedError as e:
            return {'error': 'Payment failed', 'details': str(e)}, 400


class OrderOrchestrationService:
    def __init__(self, user_client: UserClient,
                 inventory_client: InventoryClient,
                 payment_client: PaymentClient,
                 order_repo: OrderRepository):
        self.user_client = user_client
        self.inventory_client = inventory_client
        self.payment_client = payment_client
        self.order_repo = order_repo
    
    def create_order(self, request: CreateOrderRequest) -> Order:
        # GOOD: Abstract service clients handle communication
        user = self.user_client.get_user(request.user_id)
        
        # GOOD: Inventory check with retries and circuit breaker
        for item in request.items:
            if not self.inventory_client.check_availability(
                item.product_id, item.quantity
            ):
                raise ProductUnavailableError(item.product_id)
        
        # GOOD: Payment processing with abstraction
        payment = self.payment_client.process_payment(
            request.amount, request.payment_details
        )
        
        # GOOD: Create and save order
        order = Order.create(
            user_id=request.user_id,
            payment_id=payment.id,
            total=request.amount,
            items=request.items
        )
        self.order_repo.save(order)
        
        return order


class UserClient:
    def __init__(self, base_url: str, http_client: HttpClient):
        self.base_url = base_url
        self.http = http_client
    
    def get_user(self, user_id: int) -> User:
        # GOOD: Abstraction over HTTP calls with retry logic
        response = self.http.get(f'{self.base_url}/users/{user_id}')
        return User.from_dict(response.json())
```

**Improvements:**
- Facade controller with single orchestration service
- Service clients abstract external service communication
- Centralized error handling
- Retry and circuit breaker logic in clients
- Configuration-based service URLs
- Easy to mock for testing
- Each client has single responsibility
- Low coupling through abstractions

### Explanation

The GOOD example demonstrates the Facade Controller pattern. OrderFacadeController delegates to OrderOrchestrationService which coordinates multiple external services through dedicated client classes (UserClient, InventoryClient, PaymentClient). Each client handles communication details including retries, circuit breakers, and error translation. This provides indirection between the controller and external services (Protected Variations pattern), making the system more maintainable and testable.

---

## Example 4: Payment Processing

### BAD Example: Controller with Complex Logic

```python
class PaymentController:
    def process_payment(self, request):
        # BAD: Payment method selection in controller
        payment_method = request.get('payment_method')
        
        # BAD: Type checking instead of polymorphism
        if payment_method == 'credit_card':
            # BAD: Credit card logic in controller
            card = request.get('card')
            if not self.validate_card(card):
                return {'error': 'Invalid card'}, 400
            result = self.process_credit_card(card, request.get('amount'))
        elif payment_method == 'paypal':
            # BAD: PayPal logic in controller
            paypal = request.get('paypal')
            if not self.validate_paypal(paypal):
                return {'error': 'Invalid PayPal'}, 400
            result = self.process_paypal(paypal, request.get('amount'))
        elif payment_method == 'bank_transfer':
            # BAD: Bank transfer logic in controller
            bank = request.get('bank')
            result = self.process_bank_transfer(bank, request.get('amount'))
        else:
            return {'error': 'Invalid payment method'}, 400
        
        # BAD: Save payment directly
        payment = Payment.objects.create(
            method=payment_method,
            amount=request.get('amount'),
            status=result['status'],
            transaction_id=result['transaction_id']
        )
        
        return {'payment_id': payment.id}, 201
```

**Problems:**
- Type checking instead of polymorphism
- Payment logic mixed in controller
- Duplicate validation code
- Hard to add new payment methods
- Violates Open/Closed Principle
- Each payment method tightly coupled
- No reusable payment processing logic

### GOOD Example: Controller with Polymorphic Payment Processors

```python
class PaymentController:
    def __init__(self, payment_service: PaymentService):
        self.payment_service = payment_service
    
    def process_payment(self, request):
        # GOOD: Create request DTO
        try:
            payment_request = PaymentRequest(**request)
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        # GOOD: Delegate to service with polymorphism
        try:
            payment = self.payment_service.process_payment(payment_request)
            return PaymentResponse.from_payment(payment), 201
        except PaymentProcessingError as e:
            return {'error': str(e)}, 400


class PaymentService:
    def __init__(self, payment_processor_factory: PaymentProcessorFactory,
                 payment_repo: PaymentRepository):
        self.processor_factory = payment_processor_factory
        self.payment_repo = payment_repo
    
    def process_payment(self, request: PaymentRequest) -> Payment:
        # GOOD: Factory creates appropriate processor (Polymorphism)
        processor = self.processor_factory.get_processor(request.payment_method)
        
        # GOOD: Polymorphic payment processing
        result = processor.process(request.amount, request.payment_details)
        
        # GOOD: Create and save payment
        payment = Payment.create(
            method=request.payment_method,
            amount=request.amount,
            status=result.status,
            transaction_id=result.transaction_id
        )
        self.payment_repo.save(payment)
        
        return payment


class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float, details: dict) -> PaymentResult:
        pass


class CreditCardProcessor(PaymentProcessor):
    def process(self, amount: float, details: dict) -> PaymentResult:
        # GOOD: Encapsulated credit card logic
        if not self._validate_card(details):
            raise InvalidCardError()
        
        gateway_result = self._call_gateway(amount, details)
        return PaymentResult(
            status=gateway_result['status'],
            transaction_id=gateway_result['transaction_id']
        )
    
    def _validate_card(self, details: dict) -> bool:
        # Credit card specific validation
        pass
    
    def _call_gateway(self, amount: float, details: dict) -> dict:
        # Credit card gateway call
        pass


class PayPalProcessor(PaymentProcessor):
    def process(self, amount: float, details: dict) -> PaymentResult:
        # GOOD: Encapsulated PayPal logic
        if not self._validate_paypal(details):
            raise InvalidPayPalError()
        
        api_result = self._call_paypal_api(amount, details)
        return PaymentResult(
            status=api_result['status'],
            transaction_id=api_result['payment_id']
        )


class PaymentProcessorFactory:
    def __init__(self):
        self.processors = {
            'credit_card': CreditCardProcessor(),
            'paypal': PayPalProcessor(),
            'bank_transfer': BankTransferProcessor()
        }
    
    def get_processor(self, method: str) -> PaymentProcessor:
        processor = self.processors.get(method)
        if not processor:
            raise InvalidPaymentMethodError(method)
        return processor
```

**Improvements:**
- Polymorphic payment processing
- Each processor handles its own logic
- Factory pattern for processor creation
- Easy to add new payment methods
- Open/Closed Principle followed
- Clear separation of concerns
- High cohesion in each processor
- Low coupling through abstraction

### Explanation

The GOOD example demonstrates Polymorphism pattern applied to payment processing. PaymentController delegates to PaymentService which uses a factory to get the appropriate PaymentProcessor. Each processor (CreditCardProcessor, PayPalProcessor) handles its specific logic independently. New payment methods can be added by creating new processor classes without modifying existing code (Open/Closed Principle). The controller remains thin and focused on orchestration.

---

## Example 5: File Upload Handler

### BAD Example: Controller with File Processing Logic

```python
class FileController:
    def upload_file(self, request):
        file = request.FILES.get('file')
        
        # BAD: Validation in controller
        if not file:
            return {'error': 'No file provided'}, 400
        
        # BAD: File size validation in controller
        if file.size > 10 * 1024 * 1024:  # 10MB
            return {'error': 'File too large'}, 400
        
        # BAD: File type validation in controller
        allowed_types = ['image/jpeg', 'image/png', 'application/pdf']
        if file.content_type not in allowed_types:
            return {'error': 'Invalid file type'}, 400
        
        # BAD: Virus scanning in controller
        if self.scan_for_virus(file):
            return {'error': 'File contains virus'}, 400
        
        # BAD: Image processing in controller
        if file.content_type.startswith('image/'):
            image = Image.open(file)
            # Resize image
            image.thumbnail((800, 800))
            image_bytes = BytesIO()
            image.save(image_bytes, format='JPEG')
            file = image_bytes
        
        # BAD: File storage logic in controller
        filename = f'{uuid.uuid4()}.{file.name.split(".")[-1]}'
        path = f'/uploads/{datetime.now().strftime("%Y/%m/%d")}/'
        os.makedirs(path, exist_ok=True)
        
        with open(f'{path}{filename}', 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        
        # BAD: Database save in controller
        uploaded_file = UploadedFile.objects.create(
            filename=filename,
            path=f'{path}{filename}',
            size=file.size,
            content_type=file.content_type
        )
        
        return {'file_id': uploaded_file.id}, 201
```

**Problems:**
- All logic in controller method
- Validation mixed with controller
- File processing logic in controller
- Storage logic not reusable
- Virus scanning tightly coupled
- Image processing not isolated
- Direct filesystem operations
- No abstraction over storage

### GOOD Example: Controller with File Processing Service

```python
class FileController:
    def __init__(self, file_service: FileService):
        self.file_service = file_service
    
    def upload_file(self, request):
        # GOOD: Extract file from request
        file = request.FILES.get('file')
        if not file:
            return {'error': 'No file provided'}, 400
        
        # GOOD: Create upload request DTO
        try:
            upload_request = FileUploadRequest(
                file=file,
                user_id=request.user.id
            )
        except ValidationError as e:
            return {'error': str(e)}, 400
        
        # GOOD: Delegate to service
        try:
            uploaded_file = self.file_service.upload_file(upload_request)
            return FileUploadResponse.from_file(uploaded_file), 201
        except FileValidationError as e:
            return {'error': str(e)}, 400
        except VirusDetectedError as e:
            return {'error': 'Virus detected'}, 400
        except FileTooLargeError as e:
            return {'error': 'File too large'}, 400


class FileService:
    def __init__(self, file_validator: FileValidator,
                 virus_scanner: VirusScanner,
                 image_processor: ImageProcessor,
                 file_storage: FileStorage,
                 file_repo: FileRepository):
        self.validator = file_validator
        self.scanner = virus_scanner
        self.image_processor = image_processor
        self.storage = file_storage
        self.file_repo = file_repo
    
    def upload_file(self, request: FileUploadRequest) -> UploadedFile:
        # GOOD: Validation in dedicated validator
        self.validator.validate(request.file)
        
        # GOOD: Virus scanning in separate service
        if self.scanner.scan(request.file):
            raise VirusDetectedError()
        
        processed_file = request.file
        
        # GOOD: Image processing if applicable
        if request.file.content_type.startswith('image/'):
            processed_file = self.image_processor.process_thumbnail(
                request.file,
                max_size=(800, 800)
            )
        
        # GOOD: Storage abstraction
        storage_path = self.storage.save(processed_file)
        
        # GOOD: Save metadata through repository
        uploaded_file = UploadedFile.create(
            filename=processed_file.name,
            path=storage_path,
            size=processed_file.size,
            content_type=processed_file.content_type,
            uploaded_by=request.user_id
        )
        self.file_repo.save(uploaded_file)
        
        return uploaded_file


class FileValidator:
    def __init__(self, max_size: int = 10 * 1024 * 1024,
                 allowed_types: List[str] = None):
        self.max_size = max_size
        self.allowed_types = allowed_types or [
            'image/jpeg', 'image/png', 'application/pdf'
        ]
    
    def validate(self, file: UploadedFile):
        if file.size > self.max_size:
            raise FileTooLargeError(file.size, self.max_size)
        
        if file.content_type not in self.allowed_types:
            raise InvalidFileTypeError(file.content_type, self.allowed_types)


class FileStorage(ABC):
    @abstractmethod
    def save(self, file: UploadedFile) -> str:
        pass


class LocalFileStorage(FileStorage):
    def save(self, file: UploadedFile) -> str:
        filename = f'{uuid.uuid4()}.{file.extension}'
        path = f'/uploads/{datetime.now().strftime("%Y/%m/%d")}/'
        os.makedirs(path, exist_ok=True)
        full_path = f'{path}{filename}'
        
        with open(full_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        
        return full_path


class S3FileStorage(FileStorage):
    def save(self, file: UploadedFile) -> str:
        # S3-specific implementation
        pass
```

**Improvements:**
- Controller thin with single responsibility
- File validation extracted to dedicated validator
- Virus scanning isolated in separate service
- Image processing in dedicated processor
- Storage abstracted with strategy pattern
- Repository for data persistence
- Easy to add new storage backends
- Each component has high cohesion

### Explanation

The GOOD example demonstrates proper Controller pattern with clear separation of concerns. FileController only handles HTTP concerns and delegates to FileService. FileService coordinates multiple specialized services (FileValidator, VirusScanner, ImageProcessor, FileStorage) each with a single responsibility. FileStorage is an abstract base class allowing different implementations (LocalFileStorage, S3FileStorage) to be easily swapped. This design follows Low Coupling (dependencies on abstractions) and High Cohesion (each class does one thing).

---

## Language-Specific Notes

### Idioms and Patterns

- **FastAPI routers**: Use `APIRouter` with dependency injection via `Depends()`
- **Django class-based views**: Inherit from `View` or `APIView` for REST framework
- **Flask blueprints**: Organize controllers by feature area
- **Dependency injection**: Use constructor injection or framework-specific DI

### Language Features

**Features that help:**
- **Decorators**: `@router.post`, `@app.route` for route definition
- **Type hints**: Improve clarity and enable static analysis
- **Dataclasses**: Clean DTO and model definitions
- **Context managers**: Resource management for database connections
- **Async/await**: Non-blocking I/O for better performance

**Features that hinder:**
- **Dynamic typing**: Can lead to runtime errors if not careful with validation
- **Global state**: Makes testing harder and creates hidden dependencies
- **Monkey patching**: Can lead to hard-to-debug coupling issues

### Framework Considerations

- **FastAPI**: Modern, async-first with built-in validation via Pydantic
- **Django**: Full-featured with batteries included, uses ORM
- **Flask**: Lightweight, flexible, requires more setup
- **Pyramid**: Very flexible, but more verbose

### Common Pitfalls

1. **Fat views**: Putting too much logic in view functions
   - Use services and domain objects for business logic
   - Keep views under 20 lines

2. **Direct ORM queries in views**: Creates tight coupling
   - Use repository pattern
   - Abstract data access behind interfaces

3. **No request/response DTOs**: Leads to scattered validation
   - Use Pydantic models or dataclasses
   - Centralize validation logic

4. **Not using dependency injection**: Makes testing hard
   - Inject dependencies via constructor
   - Use framework DI where available

5. **Returning domain objects directly**: Exposes internal state
   - Use DTOs or view models for responses
   - Control what data is exposed to clients
