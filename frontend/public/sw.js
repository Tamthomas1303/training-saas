// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 2) - service worker CHI lo web push + click, KHONG cache
// app/offline (tranh phuc vu ban cu). Dang ky trong src/main.jsx.

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { title: 'Thông báo', body: event.data ? event.data.text() : '' }
  }
  const title = data.title || 'Thông báo'
  const options = {
    body: data.body || '',
    icon: data.icon || '/icon-192.png',
    badge: '/icon-192.png',
    data: { link: data.link || '/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const link = (event.notification.data && event.notification.data.link) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        const clientUrl = new URL(client.url)
        if (clientUrl.origin === self.location.origin && 'focus' in client) {
          client.focus()
          if ('navigate' in client) client.navigate(link)
          return
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(link)
    })
  )
})
