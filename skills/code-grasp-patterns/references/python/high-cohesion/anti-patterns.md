# High Cohesion Anti-Patterns - Python

## Introduction

This document catalogs common anti-patterns that violate High Cohesion principle in Python.

## Anti-Pattern: God Class

### Description

A class that does too much, handling multiple unrelated responsibilities.

### BAD Example

```python
class UserManager:
    # User management
    def create_user(self, data): pass
    def update_user(self, user_id, data): pass
    def delete_user(self, user_id): pass
    
    # Authentication
    def login(self, email, password): pass
    def logout(self, user): pass
    def reset_password(self, email): pass
    
    # Email
    def send_welcome_email(self, user): pass
    def send_password_reset(self, email): pass
    def send_notification(self, user, message): pass
    
    # Reports
    def generate_user_report(self): pass
    def export_to_csv(self): pass
    def export_to_pdf(self): pass
    
    # Logging
    def log_login(self, user): pass
    def log_activity(self, user, action): pass
    
    # Backup
    def backup_users(self): pass
    def restore_users(self, backup_file): pass
    
    # Validation
    def validate_email(self, email): pass
    def validate_password(self, password): pass
    def validate_name(self, name): pass
```

### Why It's Problematic

- **Violates SRP**: Multiple unrelated responsibilities
- **Hard to maintain**: Changes affect many areas
- **Hard to test**: Massive test suite needed
- **Team conflicts**: Multiple developers stepping on each other

### GOOD Example

```python
class UserService:
    def create_user(self, data: User) -> User:
        self.user_repo.save(data)
    def update_user(self, user_id: int, data: dict) -> User:
        pass

class AuthService:
    def login(self, email: str, password: str) -> Token:
        pass
    def logout(self, user: User) -> None:
        pass
    def reset_password(self, email: str) -> None:
        pass

class EmailService:
    def send_welcome(self, user: User) -> None:
        pass
    def send_password_reset(self, email: str) -> None:
        pass

class ReportService:
    def generate_user_report(self) -> dict:
        pass

class UserValidator:
    def validate_email(self, email: str) -> bool:
        return '@' in email
```

**Key Changes:**
- Split into focused classes
- Each class single responsibility
- High cohesion maintained

## Anti-Pattern: Swiss Army Knife Class

### Description

Class that tries to do everything for everyone, accepting unrelated operations.

### BAD Example

```python
class Utility:
    @staticmethod
    def format_date(date): pass
    
    @staticmethod
    def calculate_tax(amount): pass
    
    @staticmethod
    def send_email(to, subject): pass
    
    @staticmethod
    def log_message(message): pass
    
    @staticmethod
    def validate_phone(phone): pass
    
    @staticmethod
    def encrypt_data(data): pass
    
    @staticmethod
    def compress_file(file): pass
    
    @staticmethod
    def generate_report(data): pass
```

### Why It's Problematic

- **No cohesion**: Completely unrelated functions
- **Hard to find**: Functions scattered in one class
- **Violates SRP**: No single responsibility
- **Hard to test**: Need to test everything together

### GOOD Example

```python
class DateFormatter:
    @staticmethod
    def to_iso(date: datetime) -> str:
        return date.isoformat()

class TaxCalculator:
    @staticmethod
    def calculate(amount: float, rate: float = 0.08) -> float:
        return amount * rate

class EmailSender:
    def send(self, to: str, subject: str, body: str) -> None:
        pass

class Logger:
    def log(self, message: str) -> None:
        pass

class PhoneValidator:
    @staticmethod
    def is_valid(phone: str) -> bool:
        return phone.startswith('+')
```

**Key Changes:**
- Split into focused utilities
- Each class single purpose
- Better organization

## Detection Checklist

### Code Review Questions

- [ ] Does class handle multiple unrelated concerns?
- [ ] Are methods not related to class name?
- [ ] Would class need to be split by different teams?
- [ ] Does class have >10 public methods?
- [ ] Are methods grouped by different functionality?

### Common Symptoms

- **God classes**: Single class with 50+ methods
- **Utility classes**: "Utils" with everything
- **Fat services**: Services doing everything
- **Mixed concerns**: Validation, persistence, formatting in same class
