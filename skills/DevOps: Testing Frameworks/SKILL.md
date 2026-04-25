---
name: DevOps: Testing Frameworks
description: |
  Testing frameworks reference by language.
  Use when: Writing tests, setting up testing infrastructure, choosing frameworks, mocking external dependencies.
  
  Covers: Python (pytest, unittest), JavaScript/TypeScript (Jest, Mocha + Chai), Go (testing, testify), Java (JUnit 5), Rust (built-in test framework)
  
  Includes: Framework selection, commands, fixtures, parametrization, mocking, assertions, test patterns, and best practices.
---

# Testing Frameworks Reference

Comprehensive reference for testing frameworks across multiple programming languages. Use this skill when writing tests, setting up testing infrastructure, or choosing the right testing framework for your project.

---

## Quick Reference

| Language | Primary Framework | Mock Library | Test Runner | Coverage Tool |
|----------|------------------|--------------|-------------|---------------|
| Python | pytest | unittest.mock, pytest-mock | pytest | pytest-cov |
| JavaScript/TypeScript | Jest | jest.mock | Jest | built-in |
| JavaScript/TypeScript | Mocha + Chai | Sinon | Mocha | nyc/istanbul |
| Go | testing | testify/mock | go test | built-in |
| Java | JUnit 5 | Mockito | Maven/Gradle | JaCoCo |
| Rust | built-in | mockall | cargo test | tarpaulin |

---

## Python Testing

### pytest (Recommended)

**Installation:**
```bash
pip install pytest pytest-asyncio pytest-mock hypothesis pytest-cov
```

**Test Discovery:**
- Files: `test_*.py` or `*_test.py`
- Directories: `tests/` by convention
- Functions: Functions starting with `test_`
- Classes: Classes starting with `Test` with methods starting with `test_`

**Basic Commands:**
```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_module.py

# Run specific test function
pytest tests/test_module.py::test_function_name

# Run tests matching pattern
pytest tests/ -k "pattern"

# Run with coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run only failed tests from last run
pytest tests/ --lf

# Stop on first failure
pytest tests/ -x

# Run in parallel
pytest tests/ -n auto
```

**Test Structure (AAA Pattern):**
```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from myapp.services import UserService
from myapp.models import User

class TestUserService:
    """Test suite for UserService"""
    
    @pytest.fixture
    def user_service(self):
        """Create UserService instance for testing"""
        mock_db = Mock()
        return UserService(mock_db)
    
    @pytest.fixture
    def sample_user(self):
        """Create sample user data"""
        return User(id=1, name="John Doe", email="john@example.com")
    
    def test_should_create_user_with_valid_data(self, user_service, sample_user):
        """Test happy path - user creation with valid data"""
        # Arrange
        user_data = {"name": "John Doe", "email": "john@example.com"}
        user_service.repository.find_by_email.return_value = None
        
        # Act
        result = user_service.create_user(user_data)
        
        # Assert
        assert result is not None
        assert result.name == "John Doe"
        assert result.email == "john@example.com"
        user_service.repository.save.assert_called_once()
    
    def test_should_raise_error_with_duplicate_email(self, user_service, sample_user):
        """Test error handling - duplicate email"""
        # Arrange
        user_data = {"name": "John Doe", "email": "john@example.com"}
        user_service.repository.find_by_email.return_value = sample_user
        
        # Act & Assert
        with pytest.raises(ValueError, match="Email already exists"):
            user_service.create_user(user_data)
    
    def test_should_return_none_when_user_not_found(self, user_service):
        """Test edge case - user not found"""
        # Arrange
        user_service.repository.find_by_id.return_value = None
        
        # Act
        result = user_service.get_user(999)
        
        # Assert
        assert result is None
    
    @pytest.mark.parametrize("email,expected_valid", [
        ("user@example.com", True),
        ("invalid-email", False),
        ("", False),
        (None, False),
        ("user@", False),
        ("@example.com", False),
    ])
    def test_should_validate_email_correctly(self, user_service, email, expected_valid):
        """Test email validation with multiple inputs"""
        # Act
        is_valid = user_service.validate_email(email)
        
        # Assert
        assert is_valid == expected_valid
    
    @pytest.mark.parametrize("age", [0, 1, 17, 18, 65, 100, 150])
    def test_should_handle_boundary_ages(self, user_service, age):
        """Test age boundaries"""
        # Act
        result = user_service.can_vote(age)
        
        # Assert
        if age >= 18:
            assert result is True
        else:
            assert result is False
    
    @pytest.mark.asyncio
    async def test_async_function(self, user_service):
        """Test async function"""
        # Arrange
        user_service.repository.async_get = AsyncMock(return_value={"id": 1})
        
        # Act
        result = await user_service.async_operation()
        
        # Assert
        assert result is not None
    
    @patch('myapp.services.external_api')
    def test_with_patch_decorator(self, mock_api, user_service):
        """Test with patch decorator"""
        # Arrange
        mock_api.get_user.return_value = {"id": 1, "name": "Test"}
        
        # Act
        result = user_service.fetch_from_external_api(1)
        
        # Assert
        mock_api.get_user.assert_called_once_with(1)
        assert result.name == "Test"
    
    def test_with_context_manager_patch(self, user_service):
        """Test with context manager patch"""
        with patch('myapp.services.database') as mock_db:
            # Arrange
            mock_db.query.return_value = [{"id": 1}]
            
            # Act
            result = user_service.query_users()
            
            # Assert
            assert len(result) == 1
```

**Fixtures:**
```python
import pytest

@pytest.fixture
def setup_database():
    """Setup and teardown database"""
    # Setup
    db = Database(":memory:")
    db.create_tables()
    yield db
    # Teardown
    db.close()

@pytest.fixture(scope="module")
def module_fixture():
    """Run once per module"""
    return expensive_setup()

@pytest.fixture(scope="session")
def session_fixture():
    """Run once per test session"""
    return very_expensive_setup()

@pytest.fixture(params=["value1", "value2"])
def parametrized_fixture(request):
    """Run test multiple times with different values"""
    return request.param

# Using fixtures
def test_with_fixtures(setup_database, parametrized_fixture):
    assert setup_database is not None
    assert parametrized_fixture in ["value1", "value2"]
```

**Mocking with pytest-mock:**
```python
def test_with_mocker(mocker):
    """Test using pytest-mock (mocker fixture)"""
    # Mock a function
    mock_function = mocker.patch('module.function_name')
    mock_function.return_value = "mocked"
    
    # Mock a class
    mock_class = mocker.patch('module.ClassName')
    mock_class.return_value.method.return_value = "result"
    
    # Spy on a function (calls real function but allows assertions)
    spy = mocker.spy(module, 'function_name')
    
    # Mock object attribute
    mocker.patch.object(obj, 'attribute', 'new_value')
```

**Property-Based Testing with Hypothesis:**
```python
from hypothesis import given, strategies as st

@given(st.integers(), st.integers())
def test_addition_commutative(x, y):
    """Test that addition is commutative"""
    assert x + y == y + x

@given(st.lists(st.integers()))
def test_reversing_twice_returns_original(lst):
    """Test that reversing twice returns original list"""
    assert list(reversed(list(reversed(lst)))) == lst

@given(st.text())
def test_string_length(s):
    """Test string length property"""
    assert len(s) >= 0
```

### unittest (Standard Library)

**Basic Usage:**
```python
import unittest
from unittest.mock import Mock, patch
from myapp.services import UserService

class TestUserService(unittest.TestCase):
    def setUp(self):
        """Run before each test"""
        self.service = UserService(Mock())
    
    def tearDown(self):
        """Run after each test"""
        pass
    
    def test_create_user(self):
        """Test user creation"""
        user_data = {"name": "John", "email": "john@example.com"}
        result = self.service.create_user(user_data)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "John")
    
    def test_raises_error_with_invalid_data(self):
        """Test error handling"""
        with self.assertRaises(ValueError):
            self.service.create_user(None)
    
    @patch('myapp.services.external_api')
    def test_with_patch(self, mock_api):
        """Test with mocking"""
        mock_api.get_user.return_value = {"id": 1}
        result = self.service.fetch_user(1)
        self.assertEqual(result.id, 1)

if __name__ == '__main__':
    unittest.main()
```

**Test Discovery:**
```bash
# Discover and run tests
python -m unittest discover tests/

# Run specific test module
python -m unittest tests.test_module

# Run specific test class
python -m unittest tests.test_module.TestClassName

# Run specific test method
python -m unittest tests.test_module.TestClassName.test_method
```

### Testcontainers (Python Integration Testing)

**Installation:**
```bash
pip install testcontainers pytest
# Database-specific drivers
pip install psycopg2-binary  # PostgreSQL
pip install pymysql          # MySQL
pip install redis            # Redis
```

**Why Testcontainers for Python?**
- Real database instances for integration tests
- No need for in-memory SQLite with different behavior
- Consistent test environment across CI/CD and local development

