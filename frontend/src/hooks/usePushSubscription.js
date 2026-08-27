import { useEffect, useState } from 'react'
import { getCurrentPushSubscription, pushSupported, subscribeToPush, unsubscribeFromPush } from '../utils/push'

// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 4) - trang thai + hanh dong bat/tat thong bao day, dung
// chung boi UserMenu (desktop) va mobile-topstrip (mobile).
export function usePushSubscription() {
  const [supported, setSupported] = useState(false)
  const [subscribed, setSubscribed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const ok = pushSupported()
    setSupported(ok)
    if (ok) {
      getCurrentPushSubscription().then((sub) => setSubscribed(!!sub)).catch(() => {})
    }
  }, [])

  async function toggle() {
    setLoading(true)
    setError('')
    try {
      if (subscribed) {
        await unsubscribeFromPush()
        setSubscribed(false)
      } else {
        await subscribeToPush()
        setSubscribed(true)
      }
    } catch (err) {
      setError(err.message || 'Có lỗi xảy ra.')
    } finally {
      setLoading(false)
    }
  }

  return { supported, subscribed, loading, error, toggle }
}
