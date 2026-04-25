---
name: Security: Severity Classification
description: |
  Vulnerability severity classification framework for security audits and code reviews.
  Use when: Security audits, vulnerability reporting, risk assessment, code review prioritization, security issue triage.
  
  Covers: CVSS scoring methodology, severity levels (CRITICAL/HIGH/MEDIUM/LOW/INFO), 
  priority timeframes, exploitability assessment criteria, and remediation SLAs.
---

# Security Severity Classification Framework

## Overview

This skill provides a standardized severity classification system for security vulnerabilities and code quality issues. It combines industry-standard CVSS scoring with practical prioritization timeframes to help teams triage and remediate issues effectively.

---

## Severity Levels

### 🔴 CRITICAL

**Definition**: Vulnerabilities that can lead to immediate system compromise, data breach, or complete takeover.

**Security Examples**:
- Remote code execution (RCE)
- SQL injection with authentication bypass
- Hardcoded admin credentials
- Critical CVE with CVSS 9.0+
- Exposed database credentials
- Authentication bypass vulnerabilities
- Arbitrary file upload leading to RCE
- Deserialization attacks with exploit chains

**Code Quality Examples**:
- Null pointer exceptions in critical paths
- Uncaught exceptions causing crashes
- Data corruption risks
- Race conditions in financial transactions
- Breaking API changes

**Priority Timeframe**: 
- ⚠️ **Fix IMMEDIATELY** (within 24 hours)
- Emergency patching required
- Production deployment blocked until fixed

**CVSS Range**: 9.0 - 10.0

**Business Impact**: 
- Complete system compromise
- Massive data breach
- Financial loss
- Reputation damage
- Regulatory violations (GDPR, HIPAA, PCI-DSS)

---

### 🟠 HIGH

**Definition**: Vulnerabilities that can lead to significant security breaches or serious code quality issues.

**Security Examples**:
- SQL injection without auth bypass
- XSS in authenticated pages
- SSRF with internal network access
- Broken authentication mechanisms
- Sensitive data exposure
- HIGH CVE with CVSS 7.0-8.9
- Privilege escalation vulnerabilities
- Insecure deserialization
- Path traversal attacks
- XXE (XML External Entity) attacks

**Code Quality Examples**:
- Missing authentication/authorization checks
- Memory leaks in long-running processes
- Improper error handling exposing sensitive data
- Insufficient input validation
- Insecure direct object references

**Priority Timeframe**: 
- ⚠️ **Fix within 24-48 hours**
- Hotfix or emergency release
- Cannot wait for next sprint

**CVSS Range**: 7.0 - 8.9

**Business Impact**:
- Data breach risk
- Unauthorized access to sensitive data
- Service degradation
- Compliance violations

---

### 🟡 MEDIUM

**Definition**: Vulnerabilities with limited impact or code quality issues affecting maintainability.

**Security Examples**:
- Missing security headers (CSP, HSTS, X-Frame-Options)
- Weak password policies
- Information disclosure in error messages
- MEDIUM CVE with CVSS 4.0-6.9
- Deprecated/insecure API usage
- Session management weaknesses
- Missing rate limiting (non-auth endpoints)
- Verbose error messages

**Code Quality Examples**:
- High cyclomatic complexity (>15)
- Functions longer than 50 lines
- Deep nesting (>3 levels)
- DRY violations (code duplication)
- Missing error handling
- Poor naming conventions
- Missing type hints/annotations

**Priority Timeframe**: 
- 📅 **Fix within 1-2 weeks**
- Include in next sprint
- Standard remediation timeline

**CVSS Range**: 4.0 - 6.9

**Business Impact**:
- Reduced code maintainability
- Increased technical debt
- Potential for future security issues
- Developer productivity impact

---

### 🟢 LOW

**Definition**: Minor vulnerabilities or code quality issues with minimal direct impact.

**Security Examples**:
- Missing rate limiting on non-sensitive endpoints
- Verbose error messages (non-sensitive info)
- Outdated dependencies (no known CVE)
- Debug code left in comments
- Missing HTTPOnly flag on cookies
- Insecure cookie settings (without Secure flag)