**1. PostgreSQL Example:**
```python
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="module")
def postgres_container():
    """Start PostgreSQL container for the test module"""
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres

@pytest.fixture
def db_session(postgres_container):
    """Create database session for each test"""
    engine = create_engine(postgres_container.get_connection_url())
    
    # Create schema
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL
            )
        """))
        conn.commit()
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Cleanup
    session.close()
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        conn.commit()

def test_create_user(db_session):
    """Test user creation with real PostgreSQL"""
    # Arrange
    result = db_session.execute(
        text("INSERT INTO users (name, email) VALUES (:name, :email) RETURNING id"),
        {"name": "John Doe", "email": "john@example.com"}
    )
    user_id = result.scalar()
    db_session.commit()
    
    # Act
    result = db_session.execute(
        text("SELECT * FROM users WHERE id = :id"),
        {"id": user_id}
    )
    user = result.fetchone()
    
    # Assert
    assert user is not None
    assert user.name == "John Doe"
    assert user.email == "john@example.com"

def test_unique_email_constraint(db_session):
    """Test unique constraint on email"""
    # Insert first user
    db_session.execute(
        text("INSERT INTO users (name, email) VALUES (:name, :email)"),
        {"name": "John", "email": "john@example.com"}
    )
    db_session.commit()
    
    # Try to insert duplicate - should fail
    with pytest.raises(Exception):  # IntegrityError
        db_session.execute(
            text("INSERT INTO users (name, email) VALUES (:name, :email)"),
            {"name": "Jane", "email": "john@example.com"}
        )
        db_session.commit()
```

**2. Redis Example:**
```python
import pytest
from testcontainers.redis import RedisContainer
import redis as redis_lib

@pytest.fixture(scope="module")
def redis_container():
    """Start Redis container for the test module"""
    with RedisContainer("redis:7-alpine") as redis:
        yield redis

@pytest.fixture
def redis_client(redis_container):
    """Create Redis client for each test"""
    client = redis_lib.Redis(
        host=redis_container.get_container_host_ip(),
        port=redis_container.get_exposed_port(6379),
        decode_responses=True
    )
    yield client
    client.flushall()  # Cleanup after test

def test_cache_operations(redis_client):
    """Test caching with real Redis"""
    # Set value
    redis_client.set("user:1", "John Doe")
    
    # Get value
    result = redis_client.get("user:1")
    assert result == "John Doe"
    
    # Check expiration
    redis_client.setex("temp:key", 1, "value")
    assert redis_client.get("temp:key") == "value"

def test_hash_operations(redis_client):
    """Test Redis hash operations"""
    redis_client.hset("user:123", mapping={
        "name": "John",
        "email": "john@example.com"
    })
    
    result = redis_client.hgetall("user:123")
    assert result["name"] == "John"
    assert result["email"] == "john@example.com"
```

**3. MySQL Example:**
```python
import pytest
from testcontainers.mysql import MySqlContainer

@pytest.fixture(scope="module")
def mysql_container():
    """Start MySQL container for the test module"""
    with MySqlContainer("mysql:8.0") as mysql:
        yield mysql

def test_mysql_connection(mysql_container):
    """Test MySQL connection and basic operations"""
    import pymysql
    
    connection = pymysql.connect(
        host=mysql_container.get_container_host_ip(),
        port=mysql_container.get_exposed_port(3306),
        user=mysql_container.username,
        password=mysql_container.password,
        database=mysql_container.dbname
    )
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result == (1,)
    finally:
        connection.close()
```

**4. Generic Container Example:**
```python
import pytest
from testcontainers.core.generic import GenericContainer

@pytest.fixture(scope="module")
def custom_container():
    """Start a custom container"""
    container = GenericContainer("nginx:alpine")
    container.with_exposed_ports(80)
    container.start()
    yield container
    container.stop()

def test_custom_container(custom_container):
    """Test interaction with custom container"""
    import requests
    
    host = custom_container.get_container_host_ip()
    port = custom_container.get_exposed_port(80)
    
    response = requests.get(f"http://{host}:{port}/")
    assert response.status_code == 200
```

**Testcontainers Python Tips:**
- ✅ Use `scope="module"` to reuse containers across tests (faster)
- ✅ Use `scope="function"` for isolated tests (slower but cleaner)
- ✅ Clean up data between tests (TRUNCATE, FLUSHALL)
- ✅ Use alpine images for smaller container sizes
- ✅ Use context managers (`with`) for automatic cleanup
- ❌ Don't hardcode container ports
- ❌ Don't forget to close connections in teardown

---

## JavaScript/TypeScript Testing

### Jest (Recommended)

**Installation:**
```bash
npm install --save-dev jest @types/jest ts-jest
# For React testing
npm install --save-dev @testing-library/react @testing-library/jest-dom
# For mocking
npm install --save-dev msw
```

**Configuration (`jest.config.js`):**
```javascript
module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/tests'],
  testMatch: ['**/__tests__/**/*.ts', '**/*.test.ts'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/**/index.ts'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1'
  }
};
```

**Basic Commands:**
```bash
# Run all tests
npm test

# Run in watch mode
npm test -- --watch

# Run with coverage
npm test -- --coverage

# Run specific test file
npm test -- path/to/test.test.ts

# Run tests matching pattern
npm test -- -t "pattern"

# Update snapshots
npm test -- -u

# Run tests in parallel
npm test -- --maxWorkers=4
```

**Test Structure (AAA Pattern):**
```typescript
import { UserService } from './user-service';
import { UserRepository } from './user-repository';

describe('UserService', () => {
  let userService: UserService;
  let mockRepository: jest.Mocked<UserRepository>;

  beforeEach(() => {
    // Create mock repository
    mockRepository = {
      findById: jest.fn(),
      save: jest.fn(),
      delete: jest.fn(),
      findAll: jest.fn()
    } as any;

    userService = new UserService(mockRepository);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createUser', () => {
    it('should create user with valid data', async () => {
      // Arrange
      const userData = { name: 'John Doe', email: 'john@example.com' };
      const expectedUser = { id: '1', ...userData };
      mockRepository.findById.mockResolvedValue(null);
      mockRepository.save.mockResolvedValue(expectedUser);

      // Act
      const result = await userService.createUser(userData);

      // Assert
      expect(result).toEqual(expectedUser);
      expect(mockRepository.save).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'John Doe',
          email: 'john@example.com'
        })
      );
      expect(mockRepository.save).toHaveBeenCalledTimes(1);
    });

    it('should throw error when email already exists', async () => {
      // Arrange
      const userData = { name: 'John Doe', email: 'john@example.com' };
      mockRepository.findById.mockResolvedValue({ id: '1', ...userData });

      // Act & Assert
      await expect(userService.createUser(userData))
        .rejects.toThrow('Email already exists');
      
      expect(mockRepository.save).not.toHaveBeenCalled();
    });
  });

  describe('getUser', () => {
    it('should return user when found', async () => {
      // Arrange
      const userId = '1';
      const expectedUser = { id: userId, name: 'John', email: 'john@example.com' };
      mockRepository.findById.mockResolvedValue(expectedUser);

      // Act
      const result = await userService.getUser(userId);

      // Assert
      expect(result).toEqual(expectedUser);
    });

    it('should return null when user not found', async () => {
      // Arrange
      mockRepository.findById.mockResolvedValue(null);

      // Act
      const result = await userService.getUser('999');

      // Assert
      expect(result).toBeNull();
    });
  });
});
```

**Parametrized Tests:**
```typescript
describe('email validation', () => {
  const testCases = [
    { email: 'user@example.com', expected: true },
    { email: 'invalid-email', expected: false },
    { email: '', expected: false },
    { email: 'user@', expected: false },
    { email: '@example.com', expected: false },
  ];

  test.each(testCases)('should validate $email as $expected', ({ email, expected }) => {
    const result = isValidEmail(email);
    expect(result).toBe(expected);
  });
});

// Alternative syntax
describe('age validation', () => {
  it.each([
    [0, false],
    [17, false],
    [18, true],
    [65, true],
    [150, false],
  ])('should validate age %i as %p', (age, expected) => {
    expect(canVote(age)).toBe(expected);
  });
});
```

**Mocking:**
```typescript
// Mock entire module
jest.mock('./external-api');
import { externalApi } from './external-api';

const mockExternalApi = externalApi as jest.Mocked<typeof externalApi>;

// Setup mock
mockExternalApi.fetchUser.mockResolvedValue({ id: '1', name: 'John' });

// Assert mock was called
expect(mockExternalApi.fetchUser).toHaveBeenCalledWith('1');
expect(mockExternalApi.fetchUser).toHaveBeenCalledTimes(1);

// Mock implementation
mockExternalApi.fetchUser.mockImplementation(async (id: string) => {
  return { id, name: 'Mock User' };
});

// Mock return value
mockExternalApi.fetchUser.mockReturnValue({ id: '1', name: 'John' });

// Mock once
mockExternalApi.fetchUser.mockResolvedValueOnce({ id: '1', name: 'First' });
mockExternalApi.fetchUser.mockResolvedValueOnce({ id: '2', name: 'Second' });

// Clear mocks
mockExternalApi.fetchUser.mockClear();
jest.clearAllMocks();

// Spy on method
const spy = jest.spyOn(userService, 'privateMethod');
spy.mockReturnValue('mocked value');
spy.mockRestore();
```

**Snapshot Testing:**
```typescript
import { render } from '@testing-library/react';
import { UserProfile } from './UserProfile';

describe('UserProfile', () => {
  it('should match snapshot', () => {
    const { container } = render(<UserProfile name="John" email="john@example.com" />);
    expect(container).toMatchSnapshot();
  });

  it('should match inline snapshot', () => {
    const user = { id: '1', name: 'John' };
    expect(user).toMatchInlineSnapshot(`
      {
        "id": "1",
        "name": "John"
      }
    `);
  });
});
```

