---
name: Security: OWASP Top 10
description: |
  OWASP API Security Top 10 reference for security audits.
  Use when: Conducting security audits, vulnerability scanning, API security review, penetration testing.
  
  Covers: Broken object-level authorization, authentication, injection, cryptographic failures, security misconfiguration, and more.
  Includes detection patterns, code examples, and remediation strategies for each vulnerability category.
---

# OWASP API Security Top 10 Reference

## Overview

This skill provides comprehensive coverage of the OWASP Top 10 security vulnerabilities for API and web applications. Use this reference during security audits, code reviews, and penetration testing to systematically identify and remediate security issues.

**Key Features**:
- Complete OWASP Top 10 checklist with vulnerability patterns
- Detection patterns for multiple programming languages
- Code examples of vulnerable and secure implementations
- Severity classification guidelines
- Remediation strategies for each category
- CWE mapping for industry standardization

---

## OWASP Top 10 Categories

### A01: Broken Access Control

**Description**: Restrictions on what authenticated users are allowed to do are not properly enforced, allowing attackers to access unauthorized functionality or data.

**Common Vulnerabilities**:
- Missing authentication checks
- Insecure Direct Object Reference (IDOR)
- Privilege escalation
- Force browsing to restricted URLs
- Improper CORS configuration

**Severity Classification**:

**CRITICAL**:
- IDOR allowing access to any user's data
- Privilege escalation to admin level
- Missing authentication on sensitive endpoints

**HIGH**:
- Unauthorized access to user data
- Missing authorization checks on write operations
- CORS misconfiguration allowing credential theft

**MEDIUM**:
- Force browsing to restricted URLs
- Missing rate limiting on endpoints
- Improper CORS policies

**Detection Patterns**:

Python:
```python
# VULNERABLE: Missing authorization check
@app.route('/api/user/<user_id>')
def get_user(user_id):
    return User.query.get(user_id)  # No auth check

# SECURE: Proper authorization
@app.route('/api/user/<user_id>')
@login_required
def get_user(user_id):
    if current_user.id != user_id and not current_user.is_admin:
        abort(403)
    return User.query.get(user_id)
```

JavaScript (Node.js/Express):
```javascript
// VULNERABLE: Missing authorization check
app.get('/api/user/:userId', (req, res) => {
  const user = await User.findById(req.params.userId);
  res.json(user);  // No auth check
});

// SECURE: Proper authorization
app.get('/api/user/:userId', authenticate, (req, res) => {
  if (req.user.id !== req.params.userId && !req.user.isAdmin) {
    return res.status(403).json({ error: 'Forbidden' });
  }
  const user = await User.findById(req.params.userId);
  res.json(user);
});
```

Java (Spring Boot):
```java
// VULNERABLE: Missing authorization check
@GetMapping("/api/user/{userId}")
public User getUser(@PathVariable Long userId) {
    return userRepository.findById(userId);  // No auth check
}

// SECURE: Proper authorization
@GetMapping("/api/user/{userId}")
@PreAuthorize("hasRole('ADMIN') or #userId == authentication.principal.id")
public User getUser(@PathVariable Long userId) {
    return userRepository.findById(userId);
}
```

**Remediation**:
1. Implement proper access control checks on every endpoint
2. Use role-based access control (RBAC)
3. Validate user permissions server-side
4. Implement proper CORS policies
5. Deny by default, require explicit permission grants

---

### A02: Cryptographic Failures

**Description**: Failures related to cryptography which often leads to exposure of sensitive data.

**Common Vulnerabilities**:
- Weak cryptographic algorithms (MD5, SHA1, RC4, DES)
- Hardcoded secrets in source code
- Insecure key generation or storage
- No encryption for sensitive data at rest
- Missing or weak TLS/SSL configuration

**Severity Classification**:

**CRITICAL**:
- Hardcoded production database credentials
- Weak encryption on sensitive user data (PII, financial)
- Missing encryption on passwords or auth tokens

**HIGH**:
- Weak hashing algorithms (MD5, SHA1) for passwords
- Hardcoded API keys or secrets
- Missing TLS/SSL on sensitive endpoints

