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

function createOfflineBanner(): HTMLElement {
  const banner = document.createElement('div');
  banner.id = 'offline-banner';
  banner.className = 'offline-banner';
  banner.setAttribute('role', 'status');
  banner.setAttribute('aria-live', 'polite');
  banner.textContent = '📡 You are offline — showing cached data';
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
  msg.textContent = '🆕 A new version is available';
  banner.appendChild(msg);

  const updateBtn = document.createElement('button');
  updateBtn.className = 'update-banner__btn';
  updateBtn.type = 'button';
  updateBtn.textContent = 'Update now';
  banner.appendChild(updateBtn);

  const dismissBtn = document.createElement('button');
  dismissBtn.className = 'update-banner__dismiss';
  dismissBtn.type = 'button';
  dismissBtn.setAttribute('aria-label', 'Dismiss');
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
    badge.textContent = '⏳ ' + (count === 1 ? '%(count)s pending change' : '%(count)s pending changes').replace('%(count)s', String(count));
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

function detectIos(): { isIos: boolean; isSafari: boolean } {
  const ua = navigator.userAgent;
  const isIphone = /iphone|ipod/i.test(ua);
  // On iPadOS 13+, Safari reports the platform as "Macintosh" but still exposes navigator.standalone;
  // we use that (plus touch support) as a signal that this is iPadOS Safari / iOS-style install UX.
  const isIpad = /ipad/i.test(ua) || (/macintosh/i.test(ua) && 'standalone' in navigator && 'ontouchend' in document);
  const isIos = isIphone || isIpad;
  // Chrome, Firefox, Edge, Opera on iOS are still WebKit-based, but are third-party browsers whose
  // PWA install UX differs from Safari; we only treat Safari as "install-capable" for this banner.
  const isThirdPartyBrowser = /CriOS|FxiOS|EdgiOS|OPiOS/i.test(ua);
  return { isIos, isSafari: isIos && !isThirdPartyBrowser };
}

function createInstallBanner(): HTMLElement {
  const banner = document.createElement('div');
  banner.id = 'install-banner';
  banner.className = 'install-banner';
  banner.setAttribute('role', 'complementary');
  banner.setAttribute('aria-label', 'Install app prompt');

  const msg = document.createElement('span');
  msg.textContent = '📲 Install this app on your device';
  banner.appendChild(msg);

  const addBtn = document.createElement('button');
  addBtn.className = 'install-banner__btn';
  addBtn.type = 'button';
  addBtn.textContent = 'How to install';
  banner.appendChild(addBtn);

  const dismissBtn = document.createElement('button');
  dismissBtn.className = 'install-banner__dismiss';
  dismissBtn.type = 'button';
  dismissBtn.setAttribute('aria-label', 'Dismiss');
  dismissBtn.textContent = '\u00d7';
  banner.appendChild(dismissBtn);

  document.body.appendChild(banner);
  return banner;
}

function initIosInstallBanner(): void {
  const { isIos, isSafari } = detectIos();
  if (!isIos) return;

  // Already installed as PWA
  const isStandalone = (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (isStandalone) return;

  // User already dismissed
  if (localStorage.getItem('wine-cellar-install-dismissed')) return;

  const modal = document.getElementById('ios-install-modal') as HTMLElement | null;
  const modalBody = document.getElementById('ios-install-modal-body');
  if (!modal || !modalBody) return;

  if (isSafari) {
    modalBody.innerHTML =
      'To install this app and remember camera permissions:<br><br>' +
      '1. Tap the <strong>Share</strong> button <i class="fa-solid fa-arrow-up-from-bracket"></i> at the bottom of Safari<br>' +
      '2. Scroll down and tap <strong>Add to Home Screen</strong><br>' +
      '3. Tap <strong>Add</strong>';
  } else {
    modalBody.innerHTML =
      'To install this app, open this page in <strong>Safari</strong>:<br><br>' +
      '1. Tap the browser menu and select <strong>Open in Safari</strong><br>' +
      '2. Tap the <strong>Share</strong> button <i class="fa-solid fa-arrow-up-from-bracket"></i><br>' +
      '3. Tap <strong>Add to Home Screen</strong>, then <strong>Add</strong>';
  }

  const banner = createInstallBanner();

  function showInstallBanner(): void {
    // Don't show while offline or when an update banner is present — they take priority.
    // Treating the presence of the update banner element as blocking avoids same-frame races
    // where the element exists but its "--visible" class has not yet been applied.
    const offlineBanner = document.getElementById('offline-banner');
    const updateBanner = document.getElementById('update-banner');
    const offlineVisible = offlineBanner?.classList.contains('offline-banner--visible') ?? false;
    const updateBlocking = !!updateBanner;

    if (!offlineVisible && !updateBlocking) {
      banner.classList.add('install-banner--visible');
    } else {
      banner.classList.remove('install-banner--visible');
    }
  }

  requestAnimationFrame(showInstallBanner);

  // Re-evaluate when connectivity changes
  window.addEventListener('online', () => showInstallBanner());
  window.addEventListener('offline', () => banner.classList.remove('install-banner--visible'));

  // Re-evaluate when the update banner is dynamically added or removed from the DOM
  if ('MutationObserver' in window) {
    const bodyObserver = new MutationObserver((mutations) => {
      const affectsUpdateBanner = mutations.some((m) =>
        Array.from(m.addedNodes).concat(Array.from(m.removedNodes)).some(
          (n) => (n as HTMLElement).id === 'update-banner'
        )
      );
      if (affectsUpdateBanner) showInstallBanner();
    });
    bodyObserver.observe(document.body, { childList: true });
  }

  banner.querySelector('.install-banner__btn')!.addEventListener('click', () => {
    modal.hidden = false;
    banner.classList.remove('install-banner--visible');
  });

  banner.querySelector('.install-banner__dismiss')!.addEventListener('click', () => {
    banner.classList.remove('install-banner--visible');
    localStorage.setItem('wine-cellar-install-dismissed', '1');
  });

  modal.querySelector('.ios-install-modal__backdrop')?.addEventListener('click', () => {
    modal.hidden = true;
    showInstallBanner();
  });
  modal.querySelector('.ios-install-modal__close')?.addEventListener('click', () => {
    modal.hidden = true;
    showInstallBanner();
  });
}

function init(): void {
  const banner = createOfflineBanner();
  const badge = createSyncBadge();
  updateOnlineStatus(banner);
  updateSyncBadge(badge);
  registerServiceWorker();
  initIosInstallBanner();

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