**Testing Async Code:**
```typescript
describe('async operations', () => {
  it('should handle promises', async () => {
    const result = await fetchData();
    expect(result).toBeDefined();
  });

  it('should handle rejected promises', async () => {
    await expect(fetchFailingData()).rejects.toThrow('Network error');
  });

  it('should handle callbacks', (done) => {
    fetchDataCallback((result) => {
      expect(result).toBeDefined();
      done();
    });
  });

  it('should handle timeouts', async () => {
    await expect(
      fetchDataWithTimeout(1000)
    ).resolves.toBeDefined();
  }, 2000); // Set test timeout to 2 seconds
});
```

**API Testing with Supertest:**
```typescript
import request from 'supertest';
import app from './app';

describe('Users API', () => {
  describe('GET /api/users', () => {
    it('should return list of users', async () => {
      const response = await request(app)
        .get('/api/users')
        .set('Authorization', `Bearer ${token}`)
        .expect(200);
      
      expect(response.body).toHaveProperty('users');
      expect(response.body.users).toBeInstanceOf(Array);
      expect(response.body.users.length).toBeGreaterThan(0);
    });

    it('should return 401 without auth token', async () => {
      await request(app)
        .get('/api/users')
        .expect(401);
    });
  });

  describe('POST /api/users', () => {
    it('should create user with valid data', async () => {
      const response = await request(app)
        .post('/api/users')
        .send({ name: 'John', email: 'john@example.com' })
        .set('Authorization', `Bearer ${token}`)
        .expect(201);
      
      expect(response.body).toHaveProperty('id');
      expect(response.body.name).toBe('John');
    });
  });
});
```

### Mocha + Chai

**Installation:**
```bash
npm install --save-dev mocha chai @types/mocha @types/chai
npm install --save-dev sinon @types/sinon
```

**Basic Usage:**
```typescript
import { expect } from 'chai';
import { stub, spy } from 'sinon';
import { UserService } from './user-service';

describe('UserService', () => {
  let userService: UserService;

  beforeEach(() => {
    userService = new UserService();
  });

  afterEach(() => {
    // Cleanup
  });

  describe('createUser', () => {
    it('should create user with valid data', () => {
      const userData = { name: 'John', email: 'john@example.com' };
      const result = userService.createUser(userData);
      
      expect(result).to.be.an('object');
      expect(result.name).to.equal('John');
      expect(result.email).to.equal('john@example.com');
    });

    it('should throw error with invalid data', () => {
      expect(() => userService.createUser(null)).to.throw('Invalid data');
    });
  });
});
```

**Chai Assertions:**
```typescript
// Equality
expect(result).to.equal(expected);
expect(result).to.deep.equal({ id: 1, name: 'John' });

// Type checks
expect(result).to.be.an('object');
expect(result).to.be.an('array');
expect(result).to.be.a('string');
expect(result).to.be.a('number');

// Boolean
expect(result).to.be.true;
expect(result).to.be.false;
expect(result).to.exist;
expect(result).to.not.exist;

// Array/Collection
expect(array).to.have.lengthOf(3);
expect(array).to.include(2);
expect(array).to.have.members([1, 2, 3]);

// Object
expect(obj).to.have.property('name');
expect(obj).to.have.property('name', 'John');
expect(obj).to.have.all.keys('id', 'name', 'email');

// Throws
expect(() => fn()).to.throw('Error message');
expect(() => fn()).to.throw(Error);
```

**Sinon Mocking:**
```typescript
import { stub, mock, spy } from 'sinon';

describe('with mocking', () => {
  it('should stub method', () => {
    const stubbedMethod = stub(userService, 'getUser');
    stubbedMethod.returns({ id: '1', name: 'Mock' });
    
    const result = userService.getUser('1');
    
    expect(result.name).to.equal('Mock');
    expect(stubbedMethod.calledOnce).to.be.true;
    
    stubbedMethod.restore();
  });

  it('should spy on method', () => {
    const spiedMethod = spy(userService, 'createUser');
    
    userService.createUser({ name: 'John' });
    
    expect(spiedMethod.calledOnce).to.be.true;
    expect(spiedMethod.calledWith({ name: 'John' })).to.be.true;
    
    spiedMethod.restore();
  });
});
```

---

## Go Testing

### testing Package (Standard Library)

**Test Discovery:**
- Files: `*_test.go` in the same package
- Functions: Functions with signature `func TestXxx(t *testing.T)`

**Basic Commands:**
```bash
# Run all tests in current directory
go test

# Run tests with verbose output
go test -v

# Run tests in all packages
go test ./...

# Run specific test
go test -run TestFunctionName

# Run tests matching pattern
go test -run "TestPattern"

# Run with coverage
go test -cover

# Generate coverage report
go test -coverprofile=coverage.out
go tool cover -html=coverage.out

# Run benchmarks
go test -bench=.

# Run specific benchmark
go test -bench=BenchmarkFunctionName

# Run with race detection
go test -race
```

**Test Structure (Table-Driven Tests):**
```go
package mypackage_test

import (
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestAdd(t *testing.T) {
    tests := []struct {
        name     string
        a        int
        b        int
        expected int
    }{
        {"positive numbers", 2, 3, 5},
        {"negative numbers", -1, -1, -2},
        {"zero", 0, 0, 0},
        {"mixed signs", -5, 3, -2},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            result := Add(tt.a, tt.b)
            assert.Equal(t, tt.expected, result)
        })
    }
}

func TestUserService_CreateUser(t *testing.T) {
    tests := []struct {
        name        string
        userData    User
        expectError bool
        errorMsg    string
    }{
        {
            name:     "valid user",
            userData: User{Name: "John", Email: "john@example.com"},
            expectError: false,
        },
        {
            name:     "missing name",
            userData: User{Email: "john@example.com"},
            expectError: true,
            errorMsg: "name is required",
        },
        {
            name:     "missing email",
            userData: User{Name: "John"},
            expectError: true,
            errorMsg: "email is required",
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            service := NewUserService()
            
            result, err := service.CreateUser(tt.userData)
            
            if tt.expectError {
                require.Error(t, err)
                assert.Contains(t, err.Error(), tt.errorMsg)
                assert.Nil(t, result)
            } else {
                require.NoError(t, err)
                assert.NotNil(t, result)
                assert.Equal(t, tt.userData.Name, result.Name)
            }
        })
    }
}
```

**Subtests and Setup/Teardown:**
```go
func TestMain(m *testing.M) {
    // Setup before all tests
    code := m.Run()
    // Teardown after all tests
    os.Exit(code)
}

func TestWithSetup(t *testing.T) {
    // Setup
    db := setupTestDatabase()
    defer db.Close() // Teardown
    
    t.Run("test case 1", func(t *testing.T) {
        // Test logic
    })
    
    t.Run("test case 2", func(t *testing.T) {
        // Test logic
    })
}

func setupTestDatabase() *Database {
    db := NewDatabase(":memory:")
    db.CreateTables()
    return db
}
```

### testify (Recommended)

**Installation:**
```bash
go get github.com/stretchr/testify
```

**Assertions:**
```go
import (
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestWithAssert(t *testing.T) {
    // Assert (continues on failure)
    assert.Equal(t, 200, statusCode)
    assert.NotNil(t, result)
    assert.Contains(t, result.Name, "John")
    
    // Require (stops on failure)
    require.NoError(t, err)
    require.NotNil(t, result)
    
    // Various assertions
    assert.True(t, isValid)
    assert.False(t, isInvalid)
    assert.Len(t, items, 3)
    assert.Empty(t, items)
    assert.NotNil(t, obj)
    assert.Nil(t, err)
    assert.Equal(t, expected, actual)
    assert.NotEqual(t, unexpected, actual)
    assert.Contains(t, string, substring)
    assert.Greater(t, a, b)
    assert.Less(t, a, b)
    assert.InDelta(t, 3.14, result, 0.01)
    assert.Implements(t, (*Interface)(nil), obj)
}
```

**Mocking with testify/mock:**
```go
import (
    "testing"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/assert"
)

type MockRepository struct {
    mock.Mock
}

func (m *MockRepository) FindById(id string) (*User, error) {
    args := m.Called(id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*User), args.Error(1)
}

func (m *MockRepository) Save(user *User) error {
    args := m.Called(user)
    return args.Error(0)
}

func TestUserService_GetUser(t *testing.T) {
    mockRepo := new(MockRepository)
    service := NewUserService(mockRepo)
    
    // Setup mock
    expectedUser := &User{ID: "1", Name: "John"}
    mockRepo.On("FindById", "1").Return(expectedUser, nil)
    
    // Test
    result, err := service.GetUser("1")
    
    // Assert
    assert.NoError(t, err)
    assert.Equal(t, expectedUser, result)
    mockRepo.AssertExpectations(t)
}

func TestUserService_CreateUser_Error(t *testing.T) {
    mockRepo := new(MockRepository)
    service := NewUserService(mockRepo)
    
    // Setup mock
    mockRepo.On("Save", mock.AnythingOfType("*User")).
        Return(errors.New("database error"))
    
    // Test
    result, err := service.CreateUser(&User{Name: "John"})
    
    // Assert
    assert.Error(t, err)
    assert.Nil(t, result)
    mockRepo.AssertExpectations(t)
}
```