**Code Quality Examples**:
- Inconsistent code style
- Magic numbers in code
- Missing docstrings
- Poor variable names
- Minor refactoring opportunities
- Test coverage gaps (non-critical paths)

**Priority Timeframe**: 
- 📋 **Backlog for next sprint**
- Fix when convenient
- No immediate pressure

**CVSS Range**: 0.1 - 3.9

**Business Impact**:
- Minimal direct impact
- Accumulates as technical debt
- May enable future attacks

---

### ℹ️ INFO

**Definition**: Best practices recommendations, improvements, and informational findings.

**Examples**:
- Security improvements (defense in depth)
- Configuration suggestions
- Performance optimizations
- Best practice recommendations
- Documentation improvements
- Code style suggestions
- Enhanced logging recommendations

**Priority Timeframe**: 
- 📝 **Address when convenient**
- Optional improvements
- Low priority backlog items

**CVSS Range**: N/A (informational)

**Business Impact**:
- Improves overall security posture
- Enhances code quality
- Reduces future risk

---

## CVSS (Common Vulnerability Scoring System) Framework

### Overview

CVSS provides a standardized method for rating vulnerability severity. The score ranges from 0.0 to 10.0 and is calculated based on multiple metrics.

### CVSS v3.1 Scoring Metrics

**Base Score Metrics**:

1. **Attack Vector (AV)** - How the vulnerability is exploited
   - Network (AV:N) - Exploitable remotely
   - Adjacent (AV:A) - Local network only
   - Local (AV:L) - Requires local access
   - Physical (AV:P) - Requires physical access

2. **Attack Complexity (AC)** - Complexity of the attack
   - Low (AC:L) - Specialized conditions not required
   - High (AC:H) - Specialized conditions required

3. **Privileges Required (PR)** - Level of privileges needed
   - None (PR:N) - No authentication required
   - Low (PR:L) - Basic user privileges
   - High (PR:H) - Admin/privileged access

4. **User Interaction (UI)** - User interaction required
   - None (UI:N) - No interaction required
   - Required (UI:R) - User interaction required

5. **Scope (S)** - Impact beyond vulnerable component
   - Unchanged (S:U) - Affects only vulnerable component
   - Changed (S:C) - Affects other components

6. **Impact Metrics** - Confidentiality, Integrity, Availability
   - High (H) - Total impact
   - Low (L) - Limited impact
   - None (N) - No impact

### CVSS Severity Ratings

| Severity | CVSS Score | Priority |
|----------|------------|----------|
| Critical | 9.0 - 10.0 | Immediate |
| High | 7.0 - 8.9 | 24-48 hours |
| Medium | 4.0 - 6.9 | 1-2 weeks |
| Low | 0.1 - 3.9 | Backlog |
| None | 0.0 | N/A |

### CVSS Calculator

Use the official CVSS calculator: https://www.first.org/cvss/calculator/3.1

**Example CVSS Vector**:
```
CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
```
- Attack Vector: Network
- Attack Complexity: Low
- Privileges Required: None
- User Interaction: None
- Scope: Unchanged
- Confidentiality Impact: High
- Integrity Impact: High
- Availability Impact: High
- **CVSS Score: 9.8 (CRITICAL)**

---

## Exploitability Assessment Criteria

### High Exploitability

Vulnerability is highly exploitable when:
- ✅ Public exploit code available
- ✅ Active exploitation in the wild
- ✅ Easy to exploit (no specialized skills needed)
- ✅ Exploitable over the network
- ✅ No authentication required
- ✅ Reliable exploit chain exists
- ✅ No user interaction required
- ✅ Exploitation tools readily available

**Action**: Upgrade severity by 1 level (e.g., HIGH → CRITICAL)

### Medium Exploitability

