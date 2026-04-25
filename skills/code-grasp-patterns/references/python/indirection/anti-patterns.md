# Indirection Anti-Patterns - Python

## Anti-Pattern: No Abstraction

### BAD Example

```python
class OrderService:
    def __init__(self):
        self.db = psycopg2.connect(...)
        self.email = smtplib.SMTP(...)
```

### GOOD Example

```python
class OrderService:
    def __init__(self, db: Database, email: EmailProvider):
        self.db = db
        self.email = email
```

## Detection Checklist

- [ ] Direct database calls
- [ ] Direct external API calls
- [ ] Tight coupling to implementations
- [ ] No repository pattern
