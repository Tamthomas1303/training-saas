import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { applyBrand } from '../utils/color'
import { BRAND_COLORS } from '../config/brandColors'
import { compressImageFile } from '../utils/compressImage'
import { ADMIN_CORE_MENU_PATHS, CONFIGURABLE_ROLES, MENU_CATALOG, isEnabledByDefault } from '../config/menuCatalog'
import { DashboardConfigContent } from './DashboardConfigPage'
import * as s from './listPageStyles'

// Man Cai dat /settings - UI dot 3 (Prompt_UI_Dot3_CaiDat_GradingConfig.md muc A). 4 the: Thong
// tin chung / Cau hinh Email / Cau hinh thang danh gia & cong thuc / Cau hinh Dashboard (doi tu
// /dashboard-config vao day - xem App.jsx, route cu gio redirect qua ?tab=dashboard).
const TABS = [
  { key: 'general', label: 'Thông tin chung' },
  { key: 'email', label: 'Cấu hình Email' },
  { key: 'grading', label: 'Cấu hình thang đánh giá & công thức' },
  { key: 'dashboard', label: 'Cấu hình Dashboard' },
  // Muc 16 Phase 1 phan B (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md).
  { key: 'role-menu', label: 'Cấu hình menu theo vai trò' },
]

function TabButton({ active, onClick, children }) {
  return (
    <button
      className={active ? 'btn-sm' : 'btn-sm btn-outline'}
      onClick={onClick}
      style={{ whiteSpace: 'nowrap' }}
    >
      {children}
    </button>
  )
}

