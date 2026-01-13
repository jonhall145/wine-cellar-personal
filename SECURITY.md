# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do NOT open a public GitHub issue** for security vulnerabilities
2. Email your report to the maintainers (see [AUTHORS](AUTHORS) or repository owner profile)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Initial assessment**: Within 1 week
- **Resolution timeline**: Depends on severity, typically 2-4 weeks
- **Credit**: You will be credited in the release notes (unless you prefer anonymity)

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| Critical | Remote code execution, authentication bypass | 24-48 hours |
| High | Data exposure, privilege escalation | 1 week |
| Medium | Cross-site scripting, CSRF | 2 weeks |
| Low | Information disclosure, minor issues | 4 weeks |

## Security Best Practices

When deploying Wine Cellar:

### Production Checklist

- [ ] Set `DJANGO_DEBUG=False`
- [ ] Use a strong, unique `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Set up HTTPS with valid certificates
- [ ] Use PostgreSQL (not SQLite) for production
- [ ] Keep dependencies updated
- [ ] Enable Django's security middleware
- [ ] Configure proper CSRF and session cookies

### Environment Variables

Never commit sensitive values. Use `.env` files (gitignored) or environment variables:

```bash
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@host:5432/db
EMAIL_HOST_PASSWORD=your-password
```

### Database Security

- Use strong, unique database passwords
- Restrict database network access
- Enable SSL for database connections
- Regular backups (see [docs/backup.md](docs/backup.md))

### Authentication

- Django's password hashing is secure by default (PBKDF2)
- Session cookies are HTTP-only and secure in production
- Consider enabling rate limiting for login attempts

## Known Security Considerations

### Self-Hosted Nature

Wine Cellar is designed for self-hosting. Users are responsible for:

- Server security and updates
- Network configuration and firewalls
- SSL/TLS certificate management
- Backup and disaster recovery

### Third-Party Dependencies

- Dependencies are managed via `requirements.txt` and `package.json`
- Renovate is configured for automated security updates
- Review dependency changes before deploying

## Security Features

Wine Cellar includes:

- **CSRF Protection**: Django's built-in CSRF middleware
- **SQL Injection Prevention**: Django ORM parameterized queries
- **XSS Protection**: Template auto-escaping
- **Clickjacking Protection**: X-Frame-Options header
- **Content Type Sniffing Protection**: X-Content-Type-Options header
- **User Data Isolation**: Queries filtered by authenticated user

## Disclosure Policy

- We will acknowledge receipt of your report
- We will investigate and validate the issue
- We will work on a fix and prepare a release
- We will publicly disclose the issue after a fix is available
- We will credit researchers who report valid vulnerabilities

Thank you for helping keep Wine Cellar secure!
