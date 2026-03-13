/**
 * PWA offline sync initializer.
 *
 * Runs on every page load to:
 * 1. Sync cellar data to IndexedDB when online
 * 2. Show/hide an offline indicator banner
 */

import { syncCellarData } from './offline_store';
import { getPendingCount, replayMutations } from './sync_queue';

function createOfflineBanner(): HTMLElement {
  const banner = document.createElement('div');
  banner.id = 'offline-banner';
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.style.cssText = [
    'position: fixed',
    'bottom: 60px',  // above the mobile bottom nav
    'left: 0',
    'right: 0',
    'background: #f59e0b',
    'color: #000',
    'text-align: center',
    'padding: 8px 16px',
    'font-size: 14px',
    'z-index: 9999',
    'display: none',
    'font-weight: 500',
  ].join(';');
  banner.textContent = '📡 You are offline — showing cached data';
  document.body.appendChild(banner);
  return banner;
}

function createSyncBadge(): HTMLElement {
  const badge = document.createElement('div');
  badge.id = 'sync-badge';
  badge.setAttribute('role', 'status');
  badge.setAttribute('aria-live', 'polite');
  badge.style.cssText = [
    'position: fixed',
    'bottom: 60px',
    'right: 12px',
    'background: #3b82f6',
    'color: #fff',
    'padding: 6px 12px',
    'border-radius: 16px',
    'font-size: 13px',
    'z-index: 10000',
    'display: none',
    'box-shadow: 0 2px 8px rgba(0,0,0,0.15)',
  ].join(';');
  document.body.appendChild(badge);
  return badge;
}

async function updateSyncBadge(badge: HTMLElement): Promise<void> {
  const count = await getPendingCount();
  if (count > 0) {
    badge.textContent = `⏳ ${count} pending change${count > 1 ? 's' : ''}`;
    badge.style.display = 'block';
  } else {
    badge.style.display = 'none';
  }
}

function updateOnlineStatus(banner: HTMLElement): void {
  banner.style.display = navigator.onLine ? 'none' : 'block';
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