function GeneralTab() {
  const { setBrand } = useAuth()
  const [form, setForm] = useState({ system_name: '', logo_url: '', favicon_url: '', brand_hex: '#1e6f5c', theme_mode: 'light' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const logoFileRef = useRef(null)

  useEffect(() => {
    api.get('/settings/brand/')
      .then(({ data }) => setForm({
        system_name: data.system_name || '', logo_url: data.logo_url || '',
        favicon_url: data.favicon_url || '', brand_hex: data.brand_hex || '#1e6f5c',
        theme_mode: data.theme_mode || 'light',
      }))
      .catch(() => setMsg('Không tải được cấu hình thương hiệu.'))
      .finally(() => setLoading(false))
  }, [])

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function save() {
    setSaving(true)
    setMsg('')
    try {
      const { data } = await api.put('/settings/brand/', form)
      applyBrand(data.brand_hex)
      setBrand(data)
      setMsg('Đã lưu. Màu thương hiệu áp dụng ngay.')
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Lưu thất bại - kiểm tra lại dữ liệu (URL logo/favicon phải hợp lệ).')
    } finally {
      setSaving(false)
    }
  }

  async function uploadLogoFile(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    setSaving(true)
    setMsg('')
    try {
      const dataUrl = await compressImageFile(file)
      const { data } = await api.put('/settings/brand/', { ...form, logo_url: dataUrl })
      setForm((f) => ({ ...f, logo_url: data.logo_url }))
      applyBrand(data.brand_hex)
      setBrand(data)
      setMsg('Đã tải logo lên và lưu.')
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Tải logo lên thất bại.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="muted-note">Đang tải...</p>

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Thông tin chung</h3>
      <div style={{ display: 'grid', gap: 12, maxWidth: 520 }}>
        <label>
          Tên hệ thống
          <input style={{ ...s.input, width: '100%' }} value={form.system_name} onChange={(e) => set('system_name', e.target.value)} />
        </label>
        <div>
          <div style={{ marginBottom: 6 }}>Logo</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            {form.logo_url && (
              <img src={form.logo_url} alt="Logo" style={{ height: 40, maxWidth: 120, objectFit: 'contain', border: '1px solid var(--card-border)', borderRadius: 6, background: '#fff' }} />
            )}
            <button type="button" className="btn-outline btn-sm" onClick={() => logoFileRef.current?.click()} disabled={saving}>
              Tải logo lên
            </button>
            <input ref={logoFileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={uploadLogoFile} />
          </div>
          <label>
            Hoặc dán URL logo (link Google Drive dạng chia sẻ sẽ tự chuyển sang link nhúng được)
            <input style={{ ...s.input, width: '100%' }} value={form.logo_url} onChange={(e) => set('logo_url', e.target.value)} placeholder="https://..." />
          </label>
        </div>
        <label>
          Favicon (URL)
          <input style={{ ...s.input, width: '100%' }} value={form.favicon_url} onChange={(e) => set('favicon_url', e.target.value)} placeholder="https://..." />
        </label>
        <div>
          <div style={{ marginBottom: 6 }}>Màu thương hiệu</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
            {BRAND_COLORS.map((c) => (
              <button
                key={c.key} type="button" title={c.name} onClick={() => set('brand_hex', c.hex)}
                style={{
                  width: 28, height: 28, borderRadius: '50%', background: c.hex, cursor: 'pointer',
                  border: form.brand_hex.toLowerCase() === c.hex.toLowerCase() ? '3px solid var(--brand-dark, #333)' : '1px solid var(--card-border)',
                }}
              />
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="color" value={/^#[0-9a-fA-F]{6}$/.test(form.brand_hex) ? form.brand_hex : '#1e6f5c'} onChange={(e) => set('brand_hex', e.target.value)} />
            <input style={{ ...s.input, width: 120 }} value={form.brand_hex} onChange={(e) => set('brand_hex', e.target.value)} placeholder="#1e6f5c" />
          </div>
        </div>
        <label>
          Chế độ hiển thị
          <select style={{ ...s.select, width: '100%' }} value={form.theme_mode} onChange={(e) => set('theme_mode', e.target.value)}>
            <option value="light">Sáng (Light)</option>
            <option value="dark">Tối (Dark)</option>
          </select>
        </label>
        <div>
          <button onClick={save} disabled={saving}>Lưu</button>
          {msg && <span className="muted-note" style={{ marginLeft: 8 }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

function EmailListInput({ label, value, onChange }) {
  const text = (value || []).join(', ')
  return (
    <label>
      {label}
      <input
        style={{ ...s.input, width: '100%' }} defaultValue={text}
        placeholder="email1@x.com, email2@x.com"
        onBlur={(e) => onChange(e.target.value.split(',').map((v) => v.trim()).filter(Boolean))}
      />
    </label>
  )
}

const WEEKDAY_OPTIONS = [
  { value: 0, label: 'Thứ Hai' }, { value: 1, label: 'Thứ Ba' }, { value: 2, label: 'Thứ Tư' },
  { value: 3, label: 'Thứ Năm' }, { value: 4, label: 'Thứ Sáu' }, { value: 5, label: 'Thứ Bảy' },
  { value: 6, label: 'Chủ Nhật' },
]

function EmailTab() {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/settings/email/').then(({ data }) => setForm(data)).catch(() => setMsg('Không tải được cấu hình email.'))
  }, [])

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function save() {
    setSaving(true)
    setMsg('')
    try {
      const { data } = await api.put('/settings/email/', form)
      setForm(data)
      setMsg('Đã lưu.')
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Lưu thất bại.')
    } finally {
      setSaving(false)
    }
  }

  if (!form) return <p className="muted-note">{msg || 'Đang tải...'}</p>

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Cấu hình Email</h3>
      <p className="muted-note">
        Chỉ cấu hình người nhận + lịch gửi báo cáo. Máy chủ gửi thư (SMTP)/mật khẩu KHÔNG cấu hình
        ở đây - giữ nguyên trong biến môi trường của hệ thống (do kỹ thuật quản lý).
      </p>
      <div style={{ display: 'grid', gap: 12, maxWidth: 560 }}>
        <label>
          Tên người gửi hiển thị
          <input style={{ ...s.input, width: '100%' }} value={form.from_display_name || ''} onChange={(e) => set('from_display_name', e.target.value)} />
        </label>
        <EmailListInput label="Người nhận" value={form.recipients} onChange={(v) => set('recipients', v)} />
        <EmailListInput label="CC" value={form.cc} onChange={(v) => set('cc', v)} />

        <div className="card" style={{ background: 'var(--brand-soft, #f4f6f5)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={!!form.weekly_enabled} onChange={(e) => set('weekly_enabled', e.target.checked)} />
            Gửi báo cáo hàng tuần
          </label>
          {form.weekly_enabled && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <select style={s.select} value={form.weekly_weekday} onChange={(e) => set('weekly_weekday', Number(e.target.value))}>
                {WEEKDAY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <select style={s.select} value={form.weekly_hour} onChange={(e) => set('weekly_hour', Number(e.target.value))}>
                {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{h}:00</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="card" style={{ background: 'var(--brand-soft, #f4f6f5)' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={!!form.monthly_enabled} onChange={(e) => set('monthly_enabled', e.target.checked)} />
            Gửi báo cáo hàng tháng
          </label>
          {form.monthly_enabled && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <select style={s.select} value={form.monthly_day} onChange={(e) => set('monthly_day', Number(e.target.value))}>
                {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>Ngày {d}</option>)}
              </select>
              <select style={s.select} value={form.monthly_hour} onChange={(e) => set('monthly_hour', Number(e.target.value))}>
                {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{h}:00</option>)}
              </select>
            </div>
          )}
        </div>

        <label>
          Múi giờ
          <input style={{ ...s.input, width: '100%' }} value={form.timezone || ''} onChange={(e) => set('timezone', e.target.value)} />
        </label>

        <div>
          <button onClick={save} disabled={saving}>Lưu</button>
          {msg && <span className="muted-note" style={{ marginLeft: 8 }}>{msg}</span>}
        </div>
      </div>
    </div>
  )
}

const GRADING_FIELDS = [
  { key: 'exam_pass_percent', label: 'Điểm đạt thi (%)', group: 'Thi' },
  { key: 'skill_pass_percent', label: 'Điểm đạt kỹ năng (%)', group: 'Kỹ năng' },
  { key: 'weight_exam', label: 'Trọng số điểm thi (phiếu kết quả thử việc)', group: 'Điểm tổng hợp' },
  { key: 'weight_practice', label: 'Trọng số điểm thực hành (phiếu kết quả thử việc)', group: 'Điểm tổng hợp' },
  { key: 'weight_theory', label: 'Trọng số lý thuyết (năng lực - mặc định khi chưa cấu hình riêng)', group: 'Năng lực' },
  { key: 'weight_practical', label: 'Trọng số thực hành (năng lực - mặc định khi chưa cấu hình riêng)', group: 'Năng lực' },
  { key: 'days_staff', label: 'Số ngày - Nhân viên (S)', group: 'Lộ trình' },
  { key: 'days_supervisor_deputy', label: 'Số ngày - Giám sát/Bếp phó', group: 'Lộ trình' },
  { key: 'days_manager_chef', label: 'Số ngày - Quản lý/Bếp trưởng', group: 'Lộ trình' },
  { key: 'allowance_per_person', label: 'Phụ cấp / người (đ)', group: 'Phụ cấp' },
  { key: 'allowance_exam_min', label: 'Ngưỡng điểm thi tối thiểu để tính phụ cấp (%)', group: 'Phụ cấp' },
  { key: 'allowance_skill_min', label: 'Ngưỡng điểm kỹ năng tối thiểu để tính phụ cấp (%)', group: 'Phụ cấp' },
  { key: 'cert_positions_required', label: 'Số vị trí tối thiểu để đạt chứng chỉ', group: 'Chứng chỉ' },
]

// Muc 11 muc 3 (Prompt_Muc11_KPI_Gio.md) - bang "vi tri -> muc tieu gio/thang", hien khi
// GradingConfig.kpi_mode='hours'. position='' = gia tri MAC DINH CHUNG.
function KpiHourTargetsPanel() {
  const [positions, setPositions] = useState([])
  const [targets, setTargets] = useState([])
  const [form, setForm] = useState({ id: null, position: '', target_minutes_per_month: '' })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  function load() {
    api.get('/employees/positions-catalog/', { params: { page_size: 200 } })
      .then(({ data }) => setPositions(data.results || []))
      .catch(() => {})
    api.get('/kpi/hour-targets/', { params: { page_size: 200 } })
      .then(({ data }) => setTargets(data.results || []))
      .catch(() => {})
  }
  useEffect(load, [])

  function openCreate() {
    setForm({ id: null, position: '', target_minutes_per_month: '' })
    setMsg('')
  }

  function openEdit(t) {
    setForm({ id: t.id, position: t.position, target_minutes_per_month: t.target_minutes_per_month })
    setMsg('')
  }

  async function save() {
    setSaving(true)
    setMsg('')
    const payload = {
      position: form.position,
      target_minutes_per_month: Number(form.target_minutes_per_month) || 0,
    }
    try {
      if (form.id) {
        await api.patch(`/kpi/hour-targets/${form.id}/`, payload)
      } else {
        await api.post('/kpi/hour-targets/', payload)
      }
      openCreate()
      load()
    } catch (err) {
      setMsg(
        err.response?.data?.detail ||
          Object.values(err.response?.data || {}).flat().join(' ') ||
          'Không lưu được mục tiêu.'
      )
    } finally {
      setSaving(false)
    }
  }

  async function removeTarget(t) {
    if (!window.confirm(`Xóa mục tiêu giờ cho "${t.position || '(mặc định chung)'}"?`)) return
    await api.delete(`/kpi/hour-targets/${t.id}/`)
    load()
  }

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <h3 style={{ marginTop: 0 }}>Mục tiêu giờ đào tạo/tháng theo vị trí</h3>
      <p className="muted-note">
        Áp theo vị trí/chức danh của người tổ chức buổi (BQL). Thêm 1 dòng để trống "Vị trí" làm
        giá trị mặc định chung, dùng khi vị trí chưa đặt riêng.
      </p>
      <Table>
        <thead>
          <tr>
            <th>Vị trí</th>
            <th>Mục tiêu (phút/tháng)</th>
            <th>≈ Giờ/tháng</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {targets.map((t) => (
            <tr key={t.id}>
              <td>{t.position || <span className="muted-note">(mặc định chung)</span>}</td>
              <td>{t.target_minutes_per_month}</td>
              <td>{(t.target_minutes_per_month / 60).toFixed(1)}h</td>
              <td style={{ display: 'flex', gap: 6 }}>
                <button className="btn-outline btn-sm" onClick={() => openEdit(t)}>Sửa</button>
                <button className="btn-danger btn-sm" onClick={() => removeTarget(t)}>Xóa</button>
              </td>
            </tr>
          ))}
          {targets.length === 0 && (
            <tr>
              <td colSpan={4} className="muted-note">Chưa có mục tiêu nào.</td>
            </tr>
          )}
        </tbody>
      </Table>

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap', marginTop: 12 }}>
        <label style={{ fontSize: 13 }}>
          Vị trí
          <select
            style={{ ...s.select, display: 'block' }}
            value={form.position}
            onChange={(e) => setForm({ ...form, position: e.target.value })}
          >
            <option value="">(mặc định chung)</option>
            {positions.map((p) => (
              <option key={p.id} value={p.name}>{p.name}</option>
            ))}
          </select>
        </label>
        <label style={{ fontSize: 13 }}>
          Mục tiêu (phút/tháng)
          <input
            type="number" min={0}
            style={{ ...s.input, display: 'block', width: 140 }}
            value={form.target_minutes_per_month}
            onChange={(e) => setForm({ ...form, target_minutes_per_month: e.target.value })}
          />
        </label>
        <button onClick={save} disabled={saving}>{form.id ? 'Cập nhật' : '+ Thêm'}</button>
        {form.id && <button className="btn-outline" onClick={openCreate}>Hủy sửa</button>}
      </div>
      {msg && <p style={{ color: 'var(--danger)' }}>{msg}</p>}
    </div>
  )
}

function GradingTab() {
  const [config, setConfig] = useState(null)
  const [form, setForm] = useState({})
  const [history, setHistory] = useState([])
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  function load() {
    api.get('/settings/grading/').then(({ data }) => { setConfig(data); setForm(data) }).catch(() => setMsg('Không tải được cấu hình.'))
    api.get('/settings/grading/history/').then(({ data }) => setHistory(Array.isArray(data) ? data : [])).catch(() => {})
  }
  useEffect(load, [])

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function save() {
    setSaving(true)
    setMsg('')
    try {
      const { data } = await api.put('/settings/grading/', form)
      setConfig(data)
      setForm(data)
      setMsg(data._changed_count > 0 ? `Đã lưu ${data._changed_count} thay đổi.` : 'Không có thay đổi.')
      api.get('/settings/grading/history/').then(({ data: h }) => setHistory(Array.isArray(h) ? h : [])).catch(() => {})
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Lưu thất bại - kiểm tra lại dữ liệu nhập.')
    } finally {
      setSaving(false)
    }
  }

  if (!config) return <p className="muted-note">{msg || 'Đang tải...'}</p>

  const groups = [...new Set(GRADING_FIELDS.map((f) => f.group))]

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Cấu hình thang đánh giá & công thức</h3>
        <p className="muted-note">
          Đổi các con số này sẽ ảnh hưởng trực tiếp đến kết quả thi/đạt thử việc, hoa hồng trainer
          và điều kiện chứng chỉ trên toàn hệ thống. Mỗi lần lưu, thay đổi từng trường được ghi lại
          ở lịch sử bên dưới.
        </p>

        {/* Muc 11 (Prompt_Muc11_KPI_Gio.md muc 1) - cong tac che do KPI. Mac dinh 'sessions'
            (dem so buoi) - giu nguyen hanh vi hien tai; chi bat 'hours' khi can theo doi GIO. */}
        <div className="card" style={{ background: 'var(--brand-soft, #f4f6f5)', marginBottom: 16 }}>
          <label style={{ fontSize: 13, fontWeight: 'bold' }}>
            Chế độ KPI đào tạo
            <select
              style={{ ...s.select, width: '100%', marginTop: 4 }}
              value={form.kpi_mode || 'sessions'}
              onChange={(e) => set('kpi_mode', e.target.value)}
            >
              <option value="sessions">Đếm số buổi (mặc định)</option>
              <option value="hours">Đếm giờ đào tạo</option>
            </select>
          </label>
          <p className="muted-note" style={{ marginTop: 6, marginBottom: 0 }}>
            Bật "Đếm giờ đào tạo" sẽ kích hoạt: thời lượng chuẩn cho nội dung (tab Tài liệu), mục
            tiêu giờ/tháng theo vị trí (bảng bên dưới, hiện sau khi lưu), và ô thời lượng khi ghi
            buổi KPI. Không xóa số liệu đếm buổi hiện có.
          </p>
        </div>

        {groups.map((groupName) => (
          <div key={groupName} style={{ marginBottom: 16 }}>
            <h4 style={{ marginBottom: 8 }}>{groupName}</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
              {GRADING_FIELDS.filter((f) => f.group === groupName).map((f) => (
                <label key={f.key} style={{ fontSize: 13 }}>
                  {f.label}
                  <input
                    style={{ ...s.input, width: '100%' }} type="number" step="any"
                    value={form[f.key] ?? ''} onChange={(e) => set(f.key, e.target.value)}
                  />
                </label>
              ))}
              {groupName === 'Phụ cấp' && (
                <label style={{ fontSize: 13 }}>
                  Áp dụng hoa hồng cho nhà hàng (mã, cách nhau dấu phẩy - để trống = tất cả)
                  <input
                    style={{ ...s.input, width: '100%' }}
                    defaultValue={(form.allowance_scope || []).join(', ')}
                    placeholder="VD: NH1, NH2 (để trống = áp dụng tất cả)"
                    onBlur={(e) => set('allowance_scope', e.target.value.split(',').map((v) => v.trim()).filter(Boolean))}
                  />
                </label>
              )}
            </div>
          </div>
        ))}
        <div>
          <button onClick={save} disabled={saving}>Lưu</button>
          {msg && <span className="muted-note" style={{ marginLeft: 8 }}>{msg}</span>}
        </div>
      </div>

      {config.kpi_mode === 'hours' && <KpiHourTargetsPanel />}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Lịch sử thay đổi</h3>
        {history.length === 0 && <p className="muted-note">Chưa có thay đổi nào.</p>}
        {history.length > 0 && (
          <Table>
            <thead>
              <tr><th>Thời gian</th><th>Người đổi</th><th>Trường</th><th>Giá trị cũ</th><th>Giá trị mới</th></tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id}>
                  <td>{new Date(row.changed_at).toLocaleString('vi-VN')}</td>
                  <td>{row.changed_by_name || '—'}</td>
                  <td>
                    {row.field === 'kpi_mode'
                      ? 'Chế độ KPI'
                      : GRADING_FIELDS.find((f) => f.key === row.field)?.label || row.field}
                  </td>
                  <td>{row.old_value}</td>
                  <td>{row.new_value}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>
    </>
  )
}

function RoleMenuTab() {
  const { setRoleMenuConfig } = useAuth()
  // overrides: {role: [path,...]} CHI cho vai tro DA cau hinh rieng (tu API) - vai tro vang mat
  // dung mac dinh tinh boi isEnabledByDefault (xem config/menuCatalog.js).
  const [overrides, setOverrides] = useState(null)
  const [history, setHistory] = useState([])
  const [saving, setSaving] = useState('')
  const [msg, setMsg] = useState('')

  function load() {
    api.get('/settings/role-menu/').then(({ data }) => setOverrides(data || {})).catch(() => setOverrides({}))
    api.get('/settings/role-menu/history/').then(({ data }) => setHistory(Array.isArray(data) ? data : [])).catch(() => {})
  }
  useEffect(load, [])

  function isEnabled(role, path) {
    const rowsForRole = overrides?.[role]
    if (rowsForRole) return rowsForRole.includes(path)
    return isEnabledByDefault(role, path)
  }

  async function toggle(role, path) {
    // Cau hinh phai luu CA danh sach (menu_keys), khong phai 1 co bat/tat rieng le - neu vai tro
    // nay CHUA co override, xuat phat tu toan bo tap mac dinh hien tai (khong chi 1 muc) roi moi
    // dao trang thai dung path vua bam, tranh vo tinh xoa mat cac muc mac dinh khac.
    const current = overrides?.[role] || MENU_CATALOG.filter((m) => isEnabledByDefault(role, m.path)).map((m) => m.path)
    const next = current.includes(path) ? current.filter((p) => p !== path) : [...current, path]

    setSaving(`${role}:${path}`)
    setMsg('')
    try {
      const { data } = await api.put('/settings/role-menu/', { role, menu_keys: next })
      const updated = { ...(overrides || {}), [role]: data.menu_keys }
      setOverrides(updated)
      setRoleMenuConfig(updated)
      api.get('/settings/role-menu/history/').then(({ data: h }) => setHistory(Array.isArray(h) ? h : [])).catch(() => {})
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Không lưu được cấu hình.')
    } finally {
      setSaving('')
    }
  }

  if (!overrides) return <p className="muted-note">Đang tải...</p>

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ marginTop: 0 }}>Cấu hình menu theo vai trò</h3>
        <p className="muted-note">
          Bật/tắt các thẻ menu hiển thị cho từng vai trò. Đây CHỈ là cấu hình hiển thị — bật một
          thẻ không cấp thêm quyền: nếu vai trò đó vốn không có quyền vào màn tương ứng, thẻ sẽ
          hiện nhưng truy cập vẫn bị chặn như bình thường. Các thẻ cốt lõi của Admin (đánh dấu 🔒)
          luôn được giữ để tránh Admin tự khóa mình khỏi màn Cài đặt này.
        </p>
        {msg && <p style={{ color: 'var(--danger)' }}>{msg}</p>}
        <div className="table-sticky">
          <Table>
            <thead>
              <tr>
                <th>Thẻ / Chức năng</th>
                {CONFIGURABLE_ROLES.map((r) => (
                  <th key={r.value} style={{ textAlign: 'center' }}>{r.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MENU_CATALOG.map((m) => (
                <tr key={m.path}>
                  <td>{m.label} <span className="muted-note" style={{ fontSize: 11 }}>{m.path}</span></td>
                  {CONFIGURABLE_ROLES.map((r) => {
                    const locked = r.value === 'admin' && ADMIN_CORE_MENU_PATHS.includes(m.path)
                    const checked = locked || isEnabled(r.value, m.path)
                    return (
                      <td key={r.value} style={{ textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={locked || saving === `${r.value}:${m.path}`}
                          title={locked ? 'Thẻ cốt lõi của Admin - luôn bật' : ''}
                          onChange={() => toggle(r.value, m.path)}
                        />
                        {locked && ' 🔒'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Lịch sử thay đổi</h3>
        {history.length === 0 && <p className="muted-note">Chưa có thay đổi nào.</p>}
        {history.length > 0 && (
          <Table>
            <thead>
              <tr><th>Thời gian</th><th>Người đổi</th><th>Vai trò</th><th>Số thẻ trước</th><th>Số thẻ sau</th></tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id}>
                  <td>{new Date(row.changed_at).toLocaleString('vi-VN')}</td>
                  <td>{row.changed_by_name || '—'}</td>
                  <td>{CONFIGURABLE_ROLES.find((r) => r.value === row.role)?.label || row.role}</td>
                  <td>{row.old_keys.length}</td>
                  <td>{row.new_keys.length}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </div>
    </>
  )
}

export default function SettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = TABS.some((t) => t.key === searchParams.get('tab')) ? searchParams.get('tab') : 'general'

  function goTab(key) {
    setSearchParams({ tab: key })
  }

  return (
    <AppShell>
      <h2>Cài đặt</h2>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {TABS.map((t) => (
          <TabButton key={t.key} active={tab === t.key} onClick={() => goTab(t.key)}>{t.label}</TabButton>
        ))}
      </div>

      {tab === 'general' && <GeneralTab />}
      {tab === 'email' && <EmailTab />}
      {tab === 'grading' && <GradingTab />}
      {tab === 'dashboard' && <DashboardConfigContent />}
      {tab === 'role-menu' && <RoleMenuTab />}
    </AppShell>
  )
}
