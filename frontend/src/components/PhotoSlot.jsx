import { useRef, useState } from 'react'
import { compressImageFile } from '../utils/compressImage'

export default function PhotoSlot({ label, value, onChange }) {
  const inputRef = useRef(null)
  const [error, setError] = useState('')

  async function handleFile(e) {
    const file = e.target.files[0]
    if (!file) return
    try {
      const dataUrl = await compressImageFile(file)
      onChange(dataUrl)
      setError('')
    } catch {
      setError('Không xử lý được ảnh.')
    }
  }

  return (
    <div style={{ textAlign: 'center' }}>
      <div
        onClick={() => inputRef.current?.click()}
        style={{
          width: 140,
          height: 105,
          border: '2px dashed #999',
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          overflow: 'hidden',
          background: '#fafafa',
        }}
      >
        {value ? (
          <img src={value} alt={label} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ color: '#999', fontSize: 13 }}>+ Chụp / Tải ảnh</span>
        )}
      </div>
      <div style={{ marginTop: 4, fontSize: 13 }}>{label}</div>
      {error && <div style={{ color: 'red', fontSize: 11 }}>{error}</div>}
      {/* Bỏ 'capture' để trên điện thoại hiện lựa chọn Chụp ảnh HOẶC chọn ảnh có sẵn trong máy */}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleFile}
      />
    </div>
  )
}
