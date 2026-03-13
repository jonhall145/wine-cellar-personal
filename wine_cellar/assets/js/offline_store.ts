/**
 * IndexedDB offline storage for PWA cellar data.
 *
 * Stores beverages, stock items, and storages locally so the app can
 * display cellar contents when offline. Uses a single "cellar" database
 * with object stores for each entity type plus a metadata store for
 * tracking sync state.
 */

const DB_NAME = 'cellar-offline';
const DB_VERSION = 2;

interface CellarSyncResponse {
  app_type: string;
  currency: string;
  beverages: Record<string, unknown>[];
  stock_items: Record<string, unknown>[];
  storages: Record<string, unknown>[];
  is_incremental: boolean;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
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
      if (!db.objectStoreNames.contains('sync_queue')) {
        const queueStore = db.createObjectStore('sync_queue', { keyPath: 'id' });
        queueStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function putAll(
  db: IDBDatabase,
  storeName: string,
  items: Record<string, unknown>[]
): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    for (const item of items) {
      store.put(item);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function clearAndPutAll(
  db: IDBDatabase,
  storeName: string,
  items: Record<string, unknown>[]
): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    store.clear();
    for (const item of items) {
      store.put(item);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getMeta(db: IDBDatabase, key: string): Promise<string | null> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('meta', 'readonly');
    const request = tx.objectStore('meta').get(key);
    request.onsuccess = () => resolve(request.result?.value ?? null);
    request.onerror = () => reject(request.error);
  });
}

async function setMeta(db: IDBDatabase, key: string, value: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction('meta', 'readwrite');
    tx.objectStore('meta').put({ key, value });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

/**
 * Sync cellar data from server to IndexedDB.
 * On first sync, fetches everything. On subsequent syncs,
 * only fetches records modified since last sync.
 */
export async function syncCellarData(): Promise<boolean> {
  try {
    const db = await openDB();
    const lastSync = await getMeta(db, 'last_sync');

    let url = '/api/cellar/sync/';
    if (lastSync) {
      url += `?since=${encodeURIComponent(lastSync)}`;
    }

    const response = await fetch(url, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });

    if (!response.ok) {
      db.close();
      return false;
    }

    const data: CellarSyncResponse = await response.json();
    const syncTime = new Date().toISOString();

    if (data.is_incremental) {
      // Incremental: merge new/updated records
      await putAll(db, 'beverages', data.beverages);
      await putAll(db, 'stock_items', data.stock_items);
      await putAll(db, 'storages', data.storages);
    } else {
      // Full sync: replace everything
      await clearAndPutAll(db, 'beverages', data.beverages);
      await clearAndPutAll(db, 'stock_items', data.stock_items);
      await clearAndPutAll(db, 'storages', data.storages);
    }

    await setMeta(db, 'last_sync', syncTime);
    await setMeta(db, 'app_type', data.app_type);
    await setMeta(db, 'currency', data.currency);

    db.close();
    return true;
  } catch (err) {
    console.warn('Cellar sync failed:', err);
    return false;
  }
}

/** Read all beverages from IndexedDB. */
export async function getOfflineBeverages(): Promise<Record<string, unknown>[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('beverages', 'readonly');
    const request = tx.objectStore('beverages').getAll();
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

/** Read all stock items from IndexedDB. */
export async function getOfflineStockItems(): Promise<Record<string, unknown>[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('stock_items', 'readonly');
    const request = tx.objectStore('stock_items').getAll();
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

/** Read all storages from IndexedDB. */
export async function getOfflineStorages(): Promise<Record<string, unknown>[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('storages', 'readonly');
    const request = tx.objectStore('storages').getAll();
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

/** Get sync metadata (last_sync, app_type, currency). */
export async function getSyncMeta(): Promise<Record<string, string | null>> {
  const db = await openDB();
  const lastSync = await getMeta(db, 'last_sync');
  const appType = await getMeta(db, 'app_type');
  const currency = await getMeta(db, 'currency');
  db.close();
  return { last_sync: lastSync, app_type: appType, currency };
}

/** Clear all offline data (e.g. on logout). */
export async function clearOfflineData(): Promise<void> {
  const db = await openDB();
  const stores = ['beverages', 'stock_items', 'storages', 'meta'];
  return new Promise((resolve, reject) => {
    const tx = db.transaction(stores, 'readwrite');
    for (const name of stores) {
      tx.objectStore(name).clear();
    }
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