**MEDIUM**:
- Weak TLS configuration (SSLv3, TLS 1.0)
- Improper key management
- Missing integrity checks on encrypted data

**Detection Patterns**:

Python:
```python
# VULNERABLE: Weak hashing
import hashlib
password_hash = hashlib.md5(password).hexdigest()

# SECURE: Strong hashing with salt
import bcrypt
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# VULNERABLE: Hardcoded secret
API_KEY = "sk-1234567890abcdef"

# SECURE: Environment variable
import os
API_KEY = os.environ.get('API_KEY')
```

JavaScript (Node.js):
```javascript
// VULNERABLE: Weak hashing
const crypto = require('crypto');
const hash = crypto.createHash('md5').update(password).digest('hex');

// SECURE: Strong hashing with bcrypt
const bcrypt = require('bcrypt');
const hash = await bcrypt.hash(password, 10);

// VULNERABLE: Hardcoded secret
const API_KEY = "sk-1234567890abcdef";

// SECURE: Environment variable
const API_KEY = process.env.API_KEY;
```

Java:
```java
// VULNERABLE: Weak hashing
import java.security.MessageDigest;
MessageDigest md = MessageDigest.getInstance("MD5");
byte[] hash = md.digest(password.getBytes());

// SECURE: Strong hashing with BCrypt
import org.mindrot.jbcrypt.BCrypt;
String hash = BCrypt.hashpw(password, BCrypt.gensalt());

// VULNERABLE: Hardcoded secret
String API_KEY = "sk-1234567890abcdef";

// SECURE: Environment variable
String API_KEY = System.getenv("API_KEY");
```

**Remediation**:
1. Use strong, modern cryptographic algorithms (AES-256, SHA-256, bcrypt)
2. Never hardcode secrets - use environment variables or secret managers
3. Implement proper key management and rotation
4. Encrypt sensitive data at rest and in transit
5. Use TLS 1.2+ with strong cipher suites

---

### A03: Injection

**Description**: User-supplied data is not validated, filtered, or sanitized by the application, allowing attackers to inject malicious commands.

**Common Vulnerabilities**:
- SQL injection
- NoSQL injection
- Command injection (RCE)
- LDAP injection
- XSS (Cross-Site Scripting)
- Template injection
- Path traversal

**Severity Classification**:

**CRITICAL**:
- SQL injection with data extraction
- Remote code execution via command injection
- Template injection with RCE capability

**HIGH**:
- SQL injection on authentication endpoints
- Command injection with limited impact
- NoSQL injection leading to data breach
- XSS with credential theft potential

**MEDIUM**:
- SQL injection on non-sensitive data
- Path traversal vulnerabilities
- LDAP injection
- XSS without session hijacking

**Detection Patterns**:

Python:
```python
# VULNERABLE: SQL injection
query = f"SELECT * FROM users WHERE id = {user_input}"

# SECURE: Parameterized query
query = "SELECT * FROM users WHERE id = ?"
cursor.execute(query, (user_input,))

# VULNERABLE: Command injection
os.system(f"ping {user_input}")

# SECURE: Input validation and sanitization
import shlex
safe_input = shlex.quote(user_input)
subprocess.run(['ping', safe_input], check=True)
```

JavaScript (Node.js):
```javascript
// VULNERABLE: SQL injection
const query = `SELECT * FROM users WHERE id = ${userId}`;

// SECURE: Parameterized query
const query = 'SELECT * FROM users WHERE id = ?';
db.execute(query, [userId]);

// VULNERABLE: Command injection
const { exec } = require('child_process');
exec(`ping ${userInput}`);

// SECURE: Input validation and sanitization
const { spawn } = require('child_process');
const sanitized = userInput.replace(/[^a-zA-Z0-9.-]/g, '');
spawn('ping', [sanitized]);
```

Java:
```java
// VULNERABLE: SQL injection
String query = "SELECT * FROM users WHERE id = " + userId;

// SECURE: Parameterized query (PreparedStatement)
String query = "SELECT * FROM users WHERE id = ?";
PreparedStatement stmt = connection.prepareStatement(query);
stmt.setString(1, userId);
ResultSet rs = stmt.executeQuery();

// VULNERABLE: Command injection
Runtime.getRuntime().exec("ping " + userInput);

// SECURE: Input validation and sanitization
ProcessBuilder pb = new ProcessBuilder("ping", sanitizedInput);
pb.start();
```

