import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { applyBrand } from '../utils/color'
import { BRAND_COLORS } from '../config/brandColors'
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

  if (loading) return <p className="muted-note">Đang tải...</p>

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Thông tin chung</h3>
      <div style={{ display: 'grid', gap: 12, maxWidth: 520 }}>
        <label>
          Tên hệ thống
          <input style={{ ...s.input, width: '100%' }} value={form.system_name} onChange={(e) => set('system_name', e.target.value)} />
        </label>
        <label>
          Logo (URL)
          <input style={{ ...s.input, width: '100%' }} value={form.logo_url} onChange={(e) => set('logo_url', e.target.value)} placeholder="https://..." />
        </label>
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
                  <td>{GRADING_FIELDS.find((f) => f.key === row.field)?.label || row.field}</td>
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
    </AppShell>
  )
}
