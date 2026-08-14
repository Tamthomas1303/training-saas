import { useEffect, useRef, useState } from 'react'
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

const SAMPLE_TEXT = {
  recipient_name: 'Nguyễn Văn A',
  program_or_course_name: 'Nghiệp vụ nhà hàng',
  completion_line: 'ĐÃ HOÀN THÀNH KHÓA HỌC',
  issue_date: 'Ngày cấp: 14/08/2026',
  cert_code: 'CC202608ABCD1234',
}
const CERT_W = 853
const CERT_H = 603
const CERT_EDGE_MARGIN = 24

let _measureCanvas
function measureTextWidth(text, px, bold) {
  if (typeof document === 'undefined') return 0
  if (!_measureCanvas) _measureCanvas = document.createElement('canvas')
  const ctx = _measureCanvas.getContext('2d')
  ctx.font = `${bold ? 700 : 400} ${px}px sans-serif`
  return ctx.measureText(text).width
}

// Cỡ chữ hiển thị sau khi tự thu nhỏ cho vừa mép (mirror backend integration/pdf.py::_fit_font_size)
function fittedFontPx(text, x, align, rawPx, scale, bold) {
  let availPt
  if (align === 'left') availPt = CERT_W - x - CERT_EDGE_MARGIN
  else if (align === 'right') availPt = x - CERT_EDGE_MARGIN
  else availPt = 2 * Math.min(x, CERT_W - x) - CERT_EDGE_MARGIN
  const availPx = Math.max(0, availPt * scale)
  if (availPx <= 0) return rawPx
  const w = measureTextWidth(text, rawPx, bold)
  return w > availPx ? Math.max(6, (rawPx * availPx) / w) : rawPx
}

// Trình kéo-thả căn chữ trực tiếp trên ảnh nền (khớp render backend: gốc dưới-trái, Y = chân chữ,
// ảnh phủ kín 853x603). Kéo nhãn -> tự tính toạ độ (pt). Cỡ chữ/căn lề vẫn chỉnh ở bảng số bên dưới.
function CertDragPreview({ imageUrl, config, onChange }) {
  const boxRef = useRef(null)
  const dragRef = useRef(null)
  const [boxW, setBoxW] = useState(680)
  const [dragKey, setDragKey] = useState(null)

  useEffect(() => {
    if (!boxRef.current) return
    const ro = new ResizeObserver((entries) => setBoxW(entries[0].contentRect.width))
    ro.observe(boxRef.current)
    return () => ro.disconnect()
  }, [imageUrl])

  useEffect(() => {
    function move(e) {
      const d = dragRef.current
      if (!d) return
      const scale = boxW / CERT_W
      let x = Math.round(d.startX + (e.clientX - d.grabX) / scale)
      let y = Math.round(d.startY - (e.clientY - d.grabY) / scale) // màn hình đi xuống -> y (gốc dưới) giảm
      x = Math.max(0, Math.min(CERT_W, x))
      y = Math.max(0, Math.min(CERT_H, y))
      const f = config[d.key] || {}
      onChange({ ...config, [d.key]: { ...f, x, y } })
    }
    function up() { dragRef.current = null; setDragKey(null) }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [boxW, config, onChange])

  function onDown(e, key) {
    e.preventDefault()
    const f = config[key] || {}
    dragRef.current = { key, grabX: e.clientX, grabY: e.clientY, startX: f.x ?? CERT_W / 2, startY: f.y ?? CERT_H / 2 }
    setDragKey(key)
  }

  if (!imageUrl) {
    return <p className="muted-note" style={{ marginBottom: 12 }}>Tải ảnh nền mẫu để dùng chế độ kéo-thả căn chữ.</p>
  }

  const scale = boxW / CERT_W
  return (
    <div style={{ marginBottom: 12 }}>
      <p className="muted-note" style={{ marginBottom: 6 }}>
        Kéo từng chữ tới vị trí mong muốn — hệ thống tự tính toạ độ. Cỡ chữ / độ đậm / căn lề chỉnh ở bảng
        dưới. (Xem trước gần đúng; nên sinh thử 1 chứng chỉ để đối chiếu.)
      </p>
      <div
        ref={boxRef}
        style={{
          position: 'relative', width: '100%', maxWidth: 680, aspectRatio: `${CERT_W} / ${CERT_H}`,
          border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', userSelect: 'none', touchAction: 'none',
        }}
      >
        <img
          src={imageUrl} alt="mẫu chứng chỉ"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill', pointerEvents: 'none' }}
        />
        {Object.keys(FIELD_LABELS).map((key) => {
          const f = config[key] || {}
          const x = f.x ?? CERT_W / 2
          const y = f.y ?? CERT_H / 2
          const align = f.align || 'center'
          const anchorX = align === 'center' ? '-50%' : align === 'right' ? '-100%' : '0'
          const fontPx = fittedFontPx(SAMPLE_TEXT[key], x, align, (f.font_size ?? 14) * scale, scale, f.bold)
          return (
            <div
              key={key}
              onPointerDown={(e) => onDown(e, key)}
              title={FIELD_LABELS[key]}
              style={{
                position: 'absolute', left: `${(x / CERT_W) * 100}%`, top: `${(1 - y / CERT_H) * 100}%`,
                transform: `translate(${anchorX}, -80%)`,
                fontSize: Math.max(8, fontPx), fontWeight: f.bold ? 700 : 400,
                whiteSpace: 'nowrap', cursor: 'move', color: '#1a1a3a', padding: '0 2px', borderRadius: 3,
                background: 'rgba(255,255,255,0.35)',
                outline: dragKey === key ? '2px solid var(--forest)' : '1px dashed rgba(0,0,0,0.35)',
              }}
            >
              {SAMPLE_TEXT[key]}
            </div>
          )
        })}
      </div>
    </div>
  )
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

      <CertDragPreview imageUrl={templatePdfUrl} config={fieldsConfig} onChange={setFieldsConfig} />
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