Go:
```go
// VULNERABLE: SQL injection
query := fmt.Sprintf("SELECT * FROM users WHERE id = %s", userID)

// SECURE: Parameterized query
query := "SELECT * FROM users WHERE id = ?"
row := db.QueryRow(query, userID)

// VULNERABLE: Command injection
cmd := exec.Command("ping", userInput)

// SECURE: Input validation
if !regexp.MustCompile(`^[a-zA-Z0-9.-]+$`).MatchString(userInput) {
    return errors.New("invalid input")
}
cmd := exec.Command("ping", userInput)
```

**Remediation**:
1. Use parameterized queries/prepared statements
2. Validate and sanitize all user inputs
3. Use ORM libraries that handle escaping
4. Implement input whitelisting where possible
5. Apply the principle of least privilege

---

### A04: Insecure Design

**Description**: Missing or ineffective control design. This represents flaws in the architecture or design phase rather than implementation.

**Common Vulnerabilities**:
- Missing rate limiting
- No input validation or sanitization
- Insecure default configurations
- Missing security headers
- Weak password policies

**Severity Classification**:

**CRITICAL**:
- No rate limiting on authentication endpoints
- Missing input validation on financial transactions
- Architectural flaws enabling complete system compromise

**HIGH**:
- Weak password policies allowing brute force
- Missing security controls on sensitive operations
- Insecure default configurations exposing data

**MEDIUM**:
- Missing security headers (CSP, X-Frame-Options)
- No rate limiting on API endpoints
- Insufficient input validation on non-critical data

**Detection Patterns**:

Python:
```python
# VULNERABLE: No rate limiting
@app.route('/api/login', methods=['POST'])
def login():
    return authenticate(request.form)

# SECURE: Rate limiting implemented
from flask_limiter import Limiter

limiter = Limiter(app, key_func=get_remote_address)

@app.route('/api/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    return authenticate(request.form)
```

JavaScript (Node.js/Express):
```javascript
// VULNERABLE: No rate limiting
app.post('/api/login', (req, res) => {
  authenticate(req.body);
});

// SECURE: Rate limiting with express-rate-limit
const rateLimit = require('express-rate-limit');

const loginLimiter = rateLimit({
  windowMs: 60 * 1000,  // 1 minute
  max: 5  // limit each IP to 5 requests per windowMs
});

app.post('/api/login', loginLimiter, (req, res) => {
  authenticate(req.body);
});
```

Java (Spring Boot):
```java
// VULNERABLE: No rate limiting
@PostMapping("/api/login")
public ResponseEntity<?> login(@RequestBody LoginRequest request) {
    return authenticate(request);
}

// SECURE: Rate limiting with Spring Security
@PostMapping("/api/login")
@RateLimiter(value = 5, timeoutDuration = "1m")
public ResponseEntity<?> login(@RequestBody LoginRequest request) {
    return authenticate(request);
}
```

**Remediation**:
1. Implement threat modeling during design phase
2. Add rate limiting on authentication endpoints
3. Use secure default configurations
4. Implement strong password policies
5. Add security headers (CSP, X-Frame-Options, etc.)

---

### A05: Security Misconfiguration

**Description**: Insecure default configurations, incomplete configurations, open cloud storage, misconfigured HTTP headers, and verbose error messages.

**Common Vulnerabilities**:
- Debug mode enabled in production
- Default credentials not changed
- Unnecessary services or features enabled
- Verbose error messages exposing information
- Directory listing enabled

**Severity Classification**:

**CRITICAL**:
- Debug mode enabled in production with remote code execution
- Default admin credentials on production systems
- Cloud storage buckets with public read/write access

**HIGH**:
- Debug mode exposing stack traces and environment data
- Default credentials on internal services
- Misconfigured CORS allowing credential theft

**MEDIUM**:
- Verbose error messages exposing internal information
- Unnecessary services or features enabled
- Directory listing enabled on web servers

**Detection Patterns**:

