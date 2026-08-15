import { useEffect, useState } from 'react'
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

export default function DashboardConfigPage() {
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
    <AppShell>
      <h2>Cấu hình Dashboard</h2>
      <p className="muted-note">
        Bật/tắt từng chỉ số, chọn màn hiển thị (Hồ sơ 360 / CEO / GĐĐT) và ngưỡng tô màu. Chỉ số tắt sẽ
        không hiện; chỉ số bật nhưng chưa có dữ liệu hiện nhãn "Chờ dữ liệu".
      </p>

      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button onClick={seedDefaults} disabled={seeding}>Khởi tạo khung năng lực + danh sách chỉ số mặc định</button>
        {seedMsg && <span className="muted-note">{seedMsg}</span>}
      </div>

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
    </AppShell>
  )
}
