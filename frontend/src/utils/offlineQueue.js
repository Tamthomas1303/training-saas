// Hang doi nhap offline (IndexedDB) - port amg_offline/submitGuarded tu scripts.html (AppsScript
// Ver 2.0). Khi mat mang (hoac goi API that bai vi loi mang), payload duoc xep vao IndexedDB thay
// vi mat; khi co mang tro lai ('online' event), tu dong flush qua /api/auth/sync/drafts/.

const DB_NAME = 'amg_offline'
const STORE_NAME = 'queue'

function idbOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function idbAdd(item) {
  const db = await idbOpen()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).add(item)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

async function idbAll() {
  const db = await idbOpen()
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const rq = tx.objectStore(STORE_NAME).getAll()
    rq.onsuccess = () => resolve(rq.result || [])
    rq.onerror = () => resolve([])
  })
}

async function idbDelete(ids) {
  const db = await idbOpen()
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    ids.forEach((id) => store.delete(id))
    tx.oncomplete = () => resolve()
  })
}

function genClientUuid(kind) {
  return `${kind}_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
}

const listeners = new Set()

export function onQueueChange(cb) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

async function notifyListeners() {
  const items = await idbAll()
  listeners.forEach((cb) => cb(items.length))
}

export async function queueCount() {
  const items = await idbAll()
  return items.length
}

export async function enqueueDraft(kind, payload) {
  if (!payload.client_uuid) payload.client_uuid = genClientUuid(kind)
  await idbAdd({ kind, payload, client_uuid: payload.client_uuid })
  await notifyListeners()
}

export async function flushQueue(api) {
  if (!navigator.onLine) return
  const items = await idbAll()
  if (!items.length) return
  const payloadItems = items.map((it) => ({ kind: it.kind, payload: it.payload, client_uuid: it.client_uuid }))
  try {
    const { data } = await api.post('/auth/sync/drafts/', payloadItems)
    const okUuids = new Set((data.results || []).filter((x) => x.ok).map((x) => x.client_uuid))
    const delIds = items.filter((it) => okUuids.has(it.client_uuid)).map((it) => it.id)
    if (delIds.length) await idbDelete(delIds)
  } catch {
    // Van con offline hoac loi mang khac - giu nguyen hang doi, thu lai lan sau.
  }
  await notifyListeners()
}

/**
 * Gui co bao ve offline: online -> goi API truc tiep; offline hoac loi mang -> xep hang nhap.
 * Loi tu server (vd validation 400) KHONG bi xep hang - bao loi ngay cho nguoi dung sua.
 */
export async function submitGuarded(kind, apiCall, payload, { onOk, onErr, onQueued } = {}) {
  if (!navigator.onLine) {
    await enqueueDraft(kind, payload)
    onQueued?.()
    return
  }
  try {
    const data = await apiCall(payload)
    onOk?.(data)
  } catch (err) {
    if (err.response) {
      onErr?.(err.response.data?.detail || 'Có lỗi xảy ra.')
    } else {
      await enqueueDraft(kind, payload)
      onQueued?.()
    }
  }
}

export function initOfflineSync(api) {
  window.addEventListener('online', () => flushQueue(api))
}
