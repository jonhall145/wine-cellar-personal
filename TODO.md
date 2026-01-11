# Wine Cellar - To-Do List of Issues to Fix

This document outlines identified issues, improvements, and technical debt items that should be addressed to improve the Wine Cellar project's code quality, security, maintainability, and user experience.

**Generated:** 2025-12-27  
**Version:** 0.3.0-rc.0

**Note:** Hardcoded credentials in settings files are development placeholders and not considered security issues.

---

## 🔴 High Priority - Security & Critical Issues

### ~~1. Wildcard Imports in Settings Files~~ ✅ DONE
**Files:**
- `wine_cellar/conf/prod.py`
- `wine_cellar/conf/test.py`

**Status:** Already uses explicit imports - no wildcard imports present.

### 2. Production Setup Marked as "Under Development"
**File:** `docs/deployment.md`  
**Issue:** Production deployment documentation states "This setup is under development. Proceed with caution."  
**Risk:** May indicate incomplete or untested production deployment process  
**Fix:**
- Thoroughly test production deployment process
- Document all production-ready configurations
- Remove warning once production setup is validated
- Add production deployment checklist

---

## 🟡 Medium Priority - Code Quality & Technical Debt

### ~~3. Fix Hacky Form Step Workaround~~ ✅ DONE
**Status:** No FIXME comments exist in codebase - issue has been resolved.

### ~~4. Missing Test Target in Makefile~~ ✅ DONE
**Status:** `make test` target exists as alias to `pytest`.

### 5. Improve Test Coverage
**Current Status:** 16 test files covering main functionality  
**Issue:** Unknown test coverage percentage, potential gaps in testing  
**Fix:**
- Run coverage report to identify untested code paths
- Add tests for:
  - Barcode scanning functionality
  - Email notification system
  - Image upload/delete operations
  - User settings management
  - Edge cases in wine filtering and sorting
- Set minimum coverage threshold (e.g., 80%)

### ~~6. Missing API Documentation~~ ✅ DONE
**Status:** API documentation exists in `docs/api.md`.

### 7. No Database Backup/Restore Documentation
**Issue:** Missing documentation for backup and restore procedures  
**Impact:** Risk of data loss without clear backup strategy  
**Fix:**
- Add docs/backup.md with:
  - Database backup procedures for PostgreSQL
  - Media files backup (wine images)
  - Restore procedures
  - Recommended backup schedules

---

## 🟢 Low Priority - Enhancements & Nice-to-Have

### 8. Add Pre-commit Hooks Configuration File
**Issue:** Husky is configured but no documented pre-commit hooks setup  
**Fix:**
- Add `.pre-commit-config.yaml` for Python developers not using npm
- Document pre-commit hook setup in setup.md
- Include black, isort, flake8 in pre-commit configuration

### 9. Improve Error Handling in Views
**Issue:** Generic error handling in views, may not provide clear feedback  
**Fix:**
- Add custom error pages (400, 403, 404, 500)
- Improve error messages for common user errors
- Add logging for debugging production issues
- Consider using Django's message framework more extensively

### ~~10. Add Health Check Endpoint~~ ✅ DONE
**Status:** `/health/` endpoint exists with database, disk space, and Celery status checks.

### 11. Internationalization Improvements
**Current Status:** German locale files present but incomplete  
**Fix:**
- Complete German translations
- Add language switcher in UI
- Document translation contribution process
- Consider adding more languages

### 12. Performance Optimization Opportunities
**Areas to investigate:**
- Add database query optimization (check for N+1 queries)
- Implement Django caching framework
- Add pagination limits to prevent large queries
- Consider adding database indexes for frequently filtered fields
- Optimize wine image serving (thumbnails, lazy loading)

### 14. Accessibility Improvements
**Issue:** No documented accessibility testing or WCAG compliance  
**Fix:**
- Run accessibility audit (e.g., with Lighthouse, axe)
- Add ARIA labels where needed
- Ensure keyboard navigation works throughout app
- Test with screen readers
- Add accessibility documentation

