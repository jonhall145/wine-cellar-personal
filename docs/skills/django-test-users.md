# Django Test User Management

## Overview

Creating and managing test users for development and automated testing.

## Create Test User via Shell

```bash
cd /path/to/project
source venv/bin/activate
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='testuser').exists():
    user = User.objects.create_user('testuser', 'test@example.com', 'testpass123')
    print('Created test user')
else:
    print('Test user already exists')
"
```

## Create Superuser

```bash
python manage.py createsuperuser --username admin --email admin@example.com
```

## Test User Credentials

For this project, a test user is available:
- **Username:** testuser
- **Password:** testpass123
- **Email:** test@example.com

## Using Test User in Playwright

```javascript
// Login with test user
await page.goto('http://localhost:8000/accounts/login/');
await page.fill('input[name="login"]', 'testuser');
await page.fill('input[name="password"]', 'testpass123');
await page.click('button[type="submit"]');
await page.waitForLoadState('networkidle');
```

## Using Test User in pytest

```python
import pytest
from django.contrib.auth import get_user_model

@pytest.fixture
def test_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

@pytest.fixture
def authenticated_client(client, test_user):
    client.login(username='testuser', password='testpass123')
    return client

def test_authenticated_view(authenticated_client):
    response = authenticated_client.get('/protected-page/')
    assert response.status_code == 200
```

## Factory Boy Pattern

```python
import factory
from django.contrib.auth import get_user_model

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')

# Usage
user = UserFactory()
user = UserFactory(username='custom_name')
```

## Fixtures

Load sample users from fixtures:

```bash
python manage.py loaddata fixtures/users.json
```

Example fixture file (`fixtures/users.json`):

```json
[
  {
    "model": "auth.user",
    "pk": 1,
    "fields": {
      "username": "testuser",
      "email": "test@example.com",
      "password": "pbkdf2_sha256$...",
      "is_active": true
    }
  }
]
```

## Reset Test User

```python
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.filter(username='testuser').delete()
User.objects.create_user('testuser', 'test@example.com', 'testpass123')
print('Test user reset')
"
```

## Security Notes

1. **Never use test credentials in production**
2. **Use strong passwords for admin/superuser accounts**
3. **Test users should be created fresh for each test run when possible**
4. **Don't commit real credentials to version control**