Python:
```python
# VULNERABLE: Debug mode in production
app.run(debug=True)

# SECURE: Debug mode controlled by environment
app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')

# VULNERABLE: Exposing stack traces
@app.errorhandler(Exception)
def handle_error(e):
    return str(e), 500

# SECURE: Generic error messages
@app.errorhandler(Exception)
def handle_error(e):
    logger.exception("Internal error")
    return {"error": "Internal server error"}, 500
```

JavaScript (Node.js/Express):
```javascript
// VULNERABLE: Debug mode in production
app.set('env', 'development');

// SECURE: Environment-based configuration
app.set('env', process.env.NODE_ENV || 'production');

// VULNERABLE: Exposing stack traces
app.use((err, req, res, next) => {
  res.status(500).json({ error: err.stack });
});

// SECURE: Generic error messages
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Internal server error' });
});
```

Java (Spring Boot):
```java
// VULNERABLE: Debug mode in production
@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
// With application.properties: spring.profiles.active=dev

// SECURE: Environment-based configuration
// application.properties: spring.profiles.active=prod
// Or use environment variable: SPRING_PROFILES_ACTIVE=prod

// VULNERABLE: Exposing stack traces
@ControllerAdvice
public class ErrorHandler {
    @ExceptionHandler(Exception.class)
    public ResponseEntity<String> handle(Exception e) {
        return ResponseEntity.status(500).body(e.getMessage());
    }
}

// SECURE: Generic error messages
@ControllerAdvice
public class ErrorHandler {
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, String>> handle(Exception e) {
        log.error("Internal error", e);
        return ResponseEntity.status(500)
            .body(Map.of("error", "Internal server error"));
    }
}
```

**Remediation**:
1. Disable debug mode in production
2. Change default credentials
3. Remove unnecessary features and services
4. Implement proper error handling
5. Disable directory listing
6. Use security hardening guides

---

### A06: Vulnerable and Outdated Components

**Description**: Using components with known vulnerabilities or failing to update dependencies in a timely manner.

**Common Vulnerabilities**:
- Outdated dependencies with known CVEs
- Unpatched libraries or frameworks
- End-of-life software
- Dependencies with known vulnerabilities

**Severity Classification**:

**CRITICAL**:
- Dependencies with actively exploited RCE vulnerabilities (CVSS 9.0+)
- End-of-life frameworks with unpatched critical vulnerabilities
- Known vulnerable crypto libraries

**HIGH**:
- Dependencies with high-severity CVEs (CVSS 7.0-8.9)
- Outdated frameworks with known security issues
- Unpatched authentication libraries

**MEDIUM**:
- Dependencies with medium-severity CVEs (CVSS 4.0-6.9)
- Outdated but still maintained packages
- Deprecated features with limited security impact

**Detection Patterns**:

Bash (Package Scanning):
```bash
# Check for vulnerable dependencies
npm audit
pip-audit
safety check
yarn audit

# Check package versions
npm outdated
pip list --outdated

# Python specific
pip-audit --desc

# Node.js specific
npm audit fix
npm audit fix --force  # breaking changes
```

JavaScript (Node.js - package.json):
```json
{
  "dependencies": {
    "express": "4.17.1",
    "lodash": "4.17.15",  // VULNERABLE: CVE-2020-8203
    "axios": "0.19.0"
  }
}

// SECURE: Update to patched versions
{
  "dependencies": {
    "express": "4.18.2",
    "lodash": "4.17.21",  // PATCHED
    "axios": "1.6.0"
  }
}
```

Python (requirements.txt):
```python
# VULNERABLE: Known CVE
django==2.2.0  # CVE-2019-12308, CVE-2019-14232
flask==1.0.0
requests==2.22.0

# SECURE: Updated versions
django==4.2.7
flask==3.0.0
requests==2.31.0
```

Java (Maven - pom.xml):
```xml
<!-- VULNERABLE: Known CVE -->
<dependency>
    <groupId>org.springframework</groupId>
    <artifactId>spring-core</artifactId>
    <version>5.2.0.RELEASE</version>  <!-- CVE-2022-22965 -->
</dependency>

<!-- SECURE: Updated version -->
<dependency>
    <groupId>org.springframework</groupId>
    <artifactId>spring-core</artifactId>
    <version>5.3.27</version>  <!-- PATCHED -->
</dependency>
```