**Test Suites:**
```go
import (
    "github.com/stretchr/testify/suite"
    "testing"
)

type UserServiceTestSuite struct {
    suite.Suite
    service *UserService
    mockRepo *MockRepository
}

func (suite *UserServiceTestSuite) SetupTest() {
    // Run before each test
    suite.mockRepo = new(MockRepository)
    suite.service = NewUserService(suite.mockRepo)
}

func (suite *UserServiceTestSuite) TearDownTest() {
    // Run after each test
}

func (suite *UserServiceTestSuite) TestCreateUser() {
    user := &User{Name: "John"}
    suite.mockRepo.On("Save", user).Return(nil)
    
    result, err := suite.service.CreateUser(user)
    
    suite.NoError(err)
    suite.NotNil(result)
    suite.mockRepo.AssertExpectations(suite.T())
}

func TestUserServiceTestSuite(t *testing.T) {
    suite.Run(t, new(UserServiceTestSuite))
}
```

**Benchmarks:**
```go
func BenchmarkAdd(b *testing.B) {
    for i := 0; i < b.N; i++ {
        Add(2, 3)
    }
}

func BenchmarkUserService_GetUser(b *testing.B) {
    service := NewUserService()
    b.ResetTimer() // Reset timer after setup
    
    for i := 0; i < b.N; i++ {
        service.GetUser("1")
    }
}
```

**Fuzzing (Go 1.18+):**
```go
func FuzzAdd(f *testing.F) {
    // Add seed corpus
    f.Add(2, 3)
    f.Add(-1, 5)
    
    f.Fuzz(func(t *testing.T, a int, b int) {
        result := Add(a, b)
        // Property: addition should be commutative
        assert.Equal(t, Add(b, a), result)
        // Property: adding zero should return same value
        assert.Equal(t, Add(a, 0), a)
    })
}
```

---

## Java Testing

### JUnit 5

**Installation (Maven):**
```xml
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>5.9.2</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-core</artifactId>
    <version>5.3.1</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.assertj</groupId>
    <artifactId>assertj-core</artifactId>
    <version>3.24.2</version>
    <scope>test</scope>
</dependency>
```

**Basic Commands:**
```bash
# Run all tests with Maven
mvn test

# Run specific test class
mvn test -Dtest=UserServiceTest

# Run specific test method
mvn test -Dtest=UserServiceTest#testCreateUser

# Run with coverage (JaCoCo)
mvn test jacoco:report
```

**Test Structure:**
```java
import org.junit.jupiter.api.*;
import org.mockito.*;
import static org.mockito.Mockito.*;
import static org.assertj.core.api.Assertions.*;

@DisplayName("UserService Tests")
class UserServiceTest {
    
    @Mock
    private UserRepository userRepository;
    
    @InjectMocks
    private UserService userService;
    
    private AutoCloseable closeable;
    
    @BeforeEach
    void setUp() {
        closeable = MockitoAnnotations.openMocks(this);
    }
    
    @AfterEach
    void tearDown() throws Exception {
        closeable.close();
    }
    
    @Test
    @DisplayName("Should create user with valid data")
    void shouldCreateUserWithValidData() {
        // Arrange
        User user = new User("John", "john@example.com");
        when(userRepository.save(any(User.class))).thenReturn(user);
        
        // Act
        User result = userService.createUser(user);
        
        // Assert
        assertThat(result).isNotNull();
        assertThat(result.getName()).isEqualTo("John");
        assertThat(result.getEmail()).isEqualTo("john@example.com");
        
        verify(userRepository, times(1)).save(user);
    }
    
    @Test
    @DisplayName("Should throw exception with invalid data")
    void shouldThrowExceptionWithInvalidData() {
        // Arrange
        User invalidUser = new User(null, "invalid-email");
        
        // Act & Assert
        assertThatThrownBy(() -> userService.createUser(invalidUser))
            .isInstanceOf(ValidationException.class)
            .hasMessageContaining("Invalid email");
        
        verify(userRepository, never()).save(any());
    }
    
    @Test
    @DisplayName("Should return user when found")
    void shouldReturnUserWhenFound() {
        // Arrange
        String userId = "1";
        User expectedUser = new User("John", "john@example.com");
        when(userRepository.findById(userId)).thenReturn(Optional.of(expectedUser));
        
        // Act
        Optional<User> result = userService.getUser(userId);
        
        // Assert
        assertThat(result).isPresent();
        assertThat(result.get()).isEqualTo(expectedUser);
    }
    
    @Test
    @DisplayName("Should return empty when user not found")
    void shouldReturnEmptyWhenUserNotFound() {
        // Arrange
        when(userRepository.findById("999")).thenReturn(Optional.empty());
        
        // Act
        Optional<User> result = userService.getUser("999");
        
        // Assert
        assertThat(result).isEmpty();
    }
    
    @Nested
    @DisplayName("Email Validation")
    class EmailValidation {
        
        @ParameterizedTest
        @ValueSource(strings = {"user@example.com", "test@test.org", "john.doe@company.co.uk"})
        @DisplayName("Should accept valid emails")
        void shouldAcceptValidEmails(String email) {
            boolean isValid = userService.isValidEmail(email);
            assertThat(isValid).isTrue();
        }
        
        @ParameterizedTest
        @ValueSource(strings = {"invalid", "@example.com", "user@", ""})
        @DisplayName("Should reject invalid emails")
        void shouldRejectInvalidEmails(String email) {
            boolean isValid = userService.isValidEmail(email);
            assertThat(isValid).isFalse();
        }
    }
    
    @Test
    @Disabled("Temporarily disabled")
    void disabledTest() {
        // This test will be skipped
    }
}
```

**Parameterized Tests:**
```java
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.*;

@ParameterizedTest
@ValueSource(ints = {0, 1, 2, 3, 10})
void testWithIntValues(int value) {
    assertThat(value).isGreaterThanOrEqualTo(0);
}

@ParameterizedTest
@CsvSource({
    "1, One",
    "2, Two",
    "3, Three"
})
void testWithCsvSource(int id, String name) {
    assertThat(id).isPositive();
    assertThat(name).isNotEmpty();
}

@ParameterizedTest
@MethodSource("provideUserTestData")
void testWithMethodSource(String name, String email, boolean expected) {
    boolean isValid = userService.validateUser(name, email);
    assertThat(isValid).isEqualTo(expected);
}

static Stream<Arguments> provideUserTestData() {
    return Stream.of(
        Arguments.of("John", "john@example.com", true),
        Arguments.of("", "john@example.com", false),
        Arguments.of("John", "", false)
    );
}
```

**Mocking with Mockito (Deep Dive):**

**Basic Mocking:**
```java
import static org.mockito.Mockito.*;

@Mock
UserRepository mockRepository;

@InjectMocks
UserService userService;

@Test
void testWithMock() {
    // Setup mock
    User user = new User("1", "John");
    when(mockRepository.findById("1")).thenReturn(Optional.of(user));
    when(mockRepository.save(any(User.class))).thenReturn(user);
    
    // Use mock
    Optional<User> result = userService.getUser("1");
    
    // Verify
    assertThat(result).isPresent();
    verify(mockRepository, times(1)).findById("1");
    verify(mockRepository, never()).delete(any());
    
    // Reset mock
    reset(mockRepository);
}
```

**Advanced Mockito Features:**

**1. Argument Matchers:**
```java
import static org.mockito.ArgumentMatchers.*;

@Test
void testWithArgumentMatchers() {
    // any() - matches any object
    when(mockRepository.save(any(User.class))).thenReturn(new User());
    
    // eq() - matches specific value (use when combining with other matchers)
    when(mockRepository.findById(eq("1"))).thenReturn(Optional.of(user));
    
    // anyString(), anyInt(), anyList() - type-specific matchers
    when(mockRepository.findByName(anyString())).thenReturn(Arrays.asList(user));
    
    // isNull() and isNotNull()
    when(mockRepository.findByEmail(isNull())).thenReturn(Optional.empty());
    
    // contains(), startsWith(), endsWith() for strings
    when(mockRepository.searchByName(contains("John"))).thenReturn(users);
    
    // argThat() - custom matcher
    when(mockRepository.save(argThat(user -> 
        user.getEmail().contains("@example.com")
    ))).thenReturn(user);
    
    // ArgumentCaptor - capture arguments for complex assertions
    @Captor
    ArgumentCaptor<User> userCaptor;
    
    userService.createUser("John", "john@example.com");
    verify(mockRepository).save(userCaptor.capture());
    
    User capturedUser = userCaptor.getValue();
    assertThat(capturedUser.getName()).isEqualTo("John");
    assertThat(capturedUser.getEmail()).isEqualTo("john@example.com");
}
```

**2. Mocking Different Return Scenarios:**
```java
@Test
void testMultipleReturnValues() {
    // Return different values on consecutive calls
    when(mockRepository.findById("1"))
        .thenReturn(Optional.of(user1))    // First call
        .thenReturn(Optional.of(user2))    // Second call
        .thenReturn(Optional.empty());     // Third call and beyond
    
    // Or using varargs
    when(mockRepository.count())
        .thenReturn(1L, 2L, 3L);
    
    // Throw exception
    when(mockRepository.findById("999"))
        .thenThrow(new UserNotFoundException("User not found"));
    
    // Throw exception on specific call
    when(mockRepository.save(any()))
        .thenReturn(user)
        .thenThrow(new DatabaseException("Connection lost"));
    
    // Call real method
    when(mockRepository.validateEmail(anyString())).thenCallRealMethod();
    
    // Custom answer (complex logic)
    when(mockRepository.save(any(User.class))).thenAnswer(invocation -> {
        User user = invocation.getArgument(0);
        user.setId(UUID.randomUUID().toString());
        return user;
    });
    
    // Answer with Answer interface
    when(mockRepository.save(any())).thenAnswer(new Answer<User>() {
        @Override
        public User answer(InvocationOnMock invocation) throws Throwable {
            User user = invocation.getArgument(0);
            // Custom logic
            return user;
        }
    });
}
```

