import { usePushSubscription } from '../hooks/usePushSubscription'

// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 4) - nut "Bat thong bao day" gon cho mobile-topstrip
// (khong co dropdown menu nhu UserMenu desktop nen dat truc tiep 1 nut nho canh chuong).
export default function PushToggleButton() {
  const push = usePushSubscription()
  if (!push.supported) return null

  return (
    <button
      className="btn-outline btn-sm"
      onClick={push.toggle}
      disabled={push.loading}
      title={push.error || (push.subscribed ? 'Tắt thông báo đẩy' : 'Bật thông báo đẩy')}
    >
      {push.subscribed ? '🔔 Đã bật' : '🔕 Bật đẩy'}
    </button>
  )
}