### 15. Mobile Responsiveness Review
**Issue:** Unknown state of mobile responsiveness  
**Fix:**
- Test all pages on mobile devices
- Ensure barcode scanner works on mobile
- Optimize map view for mobile
- Add viewport meta tags if missing
- Test touch interactions

### 16. Add Contributing Guidelines
**File:** Create `CONTRIBUTING.md`  
**Contents:**
- Code of conduct
- How to submit issues
- Pull request process
- Code style guidelines
- Testing requirements
- Commit message format (conventional commits)
- Development setup instructions

### 17. Add Security Policy
**File:** Create `SECURITY.md`  
**Contents:**
- How to report security vulnerabilities
- Security update policy
- Supported versions
- Response timeline

### ~~18. Improve Logging Strategy~~ ✅ DONE
**Status:** Comprehensive logging configured in `settings.py` with verbose formatters,
console/mail handlers, and dedicated wine_cellar/audit loggers.

### ~~19. Add Rate Limiting~~ ✅ DONE
**Status:** Rate limiting implemented:
- Login/signup via `ACCOUNT_RATE_LIMITS` in settings (5/min/ip)
- Wine vision extraction: 10/min/user
- Barcode scanning: 30/min/user
- Wine creation: 20/min/user

---

## 📋 Documentation Improvements

### 20. Add Architecture Documentation
**File:** Create `docs/architecture.md`  
**Contents:**
- System architecture diagram
- Data flow diagrams
- Database schema diagram
- Component interactions
- Technology stack rationale

### 21. Improve README.md
**Enhancements:**
- Add badges for build status, coverage, version
- Add quick start section
- Add screenshots/demo GIF
- Add FAQ section
- Add troubleshooting section
- Link to live demo if available

### 22. Add API Reference Documentation
**File:** Create `docs/api.md`  
**Contents:**
- List all AJAX endpoints
- Request/response formats
- Authentication requirements
- Example curl commands

### 23. Document Environment Variables
**File:** Create `docs/configuration.md`  
**Contents:**
- Complete list of all environment variables
- Default values
- Required vs optional
- Examples for different deployment scenarios

### 24. Add Upgrade Guide
**File:** Create `docs/upgrading.md`  
**Contents:**
- Version upgrade procedures
- Breaking changes between versions
- Database migration procedures
- Rollback procedures

---

## 🔧 Dependency & Build Improvements

### 25. Add Dependency License Checker
**Issue:** No automated license compliance checking  
**Fix:**
- Add tool to check dependency licenses
- Ensure all dependencies are compatible with AGPL-3.0
- Document license information

### 27. Add SBOM Generation
**Issue:** No Software Bill of Materials  
**Fix:**
- Generate SBOM for security/compliance
- Use tools like syft or cyclonedx
- Include in release artifacts

### 28. Review and Update Dependencies
**Note:** Renovate is configured for automated updates  
**Action items:**
- Review current dependency versions
- Test major version upgrades in staging
- Document any breaking changes from upgrades

---

## 🎨 UI/UX Improvements

### 29. Add Loading States
**Issue:** No visible loading indicators for async operations  
**Fix:**
- Add spinners for barcode scanning
- Add loading states for form submissions
- Add skeleton screens for data loading

### 30. Improve Empty States
**Issue:** Unknown quality of empty states (no wines, no stock)  
**Fix:**
- Add helpful empty state messages
- Include call-to-action buttons
- Add illustrations or icons

### 31. Add Data Export Functionality
**Enhancement:** Allow users to export their wine data  
**Fix:**
- Add CSV/JSON export for wine list
- Add PDF export for individual wine details
- Add backup export (all user data)

### 32. Add Bulk Operations
**Enhancement:** Support bulk actions on wines  
**Fix:**
- Bulk delete wines
- Bulk update categories
- Bulk stock updates
- Add selection UI to wine list

---

## 🔐 Security Hardening