**3. Verification Techniques:**
```java
@Test
void testVerification() {
    userService.deleteUser("1");
    
    // Basic verification
    verify(mockRepository).delete("1");
    
    // Verify number of invocations
    verify(mockRepository, times(1)).delete("1");
    verify(mockRepository, never()).delete("999");
    verify(mockRepository, atLeast(1)).delete(anyString());
    verify(mockRepository, atMost(3)).delete(anyString());
    verify(mockRepository, atLeastOnce()).delete(anyString());
    
    // Verify order of calls
    InOrder inOrder = inOrder(mockRepository, mockEmailService);
    inOrder.verify(mockRepository).findById("1");
    inOrder.verify(mockEmailService).sendDeleteNotification(any());
    inOrder.verify(mockRepository).delete("1");
    
    // Verify no more interactions
    verify(mockRepository).delete("1");
    verifyNoMoreInteractions(mockRepository);
    
    // Verify zero interactions
    verifyNoInteractions(mockAuditService);
    
    // Verify with timeout (for async operations)
    verify(mockRepository, timeout(1000).times(1)).delete("1");
    
    // Capture multiple calls
    @Captor
    ArgumentCaptor<String> idCaptor;
    
    userService.deleteUser("1");
    userService.deleteUser("2");
    
    verify(mockRepository, times(2)).delete(idCaptor.capture());
    
    List<String> allIds = idCaptor.getAllValues();
    assertThat(allIds).containsExactly("1", "2");
}
```

**4. Spy vs Mock:**
```java
@Test
void testWithSpy() {
    // Spy wraps real object - calls real methods by default
    UserRepository realRepository = new UserRepositoryImpl();
    UserRepository spyRepository = spy(realRepository);
    
    // Can override specific methods
    doReturn(Optional.of(user)).when(spyRepository).findById("1");
    
    // Other methods use real implementation
    List<User> users = spyRepository.findAll(); // Calls real method
    
    // Important: Use doReturn/doThrow/doAnswer for spies
    // This avoids calling the real method during stubbing
    doReturn(user).when(spyRepository).save(any());
    
    // For mocks, you can use either:
    // when(mock.method()).thenReturn(value)  // Preferred
    // doReturn(value).when(mock).method()    // Alternative
}

@Test
void testSpyRealObject() {
    List<String> list = new ArrayList<>();
    List<String> spyList = spy(list);
    
    // Real behavior
    spyList.add("one");
    assertThat(spyList).hasSize(1);
    
    // Override specific behavior
    when(spyList.size()).thenReturn(100);
    assertThat(spyList.size()).isEqualTo(100);
    
    // Reset to real behavior
    reset(spyList);
    assertThat(spyList.size()).isEqualTo(1);
}
```

**5. Mocking Final Classes and Static Methods (Mockito 3.4+):**
```java
// For final classes and static methods, use mockStatic and mockConstruction

@Test
void testStaticMethod() {
    try (MockedStatic<UtilityClass> mockedStatic = mockStatic(UtilityClass.class)) {
        // Mock static method
        mockedStatic.when(() -> UtilityClass.staticMethod(anyString()))
            .thenReturn("mocked result");
        
        // Test code
        String result = myService.useStaticMethod("input");
        
        // Verify
        mockedStatic.verify(() -> UtilityClass.staticMethod("input"));
        assertThat(result).isEqualTo("mocked result");
    }
    // Static mock is automatically closed
}

@Test
void testFinalClass() {
    FinalClass mock = mock(FinalClass.class);
    when(mock.finalMethod()).thenReturn("mocked");
    assertThat(mock.finalMethod()).isEqualTo("mocked");
}

@Test
void testConstructor() {
    try (MockedConstruction<DatabaseConnection> mocked = 
         mockConstruction(DatabaseConnection.class, (mock, context) -> {
         when(mock.connect()).thenReturn(true);
    })) {
        // New instances will be mocked
        DatabaseConnection conn = new DatabaseConnection();
        assertThat(conn.connect()).isTrue();
    }
}
```

**5b. Practical Static Mocking Examples:**

```java
// Example 1: Mocking LocalDateTime for deterministic time-based tests
@Test
void testWithMockedTime() {
    LocalDateTime fixedTime = LocalDateTime.of(2024, 6, 15, 10, 30, 0);
    
    try (MockedStatic<LocalDateTime> mockedTime = mockStatic(LocalDateTime.class)) {
        mockedTime.when(LocalDateTime::now).thenReturn(fixedTime);
        
        // Test code that depends on current time
        Order order = orderService.createOrder("user-123");
        
        assertThat(order.getCreatedAt()).isEqualTo(fixedTime);
        mockedTime.verify(LocalDateTime::now, times(1));
    }
}

// Example 2: Mocking UUID generation for predictable IDs
@Test
void testWithMockedUUID() {
    UUID fixedUuid = UUID.fromString("123e4567-e89b-12d3-a456-426614174000");
    
    try (MockedStatic<UUID> mockedUuid = mockStatic(UUID.class)) {
        mockedUuid.when(UUID::randomUUID).thenReturn(fixedUuid);
        
        User user = userService.createUser("John", "john@example.com");
        
        assertThat(user.getId()).isEqualTo(fixedUuid.toString());
    }
}

// Example 3: Mocking singleton or utility classes
@Test
void testWithMockedSingleton() {
    try (MockedStatic<ConfigManager> mockedConfig = mockStatic(ConfigManager.class)) {
        mockedConfig.when(ConfigManager::getApiKey).thenReturn("test-api-key");
        mockedConfig.when(() -> ConfigManager.getTimeout()).thenReturn(5000);
        
        // Service uses the mocked config
        ApiResponse response = apiService.callExternalApi();
        
        assertThat(response).isNotNull();
        mockedConfig.verify(ConfigManager::getApiKey);
        mockedConfig.verify(() -> ConfigManager.getTimeout());
    }
}

// Example 4: Combining static mock with regular mocks
@Test
void testCombinedMocking() {
    try (MockedStatic<LoggerFactory> mockedLoggerFactory = mockStatic(LoggerFactory.class)) {
        Logger mockLogger = mock(Logger.class);
        mockedLoggerFactory.when(() -> LoggerFactory.getLogger(MyService.class))
            .thenReturn(mockLogger);
        
        MyService service = new MyService(mockRepository);
        service.performAction();
        
        verify(mockLogger).info("Action performed");
    }
}
```

**5c. Advanced Verification Techniques:**

```java
// Verification with ArgumentCaptor for complex object assertions
@Test
void testWithArgumentCaptor() {
    @Captor
    ArgumentCaptor<NotificationEvent> eventCaptor;
    
    userService.notifyUser("user-123", "Welcome!");
    
    verify(notificationService).send(eventCaptor.capture());
    
    NotificationEvent capturedEvent = eventCaptor.getValue();
    assertThat(capturedEvent.getUserId()).isEqualTo("user-123");
    assertThat(capturedEvent.getMessage()).isEqualTo("Welcome!");
    assertThat(capturedEvent.getTimestamp()).isNotNull();
    assertThat(capturedEvent.getPriority()).isEqualTo(Priority.NORMAL);
}

// Capturing multiple calls for batch verification
@Test
void testMultipleCallsCapture() {
    @Captor
    ArgumentCaptor<String> userIdCaptor;
    
    userService.notifyAllUsers(Arrays.asList("u1", "u2", "u3"));
    
    verify(notificationService, times(3)).send(userIdCaptor.capture());
    
    List<String> allUserIds = userIdCaptor.getAllValues();
    assertThat(allUserIds).containsExactly("u1", "u2", "u3");
}

// Verification with async operations and timeout
@Test
void testAsyncVerification() {
    userService.asyncProcess("data");
    
    // Wait up to 2 seconds for the method to be called
    verify(auditService, timeout(2000)).logEvent(any());
    
    // Combined with times()
    verify(auditService, timeout(2000).times(1)).logEvent(any());
    
    // Combined with atLeast()
    verify(auditService, timeout(2000).atLeast(1)).logEvent(any());
}

// Verification of interactions only on specific mock (ignoring others)
@Test
void testSelectiveVerification() {
    userService.processOrder("order-123");
    
    // Verify only repository was called, ignore other collaborators
    verify(repository).save(any());
    verifyNoInteractions(emailService); // Email should NOT be called for this case
}

// Verify method was called within a time window
@Test
void testWithAfterBefore() {
    long startTime = System.currentTimeMillis();
    
    service.longRunningOperation();
    
    verify(repository).save(any());
    
    long duration = System.currentTimeMillis() - startTime;
    assertThat(duration).isLessThan(5000); // Should complete within 5 seconds
}
```

**6. BDD Style with Mockito:**
```java
import static org.mockito.BDDMockito.*;

@Test
void testBDDStyle() {
    // Given
    User user = new User("1", "John");
    given(mockRepository.findById("1")).willReturn(Optional.of(user));
    given(mockRepository.save(any())).willReturn(user);
    
    // When
    Optional<User> result = userService.getUser("1");
    
    // Then
    assertThat(result).isPresent();
    then(mockRepository).should().findById("1");
    then(mockRepository).shouldHaveNoMoreInteractions();
    then(mockRepository).should(times(1)).findById("1");
    then(mockRepository).should(never()).delete(any());
}

@Test
void testBDDWithException() {
    // Given
    given(mockRepository.findById("999"))
        .willThrow(new UserNotFoundException("Not found"));
    
    // When & Then
    assertThatThrownBy(() -> userService.getUser("999"))
        .isInstanceOf(UserNotFoundException.class)
        .hasMessage("Not found");
}
```

