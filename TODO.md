# Wine Cellar - To-Do List of Issues to Fix

This document outlines identified issues, improvements, and technical debt items that should be addressed to improve the Wine Cellar project's code quality, security, maintainability, and user experience.

**Updated:** 2026-01-11
**Version:** 0.3.0-rc.0

**Note:** Hardcoded credentials in settings files are development placeholders and not considered security issues.

---

## 🔴 High Priority - Security & Critical Issues

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

### 5. Improve Test Coverage
**Current Status:** 67% coverage (target: 80%)
**Issue:** Main gap in `views.py` at 52% coverage
**Fix:**
- Add tests for:
  - Barcode scanning functionality
  - Email notification system
  - Image upload/delete operations
  - User settings management
  - Edge cases in wine filtering and sorting
- Increase coverage to 80% minimum

---

## 🟢 Low Priority - Enhancements & Nice-to-Have

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
- #5 - Test coverage (67% → 80%)
- #33 - Content Security Policy

**Good to Have (Enhancements):**
- #31 - Data export
- #40 - Application monitoring

**Nice to Have (Future):**
- #46 - Recommendation system
- #47 - Statistics dashboard
- #39 - Visual regression testing

## Recently Completed

- #7 - Database backup/restore documentation (`docs/backup.md`)
- #16 - Contributing guidelines (`CONTRIBUTING.md`)
- #17 - Security policy (`SECURITY.md`)
- #20 - Architecture documentation (`docs/architecture.md`)
- #21 - README.md improvements (badges, quick start, FAQ, troubleshooting)
- #23 - Environment variables documentation (`docs/environment.md`)
- #24 - Upgrade guide (`docs/upgrading.md`)

---

*This to-do list should be prioritized based on team capacity, user needs, and business requirements. Items should be converted to GitHub Issues for tracking and assignment.*