Vulnerability has moderate exploitability when:
- ⚠️ Theoretical exploit exists
- ⚠️ Requires some skill to exploit
- ⚠️ Limited public information
- ⚠️ Requires authenticated access
- ⚠️ Some user interaction required
- ⚠️ Exploitation possible but complex

**Action**: Keep current severity level

### Low Exploitability

Vulnerability has low exploitability when:
- ℹ️ No known exploits
- ℹ️ Requires highly specialized skills
- ℹ️ Requires physical access
- ℹ️ Multiple conditions must align
- ℹ️ Unlikely to be exploited in practice
- ℹ️ Significant barriers to exploitation

**Action**: Consider downgrading severity by 1 level (e.g., HIGH → MEDIUM)

---

## Priority Timeframes & SLAs

### Remediation Service Level Agreements (SLAs)

| Severity | Initial Response | Fix Deadline | Escalation |
|----------|------------------|--------------|------------|
| **CRITICAL** | 1 hour | 24 hours | Immediate escalation to security team and management |
| **HIGH** | 4 hours | 48 hours | Escalate to security team lead |
| **MEDIUM** | 24 hours | 2 weeks | Escalate if not addressed in sprint |
| **LOW** | 1 week | Next quarter | Review in backlog grooming |
| **INFO** | 2 weeks | No deadline | Optional improvement |

### Escalation Path

1. **CRITICAL Issues**:
   - Notify: Security team → Engineering manager → CTO/VP Engineering
   - Block: Production deployments
   - Action: Emergency patch/hotfix

2. **HIGH Issues**:
   - Notify: Security team → Tech lead
   - Block: Release candidate
   - Action: Hotfix or next release

3. **MEDIUM Issues**:
   - Notify: Development team
   - Block: None
   - Action: Sprint planning

4. **LOW/INFO Issues**:
   - Notify: Development team (optional)
   - Block: None
   - Action: Backlog prioritization

---

## Severity Classification Decision Tree

```
START
  │
  ├─ Can lead to RCE, full system compromise, or critical CVE (9.0+)?
  │   └─ YES → CRITICAL ⚠️
  │   └─ NO ↓
  │
  ├─ Can lead to data breach, auth bypass, or HIGH CVE (7.0-8.9)?
  │   └─ YES → HIGH 🟠
  │   └─ NO ↓
  │
  ├─ Can lead to limited data exposure, MEDIUM CVE (4.0-6.9), or code quality issues?
  │   └─ YES → MEDIUM 🟡
  │   └─ NO ↓
  │
  ├─ Minor security weakness or LOW CVE (0.1-3.9)?
  │   └─ YES → LOW 🟢
  │   └─ NO ↓
  │
  └─ Best practice recommendation or improvement?
      └─ YES → INFO ℹ️
```

---

## OWASP Risk Rating Methodology

In addition to CVSS, consider OWASP risk factors:

### Likelihood Factors
- **Threat Agent**: How likely is an attack?
  - Skill level required
  - Motivation
  - Opportunity
  - Size of threat agent group

- **Vulnerability**: How easy is it to exploit?
  - Ease of discovery
  - Ease of exploit
  - Awareness
  - Intrusion detection

### Impact Factors
- **Technical Impact**:
  - Loss of confidentiality
  - Loss of integrity
  - Loss of availability
  - Loss of accountability

- **Business Impact**:
  - Financial damage
  - Reputation damage
  - Non-compliance
  - Privacy violation

### Risk Rating Matrix

| Likelihood \ Impact | High | Medium | Low |
|---------------------|------|--------|-----|
| **High** | CRITICAL | HIGH | MEDIUM |
| **Medium** | HIGH | MEDIUM | LOW |
| **Low** | MEDIUM | LOW | INFO |

---

## Special Considerations

### Context-Dependent Severity

Severity may be adjusted based on:

1. **Production vs Development**
   - Production issues: Higher priority
   - Development/Test: Lower priority

2. **Public-Facing vs Internal**
   - Public-facing: Higher risk
   - Internal-only: Lower risk (but still important)

3. **Regulatory Requirements**
   - HIPAA, PCI-DSS, GDPR compliance: Higher priority
   - Non-regulated: Standard priority