**7. Mocking Void Methods:**
```java
@Test
void testVoidMethods() {
    // doNothing() - default behavior for void methods
    doNothing().when(mockRepository).delete(anyString());
    
    // doThrow() - throw exception
    doThrow(new DatabaseException("Error"))
        .when(mockRepository).delete("999");
    
    // doAnswer() - custom behavior
    doAnswer(invocation -> {
        String id = invocation.getArgument(0);
        System.out.println("Deleting user: " + id);
        return null;
    }).when(mockRepository).delete(anyString());
    
    // Verify void method was called
    verify(mockRepository).delete("1");
}
```

**8. Mock Settings and Verification Modes:**
```java
@Test
void testMockSettings() {
    // Create mock with custom settings
    UserRepository mockRepo = mock(UserRepository.class, withSettings()
        .name("UserRepositoryMock")
        .verboseLogging()  // Log all interactions
        .defaultAnswer(RETURNS_SMART_NULLS)  // Return smart nulls instead of null
    );
    
    // Strict stubbing (fail on unused stubs)
    UserRepository strictMock = mock(UserRepository.class, withSettings()
        .strictness(Strictness.STRICT_STUBS)
    );
    
    // Lenient stubbing (allow unused stubs)
    lenient().when(mockRepository.findById(any())).thenReturn(Optional.empty());
}
```

**9. Injecting Mocks:**
```java
// Using @InjectMocks (recommended)
@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    @Mock
    private UserRepository userRepository;
    
    @Mock
    private EmailService emailService;
    
    @InjectMocks
    private UserService userService; // Automatically injected
    
    // Constructor injection, setter injection, or field injection
}

// Manual injection
@Test
void manualInjection() {
    UserRepository mockRepo = mock(UserRepository.class);
    EmailService mockEmail = mock(EmailService.class);
    
    // Constructor injection
    UserService service = new UserService(mockRepo, mockEmail);
    
    // Or setter injection
    UserService service = new UserService();
    service.setUserRepository(mockRepo);
    service.setEmailService(mockEmail);
}
```

**10. Mocking with Annotations:**
```java
@ExtendWith(MockitoExtension.class)
class AnnotationTest {
    @Mock
    private UserRepository userRepository;
    
    @Spy
    private EmailValidator emailValidator = new EmailValidator();
    
    @Captor
    private ArgumentCaptor<User> userCaptor;
    
    @InjectMocks
    private UserService userService;
    
    @Mock(answer = Answers.RETURNS_SMART_NULLS)
    private OrderRepository orderRepository;
    
    @Spy
    private List<String> spyList = new ArrayList<>();
    
    @Test
    void testWithAnnotations() {
        // All mocks are automatically initialized
        when(userRepository.findById("1")).thenReturn(Optional.of(user));
        assertThat(userService.getUser("1")).isPresent();
    }
}
```

### Testcontainers (Integration Testing)

**Installation (Maven):**
```xml
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>testcontainers</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>
<!-- Database-specific modules -->
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>postgresql</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>mysql</artifactId>
    <version>1.19.3</version>
    <scope>test</scope>
</dependency>
<!-- Other modules: kafka, mongodb, redis, elasticsearch, etc. -->
```

**Why Testcontainers?**
- Spin up real Docker containers for integration tests
- Test against actual databases, message queues, etc.
- No need for in-memory databases (H2, HSQLDB)
- Consistent test environment across all machines
- Isolated test environments that don't affect local setup

**1. Basic Database Testing:**

```java
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.junit.jupiter.api.*;

@Testcontainers
class UserRepositoryIntegrationTest {
    
    // Container will be started once and shared across all tests
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
        .withDatabaseName("testdb")
        .withUsername("test")
        .withPassword("test");
    
    private UserRepository userRepository;
    private DataSource dataSource;
    
    @BeforeEach
    void setUp() {
        // Create datasource using container connection info
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(postgres.getJdbcUrl());
        config.setUsername(postgres.getUsername());
        config.setPassword(postgres.getPassword());
        dataSource = new HikariDataSource(config);
        
        // Initialize repository with real database
        userRepository = new UserRepository(dataSource);
        
        // Setup schema
        runMigrations(dataSource);
    }
    
    @AfterEach
    void tearDown() {
        // Clean up data
        userRepository.deleteAll();
    }
    
    @Test
    void shouldSaveAndRetrieveUser() {
        // Arrange
        User user = new User("John", "john@example.com");
        
        // Act
        User saved = userRepository.save(user);
        Optional<User> found = userRepository.findById(saved.getId());
        
        // Assert
        assertThat(found).isPresent();
        assertThat(found.get().getName()).isEqualTo("John");
        assertThat(found.get().getEmail()).isEqualTo("john@example.com");
    }
    
    @Test
    void shouldFindUsersByEmailDomain() {
        // Arrange
        userRepository.save(new User("John", "john@example.com"));
        userRepository.save(new User("Jane", "jane@example.com"));
        userRepository.save(new User("Bob", "bob@other.com"));
        
        // Act
        List<User> users = userRepository.findByEmailDomain("example.com");
        
        // Assert
        assertThat(users).hasSize(2);
        assertThat(users).extracting("email")
            .allMatch(email -> ((String) email).endsWith("@example.com"));
    }
}
```

**2. Container Lifecycle Management:**

```java
// Singleton container - started once per test class (shared)
@Testcontainers
class SharedContainerTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    // All tests share the same container instance
}

// Per-test container - started for each test (isolated)
@Testcontainers
class IsolatedContainerTest {
    @Container
    PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    // Each test gets a fresh container (slower but isolated)
}

// Manual container management
class ManualContainerTest {
    private static PostgreSQLContainer<?> postgres;
    
    @BeforeAll
    static void beforeAll() {
        postgres = new PostgreSQLContainer<>("postgres:15");
        postgres.start();
    }
    
    @AfterAll
    static void afterAll() {
        postgres.stop();
    }
    
    @Test
    void test() {
        String jdbcUrl = postgres.getJdbcUrl();
        // Use container...
    }
}
```

**3. Multiple Containers:**

```java
@Testcontainers
class MultipleContainersTest {
    
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    @Container
    static GenericContainer<?> redis = new GenericContainer<>("redis:7-alpine")
        .withExposedPorts(6379);
    
    @Container
    static KafkaContainer kafka = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.4.0")
    );
    
    @Test
    void testWithMultipleContainers() {
        // Use PostgreSQL
        String jdbcUrl = postgres.getJdbcUrl();
        
        // Use Redis
        String redisHost = redis.getHost();
        Integer redisPort = redis.getMappedPort(6379);
        Jedis jedis = new Jedis(redisHost, redisPort);
        
        // Use Kafka
        String bootstrapServers = kafka.getBootstrapServers();
        Properties props = new Properties();
        props.put("bootstrap.servers", bootstrapServers);
        
        // Test interactions between services
    }
}
```

**4. Custom Containers:**

```java
// Custom container with initialization logic
class CustomPostgreSQLContainer extends PostgreSQLContainer<CustomPostgreSQLContainer> {
    
    public CustomPostgreSQLContainer() {
        super("postgres:15-alpine");
    }
    
    @Override
    public void start() {
        super.start();
        // Run custom initialization
        runInitScripts();
    }
    
    private void runInitScripts() {
        try (Connection conn = createConnection("");
             Statement stmt = conn.createStatement()) {
            
            // Create schema
            stmt.execute("CREATE SCHEMA IF NOT EXISTS app");
            
            // Run migrations
            stmt.execute("CREATE TABLE IF NOT EXISTS app.users (...)");
            
        } catch (SQLException e) {
            throw new RuntimeException("Failed to initialize database", e);
        }
    }
}

// Using custom container
@Container
static CustomPostgreSQLContainer postgres = new CustomPostgreSQLContainer();
```

**5. Network Communication Between Containers:**

```java
@Testcontainers
class NetworkTest {
    
    static Network network = Network.newNetwork();
    
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
        .withNetwork(network)
        .withNetworkAliases("db");
    
    @Container
    static GenericContainer<?> app = new GenericContainer<>("myapp:latest")
        .withNetwork(network)
        .withEnv("DB_HOST", "db")
        .withEnv("DB_PORT", "5432")
        .dependsOn(postgres)
        .waitingFor(Wait.forHttp("/health").forPort(8080));
    
    @Test
    void testAppWithDatabase() {
        // App can connect to postgres using hostname "db"
        String appUrl = "http://" + app.getHost() + ":" + app.getMappedPort(8080);
        
        // Test app functionality
    }
}
```

**6. Database-Specific Examples:**

