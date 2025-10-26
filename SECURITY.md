# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 2.4.x   | :white_check_mark: |
| 2.3.x   | :white_check_mark: |
| < 2.3   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please do the following:

1. **Do not open a public issue** - Report security vulnerabilities privately.
2. Email us at security@ok-tools.org with the details.
3. Include the following information in your report:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any possible mitigations you've identified

We will acknowledge your report within 48 hours and work on a fix promptly.

## Security Measures

### Dependency Scanning
We use `pip-audit` in our CI/CD pipeline to automatically scan for known vulnerabilities in our dependencies. This helps us identify and address security issues before they can be exploited.

### Authentication and Authorization
- Token-based API authentication with rate limiting
- Role-based access control for admin interfaces
- CSRF protection enabled
- XSS protection headers

### Data Protection
- GDPR-compliant data handling
- Privacy controls for user data
- Secure storage of sensitive information