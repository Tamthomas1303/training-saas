import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppShell from '../components/AppShell'
import BarChart from '../components/BarChart'
import FilterBar from '../components/FilterBar'
import LineChart from '../components/LineChart'
import RadarChart from '../components/RadarChart'
import StatCard from '../components/StatCard'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

function fmtValue(indicator) {
  if (indicator.pending) return 'Chờ dữ liệu'
  const v = indicator.value
  if (v == null) return 'Chờ dữ liệu'
  if (Number.isInteger(v)) return v.toLocaleString('vi-VN')
  return v.toLocaleString('vi-VN', { maximumFractionDigits: 1 })
}

function fmtDateTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('vi-VN')
}

function IndicatorCard({ indicator }) {
  return (
    <StatCard
      label={indicator.label}
      value={fmtValue(indicator)}
      color={indicator.pending ? 'pending' : indicator.color}
    />
  )
}

export default function DashboardOverviewPage() {
  const now = new Date()
  const [scope, setScope] = useState('ceo')
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [restaurantId, setRestaurantId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 200 })

  function load() {
    setLoading(true)
    setError('')
    api.get('/dashboard/overview/', { params: { scope, month, year, restaurant: restaurantId || undefined } })
      .then(({ data }) => setData(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được dữ liệu tổng hợp.'))
      .finally(() => setLoading(false))
  }
  useEffect(load, [scope, month, year, restaurantId])

  const groups = data ? [...new Set(data.indicators.map((i) => i.group_label))] : []
  const groupAvg = data?.competency_group_avg || []

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>Dashboard tổng hợp</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn-sm ${scope === 'ceo' ? '' : 'btn-outline'}`} onClick={() => setScope('ceo')}>CEO</button>
          <button className={`btn-sm ${scope === 'gdt' ? '' : 'btn-outline'}`} onClick={() => setScope('gdt')}>Giám đốc Đào tạo</button>
        </div>
      </div>

      <FilterBar>
        <select style={s.select} value={month} onChange={(e) => setMonth(Number(e.target.value))}>
          {MONTHS.map((m) => <option key={m} value={m}>Tháng {m}</option>)}
        </select>
        <input
          type="number" style={{ ...s.input, width: 100 }} value={year}
          onChange={(e) => setYear(Number(e.target.value) || now.getFullYear())}
        />
        <select style={s.select} value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)}>
          <option value="">Tất cả nhà hàng</option>
          {restaurantOptions.results.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      {data && !loading && (
        <>
          {groups.map((groupLabel) => (
            <div key={groupLabel} style={{ marginBottom: 20 }}>
              <h3>{groupLabel}</h3>
              {groupLabel === 'Năng lực' && data.competency_snapshot_at && (
                <p className="muted-note" style={{ marginTop: -8, marginBottom: 8 }}>
                  Tính từ dữ liệu nền lúc {fmtDateTime(data.competency_snapshot_at)} (không realtime, cập nhật định kỳ).
                </p>
              )}
              <div className="stat-grid">
                {data.indicators.filter((i) => i.group_label === groupLabel).map((ind) => (
                  <IndicatorCard key={ind.key} indicator={ind} />
                ))}
              </div>
            </div>
          ))}

          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
            {data.restaurant_ranking.length > 0 && (
              <div className="card" style={{ flex: '1 1 420px', minWidth: 320 }}>
                <h3 style={{ marginTop: 0 }}>Xếp hạng nhà hàng (% đúng lộ trình)</h3>
                <BarChart
                  labels={data.restaurant_ranking.map((r) => r.restaurant)}
                  values={data.restaurant_ranking.map((r) => r.on_rate)}
                  colors={data.restaurant_ranking.map((r) => r.color)}
                  height={Math.max(180, data.restaurant_ranking.length * 32)}
                />
                <p className="muted-note" style={{ marginTop: 8 }}>Bấm 1 nhà hàng để lọc toàn màn theo nhà hàng đó:</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {data.restaurant_ranking.map((r) => (
                    <button
                      key={r.restaurant_id} className="btn-sm btn-outline"
                      onClick={() => setRestaurantId(String(r.restaurant_id))}
                    >
                      {r.restaurant} ({r.on_rate}%)
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="card" style={{ flex: '1 1 420px', minWidth: 320 }}>
              <h3 style={{ marginTop: 0 }}>Xu hướng theo tháng (% đúng lộ trình / % đạt kỹ năng lần đầu)</h3>
              <LineChart
                labels={data.trend.map((t) => `${t.month}/${t.year}`)}
                series={[
                  { label: '% đúng lộ trình', data: data.trend.map((t) => t.on_rate) },
                  { label: '% đạt kỹ năng lần đầu', data: data.trend.map((t) => t.skill_rate) },
                ]}
              />
            </div>
          </div>

          {groupAvg.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ marginTop: 0 }}>Radar năng lực trung bình (CI theo nhóm)</h3>
              {data.competency_snapshot_at && (
                <p className="muted-note">Tính từ dữ liệu nền lúc {fmtDateTime(data.competency_snapshot_at)}.</p>
              )}
              <RadarChart labels={groupAvg.map((g) => g.name)} actual={groupAvg.map((g) => g.avg_score)} />
            </div>
          )}

          {data.top_skill_gap.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ marginTop: 0 }}>Top khoảng trống năng lực toàn hệ thống</h3>
              <Table>
                <thead><tr><th>Năng lực</th><th>Gap trung bình</th><th>Số NV thiếu</th></tr></thead>
                <tbody>
                  {data.top_skill_gap.map((g) => (
                    <tr key={g.name}><td>{g.name}</td><td>{g.avg_gap}</td><td>{g.count}</td></tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}

          {data.trainer_breakdown.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ marginTop: 0 }}>Phụ cấp đào tạo theo trainer</h3>
              <Table>
                <thead><tr><th>Trainer</th><th>Số NV</th><th>Tổng phụ cấp</th></tr></thead>
                <tbody>
                  {data.trainer_breakdown.map((t) => (
                    <tr key={t.trainer}>
                      <td>{t.trainer}</td><td>{t.count}</td>
                      <td>{t.amount.toLocaleString('vi-VN')} đ</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          )}

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Bảng cảnh báo hành động</h3>
            {data.warnings_table.length === 0 && <p className="muted-note">Không có cảnh báo nào.</p>}
            {data.warnings_table.length > 0 && (
              <Table>
                <thead><tr><th>Nhân sự</th><th>Nhà hàng</th><th>Trạng thái</th><th></th></tr></thead>
                <tbody>
                  {data.warnings_table.map((w) => (
                    <tr key={w.employee_id}>
                      <td>{w.code} — {w.name}</td>
                      <td>{w.restaurant}</td>
                      <td>
                        {w.type === 'overdue'
                          ? <span style={{ color: 'var(--danger)' }}>Quá hạn {Math.abs(w.days_left)} ngày</span>
                          : <span style={{ color: 'var(--amber)' }}>Còn {w.days_left} ngày</span>}
                      </td>
                      <td><Link to={`/employee-360?employee=${w.employee_id}`}>Xem Hồ sơ 360</Link></td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </div>
        </>
      )}
    </AppShell>
  )
}