```java
// MySQL
@Container
static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
    .withDatabaseName("testdb")
    .withUsername("test")
    .withPassword("test");

// MongoDB
@Container
static MongoDBContainer mongoDB = new MongoDBContainer("mongo:6.0");

@Test
void testMongoDB() {
    String connectionString = mongoDB.getConnectionString();
    MongoClient client = MongoClients.create(connectionString);
    MongoDatabase db = client.getDatabase("testdb");
    // Use MongoDB...
}

// Redis
@Container
static GenericContainer<?> redis = new GenericContainer<>("redis:7-alpine")
    .withExposedPorts(6379);

@Test
void testRedis() {
    String host = redis.getHost();
    int port = redis.getMappedPort(6379);
    Jedis jedis = new Jedis(host, port);
    
    jedis.set("key", "value");
    assertThat(jedis.get("key")).isEqualTo("value");
}

// Elasticsearch
@Container
static ElasticsearchContainer elasticsearch = new ElasticsearchContainer(
    DockerImageName.parse("docker.elastic.co/elasticsearch/elasticsearch:8.10.0")
);

// Kafka
@Container
static KafkaContainer kafka = new KafkaContainer(
    DockerImageName.parse("confluentinc/cp-kafka:7.4.0")
);

@Test
void testKafka() throws Exception {
    String bootstrapServers = kafka.getBootstrapServers();
    
    // Producer
    Properties producerProps = new Properties();
    producerProps.put("bootstrap.servers", bootstrapServers);
    Producer<String, String> producer = new KafkaProducer<>(producerProps);
    
    // Consumer
    Properties consumerProps = new Properties();
    consumerProps.put("bootstrap.servers", bootstrapServers);
    Consumer<String, String> consumer = new KafkaConsumer<>(consumerProps);
    
    // Test Kafka operations
}
```

**7. Wait Strategies:**

```java
// Wait for HTTP endpoint
@Container
static GenericContainer<?> app = new GenericContainer<>("myapp:latest")
    .withExposedPorts(8080)
    .waitingFor(Wait.forHttp("/health")
        .forStatusCode(200)
        .forPort(8080)
        .withStartupTimeout(Duration.ofSeconds(60)));

// Wait for log message
@Container
static GenericContainer<?> service = new GenericContainer<>("service:latest")
    .waitingFor(Wait.forLogMessage(".*Server started.*", 1));

// Wait for healthcheck
@Container
static GenericContainer<?> db = new GenericContainer<>("postgres:15")
    .waitingFor(Wait.forHealthcheck());

// Custom wait strategy
@Container
static GenericContainer<?> custom = new GenericContainer<>("custom:latest")
    .waitingFor(new WaitStrategy() {
        @Override
        public void waitUntilReady(WaitStrategyTarget target) {
            // Custom wait logic
        }
    });
```

**8. Test with Flyway Migrations:**

```java
@Testcontainers
class DatabaseMigrationTest {
    
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    private Flyway flyway;
    
    @BeforeEach
    void setUp() {
        // Configure Flyway with container connection
        flyway = Flyway.configure()
            .dataSource(
                postgres.getJdbcUrl(),
                postgres.getUsername(),
                postgres.getPassword()
            )
            .locations("classpath:db/migration")
            .load();
        
        // Run migrations
        flyway.migrate();
    }
    
    @Test
    void shouldRunMigrationsSuccessfully() {
        // Verify migrations were applied
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(
                 "SELECT COUNT(*) FROM flyway_schema_history"
             )) {
            
            assertThat(rs.next()).isTrue();
            assertThat(rs.getInt(1)).isGreaterThan(0);
        }
    }
    
    @Test
    void shouldInsertDataAfterMigration() {
        // Test data access after migrations
        UserRepository repo = new UserRepository(dataSource);
        repo.save(new User("John", "john@example.com"));
        
        assertThat(repo.count()).isEqualTo(1);
    }
}
```

**9. Best Practices:**

```java
@Testcontainers
@TestMethodOrder(OrderAnnotation.class)
class BestPracticesTest {
    
    // 1. Use singleton containers for performance
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    // 2. Share expensive resources
    private static DataSource sharedDataSource;
    
    @BeforeAll
    static void initDataSource() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(postgres.getJdbcUrl());
        config.setUsername(postgres.getUsername());
        config.setPassword(postgres.getPassword());
        sharedDataSource = new HikariDataSource(config);
        
        // Run schema migrations once
        runMigrations(sharedDataSource);
    }
    
    // 3. Clean data between tests
    @BeforeEach
    void cleanData() {
        try (Connection conn = sharedDataSource.getConnection();
             Statement stmt = conn.createStatement()) {
            stmt.execute("TRUNCATE TABLE users CASCADE");
        }
    }
    
    // 4. Use lightweight images
    // postgres:15-alpine (smaller) vs postgres:15 (larger)
    
    // 5. Set resource limits
    @Container
    static GenericContainer<?> app = new GenericContainer<>("app:latest")
        .withCreateContainerCmdModifier(cmd -> 
            cmd.getHostConfig()
                .withMemory(512L * 1024 * 1024)  // 512MB
                .withCpuCount(2L)
        );
    
    // 6. Reuse containers (experimental)
    // Add to testcontainers.properties:
    // testcontainers.reuse.enable=true
    
    @Container(reuse = true)
    static PostgreSQLContainer<?> reusable = new PostgreSQLContainer<>("postgres:15");
}

// 7. Use docker-compose for complex setups
class ComposeTest {
    
    static DockerComposeContainer<?> compose = new DockerComposeContainer<>(
        new File("docker-compose.yml")
    )
        .withExposedService("db", 5432)
        .withExposedService("app", 8080);
    
    @BeforeAll
    static void start() {
        compose.start();
    }
    
    @AfterAll
    static void stop() {
        compose.stop();
    }
    
    @Test
    void test() {
        String dbHost = compose.getServiceHost("db", 5432);
        Integer dbPort = compose.getServicePort("db", 5432);
        // Use services...
    }
}
```

**10. Testing with Spring Boot:**

```java
@SpringBootTest
@Testcontainers
class SpringBootIntegrationTest {
    
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");
    
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        // Dynamically configure Spring properties
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.datasource.driver-class-name", postgres::getDriverClassName);
    }
    
    @Autowired
    private UserRepository userRepository;
    
    @Autowired
    private UserService userService;
    
    @Test
    void testWithSpringBoot() {
        // Spring Boot configured with Testcontainers
        User user = userService.createUser("John", "john@example.com");
        assertThat(user.getId()).isNotNull();
        
        Optional<User> found = userRepository.findById(user.getId());
        assertThat(found).isPresent();
    }
}
```

**Testcontainers Tips:**
- ✅ Use singleton containers to improve test performance
- ✅ Clean up data between tests (TRUNCATE, not DROP/CREATE)
- ✅ Use lightweight Docker images (alpine variants)
- ✅ Set appropriate timeouts for container startup
- ✅ Use `@DynamicPropertySource` with Spring Boot
- ❌ Don't use `@Container` on non-static fields unless you need isolation
- ❌ Don't hardcode container ports (use `getMappedPort()`)
- ❌ Don't forget to close resources (connections, clients)

---

## Rust Testing

### Built-in Test Framework

**Test Discovery:**
- Unit tests: `#[cfg(test)]` modules in source files
- Integration tests: Files in `tests/` directory
- Doc tests: Examples in documentation comments

**Basic Commands:**
```bash
# Run all tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_function_name

# Run tests matching pattern
cargo test pattern

# Run ignored tests
cargo test -- --ignored

# Run tests in parallel
cargo test -- --test-threads=4

# Run tests sequentially
cargo test -- --test-threads=1
```

**Unit Tests:**
```rust
// src/user_service.rs

pub struct UserService {
    repository: Box<dyn UserRepository>,
}

impl UserService {
    pub fn new(repository: Box<dyn UserRepository>) -> Self {
        Self { repository }
    }
    
    pub fn create_user(&self, name: &str, email: &str) -> Result<User, ValidationError> {
        if name.is_empty() {
            return Err(ValidationError::InvalidName);
        }
        if !self.is_valid_email(email) {
            return Err(ValidationError::InvalidEmail);
        }
        
        let user = User {
            id: Uuid::new_v4(),
            name: name.to_string(),
            email: email.to_string(),
        };
        
        self.repository.save(user.clone())?;
        Ok(user)
    }
    
    fn is_valid_email(&self, email: &str) -> bool {
        email.contains('@')
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mockall::predicate::*;
    use mockall::mock;
    
    mock! {
        pub UserRepository {}
        
        impl UserRepository for UserRepository {
            fn save(&self, user: User) -> Result<(), DatabaseError>;
            fn find_by_id(&self, id: Uuid) -> Result<Option<User>, DatabaseError>;
        }
    }
    
    #[test]
    fn should_create_user_with_valid_data() {
        // Arrange
        let mut mock_repo = MockUserRepository::new();
        mock_repo
            .expect_save()
            .with(predicate::always())
            .times(1)
            .returning(|_| Ok(()));
        
        let service = UserService::new(Box::new(mock_repo));
        
        // Act
        let result = service.create_user("John", "john@example.com");
        
        // Assert
        assert!(result.is_ok());
        let user = result.unwrap();
        assert_eq!(user.name, "John");
        assert_eq!(user.email, "john@example.com");
    }
    
    #[test]
    fn should_return_error_with_empty_name() {
        // Arrange
        let mock_repo = MockUserRepository::new();
        let service = UserService::new(Box::new(mock_repo));
        
        // Act
        let result = service.create_user("", "john@example.com");
        
        // Assert
        assert!(result.is_err());
        match result {
            Err(ValidationError::InvalidName) => (),
            _ => panic!("Expected InvalidName error"),
        }
    }
    
    #[test]
    fn should_return_error_with_invalid_email() {
        // Arrange
        let mock_repo = MockUserRepository::new();
        let service = UserService::new(Box::new(mock_repo));
        
        // Act
        let result = service.create_user("John", "invalid-email");
        
        // Assert
        assert!(result.is_err());
    }
    
    #[test]
    #[should_panic(expected = "assertion failed")]
    fn should_panic() {
        panic!("assertion failed");
    }
    
    #[test]
    #[ignore]
    fn ignored_test() {
        // This test will be ignored
    }
}
```

