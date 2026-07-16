import { useEffect, useRef, useState } from 'react'
import Modal from './Modal'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { compressImageFile } from '../utils/compressImage'

export default function UserMenu() {
  const { user, setUser } = useAuth()
  const [open, setOpen] = useState(false)
  const [passwordModal, setPasswordModal] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [passwordMessage, setPasswordMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const boxRef = useRef(null)
  const fileRef = useRef(null)

  useEffect(() => {
    function onClickOutside(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  async function handleAvatarFile(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    const dataUrl = await compressImageFile(file)
    const { data } = await api.post('/auth/me/avatar/', { avatar: dataUrl })
    setUser(data)
    setOpen(false)
  }

  function openPasswordModal() {
    setOldPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setPasswordError('')
    setPasswordMessage('')
    setPasswordModal(true)
    setOpen(false)
  }

  async function savePassword() {
    if (newPassword !== confirmPassword) {
      setPasswordError('Mật khẩu mới nhập lại không khớp.')
      return
    }
    setSaving(true)
    setPasswordError('')
    try {
      await api.post('/auth/me/change-password/', { old_password: oldPassword, new_password: newPassword })
      setPasswordMessage('Đã đổi mật khẩu.')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setPasswordError(err.response?.data?.detail || 'Không đổi được mật khẩu.')
    } finally {
      setSaving(false)
    }
  }

  const initial = (user?.full_name || user?.username || '?').charAt(0).toUpperCase()

  return (
    <div ref={boxRef} style={{ position: 'relative' }}>
      <button
        className="user-menu-trigger"
        onClick={() => setOpen((v) => !v)}
        style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt="" className="user-avatar-img" />
          ) : (
            <span className="user-avatar-fallback">{initial}</span>
          )}
          <span className="topbar-user">{user?.full_name || user?.username}</span>
        </div>
      </button>

      {open && (
        <div className="user-menu-popup">
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={handleAvatarFile} />
          <button className="user-menu-item" onClick={() => fileRef.current?.click()}>
            Đổi ảnh đại diện
          </button>
          <button className="user-menu-item" onClick={openPasswordModal}>
            Đổi mật khẩu
          </button>
        </div>
      )}

      <Modal
        open={passwordModal}
        title="Đổi mật khẩu"
        onClose={() => setPasswordModal(false)}
        footer={
          <>
            <button className="btn-outline" onClick={() => setPasswordModal(false)}>
              Đóng
            </button>
            <button onClick={savePassword} disabled={saving}>
              Lưu
            </button>
          </>
        }
      >
        <div style={{ display: 'grid', gap: 10 }}>
          <label>
            Mật khẩu cũ
            <input
              type="password"
              style={{ display: 'block', width: '100%' }}
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
            />
          </label>
          <label>
            Mật khẩu mới
            <input
              type="password"
              style={{ display: 'block', width: '100%' }}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </label>
          <label>
            Nhập lại mật khẩu mới
            <input
              type="password"
              style={{ display: 'block', width: '100%' }}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </label>
          {passwordError && <p style={{ color: 'var(--danger)' }}>{passwordError}</p>}
          {passwordMessage && <p style={{ color: 'var(--forest-dark)' }}>{passwordMessage}</p>}
        </div>
      </Modal>
    </div>
  )
}
