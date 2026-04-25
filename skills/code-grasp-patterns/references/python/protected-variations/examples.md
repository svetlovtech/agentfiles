# Protected Variations Examples - Python

## Introduction

This document provides paired examples of BAD and GOOD implementations of Protected Variations pattern in Python.

## Example 1: Hardcoded Payment Methods

### BAD Example

```python
class PaymentService:
    def process_payment(self, payment_type, amount, details):
        # BAD: Hardcoded payment methods
        if payment_type == 'credit_card':
            gateway = StripeGateway('sk_test_xxx')
            return gateway.charge(amount, details)
        elif payment_type == 'paypal':
            gateway = PayPalGateway('client_id', 'secret')
            return gateway.charge(amount, details)
        elif payment_type == 'bank_transfer':
            gateway = BankTransferGateway()
            return gateway.charge(amount, details)
```

### GOOD Example

```python
from abc import ABC, abstractmethod

class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: float, details: dict) -> PaymentResult:
        pass

class PaymentService:
    def __init__(self, gateway: PaymentGateway):
        # GOOD: Protected from changes via abstraction
        self.gateway = gateway
    
    def process_payment(self, amount: float, details: dict) -> PaymentResult:
        return self.gateway.charge(amount, details)

# Configuration-based gateway selection
class PaymentGatewayFactory:
    @classmethod
    def create_from_config(cls, config: dict) -> PaymentGateway:
        gateway_type = config.get('GATEWAY_TYPE', 'stripe')
        
        if gateway_type == 'stripe':
            return StripeGateway(config['STRIPE_API_KEY'])
        elif gateway_type == 'paypal':
            return PayPalGateway(config['PAYPAL_CLIENT_ID'], config['PAYPAL_SECRET'])
        elif gateway_type == 'bank_transfer':
            return BankTransferGateway()
        else:
            raise ValueError(f'Unknown gateway: {gateway_type}')
```

**Improvements:**
- Protected from payment gateway changes
- Configuration-based selection
- Easy to add new gateways
- No code changes needed

## Example 2: Hardcoded Email Provider

### BAD Example

```python
class EmailService:
    def send_email(self, to, subject, body):
        # BAD: Hardcoded SMTP settings
        import smtplib
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('user@gmail.com', 'password')
        server.sendmail('user@gmail.com', to, f'Subject: {subject}\n\n{body}')
        server.quit()
```

### GOOD Example

```python
from abc import ABC, abstractmethod

class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None:
        pass

class SMTPProvider(EmailProvider):
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
    
    def send(self, to: str, subject: str, body: str) -> None:
        import smtplib
        server = smtplib.SMTP(self.host, self.port)
        server.starttls()
        server.login(self.username, self.password)
        server.sendmail(self.username, to, f'Subject: {subject}\n\n{body}')
        server.quit()

class SendGridProvider(EmailProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def send(self, to: str, subject: str, body: str) -> None:
        import requests
        requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            json={
                'personalizations': [{'to': [{'email': to}]}],
                'from': {'email': 'noreply@example.com'},
                'subject': subject,
                'content': [{'type': 'text/plain', 'value': body}]
            },
            headers={'Authorization': f'Bearer {self.api_key}'}
        )

class EmailService:
    def __init__(self, provider: EmailProvider):
        # GOOD: Protected from provider changes
        self.provider = provider
    
    def send_email(self, to: str, subject: str, body: str) -> None:
        self.provider.send(to, subject, body)

# Configuration-based selection
class EmailProviderFactory:
    @classmethod
    def create_from_config(cls, config: dict) -> EmailProvider:
        provider_type = config.get('EMAIL_PROVIDER', 'smtp')
        
        if provider_type == 'smtp':
            return SMTPProvider(
                config['SMTP_HOST'],
                config['SMTP_PORT'],
                config['SMTP_USER'],
                config['SMTP_PASS']
            )
        elif provider_type == 'sendgrid':
            return SendGridProvider(config['SENDGRID_API_KEY'])
        else:
            raise ValueError(f'Unknown provider: {provider_type}')
```

**Improvements:**
- Protected from email provider changes
- Configuration-based selection
- Easy to switch providers
- No code changes needed

## Language-Specific Notes

### Python Protected Variations Patterns

- **ABC**: Use abstract base classes for stable interfaces
- **Configuration files**: Use environment variables, YAML, JSON for variations
- **Factory pattern**: Create appropriate implementation based on config
- **Strategy pattern**: Swap algorithms at runtime
- **Dependency injection**: Inject configured implementation
