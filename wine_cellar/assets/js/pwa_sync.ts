/**
 * PWA offline sync initializer.
 *
 * Runs on every page load to:
 * 1. Sync cellar data to IndexedDB when online
 * 2. Show/hide an offline indicator banner
 * 3. Detect service worker updates and prompt the user
 */

import { syncCellarData } from './offline_store';
import { getPendingCount, replayMutations } from './sync_queue';

const gettext = (window as any).django?.gettext || ((s: string) => s);

function createOfflineBanner(): HTMLElement {
  const banner = document.createElement('div');
  banner.id = 'offline-banner';
  banner.className = 'offline-banner';
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.textContent = gettext('📡 You are offline — showing cached data');
  document.body.appendChild(banner);
  return banner;
}

function createSyncBadge(): HTMLElement {
  const badge = document.createElement('div');
  badge.id = 'sync-badge';
  badge.className = 'sync-badge';
  badge.setAttribute('role', 'status');
  badge.setAttribute('aria-live', 'polite');
  document.body.appendChild(badge);
  return badge;
}

function createUpdateBanner(): HTMLElement {
  const banner = document.createElement('div');
  banner.id = 'update-banner';
  banner.className = 'update-banner';
  banner.setAttribute('role', 'alert');
  banner.setAttribute('aria-live', 'assertive');

  const msg = document.createElement('span');
  msg.textContent = gettext('🆕 A new version is available');
  banner.appendChild(msg);

  const updateBtn = document.createElement('button');
  updateBtn.className = 'update-banner__btn';
  updateBtn.type = 'button';
  updateBtn.textContent = gettext('Update now');
  banner.appendChild(updateBtn);

  const dismissBtn = document.createElement('button');
  dismissBtn.className = 'update-banner__dismiss';
  dismissBtn.type = 'button';
  dismissBtn.setAttribute('aria-label', gettext('Dismiss'));
  dismissBtn.textContent = '\u00d7';
  banner.appendChild(dismissBtn);

  document.body.appendChild(banner);
  return banner;
}

function showUpdateBanner(waitingSW: ServiceWorker): void {
  // Guard against multiple banners
  const existing = document.getElementById('update-banner');
  if (existing) existing.remove();

  const banner = createUpdateBanner();

  banner.querySelector('.update-banner__btn')!.addEventListener('click', () => {
    waitingSW.postMessage({ type: 'SKIP_WAITING' });
    banner.remove();
  });

  banner.querySelector('.update-banner__dismiss')!.addEventListener('click', () => {
    banner.remove();
  });

  requestAnimationFrame(() => banner.classList.add('update-banner--visible'));
}

/**
 * Register the service worker and set up update detection.
 * Replaces the inline <script> in base.html.
 */
export function registerServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return;

  // Reload when a new SW takes over (user clicked "Update now")
  let refreshing = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!refreshing) {
      refreshing = true;
      window.location.reload();
    }
  });

  navigator.serviceWorker.register('/sw.js').then((reg) => {
    // If a SW is already waiting when the page loads, prompt immediately
    if (reg.waiting) {
      showUpdateBanner(reg.waiting);
    }

    // Detect when a new SW finishes installing and enters waiting
    reg.addEventListener('updatefound', () => {
      const newSW = reg.installing;
      if (!newSW) return;

      newSW.addEventListener('statechange', () => {
        if (newSW.state === 'installed' && navigator.serviceWorker.controller) {
          showUpdateBanner(newSW);
        }
      });
    });
  }).catch((err) => console.warn('SW registration failed:', err));
}

async function updateSyncBadge(badge: HTMLElement): Promise<void> {
  const count = await getPendingCount();
  if (count > 0) {
    const ngettext = (window as any).django?.ngettext || ((s: string, p: string, n: number) => n === 1 ? s : p);
    badge.textContent = '⏳ ' + ngettext('%(count)s pending change', '%(count)s pending changes', count).replace('%(count)s', String(count));
    badge.classList.add('sync-badge--visible');
  } else {
    badge.classList.remove('sync-badge--visible');
  }
}

function updateOnlineStatus(banner: HTMLElement): void {
  if (navigator.onLine) {
    banner.classList.remove('offline-banner--visible');
  } else {
    banner.classList.add('offline-banner--visible');
  }
}

function init(): void {
  const banner = createOfflineBanner();
  const badge = createSyncBadge();
  updateOnlineStatus(banner);
  updateSyncBadge(badge);
  registerServiceWorker();

  window.addEventListener('online', async () => {
    updateOnlineStatus(banner);
    // Replay queued mutations then sync fresh data
    await replayMutations();
    await syncCellarData();
    updateSyncBadge(badge);
  });

  window.addEventListener('offline', () => {
    updateOnlineStatus(banner);
  });

  // Sync on load if online
  if (navigator.onLine) {
    syncCellarData();
  }
}

// Run when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