Go (go.mod):
```go
// VULNERABLE: Known CVE
require (
    github.com/gin-gonic/gin v1.7.0  // CVE-2022-27665
)

// SECURE: Updated version
require (
    github.com/gin-gonic/gin v1.9.1  // PATCHED
)
```

**Remediation**:
1. Regularly update dependencies
2. Use automated dependency scanners (Snyk, Dependabot)
3. Remove unused dependencies
4. Subscribe to security advisories
5. Use only actively maintained packages

---

### A07: Identification and Authentication Failures

**Description**: Confirmation of user identity, authentication, and session management is critical for security.

**Common Vulnerabilities**:
- Weak password requirements
- Session fixation or hijacking
- Missing multi-factor authentication (MFA)
- Credential stuffing vulnerabilities
- Brute force protection missing

**Detection Patterns**:

```python
# VULNERABLE: Weak password requirements
def validate_password(password):
    return len(password) >= 4

# SECURE: Strong password requirements
def validate_password(password):
    if len(password) < 12:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*]", password):
        return False
    return True

# VULNERABLE: No brute force protection
@app.route('/login', methods=['POST'])
def login():
    return authenticate(request.form)

# SECURE: Brute force protection
from flask_limiter import Limiter

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    return authenticate(request.form)
```

**Remediation**:
1. Implement strong password policies
2. Use multi-factor authentication
3. Implement brute force protection
4. Use secure session management
5. Implement account lockout mechanisms
6. Use secure password reset flows

---

### A08: Software and Data Integrity Failures

**Description**: Code and infrastructure that does not protect against integrity violations.

**Common Vulnerabilities**:
- Untrusted data sources without validation
- Missing integrity checks on updates
- Unsigned software or packages
- Missing CI/CD pipeline security

**Detection Patterns**:

```python
# VULNERABLE: No integrity check on external data
import requests
data = requests.get(untrusted_url).json()

# SECURE: Verify integrity with signature
import hmac
data = requests.get(untrusted_url).content
signature = request.headers.get('X-Signature')
expected = hmac.new(SECRET_KEY, data, 'sha256').hexdigest()
if not hmac.compare_digest(signature, expected):
    raise ValueError('Invalid signature')
```

**Remediation**:
1. Verify integrity of updates and data
2. Use signed packages and commits
3. Implement CI/CD security controls
4. Use SAST/DAST in pipeline
5. Verify third-party components

---

### A09: Security Logging and Monitoring Failures

**Description**: Insufficient logging and monitoring, coupled with missing or ineffective integration with incident response.

**Common Vulnerabilities**:
- Missing security audit logs
- Sensitive data logged in plaintext
- Insufficient log retention
- No log monitoring or alerting
- Logs tamperable or deletable

**Detection Patterns**:

```python
# VULNERABLE: Sensitive data in logs
logger.info(f"User {username} logged in with password {password}")

# SECURE: No sensitive data in logs
logger.info(f"User {username} logged in successfully")

# VULNERABLE: No security event logging
def delete_user(user_id):
    User.delete(user_id)

# SECURE: Comprehensive security logging
def delete_user(user_id):
    logger.info(f"User deletion requested: user_id={user_id} by admin_id={current_user.id}")
    User.delete(user_id)
    logger.info(f"User deleted: user_id={user_id}")
```

**Remediation**:
1. Log all security-relevant events
2. Never log sensitive data (passwords, tokens)
3. Implement centralized log management
4. Set up monitoring and alerting
5. Ensure log integrity (append-only, tamper-proof)

---

### A10: Server-Side Request Forgery (SSRF)

**Description**: SSRF flaws occur when a web application fetches a remote resource without validating the user-supplied URL.

**Common Vulnerabilities**:
- Unsafe URL handling
- Blind SSRF vulnerabilities
- Internal network exposure
- Cloud metadata access

**Detection Patterns**:

