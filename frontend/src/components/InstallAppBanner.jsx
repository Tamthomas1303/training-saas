import { useEffect, useState } from 'react'
import { isIosSafari, isStandalone } from '../utils/push'

const DISMISS_KEY = 'pwa_install_banner_dismissed'

// Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 4) - banner nhe, tat duoc (nho lua chon qua
// localStorage), khong doi bo cuc man nao (chi 1 thanh noi troi o duoi man hinh). Android/Chrome
// dung beforeinstallprompt; iOS Safari khong co prompt nen chi huong dan tay + luu y push chi
// hoat dong tu iOS 16.4+ sau khi da them vao man hinh chinh.
export default function InstallAppBanner() {
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [iosHint, setIosHint] = useState(false)
  const [dismissed, setDismissed] = useState(true)

  useEffect(() => {
    if (isStandalone()) return
    let alreadyDismissed = false
    try {
      alreadyDismissed = localStorage.getItem(DISMISS_KEY) === '1'
    } catch {
      /* localStorage khong kha dung (private mode...) - coi nhu chua tat */
    }
    if (alreadyDismissed) return
    setDismissed(false)

    if (isIosSafari()) {
      setIosHint(true)
      return
    }

    function onBeforeInstallPrompt(e) {
      e.preventDefault()
      setDeferredPrompt(e)
    }
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    return () => window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  }, [])

  function dismiss() {
    setDismissed(true)
    try {
      localStorage.setItem(DISMISS_KEY, '1')
    } catch {
      /* bo qua neu khong luu duoc */
    }
  }

  async function install() {
    if (!deferredPrompt) return
    deferredPrompt.prompt()
    await deferredPrompt.userChoice
    setDeferredPrompt(null)
    dismiss()
  }

  if (dismissed || (!deferredPrompt && !iosHint)) return null

  return (
    <div
      style={{
        position: 'fixed', left: 12, right: 12, bottom: 12, zIndex: 2000,
        maxWidth: 420, margin: '0 auto',
        background: 'var(--card, #fff)', border: '1px solid var(--card-border)', borderRadius: 10,
        boxShadow: '0 8px 24px rgba(0,0,0,0.18)', padding: 12,
        display: 'flex', alignItems: 'center', gap: 10,
      }}
    >
      <span style={{ fontSize: 20 }}>📲</span>
      <div style={{ flex: 1, fontSize: 13 }}>
        {iosHint ? (
          <>
            Cài đặt: bấm nút Chia sẻ (⬆️) trong Safari rồi chọn <b>"Thêm vào Màn hình chính"</b>.
            <div className="muted-note" style={{ fontSize: 11, marginTop: 2 }}>
              Thông báo đẩy chỉ hoạt động trên iOS 16.4+ sau khi đã thêm vào Màn hình chính.
            </div>
          </>
        ) : (
          'Cài ứng dụng để mở nhanh hơn và nhận thông báo đẩy.'
        )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {!iosHint && (
          <button className="btn-sm" onClick={install}>Cài ứng dụng</button>
        )}
        <button className="btn-outline btn-sm" onClick={dismiss}>Đóng</button>
      </div>
    </div>
  )
}
