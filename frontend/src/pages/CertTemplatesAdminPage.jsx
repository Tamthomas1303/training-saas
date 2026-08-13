import { useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import PhotoSlot from '../components/PhotoSlot'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const TYPES = [
  { value: 'hoc', label: 'Chứng chỉ khóa học' },
  { value: 'thi', label: 'Chứng chỉ bài thi' },
  { value: 'chuong_trinh', label: 'Chứng chỉ chương trình' },
]

const FIELD_LABELS = {
  recipient_name: 'Tên người nhận',
  program_or_course_name: 'Tên khóa/chương trình',
  completion_line: 'Dòng loại hoàn thành',
  issue_date: 'Ngày cấp',
  cert_code: 'Mã chứng chỉ',
}

function FieldsConfigEditor({ config, onChange }) {
  function updateField(key, patch) {
    onChange({ ...config, [key]: { ...config[key], ...patch } })
  }

  return (
    <div className="table-scroll">
      <table className="themed">
        <thead>
          <tr>
            <th>Ô chữ</th><th>X</th><th>Y</th><th>Cỡ chữ</th><th>Đậm</th><th>Căn lề</th>
          </tr>
        </thead>
        <tbody>
          {Object.keys(FIELD_LABELS).map((key) => {
            const f = config[key] || {}
            return (
              <tr key={key}>
                <td>{FIELD_LABELS[key]}</td>
                <td>
                  <input
                    type="number" value={f.x ?? 0}
                    onChange={(e) => updateField(key, { x: Number(e.target.value) })}
                    style={{ ...s.input, width: 70 }}
                  />
                </td>
                <td>
                  <input
                    type="number" value={f.y ?? 0}
                    onChange={(e) => updateField(key, { y: Number(e.target.value) })}
                    style={{ ...s.input, width: 70 }}
                  />
                </td>
                <td>
                  <input
                    type="number" value={f.font_size ?? 14}
                    onChange={(e) => updateField(key, { font_size: Number(e.target.value) })}
                    style={{ ...s.input, width: 60 }}
                  />
                </td>
                <td>
                  <input
                    type="checkbox" checked={!!f.bold}
                    onChange={(e) => updateField(key, { bold: e.target.checked })}
                  />
                </td>
                <td>
                  <select value={f.align || 'center'} onChange={(e) => updateField(key, { align: e.target.value })} style={s.select}>
                    <option value="left">Trái</option>
                    <option value="center">Giữa</option>
                    <option value="right">Phải</option>
                  </select>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="muted-note" style={{ marginTop: 4 }}>
        Toạ độ tính bằng điểm (pt), gốc (0,0) ở góc dưới-trái, khổ ngang 853×603pt.
      </p>
    </div>
  )
}

function TemplateForm({ template, onSaved, onCancel }) {
  const [type, setType] = useState(template?.type || 'hoc')
  const [name, setName] = useState(template?.name || '')
  const [templatePdfUrl, setTemplatePdfUrl] = useState(template?.template_pdf_url || '')
  const [fieldsConfig, setFieldsConfig] = useState(template?.fields_config || {})
  const [active, setActive] = useState(template?.active ?? true)
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleUpload(dataUrl) {
    setUploading(true)
    setError('')
    try {
      const { data } = await api.post('/integration/templates/upload/', { image: dataUrl })
      setTemplatePdfUrl(data.url)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không tải được ảnh mẫu.')
    } finally {
      setUploading(false)
    }
  }

  async function save() {
    if (!name.trim()) {
      setError('Nhập tên mẫu.')
      return
    }
    setSaving(true)
    setError('')
    const payload = { type, name: name.trim(), template_pdf_url: templatePdfUrl, fields_config: fieldsConfig, active }
    try {
      if (template) {
        await api.patch(`/integration/templates/${template.id}/`, payload)
      } else {
        await api.post('/integration/templates/', payload)
      }
      onSaved()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không lưu được mẫu chứng chỉ.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
        <PhotoSlot label={uploading ? 'Đang tải...' : 'Ảnh nền mẫu'} value={templatePdfUrl} onChange={handleUpload} />
        <div style={{ flex: 1, minWidth: 240 }}>
          <input
            value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên mẫu..."
            style={{ ...s.input, width: '100%', marginBottom: 8 }}
          />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select value={type} onChange={(e) => setType(e.target.value)} style={s.select}>
              {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
              <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Đang dùng
            </label>
          </div>
        </div>
      </div>

      <FieldsConfigEditor config={fieldsConfig} onChange={setFieldsConfig} />

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button onClick={save} disabled={saving}>Lưu</button>
        <button className="btn-outline" onClick={onCancel}>Hủy</button>
      </div>
    </div>
  )
}

export default function CertTemplatesAdminPage() {
  const [refreshKey, setRefreshKey] = useState(0)
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const { data, loading } = usePaginatedList('/integration/templates/', { page_size: 50, refreshKey })

  function reload() {
    setCreating(false)
    setEditingId(null)
    setRefreshKey((k) => k + 1)
  }

  return (
    <AppShell>
      <h2>Mẫu chứng chỉ</h2>
      <p className="muted-note">
        Upload ảnh nền mẫu + căn toạ độ ô chữ. Chỉ mẫu <strong>đang dùng</strong> (mới nhất) của mỗi loại
        được dùng để cấp chứng chỉ tự động.
      </p>

      {!creating && !editingId && (
        <button onClick={() => setCreating(true)} style={{ marginBottom: 16 }}>+ Tạo mẫu chứng chỉ</button>
      )}
      {creating && <TemplateForm onSaved={reload} onCancel={() => setCreating(false)} />}

      {loading && <p className="muted-note">Đang tải...</p>}
      {data.results.map((t) => (
        editingId === t.id ? (
          <TemplateForm key={t.id} template={t} onSaved={reload} onCancel={() => setEditingId(null)} />
        ) : (
          <div key={t.id} className="card" style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8 }}>
            {t.template_pdf_url && (
              <img src={t.template_pdf_url} alt={t.name} style={{ width: 80, height: 56, objectFit: 'cover', borderRadius: 6 }} />
            )}
            <div style={{ flex: 1 }}>
              <strong>{t.name}</strong>
              <div className="muted-note">{t.type_display}</div>
            </div>
            <Badge variant={t.active ? 'success' : 'neutral'}>{t.active ? 'Đang dùng' : 'Ngừng'}</Badge>
            <button className="btn-outline btn-sm" onClick={() => setEditingId(t.id)}>Sửa</button>
          </div>
        )
      ))}
      {!loading && data.results.length === 0 && !creating && (
        <p className="muted-note">Chưa có mẫu chứng chỉ nào.</p>
      )}
    </AppShell>
  )
}
