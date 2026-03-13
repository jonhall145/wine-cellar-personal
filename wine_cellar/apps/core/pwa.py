"""PWA support views: manifest.json and service worker."""

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.templatetags.static import static
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET


def _get_app_branding():
    """Return name and short_name based on CELLAR_APP_TYPE."""
    if getattr(settings, "CELLAR_APP_TYPE", "wine") == "whisky":
        return "Whisky Cabinet", "Whisky"
    return "Wine Cellar", "Wine"


@login_not_required
@require_GET
@cache_page(3600)
def manifest_json(request):
    """Serve the PWA web app manifest, dynamic per app type."""
    name, short_name = _get_app_branding()

    manifest = {
        "name": name,
        "short_name": short_name,
        "description": f"Track and manage your {short_name.lower()} collection",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#019603",
        "orientation": "any",
        "icons": [
            {
                "src": static("images/pwa-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("images/pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("images/pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }

    return JsonResponse(manifest, json_dumps_params={"indent": 2})


# Theme color constant shared with templates
PWA_THEME_COLOR = "#019603"


@login_not_required
@require_GET
def service_worker_js(request):
    """Serve the service worker from the root scope.

    The service worker must be served from / to control the entire site.
    We embed the version and static URL so the SW can manage its cache.
    """
    version = getattr(settings, "VERSION", "0.0.0")
    static_url = settings.STATIC_URL

    sw_code = f"""\
// Service Worker v{version}
const CACHE_VERSION = '{version}';
const CACHE_NAME = 'wine-cellar-v' + CACHE_VERSION;
const STATIC_URL = '{static_url}';

// Static assets to precache (versioned to match template-rendered URLs)
const PRECACHE_URLS = [
  STATIC_URL + 'base.css?v={version}',
  STATIC_URL + 'base.js?v={version}',
  STATIC_URL + 'fontawesome-vendors.css?v={version}',
  STATIC_URL + 'images/favicon.svg',
  STATIC_URL + 'images/pwa-icon-192.png',
  '/offline/',
];

// Install: precache core assets
self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {{
      return cache.addAll(PRECACHE_URLS);
    }}).then(() => self.skipWaiting())
  );
}});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {{
  event.waitUntil(
    caches.keys().then((cacheNames) => {{
      return Promise.all(
        cacheNames
          .filter((name) => name.startsWith('wine-cellar-v') && name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }}).then(() => self.clients.claim())
  );
}});

// Fetch: network-first for navigations, cache-first for static assets
self.addEventListener('fetch', (event) => {{
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Skip admin, accounts, and API requests — these must not be cached
  if (url.pathname.startsWith('/admin/')) return;
  if (url.pathname.startsWith('/accounts/')) return;
  if (url.pathname.startsWith('/api/')) return;

  // Navigation requests: network-first with offline fallback
  if (event.request.mode === 'navigate') {{
    event.respondWith(
      fetch(event.request)
        .then((response) => {{
          // Cache successful navigation responses
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        }})
        .catch(() => {{
          return caches.match(event.request).then((cached) => {{
            return cached || caches.match('/offline/');
          }});
        }})
    );
    return;
  }}

  // Static assets: cache-first
  if (url.pathname.startsWith(STATIC_URL) || url.pathname.startsWith('/media/')) {{
    event.respondWith(
      caches.match(event.request).then((cached) => {{
        if (cached) return cached;
        return fetch(event.request).then((response) => {{
          if (response.ok) {{
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }}
          return response;
        }});
      }})
    );
    return;
  }}

  // Other requests: network-first, no caching of authenticated responses
  event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
}});

// Push notifications
self.addEventListener('push', (event) => {{
  const data = event.data ? event.data.json() : {{}};
  const title = data.title || 'Wine Cellar';
  const options = {{
    body: data.body || '',
    icon: data.icon || STATIC_URL + 'images/pwa-icon-192.png',
    badge: STATIC_URL + 'images/pwa-icon-192.png',
    data: {{ url: data.url || '/' }},
  }};
  event.waitUntil(self.registration.showNotification(title, options));
}});

// Handle notification click
self.addEventListener('notificationclick', (event) => {{
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({{ type: 'window', includeUncontrolled: true }})
      .then((windowClients) => {{
        for (const client of windowClients) {{
          if (client.url.includes(url) && 'focus' in client) {{
            return client.focus();
          }}
        }}
        return clients.openWindow(url);
      }})
  );
}});

// Background Sync: replay queued mutations when connectivity returns
self.addEventListener('sync', (event) => {{
  if (event.tag === 'cellar-sync') {{
    event.waitUntil(replayQueuedMutations());
  }}
}});

async function replayQueuedMutations() {{
  const db = await new Promise((resolve, reject) => {{
    const req = indexedDB.open('cellar-offline', 2);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }});

  const mutations = await new Promise((resolve, reject) => {{
    const tx = db.transaction('sync_queue', 'readonly');
    const idx = tx.objectStore('sync_queue').index('timestamp');
    const req = idx.getAll();
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }});

  for (const m of mutations) {{
    try {{
      const resp = await fetch(m.url, {{
        method: m.method,
        headers: {{
          'Content-Type': m.contentType,
          'X-CSRFToken': m.csrfToken,
          'X-Requested-With': 'XMLHttpRequest',
        }},
        body: m.body,
        credentials: 'same-origin',
      }});
      if (resp.ok || resp.status === 302 || resp.status === 403) {{
        await new Promise((resolve, reject) => {{
          const delTx = db.transaction('sync_queue', 'readwrite');
          delTx.oncomplete = resolve;
          delTx.onerror = () => reject(delTx.error);
          delTx.objectStore('sync_queue').delete(m.id);
        }});
      }}
    }} catch (e) {{
      break;  // Network still down, stop replaying
    }}
  }}
  db.close();
}}
"""
    from django.http import HttpResponse

    return HttpResponse(
        sw_code,
        content_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )
