/**
 * PWA offline sync initializer.
 *
 * Runs on every page load to:
 * 1. Sync cellar data to IndexedDB when online
 * 2. Show/hide an offline indicator banner
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

async function updateSyncBadge(badge: HTMLElement): Promise<void> {
  const count = await getPendingCount();
  if (count > 0) {
    badge.textContent = gettext('⏳ %(count)s pending change%(plural)s').replace('%(count)s', String(count)).replace('%(plural)s', count > 1 ? 's' : '');
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
