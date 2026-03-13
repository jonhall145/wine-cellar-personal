/**
 * PWA offline sync initializer.
 *
 * Runs on every page load to:
 * 1. Sync cellar data to IndexedDB when online
 * 2. Show/hide an offline indicator banner
 */

import { syncCellarData } from './offline_store';

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

function updateOnlineStatus(banner: HTMLElement): void {
  banner.style.display = navigator.onLine ? 'none' : 'block';
}

function init(): void {
  const banner = createOfflineBanner();
  updateOnlineStatus(banner);

  window.addEventListener('online', () => {
    updateOnlineStatus(banner);
    // Re-sync when back online
    syncCellarData();
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
