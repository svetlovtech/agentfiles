# TDD Real-World Scenarios - Python

## Table of Contents

- [Introduction](#introduction)
- [Scenario 1: REST API Endpoint Development](#scenario-1-rest-api-endpoint-development)
- [Scenario 2: Business Logic Implementation](#scenario-2-business-logic-implementation)
- [Scenario 3: Legacy Code Refactoring](#scenario-3-legacy-code-refactoring)
- [Scenario 4: Complex Algorithm Implementation](#scenario-4-complex-algorithm-implementation)
- [Scenario 5: Data Validation Pipeline](#scenario-5-data-validation-pipeline)
- [Scenario 6: Integration Testing Strategy](#scenario-6-integration-testing-strategy)
- [Migration Guide](#migration-guide)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document presents real-world scenarios where TDD principles are applied in Python. Each scenario includes a practical problem, analysis of violations, and step-by-step solution with code examples.

## Scenario 1: REST API Endpoint Development

### Context

A web application needs an API endpoint for user registration. The requirements include email validation, password strength checking, duplicate user prevention, and returning appropriate HTTP status codes.

### Problem Description

The BAD approach writes the API handler first, then tests it manually with tools like Postman. This leads to edge cases being discovered late, no automated regression protection, and difficulty refactoring without manual testing.

### Analysis of Violations

**Current Issues:**
- **Test-last development**: Code written before tests
- **Manual verification**: Using Postman/curl instead of automated tests
- **Missing edge cases**: Empty email, weak passwords, etc.
- **No safety net**: Refactoring requires manual retesting

**Impact:**
- Bugs discovered in production
- Slow development cycle
- Fear of refactoring
- Inconsistent behavior

### BAD Approach

```python
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash

app = Flask(__name__)

@app.route('/api/users', methods=['POST'])
def register_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    if '@' not in email:
        return jsonify({'error': 'Invalid email'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password too short'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 409

    user = User(
        email=email,
        password_hash=generate_password_hash(password)
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'id': user.id, 'email': user.email}), 201
```

**Why This Approach Fails:**
- No test for duplicate email detection
- No test for password strength beyond length
- No test for invalid JSON input
- Cannot refactor without breaking manual tests
- Difficult to reproduce bugs

### GOOD Approach

**Solution Strategy:**
1. Write failing test for happy path
2. Write test for validation errors
3. Write test for duplicate user
4. Implement code to pass tests
5. Refactor to improve design

```python
import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

@pytest.fixture
def client():
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app.test_client()


def test_register_user_with_valid_data(client):
    response = client.post('/api/users', json={
        'email': 'alice@example.com',
        'password': 'securepassword123'
    })

    assert response.status_code == 201
    data = response.get_json()
    assert data['email'] == 'alice@example.com'
    assert 'id' in data


def test_register_user_returns_400_when_email_missing(client):
    response = client.post('/api/users', json={
        'password': 'securepassword123'
    })

    assert response.status_code == 400
    assert 'Email' in response.get_json()['error']


def test_register_user_returns_400_when_password_missing(client):
    response = client.post('/api/users', json={
        'email': 'alice@example.com'
    })

    assert response.status_code == 400
    assert 'Password' in response.get_json()['error']


def test_register_user_returns_400_for_invalid_email(client):
    response = client.post('/api/users', json={
        'email': 'not-an-email',
        'password': 'securepassword123'
    })

    assert response.status_code == 400
    assert 'Invalid email' in response.get_json()['error']


def test_register_user_returns_400_for_short_password(client):
    response = client.post('/api/users', json={
        'email': 'alice@example.com',
        'password': 'short'
    })

    assert response.status_code == 400
    assert 'Password' in response.get_json()['error']


def test_register_user_returns_409_for_duplicate_email(client):
    client.post('/api/users', json={
        'email': 'alice@example.com',
        'password': 'securepassword123'
    })

    response = client.post('/api/users', json={
        'email': 'alice@example.com',
        'password': 'anotherpassword123'
    })

    assert response.status_code == 409
    assert 'already exists' in response.get_json()['error']


def test_register_user_hashes_password(client):
    response = client.post('/api/users', json={
        'email': 'alice@example.com',
        'password': 'plaintext'
    })

    user = User.query.filter_by(email='alice@example.com').first()
    assert user.password_hash != 'plaintext'
    assert user.password_hash.startswith('pbkdf2:')
```

**Benefits:**
- All edge cases covered upfront
- Automated regression protection
- Safe refactoring
- Tests serve as documentation
- Fast feedback loop

### Implementation Steps

1. **Step 1: Write First Failing Test**
   ```python
   def test_register_user_with_valid_data(client):
       response = client.post('/api/users', json={
           'email': 'alice@example.com',
           'password': 'securepassword123'
       })
       assert response.status_code == 201
   ```

2. **Step 2: Implement Minimal Code**
   ```python
   @app.route('/api/users', methods=['POST'])
   def register_user():
       return jsonify({'id': 1, 'email': 'test@example.com'}), 201
   ```

3. **Step 3: Add Validation Tests**
   - Test for missing email
   - Test for missing password
   - Test for invalid email
   - Test for short password

4. **Step 4: Implement Validation**
   - Add request parsing
   - Add validation logic
   - Add appropriate error responses

5. **Step 5: Add Integration Test**
   - Test with database
   - Verify password hashing
   - Test duplicate detection

### Testing the Solution

**Test Cases:**
- **Happy path**: Valid user registration
- **Validation errors**: Missing fields, invalid email, weak password
- **Business logic**: Duplicate email prevention
- **Security**: Password hashing verification

**Verification:**
Run `pytest -v` to verify all tests pass. Refactor validation logic into separate validator class and verify tests still pass.

## Scenario 2: Business Logic Implementation

### Context

An e-commerce application needs a pricing engine that applies various discounts: loyalty tier discounts, bulk purchase discounts, and coupon codes. Discounts should stack correctly and have priority rules.

### Problem Description

The BAD approach implements complex discount logic in one function without tests, leading to hard-to-debug bugs when discounts don't apply correctly or when edge cases arise.

### Analysis of Violations

**Current Issues:**
- **Complex logic without tests**: Discount stacking logic is complex
- **No test coverage**: Edge cases not considered
- **Hard to debug**: Cannot isolate which discount failed
- **No regression protection**: Changes break existing discounts

**Impact:**
- Incorrect pricing calculations
- Lost revenue or customer disputes
- Fear of modifying pricing logic
- Difficulty adding new discount types

### BAD Approach

```python
def calculate_final_price(user, cart_items, coupon_code=None):
    subtotal = sum(item.price * item.quantity for item in cart_items)
    discount = 0

    if user.tier == 'gold':
        discount += subtotal * 0.15
    elif user.tier == 'silver':
        discount += subtotal * 0.10
    elif user.tier == 'bronze':
        discount += subtotal * 0.05

    if sum(item.quantity for item in cart_items) > 10:
        discount += subtotal * 0.05

    if coupon_code:
        coupon = Coupon.find_by_code(coupon_code)
        if coupon:
            if coupon.type == 'percentage':
                discount += subtotal * coupon.value / 100
            elif coupon.type == 'fixed':
                discount += coupon.value

    total = subtotal - discount
    return max(total, 0)
```

**Why This Approach Fails:**
- No test for gold + bulk + coupon stacking
- No test for minimum purchase requirements
- No test for coupon expiration
- No test for edge cases (negative discounts)
- Logic is not easily testable

### GOOD Approach

**Solution Strategy:**
1. Write tests for each discount type individually
2. Write tests for discount stacking scenarios
3. Implement discounts one at a time
4. Refactor to use strategy pattern

```python
import pytest


@pytest.fixture
def gold_user():
    user = User(tier='gold')
    return user


@pytest.fixture
def silver_user():
    user = User(tier='silver')
    return user


@pytest.fixture
def cart_items():
    return [
        CartItem(name='Book', price=10.00, quantity=5),
        CartItem(name='Pen', price=5.00, quantity=5)
    ]


def test_gold_user_gets_15_percent_discount(gold_user, cart_items):
    calculator = PricingCalculator()
    total = calculator.calculate(gold_user, cart_items)

    subtotal = 75.00
    expected = subtotal * 0.85
    assert total == expected


def test_silver_user_gets_10_percent_discount(silver_user, cart_items):
    calculator = PricingCalculator()
    total = calculator.calculate(silver_user, cart_items)

    subtotal = 75.00
    expected = subtotal * 0.90
    assert total == expected


def test_regular_user_gets_no_tier_discount(cart_items):
    user = User(tier='regular')
    calculator = PricingCalculator()
    total = calculator.calculate(user, cart_items)

    assert total == 75.00


def test_bulk_purchase_applies_5_percent_discount(cart_items):
    user = User(tier='regular')
    cart_items_large = [
        CartItem(name='Book', price=10.00, quantity=11)
    ]
    calculator = PricingCalculator()
    total = calculator.calculate(user, cart_items_large)

    expected = 110.00 * 0.95
    assert total == expected


def test_percentage_coupon_applies_after_tier_discount(gold_user, cart_items):
    calculator = PricingCalculator()
    coupon = Coupon(type='percentage', value=10)
    total = calculator.calculate(gold_user, cart_items, coupon)

    subtotal = 75.00
    tier_discount = subtotal * 0.15
    coupon_discount = (subtotal - tier_discount) * 0.10
    expected = subtotal - tier_discount - coupon_discount
    assert total == expected


def test_fixed_coupon_applies_minimum_of_zero(gold_user, cart_items):
    calculator = PricingCalculator()
    large_fixed_coupon = Coupon(type='fixed', value=100)
    total = calculator.calculate(gold_user, cart_items, large_fixed_coupon)

    assert total == 0


def test_expired_coupon_is_not_applied(gold_user, cart_items):
    calculator = PricingCalculator()
    expired_coupon = Coupon(
        type='percentage',
        value=10,
        expires_at=datetime(2024, 1, 1)
    )
    total = calculator.calculate(gold_user, cart_items, expired_coupon)

    expected = 75.00 * 0.85
    assert total == expected


def test_all_discounts_stack_correctly(gold_user, cart_items):
    calculator = PricingCalculator()

    large_cart = [
        CartItem(name='Book', price=10.00, quantity=11)
    ]
    coupon = Coupon(type='percentage', value=10)

    total = calculator.calculate(gold_user, large_cart, coupon)

    subtotal = 110.00
    tier_discount = subtotal * 0.15
    bulk_discount = 0  # Applied after tier
    coupon_discount = (subtotal - tier_discount) * 0.10
    expected = subtotal - tier_discount - coupon_discount
    assert total == expected
```

**Implementation:**

```python
class PricingCalculator:
    def __init__(self):
        self.discounts = [
            TierDiscount(),
            BulkDiscount(),
            CouponDiscount()
        ]

    def calculate(self, user, cart_items, coupon=None):
        subtotal = self._calculate_subtotal(cart_items)
        total = subtotal

        for discount in self.discounts:
            total = discount.apply(user, cart_items, total, coupon)

        return max(total, 0)

    def _calculate_subtotal(self, cart_items):
        return sum(item.price * item.quantity for item in cart_items)


class TierDiscount:
    DISCOUNT_RATES = {
        'gold': 0.15,
        'silver': 0.10,
        'bronze': 0.05
    }

    def apply(self, user, cart_items, total, coupon=None):
        rate = self.DISCOUNT_RATES.get(user.tier, 0)
        return total * (1 - rate)


class BulkDiscount:
    MINIMUM_QUANTITY = 10
    DISCOUNT_RATE = 0.05

    def apply(self, user, cart_items, total, coupon=None):
        total_quantity = sum(item.quantity for item in cart_items)
        if total_quantity >= self.MINIMUM_QUANTITY:
            return total * (1 - self.DISCOUNT_RATE)
        return total


class CouponDiscount:
    def apply(self, user, cart_items, total, coupon=None):
        if not coupon:
            return total

        if self._is_expired(coupon):
            return total

        if coupon.type == 'percentage':
            return total * (1 - coupon.value / 100)
        elif coupon.type == 'fixed':
            return max(total - coupon.value, 0)

        return total

    def _is_expired(self, coupon):
        if not coupon.expires_at:
            return False
        return datetime.now() > coupon.expires_at
```

**Benefits:**
- Each discount type independently testable
- Clear separation of concerns
- Easy to add new discount types
- All edge cases covered
- Safe refactoring

### Implementation Steps

1. **Step 1: Write Tests for Tier Discounts**
   - Test gold, silver, bronze, regular tiers
   - Implement TierDiscount class

2. **Step 2: Write Tests for Bulk Discounts**
   - Test below threshold, at threshold, above threshold
   - Implement BulkDiscount class

3. **Step 3: Write Tests for Coupon Discounts**
   - Test percentage coupons, fixed coupons
   - Test expired coupons
   - Implement CouponDiscount class

4. **Step 4: Write Tests for Discount Stacking**
   - Test combinations of discounts
   - Implement PricingCalculator to orchestrate discounts

5. **Step 5: Refactor**
   - Extract discount rates to configuration
   - Add logging for debugging
   - Verify all tests still pass

### Testing the Solution

**Test Cases:**
- **Tier discounts**: Gold (15%), Silver (10%), Bronze (5%), Regular (0%)
- **Bulk discount**: Applied when quantity >= 10
- **Coupon discounts**: Percentage and fixed types
- **Stacking**: Multiple discounts applied in correct order
- **Edge cases**: Expired coupons, negative totals, minimum of zero

**Verification:**
Run `pytest test_pricing.py -v` to verify all discount scenarios work correctly. Add new discount type by writing tests first, then implementing.

## Scenario 3: Legacy Code Refactoring

### Context

An existing codebase has a monolithic `OrderProcessor` class with 500+ lines, no tests, and handles order creation, validation, payment, shipping, and notification in one method. Changes frequently break existing functionality.

### Problem Description

The BAD approach tries to refactor without tests, leading to bugs and regression issues. The code is difficult to understand, test, and modify safely.

### Analysis of Violations

**Current Issues:**
- **No tests**: Cannot verify refactoring doesn't break anything
- **Single Responsibility**: One class does everything
- **Coupling**: All dependencies tightly integrated
- **Fear of change**: No safety net

**Impact:**
- Bugs introduced during refactoring
- Slow development velocity
- High defect rate
- Technical debt accumulation

### BAD Approach

```python
class OrderProcessor:
    def process_order(self, order_data):
        if not self._validate_data(order_data):
            return {'error': 'Invalid data'}

        if self._user_exists(order_data['user_id']):
            return {'error': 'User not found'}

        order = self._create_order(order_data)

        if not self._validate_items(order.items):
            return {'error': 'Invalid items'}

        if not self._check_inventory(order.items):
            return {'error': 'Out of stock'}

        if not self._reserve_inventory(order.items):
            return {'error': 'Could not reserve'}

        if not self._process_payment(order):
            return {'error': 'Payment failed'}

        if not self._save_order(order):
            return {'error': 'Could not save'}

        if not self._send_confirmation(order):
            return {'error': 'Could not notify'}

        return {'success': True, 'order_id': order.id}

    def _validate_data(self, data):
        return all(k in data for k in ['user_id', 'items', 'payment'])

    def _user_exists(self, user_id):
        return User.query.get(user_id) is not None

    def _create_order(self, data):
        order = Order(user_id=data['user_id'])
        order.items = [Item(**item) for item in data['items']]
        return order

    def _validate_items(self, items):
        return all(item.price > 0 for item in items)

    def _check_inventory(self, items):
        return all(item.stock >= item.quantity for item in items)

    def _reserve_inventory(self, items):
        for item in items:
            item.stock -= item.quantity
            item.save()
        return True

    def _process_payment(self, order):
        payment = PaymentGateway().charge(order.total, order.payment_method)
        return payment.success

    def _save_order(self, order):
        order.save()
        return True

    def _send_confirmation(self, order):
        EmailService().send(order.user.email, 'Order confirmed')
        return True
```

**Why This Approach Fails:**
- No tests to verify refactoring
- Cannot isolate and test individual responsibilities
- Changes risk breaking existing functionality
- Cannot measure test coverage

### GOOD Approach

**Solution Strategy:**
1. Write characterization tests for existing behavior
2. Extract responsibilities one at a time
3. Write unit tests for extracted components
4. Refactor to cleaner design

```python
import pytest


class OrderProcessorCharacterizationTests:
    """Characterization tests before refactoring"""

    def test_process_order_with_valid_data_creates_order(self, order_processor, order_data):
        result = order_processor.process_order(order_data)

        assert result['success'] is True
        assert 'order_id' in result

    def test_process_order_with_missing_fields_returns_error(self, order_processor):
        invalid_data = {'user_id': 1}

        result = order_processor.process_order(invalid_data)

        assert result['error'] == 'Invalid data'

    def test_process_order_with_nonexistent_user_returns_error(self, order_processor, order_data):
        order_data['user_id'] = 999999

        result = order_processor.process_order(order_data)

        assert result['error'] == 'User not found'

    def test_process_order_with_out_of_stock_returns_error(self, order_processor, order_data):
        order_data['items'][0]['product_id'] = 999999

        result = order_processor.process_order(order_data)

        assert result['error'] == 'Out of stock'


class RefactoredOrderValidatorTests:
    """Tests for extracted validator"""

    def test_validate_order_with_valid_data(self):
        validator = OrderValidator()
        order_data = {
            'user_id': 1,
            'items': [{'product_id': 1, 'quantity': 2}],
            'payment': {'method': 'credit_card'}
        }

        errors = validator.validate(order_data)

        assert len(errors) == 0

    def test_validate_order_with_missing_user_id(self):
        validator = OrderValidator()
        order_data = {
            'items': [],
            'payment': {}
        }

        errors = validator.validate(order_data)

        assert 'user_id' in errors


class RefactoredInventoryServiceTests:
    """Tests for extracted inventory service"""

    def test_check_inventory_with_sufficient_stock(self, inventory_service):
        product = Product(id=1, stock=10)

        available = inventory_service.check_availability(product, 5)

        assert available is True

    def test_check_inventory_with_insufficient_stock(self, inventory_service):
        product = Product(id=1, stock=3)

        available = inventory_service.check_availability(product, 5)

        assert available is False

    def test_reserve_stock_reduces_available(self, inventory_service):
        product = Product(id=1, stock=10)

        inventory_service.reserve(product, 5)

        assert product.stock == 5


class RefactoredPaymentServiceTests:
    """Tests for extracted payment service"""

    def test_process_payment_with_valid_card(self, payment_service, fake_gateway):
        order = Order(total=100, payment_method='card_123')

        result = payment_service.charge(order, gateway=fake_gateway)

        assert result.success is True
        assert fake_gateway.charged_amount == 100

    def test_process_payment_with_declined_card(self, payment_service, fake_gateway):
        fake_gateway.should_decline = True
        order = Order(total=100, payment_method='card_123')

        result = payment_service.charge(order, gateway=fake_gateway)

        assert result.success is False
```

**Refactored Implementation:**

```python
class OrderProcessor:
    def __init__(self):
        self.validator = OrderValidator()
        self.inventory = InventoryService()
        self.payment = PaymentService()
        self.repository = OrderRepository()
        self.notification = NotificationService()

    def process_order(self, order_data):
        errors = self.validator.validate(order_data)
        if errors:
            return {'error': f'Invalid data: {errors}'}

        if not self.repository.user_exists(order_data['user_id']):
            return {'error': 'User not found'}

        order = self._create_order(order_data)

        if not self.inventory.check_availability(order):
            return {'error': 'Out of stock'}

        if not self.payment.charge(order):
            return {'error': 'Payment failed'}

        self.inventory.reserve(order)
        self.repository.save(order)
        self.notification.send_confirmation(order)

        return {'success': True, 'order_id': order.id}


class OrderValidator:
    REQUIRED_FIELDS = ['user_id', 'items', 'payment']

    def validate(self, order_data):
        errors = {}

        for field in self.REQUIRED_FIELDS:
            if field not in order_data:
                errors[field] = 'is required'

        if 'items' in order_data and not order_data['items']:
            errors['items'] = 'cannot be empty'

        return errors


class InventoryService:
    def check_availability(self, order):
        for item in order.items:
            product = Product.query.get(item.product_id)
            if not product or product.stock < item.quantity:
                return False
        return True

    def reserve(self, order):
        for item in order.items:
            product = Product.query.get(item.product_id)
            product.stock -= item.quantity
            product.save()


class PaymentService:
    def charge(self, order, gateway=None):
        if gateway is None:
            gateway = PaymentGateway()
        return gateway.charge(order.total, order.payment_method)


class OrderRepository:
    def user_exists(self, user_id):
        return User.query.get(user_id) is not None

    def save(self, order):
        order.save()
        return order


class NotificationService:
    def send_confirmation(self, order):
        EmailService().send(
            order.user.email,
            f'Order {order.id} confirmed'
        )
```

**Benefits:**
- Safety net for refactoring with characterization tests
- Each component independently testable
- Clear separation of concerns
- Easy to add new features
- Improved maintainability

### Implementation Steps

1. **Step 1: Write Characterization Tests**
   - Test existing OrderProcessor behavior
   - Capture all current functionality
   - Ensure tests pass before refactoring

2. **Step 2: Extract OrderValidator**
   - Write unit tests for validator
   - Extract validation logic
   - Replace in OrderProcessor
   - Verify all tests pass

3. **Step 3: Extract InventoryService**
   - Write unit tests for inventory
   - Extract inventory logic
   - Replace in OrderProcessor
   - Verify all tests pass

4. **Step 4: Extract PaymentService**
   - Write unit tests with fake gateway
   - Extract payment logic
   - Replace in OrderProcessor
   - Verify all tests pass

5. **Step 5: Extract Repository and Notification**
   - Write unit tests for each
   - Extract logic
   - Replace in OrderProcessor
   - Verify all tests pass

6. **Step 6: Remove Old Methods**
   - Delete extracted methods from OrderProcessor
   - Final verification with all tests

### Testing the Solution

**Test Cases:**
- **Characterization tests**: Existing behavior preserved
- **Validator tests**: All validation rules
- **Inventory tests**: Availability checking and reservation
- **Payment tests**: Successful and failed payments
- **Integration tests**: End-to-end order processing

**Verification:**
Run `pytest tests/ -v --cov=src` to ensure refactoring maintains behavior. Test coverage should increase as new components have dedicated tests.

## Scenario 4: Complex Algorithm Implementation

### Context

A logistics application needs to implement the Traveling Salesman Problem (TSP) solver for route optimization. The algorithm must handle up to 20 locations efficiently and return the optimal route.

### Problem Description

The BAD approach implements the complex algorithm first, then tries to test it. This leads to incorrect implementations that are hard to debug and verify.

### Analysis of Violations

**Current Issues:**
- **Test-last approach**: Algorithm implemented before tests
- **Complex logic**: Hard to reason about correctness
- **No small examples**: Difficult to verify edge cases
- **No refactoring safety**: Changes risk breaking correctness

**Impact:**
- Incorrect route calculations
- Hard to debug algorithmic errors
- No confidence in results
- Difficult to optimize

### BAD Approach

```python
def solve_tsp(locations):
    n = len(locations)
    if n == 0:
        return []
    if n == 1:
        return [0]

    from itertools import permutations

    best_route = None
    best_distance = float('inf')

    for perm in permutations(range(n)):
        distance = calculate_distance(locations, perm)
        if distance < best_distance:
            best_distance = distance
            best_route = list(perm)

    return best_route


def calculate_distance(locations, route):
    total = 0
    for i in range(len(route) - 1):
        total += distance(locations[route[i]], locations[route[i+1]])
    total += distance(locations[route[-1]], locations[route[0]])
    return total


def distance(p1, p2):
    return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5
```

**Why This Approach Fails:**
- No test for small cases where optimal is known
- No test for edge cases (0, 1, 2 locations)
- Brute force approach is too slow for 20 locations
- No way to verify correctness without manual inspection

### GOOD Approach

**Solution Strategy:**
1. Start with trivial cases (0, 1, 2 locations)
2. Write tests for small verifiable cases (3-4 locations)
3. Implement brute force for verification
4. Implement heuristic for larger cases
5. Test heuristic against brute force for small cases

```python
import pytest
import math


def test_tsp_with_no_locations():
    locations = []
    route = solve_tsp(locations)

    assert route == []


def test_tsp_with_one_location():
    locations = [(0, 0)]
    route = solve_tsp(locations)

    assert route == [0]


def test_tsp_with_two_locations():
    locations = [(0, 0), (10, 0)]
    route = solve_tsp(locations)

    assert len(route) == 2
    assert 0 in route
    assert 1 in route


def test_tsp_with_three_locations_triangle():
    locations = [(0, 0), (10, 0), (5, 10)]
    route = solve_tsp(locations)

    distance = calculate_route_distance(locations, route)
    optimal_distance = 20.0 + math.sqrt(125)

    assert abs(distance - optimal_distance) < 0.01


def test_tsp_with_four_locations_square():
    locations = [(0, 0), (10, 0), (10, 10), (0, 10)]
    route = solve_tsp(locations)

    distance = calculate_route_distance(locations, route)

    assert abs(distance - 40.0) < 0.01


def test_tsp_returns_optimal_route():
    locations = [(0, 0), (3, 0), (3, 4), (0, 4)]
    route = solve_tsp(locations)

    distance = calculate_route_distance(locations, route)

    assert abs(distance - 14.0) < 0.01


def test_heuristic_matches_brute_force_for_small_cases():
    import random
    random.seed(42)

    locations = [(random.randint(0, 10), random.randint(0, 10)) for _ in range(6)]

    brute_route = solve_tsp_brute_force(locations)
    heuristic_route = solve_tsp_heuristic(locations)

    brute_distance = calculate_route_distance(locations, brute_route)
    heuristic_distance = calculate_route_distance(locations, heuristic_route)

    assert heuristic_distance <= brute_distance * 1.5


def test_heuristic_returns_valid_route():
    locations = [(0, 0), (5, 5), (10, 0), (5, -5)]
    route = solve_tsp_heuristic(locations)

    assert len(route) == len(locations)
    assert len(set(route)) == len(route)
    assert all(0 <= i < len(locations) for i in route)
```

**Implementation:**

```python
def solve_tsp(locations):
    if len(locations) <= 10:
        return solve_tsp_brute_force(locations)
    return solve_tsp_heuristic(locations)


def solve_tsp_brute_force(locations):
    from itertools import permutations

    n = len(locations)
    if n == 0:
        return []
    if n == 1:
        return [0]

    best_route = None
    best_distance = float('inf')

    for perm in permutations(range(n)):
        distance = calculate_route_distance(locations, list(perm))
        if distance < best_distance:
            best_distance = distance
            best_route = list(perm)

    return best_route


def solve_tsp_heuristic(locations):
    if len(locations) <= 1:
        return list(range(len(locations)))

    n = len(locations)
    unvisited = set(range(1, n))
    route = [0]

    while unvisited:
        current = route[-1]
        nearest = min(
            unvisited,
            key=lambda i: euclidean_distance(locations[current], locations[i])
        )
        route.append(nearest)
        unvisited.remove(nearest)

    return route


def calculate_route_distance(locations, route):
    if len(route) <= 1:
        return 0

    total = 0
    for i in range(len(route)):
        current = locations[route[i]]
        next_loc = locations[route[(i + 1) % len(route)]]
        total += euclidean_distance(current, next_loc)

    return total


def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
```

**Benefits:**
- Small, verifiable test cases
- Brute force verification for correctness
- Heuristic for scalability
- Clear progression from simple to complex
- Confidence in algorithm correctness

### Implementation Steps

1. **Step 1: Write Trivial Tests**
   - Test with 0 locations
   - Test with 1 location
   - Test with 2 locations

2. **Step 2: Implement Brute Force**
   - Implement permutations-based solution
   - Verify trivial tests pass

3. **Step 3: Write Verifiable Tests**
   - Test with 3 locations (triangle)
   - Test with 4 locations (square)
   - Test with known optimal solutions

4. **Step 4: Implement Heuristic**
   - Write nearest-neighbor heuristic
   - Test that it returns valid routes

5. **Step 5: Compare Heuristic to Brute Force**
   - Test on small cases
   - Verify heuristic is reasonable

6. **Step 6: Add Performance Tests**
   - Test with 20 locations
   - Verify heuristic completes quickly

### Testing the Solution

**Test Cases:**
- **Trivial cases**: 0, 1, 2 locations
- **Small verifiable**: 3-4 locations with known optimal solutions
- **Comparison**: Heuristic vs brute force on small cases
- **Performance**: 20 locations completes in reasonable time

**Verification:**
Run `pytest test_tsp.py -v -s` to verify all cases. Add new optimization by writing tests first for small cases, then comparing with brute force.

## Scenario 5: Data Validation Pipeline

### Context

A data pipeline validates CSV files before importing into a database. Validations include required fields, data type checking, range validation, and reference integrity. Invalid records should be logged with clear error messages.

### Problem Description

The BAD approach writes validation logic in one large function without tests, leading to missed validation rules and unclear error messages.

### Analysis of Violations

**Current Issues:**
- **No tests**: Validation logic untested
- **Complex logic**: Multiple validation rules intertwined
- **Unclear errors**: Generic error messages
- **Hard to extend**: Adding new rules is risky

**Impact:**
- Invalid data enters system
- Difficult to debug validation failures
- Poor user experience
- Data quality issues

### BAD Approach

```python
def validate_csv_row(row, schema):
    errors = []

    for field in schema['required']:
        if field not in row or not row[field]:
            errors.append(f'{field} is required')

    if 'email' in row:
        if '@' not in row['email'] or '.' not in row['email']:
            errors.append('Invalid email format')

    if 'age' in row:
        try:
            age = int(row['age'])
            if age < 0 or age > 120:
                errors.append('Age must be between 0 and 120')
        except ValueError:
            errors.append('Age must be a number')

    if 'salary' in row:
        try:
            salary = float(row['salary'])
            if salary < 0:
                errors.append('Salary cannot be negative')
        except ValueError:
            errors.append('Salary must be a number')

    return errors if errors else None
```

**Why This Approach Fails:**
- No test coverage
- Hard to add new validation rules
- Generic error messages
- No way to reuse validators

### GOOD Approach

**Solution Strategy:**
1. Write tests for each validation rule
2. Extract validators as separate classes
3. Compose validators into a pipeline
4. Add clear, specific error messages

```python
import pytest
from datetime import datetime


class RequiredFieldValidatorTests:
    def test_passes_when_all_required_fields_present(self):
        validator = RequiredFieldValidator(['name', 'email'])
        row = {'name': 'Alice', 'email': 'alice@example.com'}

        errors = validator.validate(row)

        assert errors is None

    def test_fails_when_required_field_missing(self):
        validator = RequiredFieldValidator(['name', 'email'])
        row = {'name': 'Alice'}

        errors = validator.validate(row)

        assert len(errors) == 1
        assert 'email' in errors[0]

    def test_fails_when_required_field_empty(self):
        validator = RequiredFieldValidator(['name'])
        row = {'name': ''}

        errors = validator.validate(row)

        assert len(errors) == 1
        assert 'name' in errors[0]


class EmailValidatorTests:
    def test_passes_for_valid_email(self):
        validator = EmailValidator('email')
        row = {'email': 'alice@example.com'}

        errors = validator.validate(row)

        assert errors is None

    def test_fails_for_email_without_at_symbol(self):
        validator = EmailValidator('email')
        row = {'email': 'aliceexample.com'}

        errors = validator.validate(row)

        assert 'email' in errors[0].lower()

    def test_fails_for_email_without_domain(self):
        validator = EmailValidator('email')
        row = {'email': 'alice@'}

        errors = validator.validate(row)

        assert 'email' in errors[0].lower()


class RangeValidatorTests:
    def test_passes_for_value_in_range(self):
        validator = RangeValidator('age', min_value=0, max_value=120)
        row = {'age': '25'}

        errors = validator.validate(row)

        assert errors is None

    def test_fails_for_value_below_minimum(self):
        validator = RangeValidator('age', min_value=0, max_value=120)
        row = {'age': '-5'}

        errors = validator.validate(row)

        assert 'age' in errors[0].lower()
        assert '0' in errors[0]

    def test_fails_for_value_above_maximum(self):
        validator = RangeValidator('age', min_value=0, max_value=120)
        row = {'age': '150'}

        errors = validator.validate(row)

        assert 'age' in errors[0].lower()
        assert '120' in errors[0]


class ValidationPipelineTests:
    def test_pipeline_validates_all_rules(self):
        schema = [
            RequiredFieldValidator(['name', 'email', 'age']),
            EmailValidator('email'),
            RangeValidator('age', min_value=0, max_value=120)
        ]
        pipeline = ValidationPipeline(schema)
        row = {
            'name': 'Alice',
            'email': 'alice@example.com',
            'age': '25'
        }

        result = pipeline.validate(row)

        assert result.is_valid() is True

    def test_pipeline_collects_all_errors(self):
        schema = [
            RequiredFieldValidator(['name', 'email', 'age']),
            EmailValidator('email'),
            RangeValidator('age', min_value=0, max_value=120)
        ]
        pipeline = ValidationPipeline(schema)
        row = {
            'name': '',
            'email': 'invalid-email',
            'age': '150'
        }

        result = pipeline.validate(row)

        assert result.is_valid() is False
        assert len(result.errors) == 3
```

**Implementation:**

```python
class ValidationResult:
    def __init__(self, errors=None):
        self.errors = errors or []

    def is_valid(self):
        return len(self.errors) == 0

    def add_error(self, error):
        self.errors.append(error)

    def merge(self, other_result):
        self.errors.extend(other_result.errors)


class RequiredFieldValidator:
    def __init__(self, fields):
        self.fields = fields

    def validate(self, row):
        errors = []
        for field in self.fields:
            if field not in row or not str(row[field]).strip():
                errors.append(f"Field '{field}' is required")

        return errors if errors else None


class EmailValidator:
    def __init__(self, field):
        self.field = field

    def validate(self, row):
        if self.field not in row:
            return None

        email = str(row[self.field]).strip()
        if not email:
            return None

        if '@' not in email or '.' not in email.split('@')[-1]:
            return [f"Field '{self.field}' must be a valid email address"]

        return None


class RangeValidator:
    def __init__(self, field, min_value=None, max_value=None):
        self.field = field
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, row):
        if self.field not in row:
            return None

        value = row[self.field]
        if value is None or value == '':
            return None

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            return [f"Field '{self.field}' must be a number"]

        errors = []
        if self.min_value is not None and numeric_value < self.min_value:
            errors.append(f"Field '{self.field}' must be at least {self.min_value}")

        if self.max_value is not None and numeric_value > self.max_value:
            errors.append(f"Field '{self.field}' must be at most {self.max_value}")

        return errors if errors else None


class ValidationPipeline:
    def __init__(self, validators):
        self.validators = validators

    def validate(self, row):
        result = ValidationResult()

        for validator in self.validators:
            errors = validator.validate(row)
            if errors:
                for error in errors:
                    result.add_error(error)

        return result
```

**Benefits:**
- Each validator independently testable
- Clear, specific error messages
- Easy to add new validators
- Composable validation rules
- Reusable validators

### Implementation Steps

1. **Step 1: Write Tests for RequiredFieldValidator**
   - Test all fields present
   - Test missing field
   - Test empty field
   - Implement validator

2. **Step 2: Write Tests for EmailValidator**
   - Test valid email
   - Test invalid formats
   - Implement validator

3. **Step 3: Write Tests for RangeValidator**
   - Test value in range
   - Test below minimum
   - Test above maximum
   - Test non-numeric
   - Implement validator

4. **Step 4: Write Tests for Pipeline**
   - Test all validators pass
   - Test multiple errors collected
   - Implement pipeline

5. **Step 5: Add More Validators**
   - DateValidator
   - ReferenceValidator
   - PatternValidator
   - Write tests first

### Testing the Solution

**Test Cases:**
- **Required fields**: Present, missing, empty
- **Email format**: Valid, invalid formats
- **Range validation**: In range, below min, above max, non-numeric
- **Pipeline**: Multiple validators, error collection

**Verification:**
Run `pytest test_validation.py -v` to verify all validators work correctly. Add new validators by writing tests first.

## Scenario 6: Integration Testing Strategy

### Context

A web application has multiple services (user authentication, payment processing, inventory management, email notifications) that need to work together. Integration tests verify end-to-end workflows.

### Problem Description

The BAD approach writes integration tests that depend on external services (real database, payment gateway, email server), making tests slow, flaky, and unreliable.

### Analysis of Violations

**Current Issues:**
- **Real I/O dependencies**: Database, network calls
- **Slow execution**: Tests take minutes
- **Flaky results**: Network failures cause test failures
- **Hard to set up**: Requires external infrastructure

**Impact:**
- Developers don't run tests
- Slow feedback loop
- Unreliable CI/CD
- Difficult to debug failures

### BAD Approach

```python
def test_complete_order_workflow_integration():
    db = Database(host='localhost', port=5432)
    db.connect()

    user = User(email='alice@example.com')
    db.save(user)

    product = Product(name='Book', price=10.00, stock=100)
    db.save(product)

    cart = Cart(user=user)
    cart.add_item(product, 2)
    db.save(cart)

    gateway = PaymentGateway(api_key='test_key')
    response = gateway.charge(20.00, 'card_123')

    assert response.success is True

    order = Order.from_cart(cart)
    order.payment_id = response.transaction_id
    order.status = 'paid'
    db.save(order)

    email_server = SMTP(host='localhost', port=25)
    email_server.connect()
    email_server.send(
        from_addr='orders@example.com',
        to_addr=user.email,
        subject='Order Confirmation',
        body=f'Your order {order.id} is confirmed'
    )

    assert order.status == 'paid'
```

**Why This Approach Fails:**
- Depends on running database server
- Depends on payment gateway
- Depends on SMTP server
- Tests are slow and flaky
- Cannot run in isolated environment

### GOOD Approach

**Solution Strategy:**
1. Use fakes for external services
2. Keep integration tests fast
3. Test interactions between components
4. Maintain test isolation

```python
import pytest


class FakeDatabase:
    def __init__(self):
        self._users = {}
        self._products = {}
        self._carts = {}
        self._orders = {}

    def save(self, obj):
        if isinstance(obj, User):
            self._users[obj.email] = obj
            obj.id = len(self._users)
        elif isinstance(obj, Product):
            self._products[obj.name] = obj
            obj.id = len(self._products)
        elif isinstance(obj, Cart):
            self._carts[obj.id] = obj
        elif isinstance(obj, Order):
            self._orders[obj.id] = obj

    def find_user_by_email(self, email):
        return self._users.get(email)

    def find_product_by_name(self, name):
        return self._products.get(name)


class FakePaymentGateway:
    def __init__(self):
        self.charges = []
        self.should_decline = False

    def charge(self, amount, card_token):
        if self.should_decline:
            return PaymentResponse(success=False, error='Card declined')

        response = PaymentResponse(
            success=True,
            transaction_id=f'txn_{len(self.charges)}'
        )
        self.charges.append({'amount': amount, 'card': card_token})
        return response


class FakeEmailService:
    def __init__(self):
        self.sent_emails = []

    def send(self, from_addr, to_addr, subject, body):
        self.sent_emails.append({
            'from': from_addr,
            'to': to_addr,
            'subject': subject,
            'body': body
        })
        return True


@pytest.fixture
def integration_test_env():
    db = FakeDatabase()
    gateway = FakePaymentGateway()
    email = FakeEmailService()

    return {
        'database': db,
        'payment_gateway': gateway,
        'email_service': email
    }


class OrderWorkflowIntegrationTests:
    def test_complete_order_workflow_succeeds(self, integration_test_env):
        db = integration_test_env['database']
        gateway = integration_test_env['payment_gateway']
        email = integration_test_env['email_service']

        user = User(email='alice@example.com')
        db.save(user)

        product = Product(name='Book', price=10.00)
        db.save(product)

        cart = Cart(user=user)
        cart.add_item(product, 2)

        order_processor = OrderProcessor(db, gateway, email)
        order = order_processor.process(cart, card_token='card_123')

        assert order.status == 'paid'
        assert order.payment_id == 'txn_0'
        assert len(gateway.charges) == 1
        assert gateway.charges[0]['amount'] == 20.00

    def test_order_workflow_fails_on_payment_declined(self, integration_test_env):
        db = integration_test_env['database']
        gateway = integration_test_env['payment_gateway']
        email = integration_test_env['email_service']
        gateway.should_decline = True

        user = User(email='alice@example.com')
        db.save(user)

        product = Product(name='Book', price=10.00)
        db.save(product)

        cart = Cart(user=user)
        cart.add_item(product, 2)

        order_processor = OrderProcessor(db, gateway, email)

        with pytest.raises(PaymentDeclinedException):
            order_processor.process(cart, card_token='card_123')

    def test_order_workflow_sends_confirmation_email(self, integration_test_env):
        db = integration_test_env['database']
        gateway = integration_test_env['payment_gateway']
        email = integration_test_env['email_service']

        user = User(email='alice@example.com')
        db.save(user)

        product = Product(name='Book', price=10.00)
        db.save(product)

        cart = Cart(user=user)
        cart.add_item(product, 2)

        order_processor = OrderProcessor(db, gateway, email)
        order = order_processor.process(cart, card_token='card_123')

        assert len(email.sent_emails) == 1
        assert email.sent_emails[0]['to'] == 'alice@example.com'
        assert 'confirmed' in email.sent_emails[0]['body'].lower()
```

**Implementation:**

```python
class OrderProcessor:
    def __init__(self, database, payment_gateway, email_service):
        self.database = database
        self.payment_gateway = payment_gateway
        self.email_service = email_service

    def process(self, cart, card_token):
        total = cart.calculate_total()

        payment_response = self.payment_gateway.charge(total, card_token)

        if not payment_response.success:
            raise PaymentDeclinedException(payment_response.error)

        order = Order.from_cart(cart)
        order.payment_id = payment_response.transaction_id
        order.status = 'paid'

        self.database.save(order)
        self._send_confirmation(order)

        return order

    def _send_confirmation(self, order):
        self.email_service.send(
            from_addr='orders@example.com',
            to_addr=order.user.email,
            subject='Order Confirmation',
            body=f'Your order {order.id} is confirmed'
        )
```

**Benefits:**
- Fast, reliable integration tests
- No external dependencies
- Tests run in milliseconds
- Easy to debug failures
- Can run in parallel

### Implementation Steps

1. **Step 1: Create Fake Implementations**
   - FakeDatabase with in-memory storage
   - FakePaymentGateway that records calls
   - FakeEmailService that tracks emails

2. **Step 2: Write Integration Tests**
   - Test happy path workflow
   - Test payment failure scenario
   - Test email sending

3. **Step 3: Implement OrderProcessor**
   - Wire up real components
   - Implement workflow logic
   - Verify tests pass

4. **Step 4: Add Edge Cases**
   - Test inventory shortage
   - Test user not found
   - Test cart validation

5. **Step 5: Add Performance Tests**
   - Test with multiple orders
   - Verify scalability

### Testing the Solution

**Test Cases:**
- **Happy path**: Successful order processing
- **Payment failure**: Gateway declines card
- **Email notification**: Confirmation sent
- **Edge cases**: Inventory, validation errors

**Verification:**
Run `pytest test_integration.py -v` to verify all workflows work correctly. Tests complete in milliseconds without external dependencies.

## Migration Guide

### Refactoring Existing Codebases

When refactoring existing Python code to follow TDD:

1. **Phase 1: Assessment**
   - Identify areas with low or no test coverage
   - Use `pytest --cov=src` to measure coverage
   - Prioritize high-risk, high-value code
   - Document current behavior with characterization tests

2. **Phase 2: Planning**
   - Create refactoring roadmap
   - Identify test doubles needed for dependencies
   - Plan incremental changes
   - Set up CI/CD with test gates

3. **Phase 3: Implementation**
   - Write characterization tests first
   - Extract one responsibility at a time
   - Write unit tests for extracted components
   - Verify all tests pass after each change

4. **Phase 4: Verification**
   - Run full test suite
   - Measure improvement in coverage
   - Run mutation testing with `mutmut`
   - Update documentation

### Incremental Refactoring Strategies

**Strategy 1: The Strangler Fig Pattern**
- Gradually replace old code with new, tested code
- Keep old code behind an interface
- Route traffic to new code incrementally
- Example: Extracting OrderProcessor validators

**Strategy 2: Test-Last to Test-First Migration**
- Start with test-last for new features
- Gradually adopt test-first for critical code
- Use spike solutions to explore, then TDD to implement
- Example: Implementing new pricing rules

**Strategy 3: Legacy Seams**
- Find points where you can intercept calls
- Insert test doubles at seams
- Test through existing interfaces
- Example: Testing legacy order processing

### Common Refactoring Patterns

1. **Extract Method**: Pull out logic into separate, testable methods
   - Helps apply Single Responsibility Principle
   - Makes individual behaviors testable

2. **Extract Class**: Move related methods to a new class
   - Reduces complexity of existing classes
   - Creates focused, testable components

3. **Parameterize Method**: Make hardcoded values parameters
   - Reduces duplication
   - Makes behavior configurable for testing

4. **Replace Conditional with Polymorphism**: Use strategy pattern
   - Eliminates complex conditionals
   - Makes each branch independently testable

### Testing During Refactoring

**Regression Testing:**
- Use `pytest -v --cov=src` to maintain coverage
- Run `pytest --last-failed` to focus on broken tests
- Use `pytest -x` to stop at first failure
- Compare coverage before/after refactoring

**Integration Testing:**
- Test at component boundaries with fakes
- Verify interactions between components
- Test error paths and edge cases
- Use `pytest-mock` for verifying interactions

**Mutation Testing:**
- Install: `pip install mutmut`
- Run: `mutmut run`
- Identifies weak assertions
- Ensures tests actually verify correctness

## Language-Specific Notes

### Common Real-World Challenges in Python

- **Dynamic typing**: Type-related bugs not caught at compile time
  - Solution: Use type hints with `mypy` and write comprehensive tests

- **Global state**: Tests interfere with each other
  - Solution: Use fixtures and ensure test isolation

- **External dependencies**: I/O makes tests slow
  - Solution: Use test doubles (fakes, mocks, stubs)

- **Async code**: Requires special test handling
  - Solution: Use `pytest-asyncio` for async tests

- **Database state**: Tests leave data behind
  - Solution: Use transaction rollbacks or in-memory databases

### Framework-Specific Scenarios

- **Django**: Use `django.test.TestCase` for database tests
- **Flask**: Use `Flask.test_client()` for API tests
- **FastAPI**: Use `TestClient` for async endpoints
- **Celery**: Use `CELERY_TASK_ALWAYS_EAGER` for synchronous testing
- **SQLAlchemy**: Use in-memory SQLite for fast tests

### Ecosystem Tools

**Refactoring Tools:**
- **Rope**: Advanced refactoring IDE support
- **PyCharm**: Built-in refactoring tools
- **AutoPEP8**: Format code automatically

**Analysis Tools:**
- **Pylint**: Code quality checks
- **Flake8**: Style and error checking
- **Black**: Code formatting
- **Mypy**: Type checking

**Testing Tools:**
- **Pytest**: Preferred test framework
- **Pytest-cov**: Coverage measurement
- **Pytest-mock**: Enhanced mocking
- **Pytest-xdist**: Parallel test execution
- **Factory Boy**: Test data generation
- **Faker**: Generate realistic test data

### Best Practices for Python

1. **Use pytest over unittest**: More concise and powerful
2. **Leverage fixtures**: Use `@pytest.fixture` for setup/teardown
3. **Use conftest.py**: Share fixtures across test modules
4. **Parametrize tests**: Use `@pytest.mark.parametrize` for data-driven tests
5. **Mock sparingly**: Prefer fakes over mocks when possible
6. **Test public API**: Avoid testing private methods
7. **Keep tests fast**: Unit tests should complete in milliseconds
8. **One assertion per test**: Tests should be focused
9. **Use descriptive names**: Test names should document behavior
10. **Run tests frequently**: Integrate with pre-commit hooks

### Case Studies

**Case Study 1: Legacy Django App Refactoring**
- Context: 5000-line views.py with no tests
- Problem: Bug fixes broke existing functionality
- Solution: Wrote characterization tests, extracted services
- Results: 80% test coverage, faster development

**Case Study 2: FastAPI Microservice**
- Context: New service built with TDD
- Problem: Complex business logic requirements
- Solution: Test-first development with pytest
- Results: 95% coverage, zero production bugs in first 6 months

**Case Study 3: Data Pipeline Migration**
- Context: Pandas-based data processing
- Problem: Inconsistent data quality
- Solution: TDD for validation and transformation logic
- Results: 60% reduction in data quality issues
