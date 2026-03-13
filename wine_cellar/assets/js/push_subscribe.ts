/**
 * Push notification subscription UI for the user settings page.
 * Manages browser push permission and sends subscription to the server.
 */

const gettext = (window as any).django?.gettext || ((s: string) => s);

function getCookie(name: string): string {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[2]) : '';
}

async function getVapidKey(): Promise<string | null> {
  try {
    const resp = await fetch('/api/push/vapid-key/');
    if (!resp.ok) return null;
    const data = await resp.json();
    return data.public_key || null;
  } catch {
    return null;
  }
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

async function subscribePush(vapidKey: string): Promise<boolean> {
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidKey),
  });
  const json = sub.toJSON();
  const resp = await fetch('/api/push/subscribe/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify({
      endpoint: sub.endpoint,
      keys: {
        p256dh: json.keys?.p256dh || '',
        auth: json.keys?.auth || '',
      },
    }),
  });
  return resp.ok;
}

async function unsubscribePush(): Promise<boolean> {
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (sub) {
    await fetch('/api/push/unsubscribe/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
      },
      body: JSON.stringify({ endpoint: sub.endpoint }),
    });
    await sub.unsubscribe();
  }
  return true;
}

function updateUI(
  btn: HTMLButtonElement,
  status: HTMLElement,
  subscribed: boolean,
): void {
  if (subscribed) {
    btn.textContent = gettext('Disable Push Notifications');
    btn.classList.remove('button__primary');
    btn.classList.add('button__danger');
    status.textContent = gettext('Push notifications are enabled.');
    status.className = 'push-status push-status--active';
  } else {
    btn.textContent = gettext('Enable Push Notifications');
    btn.classList.remove('button__danger');
    btn.classList.add('button__primary');
    status.textContent = gettext('Push notifications are disabled.');
    status.className = 'push-status push-status--inactive';
  }
}

async function init(): Promise<void> {
  const container = document.getElementById('push-notification-section');
  if (!container) return;

  const btn = container.querySelector<HTMLButtonElement>('#push-toggle-btn');
  const status = container.querySelector<HTMLElement>('#push-status');
  if (!btn || !status) return;

  // Check browser support
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    status.textContent = gettext(
      'Push notifications are not supported in this browser.',
    );
    status.className = 'push-status push-status--unsupported';
    btn.classList.add('push-toggle-btn--hidden');
    return;
  }

  // Check current subscription state
  const reg = await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  let isSubscribed = !!existing;
  updateUI(btn, status, isSubscribed);
  btn.classList.remove('push-toggle-btn--hidden');

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      if (isSubscribed) {
        await unsubscribePush();
        isSubscribed = false;
      } else {
        const vapidKey = await getVapidKey();
        if (!vapidKey) {
          status.textContent = gettext(
            'Push not configured on the server.',
          );
          return;
        }
        const ok = await subscribePush(vapidKey);
        if (ok) isSubscribed = true;
      }
      updateUI(btn, status, isSubscribed);
    } catch (err: any) {
      if (Notification.permission === 'denied') {
        status.textContent = gettext(
          'Notifications blocked. Please allow in browser settings.',
        );
        status.className = 'push-status push-status--denied';
        btn.classList.add('push-toggle-btn--hidden');
      } else {
        status.textContent = gettext('Something went wrong. Please try again.');
      }
    } finally {
      btn.disabled = false;
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => init());
} else {
  init();
}
