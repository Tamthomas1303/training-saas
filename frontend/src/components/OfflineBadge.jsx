import { useEffect, useState } from 'react'
import { onQueueChange, queueCount } from '../utils/offlineQueue'

export default function OfflineBadge() {
  const [online, setOnline] = useState(navigator.onLine)
  const [count, setCount] = useState(0)

  useEffect(() => {
    function refreshOnline() {
      setOnline(navigator.onLine)
    }
    queueCount().then(setCount)
    const unsubscribe = onQueueChange(setCount)
    window.addEventListener('online', refreshOnline)
    window.addEventListener('offline', refreshOnline)
    return () => {
      unsubscribe()
      window.removeEventListener('online', refreshOnline)
      window.removeEventListener('offline', refreshOnline)
    }
  }, [])

  if (online && count === 0) return null

  return (
    <span
      style={{
        padding: '2px 8px',
        borderRadius: 12,
        fontSize: 12,
        background: online ? '#e0f2fe' : '#fef3c7',
        color: online ? '#075985' : '#92400e',
      }}
    >
      {online ? `${count} nháp chờ đồng bộ` : `Offline${count ? ` - ${count} nháp` : ''}`}
    </span>
  )
}
