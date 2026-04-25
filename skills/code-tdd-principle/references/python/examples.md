# TDD Examples - Python

## Table of Contents

- [Introduction](#introduction)
- [Example 1: Test-First vs Test-Last Development](#example-1-test-first-vs-test-last-development)
- [Example 2: Red-Green-Refactor Cycle](#example-2-red-green-refactor-cycle)
- [Example 3: AAA Pattern (Arrange-Act-Assert)](#example-3-aaa-pattern-arrange-act-assert)
- [Example 4: Single Assertion per Test](#example-4-single-assertion-per-test)
- [Example 5: Testing Behavior, Not Implementation](#example-5-testing-behavior-not-implementation)
- [Example 6: Triangulation](#example-6-triangulation)
- [Example 7: Given-When-Then (BDD Style)](#example-7-given-when-then-bdd-style)
- [Example 8: Test Isolation](#example-8-test-isolation)
- [Example 9: Faking External Dependencies](#example-9-faking-external-dependencies)
- [Example 10: Refactoring While Green](#example-10-refactoring-while-green)
- [Python-Specific Notes](#python-specific-notes)

## Introduction

This document provides paired examples of BAD and GOOD implementations of TDD principles in Python. Each example demonstrates a common violation and the corrected implementation following test-driven development best practices.

## Example 1: Test-First vs Test-Last Development

### BAD Example: Writing Code Before Tests

```python
def calculate_discount(price, customer_type):
    if customer_type == "premium":
        return price * 0.9
    elif customer_type == "vip":
        return price * 0.8
    else:
        return price


def test_calculate_discount():
    assert calculate_discount(100, "premium") == 90
    assert calculate_discount(100, "vip") == 80
    assert calculate_discount(100, "regular") == 100
```

**Problems:**
- Code written before tests (test-last approach)
- Tests only cover happy path after implementation
- No opportunity to let tests guide design
- Missing edge cases discovered late

### GOOD Example: Test-First Development

```python
def calculate_discount(price, customer_type):
    pass


def test_premium_customer_gets_10_percent_off():
    assert calculate_discount(100, "premium") == 90


def test_vip_customer_gets_20_percent_off():
    assert calculate_discount(100, "vip") == 80


def test_regular_customer_gets_no_discount():
    assert calculate_discount(100, "regular") == 100


def test_zero_price_returns_zero():
    assert calculate_discount(0, "premium") == 0


def test_negative_price_raises_error():
    with pytest.raises(ValueError):
        calculate_discount(-50, "regular")
```

**Improvements:**
- Tests written before implementation (test-first)
- Tests guide the function signature and behavior
- Edge cases identified upfront
- Multiple small tests, each with one assertion

### Explanation

The GOOD example follows the first law of TDD: no production code unless required by a failing test. By writing tests first, the design emerges from the test requirements, edge cases are discovered early, and each test is focused on a single behavior.

## Example 2: Red-Green-Refactor Cycle

### BAD Example: Skipping the Red Phase

```python
def calculate_tax(amount, rate):
    return amount * rate / 100


def test_calculate_tax():
    result = calculate_tax(100, 10)
    assert result == 10
    assert result is not None
```

**Problems:**
- Test written after code, never saw it fail
- No confirmation test would fail correctly
- Hard-coded implementation might never change
- Multiple assertions in one test

### GOOD Example: Following Red-Green-Refactor

```python
def calculate_tax(amount, rate):
    pass


def test_calculate_tax_with_ten_percent():
    assert calculate_tax(100, 10) == 10


def test_calculate_tax_with_fifteen_percent():
    assert calculate_tax(200, 15) == 30


def test_calculate_tax_with_zero_rate():
    assert calculate_tax(100, 0) == 0
```

**Improvements:**
- Tests written first and run to see them fail (Red)
- Implementation added to make tests pass (Green)
- Each test is minimal and focused
- Clear progression through TDD cycle

### Explanation

The GOOD example demonstrates the TDD cycle: write a failing test, run it (Red), write minimal code to pass (Green), then refactor. Each iteration builds confidence that tests actually fail when code is wrong.

## Example 3: AAA Pattern (Arrange-Act-Assert)

### BAD Example: Mixed AAA Pattern

```python
def test_user_authentication():
    user = User(username="alice", password="secret")
    auth = AuthService()
    assert auth.authenticate(user.username, user.password) is True
    user.delete()
```

**Problems:**
- Act and assert mixed together
- Setup and teardown unclear
- Test intention obscured
- Hard to read and maintain

### GOOD Example: Clear AAA Pattern

```python
def test_user_authentication_with_valid_credentials():
    user = User(username="alice", password="secret")
    auth = AuthService()

    result = auth.authenticate(user.username, user.password)

    assert result is True


def test_user_authentication_with_invalid_password():
    user = User(username="alice", password="secret")
    auth = AuthService()

    result = auth.authenticate(user.username, "wrongpassword")

    assert result is False
```

**Improvements:**
- Clear separation: Arrange (setup), Act (execution), Assert (verification)
- Each section clearly demarcated
- Test intent is immediately obvious
- Easy to understand and maintain

### Explanation

The GOOD example follows the AAA pattern consistently. Arrange section sets up the test context, Act section performs the operation being tested, and Assert section verifies the outcome. This structure makes tests readable and focused.

## Example 4: Single Assertion per Test

### BAD Example: Multiple Assertions

```python
def test_user_profile_complete():
    user = User(name="Alice", email="alice@example.com")
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
    assert user.is_valid() is True
    assert user.created_at is not None
```

**Problems:**
- Multiple assertions make it unclear what's being tested
- Failure message doesn't indicate which assertion failed
- Test covers multiple behaviors
- Harder to pinpoint the root cause

### GOOD Example: Single Assertion per Test

```python
def test_user_has_correct_name():
    user = User(name="Alice", email="alice@example.com")
    assert user.name == "Alice"


def test_user_has_correct_email():
    user = User(name="Alice", email="alice@example.com")
    assert user.email == "alice@example.com"


def test_user_is_valid():
    user = User(name="Alice", email="alice@example.com")
    assert user.is_valid() is True


def test_user_has_creation_timestamp():
    user = User(name="Alice", email="alice@example.com")
    assert user.created_at is not None
```

**Improvements:**
- One assertion per test, clear focus
- Failure messages immediately indicate what's wrong
- Each test validates one specific behavior
- Tests are more granular and maintainable

### Explanation

The GOOD example demonstrates that tests should have a single responsibility. While this creates more test methods, each test is focused, fails fast with clear indication of what's wrong, and serves as living documentation for specific behaviors.

## Example 5: Testing Behavior, Not Implementation

### BAD Example: Testing Implementation Details

```python
def test_order_processing():
    order = Order(items=[Item("book", 10)])
    processor = OrderProcessor()
    processor._validate_order(order)
    processor._calculate_totals(order)
    processor._save_to_database(order)
    assert processor._db_connection.last_query == "INSERT INTO orders..."
```

**Problems:**
- Tests private methods (implementation)
- Coupled to database implementation
- Breaks when internal refactoring occurs
- Tests how, not what

### GOOD Example: Testing Behavior

```python
def test_order_processing_creates_order_record():
    order = Order(items=[Item("book", 10)])
    processor = OrderProcessor(fake_database)

    processor.process(order)

    assert fake_database.has_order_with_total(10)


def test_order_processing_calculates_correct_total():
    order = Order(items=[Item("book", 10), Item("pen", 5)])
    processor = OrderProcessor(fake_database)

    processor.process(order)

    assert fake_database.last_order_total == 15
```

**Improvements:**
- Tests public API behavior
- Not coupled to internal implementation
- Can refactor internals without breaking tests
- Tests what the system does, not how

### Explanation

The GOOD example focuses on testing the observable behavior of the system through its public interface. Tests remain stable even when internal implementation changes, enabling confident refactoring.

## Example 6: Triangulation

### BAD Example: Implementing General Solution Too Early

```python
def add(a, b):
    return a + b


def test_addition():
    assert add(2, 2) == 4
    assert add(5, 5) == 10
    assert add(-1, 1) == 0
```

**Problems:**
- Full implementation written immediately
- No incremental discovery of requirements
- Opportunity to over-engineer missed
- Tests don't drive design progression

### GOOD Example: Triangulation Approach

```python
def add(a, b):
    pass


def test_add_two_twos_returns_four():
    assert add(2, 2) == 4


def test_add_two_fives_returns_ten():
    assert add(5, 5) == 10


def test_add_negative_one_and_one_returns_zero():
    assert add(-1, 1) == 0
```

**Improvements:**
- Tests drive implementation incrementally
- Each test reveals more about the requirement
- Avoids over-generalization
- Implementation emerges from test cases

### Explanation

The GOOD example demonstrates triangulation: start with a hard-coded return value for the first test, then generalize as more tests reveal the pattern. This prevents over-engineering and ensures code only implements what's tested.

## Example 7: Given-When-Then (BDD Style)

### BAD Example: Imperative Test Description

```python
def test_discount():
    cart = ShoppingCart()
    cart.add_item(Item("book", 10))
    cart.add_item(Item("book", 10))
    cart.add_item(Item("book", 10))
    result = cart.calculate_total()
    assert result == 27
```

**Problems:**
- Test name doesn't describe the scenario
- No clear context or expected behavior
- Hard to understand business rules
- Not aligned with requirements

### GOOD Example: Given-When-Then Style

```python
def test_given_three_books_when_calculating_total_then_applies_10_percent_bulk_discount():
    cart = ShoppingCart()

    cart.add_items([Item("book", 10), Item("book", 10), Item("book", 10)])

    total = cart.calculate_total()

    assert total == 27


def test_given_two_different_books_when_calculating_total_then_no_bulk_discount_applied():
    cart = ShoppingCart()

    cart.add_items([Item("book", 10), Item("pen", 5)])

    total = cart.calculate_total()

    assert total == 15
```

**Improvements:**
- Test names clearly describe Given-When-Then
- Behavior expressed in business language
- Easy to map to requirements
- Tests serve as documentation

### Explanation

The GOOD example uses GWT naming conventions to make tests readable and aligned with business requirements. The test name tells a complete story about the scenario, making the code almost unnecessary to understand the behavior.

## Example 8: Test Isolation

### BAD Example: Tests Share State

```python
class TestUserService:
    user_service = UserService()

    def test_create_user(self):
        self.user_service.create_user("alice")
        assert self.user_service.count() == 1

    def test_count_users(self):
        self.user_service.create_user("bob")
        assert self.user_service.count() == 1
```

**Problems:**
- Tests share mutable state
- Order-dependent (test_count fails if run after test_create)
- Cannot run tests in parallel
- Flaky test behavior

### GOOD Example: Test Isolation with Fixtures

```python
@pytest.fixture
def user_service():
    return UserService()


def test_create_user(user_service):
    user_service.create_user("alice")
    assert user_service.count() == 1


def test_create_second_user(user_service):
    user_service.create_user("bob")
    assert user_service.count() == 1


def test_multiple_users_are_counted():
    user_service = UserService()
    user_service.create_user("alice")
    user_service.create_user("bob")
    assert user_service.count() == 2
```

**Improvements:**
- Each test has isolated state
- Tests can run in any order
- Tests can run in parallel
- Predictable, reliable results

### Explanation

The GOOD example uses pytest fixtures to ensure each test has its own isolated instance. Tests are independent and deterministic, making them reliable and maintainable.

## Example 9: Faking External Dependencies

### BAD Example: Over-Mocking

```python
def test_email_service():
    mock_smtp = MagicMock()
    mock_smtp.connect.return_value = True
    mock_smtp.sendmail.return_value = "250 OK"
    mock_smtp.quit.return_value = True

    service = EmailService(mock_smtp)
    service.send("user@example.com", "Hello")

    mock_smtp.connect.assert_called_once()
    mock_smtp.sendmail.assert_called_once_with(
        "user@example.com", "Hello"
    )
    mock_smtp.quit.assert_called_once()
```

**Problems:**
- Mocking implementation details
- Tests coupled to SMTP protocol
- Refactoring breaks tests
- Tests "how" not "what"

### GOOD Example: Using Test Doubles

```python
class FakeSMTP:
    def __init__(self):
        self.messages_sent = []

    def send_email(self, to, subject, body):
        self.messages_sent.append((to, subject, body))
        return True


def test_email_service_sends_message():
    fake_smtp = FakeSMTP()
    service = EmailService(fake_smtp)

    service.send("user@example.com", "Hello", "Body")

    assert len(fake_smtp.messages_sent) == 1
    assert fake_smtp.messages_sent[0][0] == "user@example.com"
```

**Improvements:**
- Simple fake, not complex mock
- Tests behavior, not implementation
- Easy to understand and maintain
- Enables safe refactoring

### Explanation

The GOOD example uses a simple fake instead of complex mocking. Tests verify the observable behavior (messages were sent) rather than implementation details (which methods were called). This follows Kent Beck's advice to minimize mocking.

## Example 10: Refactoring While Green

### BAD Example: Refactoring Without Tests

```python
def process_data(data):
    results = []
    for item in data:
        if item > 0:
            results.append(item * 2)
        else:
            results.append(0)
    return results
```

**Problems:**
- No safety net for refactoring
- Fear of breaking functionality
- Hard to verify refactoring is correct
- Manual testing required

### GOOD Example: Refactor While Tests Are Green

```python
def test_process_data_positive_numbers():
    assert process_data([1, 2, 3]) == [2, 4, 6]


def test_process_data_negative_numbers():
    assert process_data([-1, -2, -3]) == [0, 0, 0]


def test_process_data_mixed_numbers():
    assert process_data([1, -1, 2, -2]) == [2, 0, 4, 0]


def test_process_data_empty_list():
    assert process_data([]) == []


def process_data(data):
    return [item * 2 if item > 0 else 0 for item in data]
```

**Improvements:**
- Tests provide safety net
- Refactoring is confident
- List comprehension improves readability
- Tests verify behavior unchanged

### Explanation

The GOOD example demonstrates refactoring in the green phase. With all tests passing, we can safely refactor the implementation to be more concise (using list comprehension) while maintaining the exact same behavior. Tests confirm no regressions.

## Python-Specific Notes

### Idioms and Patterns

- **Pytest fixtures**: Use `@pytest.fixture` for setup/teardown instead of setUp/tearDown methods
- **Context managers**: Use `with pytest.raises()` for exception testing
- **Parametrize**: Use `@pytest.mark.parametrize` for data-driven tests
- **Monkeypatch**: Use `monkeypatch` fixture for safe patching instead of unittest.mock decorators
- **Conftest.py**: Place shared fixtures in conftest.py for automatic discovery

### Language Features

**Features that help:**
- **Decorators**: `@pytest.mark` for organizing and selecting tests
- **Context managers**: Clean resource management in tests
- **List comprehensions**: Concise test data generation
- **Type hints**: Improved IDE support and test documentation
- **Assertions**: Built-in assertion introspection

**Features that hinder:**
- **Dynamic typing**: May hide type-related bugs not caught by tests
- **Metaclasses**: Can make testing complex classes difficult
- **Magic methods**: May require special test setup
- **Global state**: Requires careful test isolation

### Framework Considerations

- **Pytest**: Preferred framework for its concise syntax, fixtures, and powerful plugins
- **Unittest**: Built-in alternative, more verbose but standard library
- **Hypothesis**: Property-based testing for finding edge cases
- **Pytest-cov**: Coverage measurement to ensure comprehensive testing
- **Pytest-mock**: Enhanced mocking utilities built on unittest.mock

### Common Pitfalls

1. **Testing private methods**: Use underscore prefix or test through public API
2. **Overusing mock.patch**: Prefer fakes or real implementations when possible
3. **Testing implementation details**: Focus on observable behavior
4. **Ignoring test isolation**: Each test should be independent
5. **Writing tests after code**: Follow TDD's red-green-refactor cycle
6. **Multiple assertions per test**: One assertion per test for clarity
7. **Hard-coded test data**: Use fixtures and parametrize for maintainability
8. **Testing external services**: Use test doubles and fakes
