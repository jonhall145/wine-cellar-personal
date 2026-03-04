# Contributing to Wine Cellar

Thank you for your interest in contributing to Wine Cellar!

## Code of Conduct

Be respectful and inclusive. We welcome contributors of all backgrounds and experience levels.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone <your-fork-url>
   cd wine-cellar-personal
   ```

2. **Install dependencies and start Docker dev stack**
   ```bash
   make install
   ```

3. **Load sample data (optional)**
   ```bash
   make fixtures           # wine sample data
   make whisky-fixtures    # whisky sample data
   ```

4. **Start the development server**
   ```bash
   make watch        # dev server + frontend rebuild on changes
   make server       # dev server only (port 8003)
   ```

A test user is created by `make fixtures` for **local development only**: `testuser` / `testpass123`

### HTTPS for Camera Access

Mobile browsers require HTTPS for camera access. Use `./run_https.sh` which generates self-signed certificates and runs on `https://0.0.0.0:8000`.

## Code Style

This project uses automated formatting and linting:

- **Black** for Python code formatting (line length 88)
- **isort** for import sorting (black-compatible profile)
- **flake8** for Python linting
- **ESLint** for JavaScript/TypeScript
- **djLint** for Django templates

Run all linters before committing:
```bash
make lint
```

Auto-fix JS lint errors:
```bash
make lint-js-fix
```

Auto-fix template lint errors:
```bash
make lint-html-fix
```

## Testing

```bash
make pytest               # run all tests
make pytest-lastfailed    # re-run failed tests
make coverage             # tests with coverage report
```

Tests use `pytest` with `pytest-django`. Settings module: `wine_cellar.conf.test`.

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring
- `perf:` Performance improvement
- `docs:` Documentation only
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Keep messages short and lowercase:
```
feat: add wine recommendation system
fix: correct price calculation in storage view
refactor(views): split large views file into modules
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes — write tests for new functionality
3. Run `make lint` and fix any issues
4. Run `make pytest` and ensure all tests pass
5. Push to your fork and open a PR against `main`
6. Address any review feedback

Keep PRs focused — one feature or fix per PR.

## Project Structure

```
wine_cellar/
├── apps/
│   ├── core/       # shared base views, forms, filters
│   ├── wine/       # wine tracking and management
│   ├── storage/    # inventory and storage locations
│   ├── user/       # user settings and preferences
│   └── household/  # multi-user household support
├── conf/           # Django settings
├── templates/      # Django templates
├── react/          # React components (barcode scanner, maps)
├── assets/         # Source CSS/JS
tests/              # pytest test suite
docs/               # MkDocs documentation
fixtures/           # sample data (grapes, wines, stock)
```

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0 License](LICENSE).