**Integration Tests:**
```rust
// tests/integration_test.rs

use myapp::UserService;

#[test]
fn test_user_creation() {
    let service = UserService::new();
    let user = service.create_user("John", "john@example.com");
    
    assert!(user.is_ok());
}
```

**Doc Tests:**
```rust
/// Adds two numbers together.
///
/// # Examples
///
/// ```
/// use myapp::add;
///
/// let result = add(2, 3);
/// assert_eq!(result, 5);
/// ```
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

**Property-Based Testing with proptest:**
```rust
// Cargo.toml
// [dev-dependencies]
// proptest = "1.2"

use proptest::prelude::*;

proptest! {
    #[test]
    fn test_addition_commutative(a: i32, b: i32) {
        prop_assert_eq!(add(a, b), add(b, a));
    }
    
    #[test]
    fn test_string_length(s: String) {
        let len = s.len();
        prop_assert!(len >= 0);
    }
}
```

---

## Mock Libraries by Language

### Python
- **unittest.mock**: Standard library, powerful and flexible
- **pytest-mock**: Pytest plugin, provides `mocker` fixture
- **responses**: HTTP mocking library
- **freezegun**: Mock datetime
- **botocore.stub**: AWS service mocking

### JavaScript/TypeScript
- **jest.mock()**: Built-in Jest mocking
- **Sinon**: Standalone mocking library (works with Mocha)
- **MSW (Mock Service Worker)**: API mocking for browser and Node
- **Nock**: HTTP mocking for Node
- **faker.js**: Generate fake data

### Go
- **testify/mock**: Part of testify suite, excellent for mocking
- **gomock**: Official Go mocking library
- **go-sqlmock**: SQL driver mocking
- **httptest**: HTTP testing utilities (standard library)

### Java
- **Mockito**: Most popular mocking framework
- **EasyMock**: Alternative mocking framework
- **PowerMock**: Extends Mockito for static methods
- **WireMock**: HTTP API mocking

### Rust
- **mockall**: Powerful mocking framework
- **mockito**: HTTP mocking
- **wiremock-rs**: HTTP mocking

---

## Test Patterns

### AAA Pattern (Arrange-Act-Assert)

**Structure:**
```python
def test_should_create_user():
    # Arrange (Setup)
    user_data = {"name": "John", "email": "john@example.com"}
    service = UserService()
    
    # Act (Execute)
    result = service.create_user(user_data)
    
    # Assert (Verify)
    assert result is not None
    assert result.name == "John"
```

### Fixture Pattern

**Test Data Fixtures:**
```python
# pytest
@pytest.fixture
def sample_user():
    return User(id=1, name="John", email="john@example.com")

@pytest.fixture
def user_service():
    return UserService()

def test_with_fixtures(sample_user, user_service):
    result = user_service.process(sample_user)
    assert result.is_valid
```

### Test Data Builder Pattern

```python
class UserBuilder:
    def __init__(self):
        self.id = 1
        self.name = "John Doe"
        self.email = "john@example.com"
    
    def with_name(self, name):
        self.name = name
        return self
    
    def with_email(self, email):
        self.email = email
        return self
    
    def build(self):
        return User(id=self.id, name=self.name, email=self.email)

# Usage
def test_user_builder():
    user = UserBuilder().with_name("Jane").with_email("jane@example.com").build()
    assert user.name == "Jane"
```

### Object Mother Pattern

```python
class UserMother:
    @staticmethod
    def create_valid_user():
        return User(id=1, name="John", email="john@example.com")
    
    @staticmethod
    def create_user_without_email():
        return User(id=1, name="John", email=None)
    
    @staticmethod
    def create_admin_user():
        return User(id=1, name="Admin", email="admin@example.com", role="admin")

def test_valid_user():
    user = UserMother.create_valid_user()
    assert user.is_valid
```

### Test Pyramid

```
         /\
        /  \  E2E Tests (Few, Slow, Expensive)
       /----\
      /      \ Integration Tests (Some, Medium Speed)
     /--------\
    /          \ Unit Tests (Many, Fast, Cheap)
   /--------------\
```

**Distribution:**
- **Unit Tests**: 70% - Test isolated units of code
- **Integration Tests**: 20% - Test component interactions
- **E2E Tests**: 10% - Test critical user flows

---

## Best Practices

### Test Organization

1. **Mirror Source Structure**
   ```
   src/
     user_service.py
     order_service.py
   tests/
     test_user_service.py
     test_order_service.py
   ```

2. **Separate Test Types**
   ```
   tests/
     unit/
       test_user_service.py
     integration/
       test_api.py
     e2e/
       test_user_flow.py
   ```

3. **Use Descriptive Names**
   ```python
   # Good
   def test_should_return_404_when_user_not_found():
       pass
   
   # Bad
   def test_user():
       pass
   ```

### Test Isolation

```python
# Good - Each test is independent
class TestUserService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = UserService()
        self.service.clear_all_data()
    
    def test_create_user(self):
        # Independent test
        pass
    
    def test_delete_user(self):
        # Independent test
        pass
```

### Mocking Strategy

```python
# Mock external dependencies only
def test_send_email(mocker):
    # Mock external email service
    mock_email_service = mocker.patch('myapp.services.email_service')
    
    service = NotificationService()
    service.send_notification("john@example.com", "Hello")
    
    # Verify email was sent
    mock_email_service.send.assert_called_once_with(
        "john@example.com",
        "Hello"
    )
```

### Coverage Strategy

1. **Aim for 85%+ coverage** on critical business logic
2. **Don't test trivial code** (getters, setters)
3. **Document coverage gaps** with justification
4. **Focus on behavior, not implementation**

### Performance

1. **Unit tests should run in seconds**
2. **Use in-memory databases** for integration tests
3. **Parallelize tests** when possible
4. **Avoid slow operations** (network, file I/O) in unit tests

---

## Framework Selection Guide

### Python
- **Use pytest when:** You want powerful fixtures, parametrization, and great plugin ecosystem
- **Use unittest when:** You need only standard library, simple tests, or legacy codebase

### JavaScript/TypeScript
- **Use Jest when:** You want all-in-one solution, React testing, snapshot testing
- **Use Mocha + Chai when:** You need flexibility, prefer separate assertion library

### Go
- **Use testing + testify when:** Standard approach, excellent assertions and mocking
- **Use only testing when:** Minimal dependencies, simple tests

### Java
- **Use JUnit 5 when:** Modern Java testing, parameterized tests, extension model

### Rust
- **Use built-in framework when:** Standard Rust testing, zero dependencies
- **Add proptest when:** Property-based testing needed
- **Add mockall when:** Complex mocking required

---

## Quick Reference Commands

### Python (pytest)
```bash
pytest tests/                      # Run all tests
pytest tests/ -v                   # Verbose output
pytest tests/ -k "pattern"         # Run matching tests
pytest tests/ --cov=src            # With coverage
pytest tests/ -x                   # Stop on first failure
pytest tests/ -n auto              # Parallel execution
```

### JavaScript/TypeScript (Jest)
```bash
npm test                           # Run all tests
npm test -- --watch                # Watch mode
npm test -- --coverage             # With coverage
npm test -- -t "pattern"           # Run matching tests
npm test -- --updateSnapshot       # Update snapshots
```

### Go
```bash
go test                            # Run tests in current package
go test ./...                      # Run all tests
go test -v                         # Verbose output
go test -cover                     # With coverage
go test -race                      # With race detection
go test -run "Pattern"             # Run matching tests
```

### Java (Maven)
```bash
mvn test                           # Run all tests
mvn test -Dtest=ClassName         # Run specific class
mvn test -Dtest=Class#method      # Run specific method
mvn test jacoco:report            # With coverage
```

### Rust (Cargo)
```bash
cargo test                         # Run all tests
cargo test -- --nocapture          # Show output
cargo test pattern                 # Run matching tests
cargo test -- --ignored            # Run ignored tests
cargo test -- --test-threads=1     # Sequential execution
```

---

## Common Testing Scenarios

### Testing Exceptions

**Python:**
```python
import pytest

def test_should_raise_error():
    with pytest.raises(ValueError, match="Invalid input"):
        service.process(None)
```

**TypeScript:**
```typescript
it('should throw error', () => {
    expect(() => service.process(null)).toThrow('Invalid input');
});
```

**Go:**
```go
func TestShouldReturnError(t *testing.T) {
    _, err := service.Process(nil)
    assert.Error(t, err)
    assert.Contains(t, err.Error(), "Invalid input")
}
```

### Testing Async Code

**Python:**
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await service.async_operation()
    assert result is not None
```

**TypeScript:**
```typescript
it('should handle async', async () => {
    const result = await service.asyncOperation();
    expect(result).toBeDefined();
});
```

### Testing HTTP APIs

**Python:**
```python
from fastapi.testclient import TestClient

def test_get_user(client: TestClient):
    response = client.get("/api/users/1")
    assert response.status_code == 200
    assert response.json()["name"] == "John"
```

**TypeScript:**
```typescript
import request from 'supertest';

it('should get user', async () => {
    const response = await request(app).get('/api/users/1');
    expect(response.status).toBe(200);
    expect(response.body.name).toBe('John');
});
```

---

**Skill Version:** 1.1  
**Last Updated:** 2026-03-04  
**Sources:** test-generator agent, api-tester agent