4. **Business Criticality**
   - Payment systems, authentication: Higher priority
   - Internal tools: Lower priority

5. **Data Sensitivity**
   - PII, financial data, health records: Higher priority
   - Public data: Lower priority

### Compound Vulnerabilities

When multiple vulnerabilities exist:
- Assess each vulnerability independently
- Consider attack chains (vulnerability combination)
- Report combined risk in executive summary
- May increase overall severity rating

### False Positive Handling

If suspected false positive:
1. Document the finding
2. Mark as "Requires Manual Review"
3. Provide reasoning for false positive suspicion
4. Do not remove from report until confirmed
5. Adjust severity if confirmed false positive

---

## Reporting Standards

### Required Information per Finding

Every vulnerability finding must include:

1. **Unique Identifier** (e.g., SEC-001)
2. **Severity Level** (CRITICAL/HIGH/MEDIUM/LOW/INFO)
3. **CVSS Score** (for security vulnerabilities)
4. **CVSS Vector** (for reproducibility)
5. **Category** (OWASP, CWE)
6. **Title/Summary**
7. **Affected Component** (file, endpoint, service)
8. **Description** (what is the issue)
9. **Impact** (business and technical impact)
10. **Remediation** (how to fix)
11. **References** (OWASP, CWE, vendor advisories)

### JSON Format for Findings

```json
{
  "id": "SEC-001",
  "severity": "CRITICAL",
  "cvss_score": 9.8,
  "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
  "category": "OWASP_A03_INJECTION",
  "cwe": "CWE-89",
  "title": "SQL Injection in User Search",
  "file": "api/search.py",
  "line": 42,
  "description": "User input directly concatenated into SQL query",
  "impact": "Full database access, data exfiltration, authentication bypass",
  "exploitability": "High - no authentication required, publicly documented",
  "remediation": "Use parameterized queries or ORM",
  "references": [
    "https://owasp.org/www-community/attacks/SQL_Injection",
    "https://cwe.mitre.org/data/definitions/89.html"
  ],
  "sla": "24 hours",
  "assigned_to": "security-team",
  "status": "open"
}
```

---

## Quick Reference Card

### Severity at a Glance

| Severity | Icon | CVSS | Timeframe | Impact |
|----------|------|------|-----------|---------|
| CRITICAL | 🔴 | 9.0-10.0 | 24h | System compromised |
| HIGH | 🟠 | 7.0-8.9 | 48h | Data breach risk |
| MEDIUM | 🟡 | 4.0-6.9 | 2 weeks | Limited exposure |
| LOW | 🟢 | 0.1-3.9 | Backlog | Minor weakness |
| INFO | ℹ️ | N/A | Optional | Best practice |

### Decision Checklist

- [ ] Can attacker execute arbitrary code? → **CRITICAL**
- [ ] Can attacker bypass authentication? → **CRITICAL**
- [ ] Can attacker access sensitive data? → **HIGH**
- [ ] Can attacker escalate privileges? → **HIGH**
- [ ] Does it violate security best practices? → **MEDIUM**
- [ ] Is it a code smell or maintainability issue? → **MEDIUM/LOW**
- [ ] Is it a minor improvement? → **LOW/INFO**

---

## Resources

### Standards & Frameworks
- **CVSS v3.1**: https://www.first.org/cvss/v3.1/specification-document
- **OWASP Risk Rating**: https://owasp.org/www-community/OWASP_Risk_Rating_Methodology
- **CWE (Common Weakness Enumeration)**: https://cwe.mitre.org/
- **NIST CVE**: https://nvd.nist.gov/

### Tools
- **CVSS Calculator**: https://www.first.org/cvss/calculator/3.1
- **OWASP ZAP**: https://www.zaproxy.org/
- **SonarQube**: https://www.sonarqube.org/
- **Snyk**: https://snyk.io/

---

**Last Updated**: 2026-03-04
**Maintained By**: Security Team
**Version**: 1.0.0
