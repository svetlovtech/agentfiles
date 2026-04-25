# TDD Anti-Patterns - Python

## Table of Contents

- [Introduction](#introduction)
- [Anti-Pattern 1: The Liar](#anti-pattern-1-the-liar)
- [Anti-Pattern 2: The Giant](#anti-pattern-2-the-giant)
- [Anti-Pattern 3: The Mockery](#anti-pattern-3-the-mockery)
- [Anti-Pattern 4: The Greeter](#anti-pattern-4-the-greeter)
- [Anti-Pattern 5: The Observer](#anti-pattern-5-the-observer)
- [Anti-Pattern 6: The Generator](#anti-pattern-6-the-generator)
- [Anti-Pattern 7: The Slowpoke](#anti-pattern-7-the-slowpoke)
- [Anti-Pattern 8: The Miracle](#anti-pattern-8-the-miracle)
- [Anti-Pattern 9: The Secret Catcher](#anti-pattern-9-the-secret-catcher)
- [Anti-Pattern 10: The Excessive Setup](#anti-pattern-10-the-excessive-setup)
- [Detection Checklist](#detection-checklist)
- [Language-Specific Notes](#language-specific-notes)

## Introduction

This document catalogs common anti-patterns and test smells that violate TDD principles in Python. Each anti-pattern includes a description, BAD example, explanation of why it's problematic, and a corrected GOOD example.

## Anti-Pattern 1: The Liar

### Description

Tests that always pass regardless of the production code's behavior, usually due to incorrect assertions, never-failing assertions, or testing the wrong thing.

### BAD Example

```python
def test_user_creation():
    user = User(name="Alice")
    user.save()
    assert user is not None
    assert True
```

### Why It's Problematic

- **assert True**: Always passes, provides no value
- **assert user is not None**: Passes even if user has wrong attributes
- **False confidence**: Tests pass but don't verify correct behavior
- **Wasted effort**: Writing tests that don't test anything

### How to Fix

**Refactoring Steps:**
1. Identify what behavior should actually be tested
2. Write assertions that verify specific, meaningful outcomes
3. Ensure assertions can fail when code is wrong
4. Run tests before implementing code to verify they fail

### GOOD Example

```python
def test_user_creation_persists_to_database():
    user = User(name="Alice")
    user.save()

    retrieved_user = User.find_by_name("Alice")
    assert retrieved_user is not None
    assert retrieved_user.name == "Alice"


def test_user_has_creation_timestamp():
    user = User(name="Alice")
    user.save()

    assert user.created_at is not None
    assert isinstance(user.created_at, datetime)
```

**Key Changes:**
- Meaningful assertions that verify actual behavior
- Tests retrieve and verify saved data
- Assertions check specific values and types
- Tests will fail if implementation is wrong

---

## Anti-Pattern 2: The Giant

### Description

Tests that are too long, test too many things, or have complex setup code. They're hard to read, maintain, and debug.

### BAD Example

```python
def test_complete_order_workflow():
    user = User(name="Alice", email="alice@example.com")
    user.save()

    product = Product(name="Book", price=10.00, stock=100)
    product.save()

    cart = Cart(user=user)
    cart.add_item(product, 2)
    cart.add_item(product, 3)

    order = Order.from_cart(cart)
    order.process_payment("4111111111111111", "12/25", "123")
    assert order.status == "paid"

    order.ship()
    assert order.status == "shipped"

    invoice = Invoice.generate(order)
    assert invoice.total == 50.00
    assert invoice.items.count() == 1

    user.points += 50
    user.save()
    assert user.points == 50

    email_service.send_confirmation(user.email, order.id)
    assert email_service.last_email.sent_to == user.email
```

### Why It's Problematic

- **Tests multiple things**: Payment, shipping, invoicing, rewards, email
- **Complex setup**: Creates multiple interdependent objects
- **Hard to debug**: Failures don't indicate what's wrong
- **Fragile**: Breaks when any step changes
- **Slow**: Each test does too much work

### How to Fix

**Refactoring Steps:**
1. Split into multiple focused tests
2. Extract common setup into fixtures
3. Each test should verify one behavior
4. Use test doubles for external dependencies

### GOOD Example

```python
@pytest.fixture
def user():
    return User(name="Alice", email="alice@example.com")


@pytest.fixture
def product():
    return Product(name="Book", price=10.00, stock=100)


@pytest.fixture
def cart_with_items(user, product):
    cart = Cart(user=user)
    cart.add_item(product, 5)
    return cart


def test_order_creation_from_cart(cart_with_items):
    order = Order.from_cart(cart_with_items)
    assert order.items.count() == 1
    assert order.total == 50.00


def test_order_payment_processing(cart_with_items, fake_payment_gateway):
    order = Order.from_cart(cart_with_items)
    order.process_payment(
        card="4111111111111111",
        expiry="12/25",
        cvv="123",
        gateway=fake_payment_gateway
    )
    assert order.status == "paid"
    assert fake_payment_gateway.charged_amount == 50.00


def test_order_shipment_updates_status(cart_with_items):
    order = Order.from_cart(cart_with_items)
    order.status = "paid"
    order.ship()
    assert order.status == "shipped"


def test_invoice_generation(cart_with_items):
    order = Order.from_cart(cart_with_items)
    invoice = Invoice.generate(order)
    assert invoice.total == 50.00


def test_loyalty_points_are_awarded(user, cart_with_items):
    order = Order.from_cart(cart_with_items)
    order.process(user)
    assert user.points == 50
```

**Key Changes:**
- Each test focuses on one behavior
- Fixtures reduce duplication
- Tests are short and clear
- Easy to identify failure points

---

## Anti-Pattern 3: The Mockery

### Description

Over-mocking external dependencies, testing implementation details rather than behavior, creating fragile tests that break on refactoring.

### BAD Example

```python
@patch('orders.OrderProcessor._validate_items')
@patch('orders.OrderProcessor._calculate_totals')
@patch('orders.OrderProcessor._check_inventory')
@patch('orders.OrderProcessor._reserve_stock')
@patch('orders.OrderProcessor._process_payment')
@patch('orders.OrderProcessor._save_order')
def test_order_processing_too_much_mocking(
    mock_save, mock_payment, mock_reserve, mock_inventory,
    mock_totals, mock_validate, order
):
    processor = OrderProcessor()

    processor.process(order)

    mock_validate.assert_called_once_with(order.items)
    mock_totals.assert_called_once_with(order.items)
    mock_inventory.assert_called_once_with(order.items)
    mock_reserve.assert_called_once_with(order.items)
    mock_payment.assert_called_once_with(order.total)
    mock_save.assert_called_once_with(order)
```

### Why It's Problematic

- **Tests implementation**: Mocking private methods
- **Fragile**: Breaks on any internal change
- **Hard to read**: More mock setup than test logic
- **False confidence**: Verifies calls, not outcomes
- **Refactoring fear**: Can't change internals without breaking tests

### How to Fix

**Refactoring Steps:**
1. Identify what observable behavior should be tested
2. Use fakes instead of mocks for dependencies
3. Test through public API only
4. Verify outcomes, not implementation details

### GOOD Example

```python
class FakePaymentGateway:
    def __init__(self):
        self.charged_amount = 0
        self.should_fail = False

    def charge(self, amount):
        if self.should_fail:
            raise PaymentError("Card declined")
        self.charged_amount = amount
        return True


class FakeInventory:
    def __init__(self):
        self.reserved_items = []

    def reserve(self, items):
        for item in items:
            self.reserved_items.append(item)
        return True


def test_order_processing_charges_correct_amount():
    order = Order(items=[Item("book", 10), Item("pen", 5)])
    fake_gateway = FakePaymentGateway()
    fake_inventory = FakeInventory()

    processor = OrderProcessor(payment_gateway=fake_gateway, inventory=fake_inventory)
    processor.process(order)

    assert fake_gateway.charged_amount == 15
    assert len(fake_inventory.reserved_items) == 2
    assert order.status == "completed"


def test_order_processing_with_failed_payment():
    order = Order(items=[Item("book", 10)])
    fake_gateway = FakePaymentGateway()
    fake_gateway.should_fail = True

    processor = OrderProcessor(payment_gateway=fake_gateway)
    processor.process(order)

    assert order.status == "payment_failed"
```

**Key Changes:**
- Simple fakes instead of complex mocks
- Tests verify observable outcomes
- No coupling to internal implementation
- Easy to refactor internals without breaking tests

---

## Anti-Pattern 4: The Greeter

### Description

Tests that print or log output instead of making assertions. They're not automated tests but manual inspection scripts.

### BAD Example

```python
def test_user_registration():
    user = User.register("alice@example.com", "password123")
    print(f"User created: {user.email}")
    print(f"User ID: {user.id}")
    print(f"Is verified: {user.is_verified}")
    print(f"Registration date: {user.created_at}")


def test_calculate_discount():
    cart = Cart(items=[Item("book", 10), Item("book", 10)])
    total = cart.calculate_total()
    print(f"Items: {cart.item_count}")
    print(f"Subtotal: {cart.subtotal}")
    print(f"Discount: {cart.discount}")
    print(f"Total: {total}")
```

### Why It's Problematic

- **Not automated**: Requires manual inspection
- **Cannot fail**: Print statements always succeed
- **No CI/CD**: Can't run in automated pipelines
- **Subjective**: Relies on human judgment
- **Inconsistent**: Different people interpret differently

### How to Fix

**Refactoring Steps:**
1. Replace print statements with assertions
2. Define expected outcomes
3. Verify specific values
4. Make tests pass/fail automatically

### GOOD Example

```python
def test_user_registration_creates_verified_user():
    user = User.register("alice@example.com", "password123")

    assert user.email == "alice@example.com"
    assert user.id is not None
    assert user.is_verified is True
    assert user.created_at is not None


def test_bulk_purchase_applies_ten_percent_discount():
    cart = Cart(items=[Item("book", 10), Item("book", 10)])

    total = cart.calculate_total()

    assert cart.item_count == 2
    assert cart.subtotal == 20.00
    assert cart.discount == 2.00
    assert total == 18.00
```

**Key Changes:**
- Automated assertions instead of print statements
- Clear pass/fail criteria
- Can run in CI/CD pipelines
- Objective verification of behavior

---

## Anti-Pattern 5: The Observer

### Description

Tests that observe the internal state of objects through private attributes or debug methods, testing implementation rather than behavior.

### BAD Example

```python
def test_order_processing():
    order = Order(items=[Item("book", 10)])
    processor = OrderProcessor()
    processor.process(order)

    assert order._status == "completed"
    assert order._payment._transaction_id is not None
    assert processor._inventory._reserved_stock == 1
    assert processor._payment_gateway._last_call == "charge"


def test_user_login():
    user = User(email="alice@example.com")
    auth = AuthService()
    auth.login(user, "password")

    assert user._session_token is not None
    assert user._last_login_at is not None
    assert auth._cache._keys["user:alice@example.com"] == user._session_token
```

### Why It's Problematic

- **Tests private state**: Accessing underscored attributes
- **Coupled to internals**: Breaks on refactoring
- **Not observable**: Tests implementation, not behavior
- **Fragile**: Internal changes break tests
- **Violates encapsulation**: Bypasses public API

### How to Fix

**Refactoring Steps:**
1. Identify public API to test through
2. Test observable behaviors and outcomes
3. Remove access to private attributes
4. Focus on what users see, not how it works

### GOOD Example

```python
def test_order_processing_completes_successfully():
    order = Order(items=[Item("book", 10)])
    processor = OrderProcessor()
    processor.process(order)

    assert order.is_completed()
    assert order.payment is_successful()
    assert processor.inventory.is_stock_reserved("book", 1)


def test_user_login_creates_active_session():
    user = User(email="alice@example.com")
    auth = AuthService()
    auth.login(user, "password")

    assert auth.is_authenticated(user.email)
    assert auth.get_session(user.email) is not None
    assert user.last_login_at is not None
```

**Key Changes:**
- Tests through public API
- Verifies observable behaviors
- Not coupled to implementation
- Respects encapsulation

---

## Anti-Pattern 6: The Generator

### Description

Tests that generate complex test data or execute loops within the test, making the test itself complex and hard to debug.

### BAD Example

```python
def test_sorting_algorithm():
    test_cases = []

    for size in range(1, 101):
        for pattern in ['random', 'sorted', 'reverse']:
            if pattern == 'random':
                data = [random.randint(0, 1000) for _ in range(size)]
            elif pattern == 'sorted':
                data = list(range(size))
            else:
                data = list(range(size-1, -1, -1))

            expected = sorted(data)
            result = quicksort(data)

            test_cases.append((data, expected, result))
            assert result == expected

    for i, (data, expected, result) in enumerate(test_cases):
        if result != expected:
            print(f"Failed case {i}: {data}")
            assert False
```

### Why It's Problematic

- **Complex test logic**: Test code is as complex as production code
- **Hard to debug**: Failures don't show which case failed clearly
- **Slow**: Generates and tests 300 cases
- **Hard to understand**: Nested loops make logic unclear
- **Maintenance burden**: Adding tests requires modifying complex code

### How to Fix

**Refactoring Steps:**
1. Use pytest.mark.parametrize for data-driven tests
2. Extract test data to separate constants
3. Keep test logic simple and linear
4. Focus on representative cases, not exhaustive enumeration

### GOOD Example

```python
@pytest.mark.parametrize("data,expected", [
    ([], []),
    ([1], [1]),
    ([2, 1], [1, 2]),
    ([1, 2, 3], [1, 2, 3]),
    ([3, 2, 1], [1, 2, 3]),
    ([5, 2, 8, 1, 9], [1, 2, 5, 8, 9]),
    ([1, 1, 1], [1, 1, 1]),
])
def test_quicksort_with_various_inputs(data, expected):
    assert quicksort(data) == expected


@pytest.mark.parametrize("size", [10, 100, 1000])
def test_quicksort_handles_large_random_arrays(size):
    data = [random.randint(0, 1000) for _ in range(size)]
    expected = sorted(data)
    assert quicksort(data) == expected


def test_quicksort_preserves_duplicates():
    data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    expected = sorted(data)
    assert quicksort(data) == expected
```

**Key Changes:**
- Uses parametrize for clean data-driven tests
- Test logic is simple and clear
- Easy to see which case fails
- Representative cases instead of exhaustive enumeration
- Fast and maintainable

---

## Anti-Pattern 7: The Slowpoke

### Description

Tests that are slow due to I/O operations, database calls, network requests, or complex computations, making the test suite painful to run.

### BAD Example

```python
def test_user_registration():
    db = Database(host="localhost", port=5432)
    db.connect()

    user = User(email="alice@example.com")
    db.save(user)

    time.sleep(1)

    retrieved = db.find_by_email("alice@example.com")
    assert retrieved.email == "alice@example.com"

    time.sleep(1)
    db.disconnect()


def test_api_client():
    client = APIClient(base_url="https://api.example.com")

    response = client.get("/users/123")
    assert response.status_code == 200

    time.sleep(0.5)

    response = client.post("/users", json={"name": "Bob"})
    assert response.status_code == 201

    time.sleep(0.5)
```

### Why It's Problematic

- **Slow execution**: Takes minutes to run test suite
- **Developers avoid tests**: Slow feedback hurts productivity
- **Can't run frequently**: Not suitable for TDD's red-green-refactor cycle
- **Unreliable**: Network/database failures cause flakiness
- **Expensive**: Real resources consumed

### How to Fix

**Refactoring Steps:**
1. Replace real I/O with test doubles (fakes, mocks)
2. Use in-memory databases for data persistence tests
3. Mock network calls
4. Isolate unit tests from integration concerns

### GOOD Example

```python
@pytest.fixture
def fake_database():
    return FakeDatabase()


def test_user_registration_saves_to_database(fake_database):
    user = User(email="alice@example.com")
    fake_database.save(user)

    retrieved = fake_database.find_by_email("alice@example.com")
    assert retrieved.email == "alice@example.com"


class FakeDatabase:
    def __init__(self):
        self._users = {}

    def save(self, user):
        self._users[user.email] = user

    def find_by_email(self, email):
        return self._users.get(email)


@pytest.fixture
def fake_api_client():
    return FakeAPIClient()


def test_api_client_gets_user(fake_api_client):
    fake_api_client.add_response("/users/123", {"id": 123, "name": "Alice"})

    response = fake_api_client.get("/users/123")

    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_api_client_creates_user(fake_api_client):
    response = fake_api_client.post("/users", json={"name": "Bob"})

    assert response.status_code == 201
    assert fake_api_client.created_user == {"name": "Bob"}
```

**Key Changes:**
- Fast in-memory fakes instead of real I/O
- Tests run in milliseconds
- Reliable and deterministic
- Suitable for TDD's fast cycle
- Easy to debug

---

## Anti-Pattern 8: The Miracle

### Description

Tests with magic numbers, arbitrary values, or unclear test data that makes the test's intent hard to understand.

### BAD Example

```python
def test_price_calculation():
    assert calculate_price(42, 17, 3) == 53.67


def test_discount_eligibility():
    assert is_eligible_for_discount(7, 23, 1995) is True


def test_premium_upgrade():
    user = User(points=347, tier=2)
    assert user.can_upgrade() is True
```

### Why It's Problematic

- **Unclear intent**: What do these numbers represent?
- **Hard to maintain**: Magic numbers scattered throughout
- **No documentation**: Test doesn't explain business rules
- **Fragile**: Magic numbers might be wrong
- **Error-prone**: Easy to mistype numbers

### How to Fix

**Refactoring Steps:**
1. Replace magic numbers with named constants
2. Use descriptive test data
3. Explain business rules in test names
4. Make test data self-documenting

### GOOD Example

```python
def test_price_calculation_with_quantity_and_tax():
    unit_price = 42.00
    quantity = 17
    tax_rate_percent = 3
    expected_total = 734.82

    result = calculate_price(unit_price, quantity, tax_rate_percent)

    assert result == expected_total


def test_discount_eligibility_for_loyalty_customer():
    customer_since = date(1995, 7, 23)
    min_years_for_discount = 25
    years_as_customer = (date.today() - customer_since).days // 365

    assert years_as_customer >= min_years_for_discount


def test_premium_upgrade_with_sufficient_points():
    POINTS_FOR_PREMIUM = 350
    CURRENT_TIER = 2  # Silver

    user = User(points=POINTS_FOR_PREMIUM + 10, tier=CURRENT_TIER)

    assert user.can_upgrade_to_premium()
```

**Key Changes:**
- Named constants replace magic numbers
- Descriptive variable names explain values
- Test names clearly state intent
- Business rules are explicit
- Self-documenting test code

---

## Anti-Pattern 9: The Secret Catcher

### Description

Tests that catch exceptions without asserting on them, hiding failures and making debugging difficult.

### BAD Example

```python
def test_division():
    try:
        result = divide(10, 2)
        assert result == 5
    except Exception as e:
        print(f"Error: {e}")


def test_file_reading():
    try:
        content = read_file("data.txt")
        assert content is not None
    except:
        pass


def test_api_call():
    try:
        response = api_client.get("/users")
        assert response.status_code == 200
    except Exception:
        assert True
```

### Why It's Problematic

- **Hides failures**: Exceptions are swallowed
- **False passes**: Test passes even when code fails
- **No debugging info**: Can't see what went wrong
- **Confusing**: Assertion `True` always passes
- **Worse than no test**: Gives false confidence

### How to Fix

**Refactoring Steps:**
1. Remove try-except blocks
2. Let exceptions fail the test
3. Use pytest.raises for expected exceptions
4. Assert specific behaviors

### GOOD Example

```python
def test_division_with_valid_inputs():
    result = divide(10, 2)
    assert result == 5


def test_division_by_zero_raises_error():
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)


def test_file_reading_returns_content():
    content = read_file("data.txt")
    assert content is not None
    assert len(content) > 0


def test_reading_nonexistent_file_raises_error():
    with pytest.raises(FileNotFoundError):
        read_file("nonexistent.txt")


def test_api_call_returns_success():
    response = api_client.get("/users")
    assert response.status_code == 200
```

**Key Changes:**
- No exception swallowing
- Tests fail properly when errors occur
- pytest.raises for expected exceptions
- Clear failure messages
- Honest test results

---

## Anti-Pattern 10: The Excessive Setup

### Description

Tests with lengthy, complex setup code that dwarfs the actual test logic, making tests hard to read and maintain.

### BAD Example

```python
def test_order_workflow():
    user = User(name="Alice", email="alice@example.com")
    user.set_password("securepassword123")
    user.verified = True
    user.tier = "gold"
    user.points = 5000
    user.preferences = {
        "notifications": True,
        "newsletter": False,
        "language": "en"
    }
    user.save()

    address = Address(
        street="123 Main St",
        city="Boston",
        state="MA",
        zip="02101",
        country="USA"
    )
    address.user = user
    address.is_default = True
    address.save()

    product1 = Product(name="Book", price=10.00, stock=100, category="Books")
    product1.is_active = True
    product1.save()

    product2 = Product(name="Pen", price=5.00, stock=200, category="Stationery")
    product2.is_active = True
    product2.save()

    discount = Discount(code="SUMMER2025", percentage=10, minimum=50)
    discount.valid_from = date(2025, 6, 1)
    discount.valid_until = date(2025, 8, 31)
    discount.applicable_categories = ["Books"]
    discount.save()

    cart = Cart(user=user)
    cart.add_item(product1, 3)
    cart.add_item(product2, 5)
    cart.shipping_address = address
    cart.discount_code = "SUMMER2025"

    order = Order.from_cart(cart)
    order.process()

    assert order.total == 47.00
```

### Why It's Problematic

- **Setup dominates**: 40+ lines of setup, 2 lines of test
- **Hard to read**: Test intent buried in setup
- **Duplication**: Similar setup copied across tests
- **Fragile**: One setup change breaks many tests
- **Hard to maintain**: Changing test data requires navigating complex setup

### How to Fix

**Refactoring Steps:**
1. Extract setup into fixtures
2. Use factory methods or factories
3. Create test data builders
4. Focus test on specific behavior

### GOOD Example

```python
@pytest.fixture
def verified_gold_user():
    return UserFactory(
        name="Alice",
        email="alice@example.com",
        password="securepassword123",
        tier="gold",
        points=5000
    )


@pytest.fixture
def book_product():
    return ProductFactory(name="Book", price=10.00, stock=100, category="Books")


@pytest.fixture
def pen_product():
    return ProductFactory(name="Pen", price=5.00, stock=200, category="Stationery")


@pytest.fixture
def summer_discount():
    return DiscountFactory(
        code="SUMMER2025",
        percentage=10,
        minimum=50,
        applicable_categories=["Books"]
    )


@pytest.fixture
def cart_with_items(verified_gold_user, book_product, pen_product):
    cart = Cart(user=verified_gold_user)
    cart.add_item(book_product, 3)
    cart.add_item(pen_product, 5)
    return cart


def test_order_with_discount_applies_correctly(cart_with_items, summer_discount):
    cart_with_items.apply_discount(summer_discount)

    order = Order.from_cart(cart_with_items)

    assert order.subtotal == 55.00
    assert order.discount == 5.50
    assert order.total == 49.50


class UserFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "name": "Test User",
            "email": "test@example.com",
            "password": "password123",
            "tier": "bronze",
            "points": 0,
            "verified": True
        }
        defaults.update(kwargs)
        return User(**defaults)


class ProductFactory:
    @staticmethod
    def create(**kwargs):
        defaults = {
            "name": "Test Product",
            "price": 10.00,
            "stock": 100,
            "category": "General",
            "is_active": True
        }
        defaults.update(kwargs)
        return Product(**defaults)
```

**Key Changes:**
- Fixtures encapsulate setup
- Factory methods for test data
- Test focuses on behavior
- Clear and concise
- Easy to maintain

---

## Detection Checklist

Use this checklist to identify TDD violations in Python code:

### Code Review Questions

- [ ] Does the test have meaningful assertions (not `assert True`)?
- [ ] Is each test focused on a single behavior?
- [ ] Are tests written before implementation (red phase)?
- [ ] Do tests use public API, not private attributes?
- [ ] Are there excessive mock.patch decorators?
- [ ] Do tests have magic numbers without explanation?
- [ ] Are try-except blocks hiding exceptions?
- [ ] Is setup code longer than test logic?
- [ ] Do tests rely on I/O operations (database, network)?
- [ ] Can tests run independently in any order?

### Automated Detection

- **Pytest-cov**: Low coverage may indicate missing tests
- **Pytest-xdist**: Run tests in parallel to find order dependencies
- **Pylint/flake8**: Check for unused variables, overly complex functions
- **Mutmut**: Mutation testing to find weak assertions
- **Bandit**: Security issues in test code

### Manual Inspection Techniques

1. **Count assertions**: More than 2-3 per test suggests it's testing too much
2. **Measure setup lines**: Setup should be < 50% of test
3. **Check for mock.patch**: More than 2-3 suggests over-mocking
4. **Look for print statements**: Indicates manual testing, not automated
5. **Verify test order independence**: Run tests in reverse order

### Common Symptoms

- **Tests pass but code is broken**: The Liar (no real assertions)
- **Running tests takes minutes**: The Slowpoke (real I/O)
- **Small code change breaks many tests**: The Observer (testing internals)
- **Test file longer than production code**: The Giant (too much in one test)
- **Developers don't run tests often**: The Slowpoke (slow feedback)

## Language-Specific Notes

### Common Causes in Python

- **Dynamic typing**: No compiler to catch errors, developers write fewer tests
- **Interpreter culture**: "Run and see if it works" instead of test-first
- **Rapid prototyping**: Speed priority over testing
- **Interactive sessions**: REPL testing instead of automated tests
- **Simple syntax**: Easy to write code without tests

### Language Features that Enable Anti-Patterns

- **Monkeypatching**: Easy to patch anything, leads to over-mocking
- **Duck typing**: Can mock anything, encourages testing implementation
- **Decorators**: Easy to add `@patch` decorators
- **Dynamic attributes**: Easy to set private attributes for testing
- **Print statements**: Convenient for debugging, leads to manual tests

### Framework-Specific Anti-Patterns

- **Django**: Testing through ORM directly, using test database for unit tests
- **Flask**: Over-mocking request/response objects
- **FastAPI**: Testing through dependency injection incorrectly
- **Celery**: Testing tasks with real broker instead of mocks
- **Asyncio**: Not properly handling async in tests

### Tooling Support

- **Pytest**: Built-in fixture system, parametrize, monkeypatch
- **Pytest-cov**: Coverage reporting to find untested code
- **Pytest-benchmark**: Detect slow tests
- **Pytest-xdist**: Parallel test execution
- **Pytest-randomly**: Randomize test order to find dependencies
- **Factory Boy**: Generate test data with factories
- **Hypothesis**: Property-based testing to find edge cases
