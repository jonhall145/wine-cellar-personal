/**
 * Offline mutation sync queue.
 *
 * Queues POST mutations made while offline and replays them
 * when connectivity returns via the Background Sync API.
 * Supports: move bottle, delete beverage, remove stock item.
 */

const DB_NAME = 'cellar-offline';
const STORE_NAME = 'sync_queue';
const DB_VERSION = 2;

export interface QueuedMutation {
  id: string;
  url: string;
  method: string;
  body: string;
  contentType: string;
  csrfToken: string;
  timestamp: number;
  retryCount: number;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      // Create stores from v1 if needed
      if (!db.objectStoreNames.contains('beverages')) {
        const beverageStore = db.createObjectStore('beverages', { keyPath: 'id' });
        beverageStore.createIndex('name', 'name', { unique: false });
        beverageStore.createIndex('type_code', 'type_code', { unique: false });
      }
      if (!db.objectStoreNames.contains('stock_items')) {
        const stockStore = db.createObjectStore('stock_items', { keyPath: 'id' });
        stockStore.createIndex('beverage_id', 'beverage_id', { unique: false });
        stockStore.createIndex('storage_id', 'storage_id', { unique: false });
      }
      if (!db.objectStoreNames.contains('storages')) {
        db.createObjectStore('storages', { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains('meta')) {
        db.createObjectStore('meta', { keyPath: 'key' });
      }
      // v2: sync queue
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const queueStore = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        queueStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getCSRFToken(): string {
  const cookie = document.cookie
    .split(';')
    .map((c) => c.trim())
    .find((c) => c.startsWith('csrftoken='));
  return cookie ? cookie.split('=')[1] : '';
}

/**
 * Queue a mutation for background sync.
 * Returns true if queued (offline), false if sent immediately (online).
 */
export async function queueMutation(
  url: string,
  method: string,
  body: Record<string, unknown>,
  contentType: string = 'application/json'
): Promise<boolean> {
  // If online, don't queue — let the normal request go through
  if (navigator.onLine) return false;

  const mutation: QueuedMutation = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    url,
    method,
    body: JSON.stringify(body),
    contentType,
    csrfToken: getCSRFToken(),
    timestamp: Date.now(),
    retryCount: 0,
  };

  const db = await openDB();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).add(mutation);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();

  // Request background sync if available
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    const reg = await navigator.serviceWorker.ready;
    try {
      await (reg as unknown as { sync: { register: (tag: string) => Promise<void> } })
        .sync.register('cellar-sync');
    } catch {
      // Background Sync not supported or permission denied
    }
  }

  return true;
}

/** Get count of pending mutations in the queue. */
export async function getPendingCount(): Promise<number> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const request = tx.objectStore(STORE_NAME).count();
    request.onsuccess = () => {
      db.close();
      resolve(request.result);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

/** Get all pending mutations ordered by timestamp. */
export async function getPendingMutations(): Promise<QueuedMutation[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const index = tx.objectStore(STORE_NAME).index('timestamp');
    const request = index.getAll();
    request.onsuccess = () => {
      db.close();
      resolve(request.result);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

/** Remove a mutation from the queue after successful replay. */
export async function removeMutation(id: string): Promise<void> {
  const db = await openDB();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

/** Replay all queued mutations in order. Returns count of successful replays. */
export async function replayMutations(): Promise<number> {
  const mutations = await getPendingMutations();
  let successCount = 0;

  for (const mutation of mutations) {
    try {
      const headers: Record<string, string> = {
        'Content-Type': mutation.contentType,
        'X-CSRFToken': mutation.csrfToken,
        'X-Requested-With': 'XMLHttpRequest',
      };

      const response = await fetch(mutation.url, {
        method: mutation.method,
        headers,
        body: mutation.body,
        credentials: 'same-origin',
      });

      if (response.ok || response.status === 302) {
        await removeMutation(mutation.id);
        successCount++;
      } else if (response.status === 403) {
        // CSRF token expired — remove stale mutation
        await removeMutation(mutation.id);
      }
      // Other errors: leave in queue for retry
    } catch {
      // Network error — stop replaying, will retry later
      break;
    }
  }

  return successCount;
}

/** Clear all pending mutations. */
export async function clearQueue(): Promise<void> {
  const db = await openDB();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}
