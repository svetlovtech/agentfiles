# Protected Variations Anti-Patterns - Python

## Anti-Pattern: Hardcoded Values

### BAD Example

```python
class PaymentService:
    def process_payment(self, amount):
        gateway = StripeGateway('sk_test_xxx')
        return gateway.charge(amount)
```

### GOOD Example

```python
class PaymentService:
    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway

factory = PaymentGatewayFactory.create(config)
service = PaymentService(factory)
```

## Detection Checklist

- [ ] Hardcoded configuration
- [ ] No factory pattern
- [ ] Tight coupling to specific implementation
- [ ] Hard to change providers
