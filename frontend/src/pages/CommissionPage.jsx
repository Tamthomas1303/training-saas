import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import StatCard from '../components/StatCard'
import Table from '../components/Table'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import * as s from './listPageStyles'

const STATUS_LABELS = {
  waiting: 'Chờ',
  eligible: 'Đủ điều kiện',
  retrain: 'Đào tạo lại',
  paid: 'Đã chi',
}

const STATUS_VARIANTS = {
  waiting: 'warning',
  eligible: 'success',
  retrain: 'danger',
  paid: 'neutral',
}

function Check({ ok }) {
  return <span style={{ color: ok ? 'var(--forest-dark)' : 'var(--danger)' }}>{ok ? '✓' : '✗'}</span>
}

export default function CommissionPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [month, setMonth] = useState('')
  const [year, setYear] = useState('')

  function load() {
    setLoading(true)
    api
      .get('/kpi/commission/', { params: { month: month || undefined, year: year || undefined } })
      .then(({ data }) => setRows(data))
      .catch(() => setError('Không tải được dữ liệu phụ cấp.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [month, year])

  async function markPaid(id) {
    try {
      await api.post(`/kpi/commission/${id}/mark-paid/`)
      setMessage('Đã đánh dấu chi.')
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Thao tác thất bại.')
    }
  }

  async function recomputeAll() {
    setMessage('')
    setError('')
    try {
      const { data } = await api.post('/kpi/commission/recompute/')
      setMessage(`Đã tính lại ${data.processed} nhân sự.`)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Thao tác thất bại.')
    }
  }

  const isAdmin = (user?.role || '').toLowerCase() === 'admin'
  const totalEligible = rows
    .filter((r) => r.status === 'eligible' || r.status === 'paid')
    .reduce((sum, r) => sum + Number(r.amount), 0)

  return (
    <AppShell>
      <h2>Phụ cấp / Hoa hồng trainer</h2>
      <p className="muted-note" style={{ fontSize: 13 }}>
        300.000đ/nhân sự khi đủ 5 điều kiện: LMS xong, thi ≥80%, checklist đào tạo 100%, BQL đánh
        giá kỹ năng ≥85%, làm đủ 30 ngày. AM/KCS kiểm tra random không đạt → tạm dừng (đào tạo lại).
      </p>

      <FilterBar>
        <select style={s.select} value={month} onChange={(e) => setMonth(e.target.value)}>
          <option value="">Tất cả tháng</option>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>
              Tháng {m}
            </option>
          ))}
        </select>
        <select style={s.select} value={year} onChange={(e) => setYear(e.target.value)}>
          <option value="">Tất cả năm</option>
          {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
      </FilterBar>
      <p className="muted-note" style={{ fontSize: 12 }}>
        Tháng/năm ghi lại lần tính gần nhất của mỗi nhân sự (không phải lịch sử các kỳ trước).
      </p>

      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16, marginBottom: 16 }}>
        <StatCard label="Tổng phụ cấp đủ điều kiện/đã chi" amber value={`${totalEligible.toLocaleString('vi-VN')}đ`} />
        {isAdmin && (
          <button className="btn-outline" onClick={recomputeAll}>
            Tính lại toàn bộ
          </button>
        )}
      </div>

      {loading && <p className="muted-note">Đang tải...</p>}
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {message && <p style={{ color: 'var(--forest-dark)' }}>{message}</p>}

      <Table>
        <thead>
          <tr>
            <th>Trainer</th>
            <th>Nhân sự</th>
            <th>Nhà hàng</th>
            <th>LMS</th>
            <th>Thi</th>
            <th>Đào tạo</th>
            <th>KN≥85</th>
            <th>Đủ 1 tháng</th>
            <th>Số tiền</th>
            <th>Trạng thái</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.trainer_name}</td>
              <td>
                {r.employee_code} - {r.employee_name}
              </td>
              <td>{r.restaurant_name}</td>
              <td>
                <Check ok={r.cond_lms} />
              </td>
              <td>
                <Check ok={r.cond_exam} />
              </td>
              <td>
                <Check ok={r.cond_training} />
              </td>
              <td>
                <Check ok={r.cond_skill_eval} />
              </td>
              <td>
                <Check ok={r.cond_worked_1month} />
              </td>
              <td>
                {r.status === 'eligible' || r.status === 'paid'
                  ? `${Number(r.amount).toLocaleString('vi-VN')}đ`
                  : '-'}
              </td>
              <td>
                <Badge variant={STATUS_VARIANTS[r.status] || 'neutral'}>
                  {STATUS_LABELS[r.status] || r.status}
                </Badge>
              </td>
              <td>
                {isAdmin && r.status === 'eligible' && (
                  <button className="btn-sm" onClick={() => markPaid(r.id)}>
                    Đã chi
                  </button>
                )}
              </td>
            </tr>
          ))}
          {rows.length === 0 && !loading && (
            <tr>
              <td colSpan={11} className="muted-note">
                Không có dữ liệu.
              </td>
            </tr>
          )}
        </tbody>
      </Table>
    </AppShell>
  )
}