```python
# VULNERABLE: Unsafe URL fetch
@app.route('/fetch')
def fetch_url():
    url = request.args.get('url')
    return requests.get(url).content

# SECURE: URL validation and whitelisting
from urllib.parse import urlparse

ALLOWED_DOMAINS = ['api.example.com', 'cdn.example.com']

@app.route('/fetch')
def fetch_url():
    url = request.args.get('url')
    parsed = urlparse(url)
    
    if parsed.hostname not in ALLOWED_DOMAINS:
        abort(403, "Domain not allowed")
    
    if parsed.scheme not in ['http', 'https']:
        abort(403, "Invalid scheme")
    
    return requests.get(url, timeout=5).content
```

**Remediation**:
1. Validate and sanitize all URLs
2. Implement URL whitelisting
3. Block requests to internal IPs
4. Disable unnecessary URL schemes
5. Use network segmentation
6. Implement rate limiting

---

### A11:2021 - Insecure Deserialization

**Description**: Insecure deserialization occurs when untrusted data is deserialized without proper validation, leading to remote code execution, object injection, authentication bypass, or denial of service attacks.

**Common Vulnerabilities**:
- Deserializing untrusted user input without validation
- Using insecure deserialization libraries (pickle, YAML.load, Marshal)
- Accepting serialized objects from untrusted sources
- Missing integrity checks on serialized data
- Deserializing objects with dangerous magic methods (__wakeup, __destruct)
- Using native serialization formats over network boundaries
- Allowing arbitrary class instantiation during deserialization

**Detection Patterns**:

Python:
```python
# VULNERABLE: pickle.loads with untrusted data
import pickle
data = request.get_data()
obj = pickle.loads(data)  # RCE vulnerability

# VULNERABLE: yaml.load without safe_load
import yaml
config = yaml.load(user_input)  # RCE via YAML tags

# VULNERABLE: marshal with untrusted data
import marshal
obj = marshal.loads(user_data)

# SECURE: Use JSON instead
import json
obj = json.loads(user_input)

# SECURE: Use yaml.safe_load
config = yaml.safe_load(user_input)
```

Java:
```java
// VULNERABLE: ObjectInputStream with untrusted data
ObjectInputStream ois = new ObjectInputStream(inputStream);
Object obj = ois.readObject();  // Deserialization RCE

// VULNERABLE: XMLDecoder with untrusted XML
XMLDecoder decoder = new XMLDecoder(new ByteArrayInputStream(xmlData));
Object obj = decoder.readObject();

// SECURE: Use JSON libraries (Jackson, Gson)
ObjectMapper mapper = new ObjectMapper();
MyObject obj = mapper.readValue(jsonString, MyObject.class);
```

JavaScript/Node.js:
```javascript
// VULNERABLE: node-serialize with untrusted JSON
var serialize = require('node-serialize');
var obj = serialize.unserialize(userJson);  // RCE via IIFE

// VULNERABLE: deserialize.js library
var deserialize = require('deserialize');
var obj = deserialize(userInput);

// SECURE: Use JSON.parse
const obj = JSON.parse(userJson);
```

PHP:
```php
// VULNERABLE: unserialize with user input
$obj = unserialize($_GET['data']);  // Object injection

// VULNERABLE: phar:// wrapper with untrusted phar files
$file = file_get_contents('phar://uploads/malicious.jpg');

// SECURE: Use JSON
$obj = json_decode($_GET['data'], true);
```

Ruby:
```ruby
# VULNERABLE: Marshal.load with untrusted data
obj = Marshal.load(user_data)  # RCE vulnerability

# VULNERABLE: YAML.load with untrusted YAML
config = YAML.load(user_yaml)  # Object injection

# SECURE: Use JSON
obj = JSON.parse(user_data)
```

**Severity Classification**:

**CRITICAL**:
- Remote Code Execution (RCE) via deserialization
- Authentication bypass through object injection
- Deserialization with known exploit chains (Apache Commons, Spring, etc.)

**HIGH**:
- Object injection with arbitrary class instantiation
- Deserialization leading to privilege escalation
- Insecure deserialization of authentication tokens

**MEDIUM**:
- Deserialization with limited gadget chains
- DoS via resource exhaustion during deserialization
- Deserialization without integrity checks

