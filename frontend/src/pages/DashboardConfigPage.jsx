import { useEffect, useRef, useState } from 'react'
import AppShell from '../components/AppShell'
import Table from '../components/Table'
import api from '../api/client'
import * as s from './listPageStyles'

const ROLE_SCOPE_OPTIONS = [
  { value: 'ho_so', label: 'Hồ sơ 360' },
  { value: 'ceo', label: 'CEO' },
  { value: 'gdt', label: 'GĐĐT' },
]

const DIRECTION_OPTIONS = [
  { value: 'higher_better', label: 'Cao tốt' },
  { value: 'lower_better', label: 'Thấp tốt' },
  { value: 'none', label: 'Không tô màu' },
]

function IndicatorRow({ indicator, onSaved }) {
  const [saving, setSaving] = useState(false)

  async function update(patch) {
    setSaving(true)
    try {
      const { data } = await api.patch(`/dashboard/indicators/${indicator.id}/`, patch)
      onSaved(data)
    } finally {
      setSaving(false)
    }
  }

  function toggleScope(value) {
    const scope = indicator.role_scope || []
    const next = scope.includes(value) ? scope.filter((v) => v !== value) : [...scope, value]
    update({ role_scope: next })
  }

  return (
    <tr style={{ opacity: saving ? 0.6 : 1 }}>
      <td>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="checkbox" checked={indicator.enabled}
            onChange={(e) => update({ enabled: e.target.checked })}
          />
          {indicator.label}
        </label>
      </td>
      <td>{indicator.group_label}</td>
      <td>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {ROLE_SCOPE_OPTIONS.map((opt) => (
            <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
              <input
                type="checkbox" checked={(indicator.role_scope || []).includes(opt.value)}
                onChange={() => toggleScope(opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </div>
      </td>
      <td>
        <select
          value={indicator.direction} style={s.select}
          onChange={(e) => update({ direction: e.target.value })}
        >
          {DIRECTION_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
      </td>
      <td>
        {indicator.direction !== 'none' && (
          <div style={{ display: 'flex', gap: 4 }}>
            <input
              type="number" defaultValue={indicator.green_threshold ?? ''} placeholder="Xanh"
              style={{ ...s.input, width: 70 }}
              onBlur={(e) => update({ green_threshold: e.target.value === '' ? null : Number(e.target.value) })}
            />
            <input
              type="number" defaultValue={indicator.yellow_threshold ?? ''} placeholder="Vàng"
              style={{ ...s.input, width: 70 }}
              onBlur={(e) => update({ yellow_threshold: e.target.value === '' ? null : Number(e.target.value) })}
            />
          </div>
        )}
      </td>
    </tr>
  )
}

function TrainingCostSourceCard() {
  const [csvUrl, setCsvUrl] = useState('')
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')
  const fileRef = useRef(null)

  function load() {
    api.get('/dashboard/training-cost-source/').then(({ data }) => setCsvUrl(data.csv_url || ''))
  }
  useEffect(load, [])

  async function save() {
    setSaving(true)
    setMsg('')
    try {
      await api.put('/dashboard/training-cost-source/', { csv_url: csvUrl })
      setMsg('Đã lưu link.')
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Lưu thất bại.')
    } finally {
      setSaving(false)
    }
  }

  async function syncNow() {
    setSyncing(true)
    setMsg('')
    try {
      const { data } = await api.post('/dashboard/training-cost-source/sync/')
      setMsg(`Đã ghi ${data.written} dòng chi phí${data.warnings?.length ? `, ${data.warnings.length} cảnh báo` : ''}.`)
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Đồng bộ thất bại.')
    } finally {
      setSyncing(false)
    }
  }

  async function importFile(file) {
    if (!file) return
    setMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const { data } = await api.post('/dashboard/training-cost-source/import-file/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setMsg(`Đã nhập ${data.written} dòng chi phí${data.warnings?.length ? `, ${data.warnings.length} cảnh báo` : ''}.`)
    } catch (err) {
      setMsg(err.response?.data?.detail || 'Nhập file thất bại.')
    } finally {
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ marginTop: 0 }}>Cổng chờ chi phí đào tạo</h3>
      <p className="muted-note">
        Dán link CSV xuất bản từ Google Sheet (theo mẫu File_HachToan_ChiPhiDaoTao_MAU.xlsx) rồi bấm "Đồng bộ
        ngay", hoặc tải file CSV/Excel lên trực tiếp. Chưa có dữ liệu, các thẻ chi phí trên CEO sẽ hiện
        "Chờ dữ liệu".
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={csvUrl} onChange={(e) => setCsvUrl(e.target.value)}
          placeholder="https://docs.google.com/.../pub?output=csv" style={{ ...s.input, flex: 1, minWidth: 260 }}
        />
        <button onClick={save} disabled={saving}>Lưu link</button>
        <button className="btn-outline" onClick={syncNow} disabled={syncing || !csvUrl}>Đồng bộ ngay</button>
        <input
          ref={fileRef} type="file" accept=".csv,.xlsx,.xlsm" style={{ display: 'none' }}
          onChange={(e) => importFile(e.target.files[0])}
        />
        <button className="btn-outline" onClick={() => fileRef.current?.click()}>Tải file lên</button>
      </div>
      {msg && <p className="muted-note" style={{ marginTop: 8 }}>{msg}</p>}
    </div>
  )
}

// UI dot 3 (Prompt_UI_Dot3_CaiDat_GradingConfig.md muc A): noi dung man nay doi vao lam the
// "Cau hinh Dashboard" trong /settings (SettingsPage.jsx) - tach rieng khoi AppShell de dung
// duoc CA hai noi (AppShell rieng cua trang nay - giu de tuong thich - VA nhung ben trong tab
// cua SettingsPage, tranh long 2 lan AppShell).
export function DashboardConfigContent() {
  const [indicators, setIndicators] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [seeding, setSeeding] = useState(false)
  const [seedMsg, setSeedMsg] = useState('')

  function load() {
    setLoading(true)
    api.get('/dashboard/indicators/', { params: { page_size: 100 } })
      .then(({ data }) => setIndicators(data.results))
      .catch(() => setError('Không tải được danh sách chỉ số.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  function handleSaved(updated) {
    setIndicators((prev) => prev.map((i) => (i.id === updated.id ? updated : i)))
  }

  async function seedDefaults() {
    setSeeding(true)
    setSeedMsg('')
    try {
      const { data } = await api.post('/dashboard/seed-defaults/')
      setSeedMsg(
        `Đã tạo ${data.groups_created} nhóm, ${data.competencies_created} năng lực, `
        + `${data.indicators_created} chỉ số mới (bấm lại không tạo trùng).`,
      )
      load()
    } catch (err) {
      setSeedMsg(err.response?.data?.detail || 'Khởi tạo thất bại.')
    } finally {
      setSeeding(false)
    }
  }

  const groups = [...new Set(indicators.map((i) => i.group_label))]

  return (
    <>
      <p className="muted-note">
        Bật/tắt từng chỉ số, chọn màn hiển thị (Hồ sơ 360 / CEO / GĐĐT) và ngưỡng tô màu. Chỉ số tắt sẽ
        không hiện; chỉ số bật nhưng chưa có dữ liệu hiện nhãn "Chờ dữ liệu".
      </p>

      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={seedDefaults} disabled={seeding}>Khởi tạo khung năng lực + danh sách chỉ số mặc định</button>
        {seedMsg && <span className="muted-note">{seedMsg}</span>}
      </div>

      <TrainingCostSourceCard />

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {groups.map((groupLabel) => (
        <div key={groupLabel} style={{ marginBottom: 20 }}>
          <h3>{groupLabel}</h3>
          <Table>
            <thead>
              <tr>
                <th>Chỉ số</th><th>Nhóm</th><th>Hiện ở màn</th><th>Hướng</th><th>Ngưỡng (Xanh/Vàng)</th>
              </tr>
            </thead>
            <tbody>
              {indicators.filter((i) => i.group_label === groupLabel).map((ind) => (
                <IndicatorRow key={ind.id} indicator={ind} onSaved={handleSaved} />
              ))}
            </tbody>
          </Table>
        </div>
      ))}
    </>
  )
}

export default function DashboardConfigPage() {
  return (
    <AppShell>
      <h2>Cấu hình Dashboard</h2>
      <DashboardConfigContent />
    </AppShell>
  )
}
