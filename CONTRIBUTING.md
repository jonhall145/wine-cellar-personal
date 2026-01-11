# Contributing to Wine Cellar

Thank you for your interest in contributing to Wine Cellar!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/wine-cellar.git
   cd wine-cellar
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   make install
   ```

4. **Set up the database**
   ```bash
   make migrate
   make fixtures  # Load sample data (optional)
   ```

5. **Start the development server**
   ```bash
   make watch  # Runs server with frontend rebuild on changes
   ```

## Code Style

This project uses automated formatting and linting:

- **Black** for Python code formatting
- **isort** for import sorting
- **flake8** for linting
- **Prettier** for JavaScript/TypeScript

Run all linters:
```bash
make lint
```

Pre-commit hooks are configured to run these checks automatically.

## Testing

Run the test suite:
```bash
make pytest
```

For coverage report:
```bash
pytest --cov=wine_cellar --cov-report=html
```

Minimum coverage threshold is **80%**.

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `refactor:` Code refactoring
- `perf:` Performance improvement
- `docs:` Documentation only
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Examples:
```
feat: add wine recommendation system
fix: correct price calculation in storage view
refactor(views): split large views file into modules
```

## Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write tests for new functionality
   - Update documentation if needed
   - Follow code style guidelines

3. **Run checks locally**
   ```bash
   make lint
   make pytest
   ```

4. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

5. **PR Review**
   - Address any review feedback
   - Keep commits focused and atomic
   - Rebase on main if needed

## Project Structure

```
wine_cellar/
├── apps/
│   ├── wine/       # Wine management (models, views, forms)
│   ├── storage/    # Inventory and storage locations
│   ├── user/       # User settings and preferences
│   └── hardware/   # Raspberry Pi integration
├── conf/           # Django settings
├── templates/      # Django templates
├── static/         # Compiled static assets
├── assets/         # Source CSS/JS (compiled by webpack)
└── react/          # React components
```

## Getting Help

- Check existing [issues](https://github.com/your-username/wine-cellar/issues)
- Read the [documentation](docs/)
- Open a new issue for bugs or feature requests

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 license.
