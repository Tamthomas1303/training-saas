import { useState } from 'react'
import api from '../api/client'
import { submitGuarded } from '../utils/offlineQueue'
import PhotoSlot from './PhotoSlot'
import SignaturePad from './SignaturePad'

const PHOTO_FIELDS = [
  { key: 'img_tailieu', label: 'Tài liệu' },
  { key: 'img_lythuyet', label: 'Lý thuyết' },
  { key: 'img_thuchanh', label: 'Thực hành' },
]

export default function TrainingItemEditor({ employeeId, checklist, progress, onSaved, onClose }) {
  const [draft, setDraft] = useState({
    img_tailieu: '',
    img_lythuyet: '',
    img_thuchanh: '',
    sign_trainer: '',
    sign_trainee: '',
  })
  const [note, setNote] = useState(progress?.note || '')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState('')

  function fieldValue(key) {
    return draft[key] || progress?.[key] || ''
  }

  async function submit(complete) {
    setSaving(true)
    setError('')
    setMessage(null)
    const payload = {
      employee: employeeId,
      checklist: checklist.id,
      note,
      complete,
      ...Object.fromEntries(Object.entries(draft).filter(([, v]) => v)),
    }
    await submitGuarded(
      'training',
      (p) => api.post('/checklist/training/save/', p).then((r) => r.data),
      payload,
      {
        onOk: (data) => {
          setMessage(data)
          onSaved(data)
        },
        onErr: setError,
        onQueued: () => setMessage({ status: 'offline', pdf_url: '' }),
      }
    )
    setSaving(false)
  }

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginTop: 8, background: '#fcfcfc' }}>
      <p style={{ fontSize: 13, color: '#666' }}>
        Mỗi buổi cần đủ 3 ảnh (tài liệu, lý thuyết, thực hành) + 2 chữ ký để hoàn thành.
      </p>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
        {PHOTO_FIELDS.map(({ key, label }) => (
          <PhotoSlot
            key={key}
            label={label}
            value={fieldValue(key)}
            onChange={(v) => setDraft((d) => ({ ...d, [key]: v }))}
          />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
        <SignaturePad
          label="Chữ ký Trainer"
          existingUrl={progress?.sign_trainer}
          value={draft.sign_trainer}
          onChange={(v) => setDraft((d) => ({ ...d, sign_trainer: v }))}
        />
        <SignaturePad
          label="Chữ ký học viên"
          existingUrl={progress?.sign_trainee}
          value={draft.sign_trainee}
          onChange={(v) => setDraft((d) => ({ ...d, sign_trainee: v }))}
        />
      </div>
      <textarea
        placeholder="Ghi chú..."
        value={note}
        onChange={(e) => setNote(e.target.value)}
        style={{ width: '100%', minHeight: 60, marginBottom: 12 }}
      />
      <div style={{ display: 'flex', gap: 8 }}>
        <button disabled={saving} onClick={() => submit(false)}>
          Lưu nháp
        </button>
        <button disabled={saving} onClick={() => submit(true)}>
          Hoàn thành & xuất PDF
        </button>
        <button disabled={saving} onClick={onClose} style={{ marginLeft: 'auto' }}>
          Đóng
        </button>
      </div>
      {saving && <p>Đang lưu...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && message.status === 'offline' && (
        <p style={{ color: '#92400e' }}>Mất mạng - đã lưu nháp offline, sẽ tự đồng bộ khi có mạng.</p>
      )}
      {message && message.status !== 'offline' && (
        <p style={{ color: 'green' }}>
          Đã lưu ({message.status}).{' '}
          {message.pdf_url && (
            <a href={message.pdf_url} target="_blank" rel="noreferrer">
              Xem biên bản PDF
            </a>
          )}
        </p>
      )}
    </div>
  )
}