### 33. Add Content Security Policy (CSP)
**Issue:** No CSP headers configured  
**Fix:**
- Configure django-csp or similar
- Set strict CSP policy
- Test with inline scripts
- Document CSP configuration

### ~~34. Add Security Headers~~ ✅ DONE
**Status:** Security headers configured in `settings.py`:
- X_FRAME_OPTIONS = "DENY"
- SECURE_CONTENT_TYPE_NOSNIFF = True
- SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
- SECURE_BROWSER_XSS_FILTER = True

### 35. Implement Password Strength Requirements
**Issue:** No documented password policy  
**Fix:**
- Configure Django password validators
- Add password strength meter in UI
- Document password requirements
- Consider adding 2FA support

### 36. Add Audit Logging
**Enhancement:** Track security-relevant events  
**Fix:**
- Log login attempts (success/failure)
- Log password changes
- Log user creation/deletion
- Log permission changes
- Store logs securely

---

## 🧪 Testing Improvements

### 37. Add End-to-End Tests
**Issue:** No E2E tests for critical user flows  
**Fix:**
- Add Selenium or Playwright tests
- Test critical flows:
  - User registration and login
  - Wine creation workflow
  - Barcode scanning
  - Stock management
- Run E2E tests in CI

### 38. Add Performance Tests
**Issue:** No performance benchmarks  
**Fix:**
- Add load testing (e.g., with Locust)
- Test database query performance
- Test concurrent user scenarios
- Document performance benchmarks

### 39. Add Visual Regression Testing
**Enhancement:** Catch unintended UI changes  
**Fix:**
- Add Percy or BackstopJS
- Create baseline screenshots
- Run on every PR

---

## 📊 Monitoring & Observability

### 40. Add Application Monitoring
**Enhancement:** Better production visibility  
**Fix:**
- Integrate with Sentry for error tracking
- Add performance monitoring (APM)
- Track user metrics
- Document monitoring setup

### 41. Add Database Monitoring
**Enhancement:** Track database health  
**Fix:**
- Monitor query performance
- Track connection pool usage
- Alert on slow queries
- Document database monitoring

---

## 🚀 Deployment & Infrastructure

### 42. Add Deployment Automation
**Enhancement:** Simplify deployment process  
**Fix:**
- Add deployment scripts
- Document zero-downtime deployment
- Add rollback procedures
- Consider adding staging environment

### 43. Add Database Migration Testing
**Issue:** No documented migration testing process  
**Fix:**
- Test migrations on production-like data
- Document migration rollback procedures
- Add migration safety checks
- Consider using django-migration-linter

---

## 🌟 Feature Completeness

### 45. Complete Email Notification System
**Status:** Drink-by reminders mentioned but implementation unclear  
**Fix:**
- Ensure email templates exist and are tested
- Add email preview functionality
- Test with different email providers
- Add email notification preferences

### 46. Add Wine Recommendation System
**Enhancement:** Suggest wines based on user preferences  
**Fix:**
- Implement basic recommendation algorithm
- Based on ratings, wine types, regions
- Add "wines you might like" section

### 47. Add Wine Statistics Dashboard
**Enhancement:** More analytics for users  
**Fix:**
- Add charts for wine types, regions, vintages
- Show spending over time
- Display collection value trends
- Add export for statistics

---

## Priority Summary

**Should Address Soon (Quality):**
- ~~#1 - Wildcard imports~~ ✅ DONE
- ~~#3 - Form step workaround~~ ✅ DONE
- #5 - Test coverage
- ~~#19 - Rate limiting~~ ✅ DONE

**Good to Have (Enhancements):**
- ~~#10 - Health check endpoint~~ ✅ DONE
- #20-24 - Documentation improvements
- #31 - Data export
- #40 - Application monitoring

**Nice to Have (Future):**
- #46 - Recommendation system
- #47 - Statistics dashboard
- #39 - Visual regression testing

---

*This to-do list should be prioritized based on team capacity, user needs, and business requirements. Items should be converted to GitHub Issues for tracking and assignment.*
