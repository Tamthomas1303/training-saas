import { useState } from 'react'
import Modal from './Modal'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'

// Nhom 1 muc C.3 (Prompt_Nhom1_NhanSu_NguoiDung.md): khi Admin dat lai mat khau tam cho user
// (must_change_password=True), lan dang nhap ke tiep BUOC doi mat khau truoc khi dung tiep he
// thong - modal khong co nut dong/click-ra-ngoai (onClose no-op), CHI bien mat khi doi mat
// khau thanh cong. Mount 1 lan o App.jsx (trong AuthProvider) de ap dung moi role/moi trang.
export default function ForcedPasswordChangeGate() {
  const { user, setUser } = useAuth()
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  if (!user?.must_change_password) return null

  async function save() {
    if (newPassword !== confirmPassword) {
      setError('Mật khẩu mới nhập lại không khớp.')
      return
    }
    setSaving(true)
    setError('')
    try {
      await api.post('/auth/me/change-password/', { old_password: oldPassword, new_password: newPassword })
      setUser({ ...user, must_change_password: false })
    } catch (err) {
      setError(err.response?.data?.detail || 'Không đổi được mật khẩu.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      title="Bắt buộc đổi mật khẩu"
      onClose={() => {}}
      footer={<button onClick={save} disabled={saving}>Đổi mật khẩu</button>}
    >
      <p className="muted-note">
        Tài khoản của bạn vừa được Admin đặt lại mật khẩu tạm. Vui lòng đổi sang mật khẩu mới
        trước khi tiếp tục sử dụng hệ thống.
      </p>
      <div style={{ display: 'grid', gap: 10 }}>
        <label>
          Mật khẩu tạm (đã được cấp)
          <input
            type="password" style={{ display: 'block', width: '100%' }}
            value={oldPassword} onChange={(e) => setOldPassword(e.target.value)}
          />
        </label>
        <label>
          Mật khẩu mới
          <input
            type="password" style={{ display: 'block', width: '100%' }}
            value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
          />
        </label>
        <label>
          Nhập lại mật khẩu mới
          <input
            type="password" style={{ display: 'block', width: '100%' }}
            value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </label>
        {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      </div>
    </Modal>
  )
}
