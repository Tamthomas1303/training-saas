// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 3/4) - dang ky/huy dang ky web push. KHONG tu dong
// subscribe - nguoi dung phai chu dong bam nut (dung y "khong auto-subscribe" cua prompt).
import api from '../api/client'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)))
}

export function pushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && typeof Notification !== 'undefined'
}

export async function getCurrentPushSubscription() {
  if (!pushSupported()) return null
  const reg = await navigator.serviceWorker.ready
  return reg.pushManager.getSubscription()
}

export async function subscribeToPush() {
  if (!pushSupported()) throw new Error('Trình duyệt không hỗ trợ thông báo đẩy.')
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('Bạn chưa cho phép nhận thông báo.')

  const { data } = await api.get('/push/vapid-public-key/')
  if (!data.vapid_public_key) throw new Error('Hệ thống chưa cấu hình thông báo đẩy.')

  const reg = await navigator.serviceWorker.ready
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(data.vapid_public_key),
  })
  const json = subscription.toJSON()
  await api.post('/push/subscribe/', { endpoint: json.endpoint, keys: json.keys })
  return subscription
}

export async function unsubscribeFromPush() {
  const subscription = await getCurrentPushSubscription()
  if (!subscription) return
  const endpoint = subscription.endpoint
  await subscription.unsubscribe()
  await api.post('/push/unsubscribe/', { endpoint })
}

export function isIosSafari() {
  const ua = window.navigator.userAgent
  const isIos = /iphone|ipad|ipod/i.test(ua)
  const isWebkit = /webkit/i.test(ua)
  const isNotOtherBrowser = !/crios|fxios|edgios/i.test(ua)
  return isIos && isWebkit && isNotOtherBrowser
}

export function isStandalone() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches
    || window.navigator.standalone === true
  )
}