**Remediation Strategies**:
1. **Avoid Deserialization of Untrusted Data**: Use JSON or other simple data formats
2. **Implement Integrity Checks**: Use digital signatures (HMAC) before deserialization
3. **Use Safe Deserializers**: Prefer json.loads() over pickle.loads(), yaml.safe_load() over yaml.load()
4. **Whitelist Allowed Classes**: Restrict which classes can be instantiated during deserialization
5. **Input Validation**: Validate serialized data structure before deserialization
6. **Patch Dependencies**: Keep serialization libraries updated to prevent gadget chain exploits
7. **Sandbox Deserialization**: Run deserialization in isolated environments

**Detection Regex Patterns**:
```regex
# Python pickle
pickle\.loads?\(
pickle\.Unpickler

# Python yaml unsafe
yaml\.load\((?!.*Loader)
yaml\.unsafe_load

# Python marshal
marshal\.loads?\(

# Java ObjectInputStream
ObjectInputStream
readObject\(\)

# Java XMLDecoder
XMLDecoder
readObject\(\)

# PHP unserialize
unserialize\(

# Node.js node-serialize
unserialize\(

# Ruby Marshal
Marshal\.load

# .NET BinaryFormatter
BinaryFormatter
Deserialize\(
```

**Example Vulnerability Report**:
```json
{
  "id": "SEC-DES-001",
  "severity": "CRITICAL",
  "category": "OWASP_A11_INSECURE_DESERIALIZATION",
  "cwe": "CWE-502",
  "title": "Insecure Deserialization in pickle.loads()",
  "file": "api/handler.py",
  "line": 45,
  "code_snippet": "obj = pickle.loads(request.data)",
  "description": "Untrusted user input deserialized using Python pickle module, allowing arbitrary code execution",
  "impact": "Remote code execution, full system compromise, data exfiltration",
  "remediation": "Use safe serialization formats (JSON) or implement digital signatures",
  "references": [
    "https://owasp.org/www-community/vulnerabilities/Insecure_deserialization",
    "https://cwe.mitre.org/data/definitions/502.html",
    "https://portswigger.net/web-security/deserialization"
  ]
}
```

---

## Detection Tools and Techniques

### Automated Scanning
- **SAST Tools**: SonarQube, Semgrep, Bandit (Python), ESLint Security
- **Dependency Scanners**: npm audit, pip-audit, Snyk, Dependabot
- **Secret Detection**: git-secrets, truffleHog, detect-secrets

### Manual Testing
1. Review authentication and authorization flows
2. Test input validation with malicious payloads
3. Check for hardcoded secrets and credentials
4. Verify encryption and cryptographic implementations
5. Test session management mechanisms
6. Review error handling for information disclosure
7. Check security headers and CORS policies

### Code Review Checklist
- [ ] All user inputs are validated and sanitized
- [ ] Parameterized queries used for database access
- [ ] No hardcoded secrets or credentials
- [ ] Strong cryptographic algorithms used
- [ ] Authentication and authorization checks in place
- [ ] Proper error handling without information disclosure
- [ ] Security headers configured
- [ ] Rate limiting implemented
- [ ] Logging and monitoring in place
- [ ] Dependencies are up-to-date

---

## References

- [OWASP Top 10 - 2021](https://owasp.org/Top10/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [CWE - Common Weakness Enumeration](https://cwe.mitre.org/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [PortSwigger Web Security Academy](https://portswigger.net/web-security)

---

## Quick Reference: CWE Mapping

| OWASP Category | Primary CWE |
|----------------|-------------|
| A01: Broken Access Control | CWE-284, CWE-285, CWE-287 |
| A02: Cryptographic Failures | CWE-261, CWE-327, CWE-328 |
| A03: Injection | CWE-78, CWE-89, CWE-94 |
| A04: Insecure Design | CWE-73, CWE-209, CWE-213 |
| A05: Security Misconfiguration | CWE-16, CWE-209, CWE-384 |
| A06: Vulnerable Components | CWE-937, CWE-1035 |
| A07: Authentication Failures | CWE-287, CWE-306, CWE-307 |
| A08: Integrity Failures | CWE-353, CWE-426, CWE-494 |
| A09: Logging Failures | CWE-117, CWE-223, CWE-532 |
| A10: SSRF | CWE-918 |
| A11: Insecure Deserialization | CWE-502 |
