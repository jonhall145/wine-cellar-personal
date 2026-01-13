# Architecture

This document describes the high-level architecture of Wine Cellar.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  Browser                                                        │
│  ├── Django Templates (Server-rendered HTML)                   │
│  ├── React Components (Barcode Scanner, Maps, Storage Grid)    │
│  └── Static Assets (CSS, JS, Images)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                          │
├─────────────────────────────────────────────────────────────────┤
│  Django 5.2                                                     │
│  ├── URL Routing                                                │
│  ├── Views (Class-Based Views)                                  │
│  ├── Forms & Validation                                         │
│  ├── Authentication (django-allauth)                            │
│  └── Middleware (CSRF, Session, Security)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Data Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  Django ORM                                                     │
│  ├── Models (Wine, Storage, User)                               │
│  ├── Migrations                                                 │
│  └── Signals                                                    │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL (Production) / SQLite (Development)                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Background Tasks                            │
├─────────────────────────────────────────────────────────────────┤
│  Celery + Redis                                                 │
│  └── Drink-by Email Reminders                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Django Apps

Wine Cellar is organized into three Django apps:

```
wine_cellar/apps/
├── wine/       # Core wine management
├── storage/    # Inventory and shelf management
└── user/       # User settings and authentication
```

#### Wine App

Handles all wine-related functionality:

- **Models**: `Wine`, `WineImage`, `WineType`, `Category`
- **Views**: List, detail, create, edit, delete, barcode lookup
- **Features**: Multi-image support, ratings, tasting notes, food pairings

#### Storage App

Manages inventory and storage locations:

- **Models**: `StorageItem`, `Shelf`
- **Views**: Stock list, shelf management, grid view
- **Features**: Bottle pricing, location tracking, drag-and-drop organization

#### User App

User management and preferences:

- **Models**: `UserSettings`
- **Views**: Settings, profile management
- **Features**: Currency preferences, date formats, notification settings

### Frontend Architecture

```
wine_cellar/
├── assets/           # Source files
│   ├── css/          # Stylesheets
│   ├── js/           # JavaScript utilities
│   └── images/       # Static images
├── react/            # React components
│   ├── react_bar_code.tsx    # Barcode scanner
│   ├── storage_grid.tsx      # Storage grid UI
│   └── maps/                 # Wine origin map
└── templates/        # Django templates
    ├── base.html     # Base layout
    └── wine/         # Wine-specific templates
```

#### Hybrid Rendering

- **Server-side**: Django templates for page structure and SEO
- **Client-side**: React for interactive features (scanning, maps, grids)
- **Build**: Webpack bundles React components into static JS

### Data Flow

#### Wine Creation Flow

```
1. User submits form
        │
        ▼
2. Django FormView validates
        │
        ▼
3. Model.save() triggers signals
        │
        ▼
4. Database record created
        │
        ▼
5. Image upload processed (Pillow)
        │
        ▼
6. Redirect to detail view
```

#### Barcode Scanning Flow

```
1. React component captures barcode
        │
        ▼
2. AJAX POST to Django view
        │
        ▼
3. Database lookup by barcode
        │
        ▼
4. JSON response with wine data
        │
        ▼
5. React updates UI / redirects
```

## Database Schema

### Entity Relationship

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│     User     │     │     Wine     │     │  WineImage   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id           │◄────│ user_id      │     │ id           │
│ username     │     │ id           │◄────│ wine_id      │
│ email        │     │ name         │     │ image        │
│ password     │     │ vintage      │     │ image_type   │
└──────────────┘     │ country      │     └──────────────┘
       │             │ wine_type    │
       │             │ rating       │
       │             │ barcode      │
       ▼             └──────────────┘
┌──────────────┐            │
│ UserSettings │            │
├──────────────┤            ▼
│ user_id      │     ┌──────────────┐
│ currency     │     │ StorageItem  │
│ date_format  │     ├──────────────┤
└──────────────┘     │ wine_id      │
                     │ user_id      │
                     │ quantity     │
                     │ price        │
                     │ shelf_id     │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Shelf     │
                     ├──────────────┤
                     │ id           │
                     │ name         │
                     │ rows         │
                     │ columns      │
                     └──────────────┘
```

### Key Relationships

- **User → Wine**: One-to-many (user owns wines)
- **Wine → WineImage**: One-to-many (wine has images)
- **Wine → StorageItem**: One-to-many (wine in multiple locations)
- **StorageItem → Shelf**: Many-to-one (items on shelves)
- **User → UserSettings**: One-to-one (user preferences)

## Authentication

### Providers

- **Local accounts**: Username/password with django-allauth
- **OpenID Connect**: External identity providers
- **Signup control**: `ENABLE_SIGNUP` environment variable

### Session Management

- Django sessions with database backend
- Secure cookies in production (HTTPOnly, Secure flags)
- CSRF protection on all forms

## Caching Strategy

Currently minimal caching:

- **Static files**: Whitenoise with Brotli compression
- **Database**: Django's default query caching

Potential improvements:

- Redis caching for expensive queries
- Template fragment caching
- API response caching

## Deployment Architecture

### Development

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ :8003
       ▼
┌─────────────┐     ┌─────────────┐
│   Django    │────▶│   SQLite    │
│ Dev Server  │     │             │
└─────────────┘     └─────────────┘
```

### Production

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ :443
       ▼
┌─────────────┐
│   Nginx     │ (Reverse Proxy, SSL)
└──────┬──────┘
       │ :8000
       ▼
┌─────────────┐     ┌─────────────┐
│  Gunicorn   │────▶│ PostgreSQL  │
│  (Django)   │     │             │
└──────┬──────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   Celery    │────▶│    Redis    │
│  (Worker)   │     │  (Broker)   │
└─────────────┘     └─────────────┘
```

## Technology Decisions

### Why Django?

- Mature, well-documented framework
- Built-in admin, auth, ORM
- Strong security defaults
- Large ecosystem (django-allauth, django-filter)

### Why React (selective)?

- Complex interactivity (barcode scanner, maps)
- Better UX for real-time features
- Progressive enhancement approach

### Why PostgreSQL?

- Robust, production-ready
- Full-text search capabilities
- JSON field support
- Strong data integrity

### Why Celery?

- Background task processing
- Scheduled jobs (drink-by reminders)
- Scalable worker architecture

## Future Considerations

- **API layer**: REST or GraphQL for mobile apps
- **Real-time updates**: WebSockets for live notifications
- **Search**: Elasticsearch for advanced wine search
- **CDN**: Media file delivery optimization
