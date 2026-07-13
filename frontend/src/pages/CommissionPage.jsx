import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import * as s from './listPageStyles'

const STATUS_LABELS = {
  waiting: 'Chờ',
  eligible: 'Đủ điều kiện',
  retrain: 'Đào tạo lại',
  paid: 'Đã chi',
}

const STATUS_COLORS = {
  waiting: { bg: '#fef3c7', fg: '#92400e' },
  eligible: { bg: '#e3f3ec', fg: '#1e7a55' },
  retrain: { bg: '#fde8e8', fg: '#c0392b' },
  paid: { bg: '#eee', fg: '#555' },
}

function Check({ ok }) {
  return <span style={{ color: ok ? '#1e7a55' : '#c0392b' }}>{ok ? '✓' : '✗'}</span>
}

export default function CommissionPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  function load() {
    setLoading(true)
    api
      .get('/kpi/commission/')
      .then(({ data }) => setRows(data))
      .catch(() => setError('Không tải được dữ liệu phụ cấp.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [])

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
    <div style={s.page}>
      <NavBar />
      <h2>Phụ cấp / Hoa hồng trainer</h2>
      <p style={{ fontSize: 13, color: '#666' }}>
        300.000đ/nhân sự khi đủ 5 điều kiện: LMS xong, thi ≥80%, checklist đào tạo 100%, BQL đánh
        giá kỹ năng ≥85%, làm đủ 30 ngày. AM/KCS kiểm tra random không đạt → tạm dừng (đào tạo lại).
      </p>

      <p>
        <strong>Tổng phụ cấp đủ điều kiện/đã chi:</strong>{' '}
        {totalEligible.toLocaleString('vi-VN')}đ
        {isAdmin && (
          <button onClick={recomputeAll} style={{ marginLeft: 16 }}>
            Tính lại toàn bộ
          </button>
        )}
      </p>

      {loading && <p>Đang tải...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && <p style={{ color: 'green' }}>{message}</p>}

      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>Trainer</th>
            <th style={s.th}>Nhân sự</th>
            <th style={s.th}>Nhà hàng</th>
            <th style={s.th}>LMS</th>
            <th style={s.th}>Thi</th>
            <th style={s.th}>Đào tạo</th>
            <th style={s.th}>KN≥85</th>
            <th style={s.th}>Đủ 1 tháng</th>
            <th style={s.th}>Số tiền</th>
            <th style={s.th}>Trạng thái</th>
            <th style={s.th}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const colors = STATUS_COLORS[r.status] || {}
            return (
              <tr key={r.id}>
                <td style={s.td}>{r.trainer_name}</td>
                <td style={s.td}>
                  {r.employee_code} - {r.employee_name}
                </td>
                <td style={s.td}>{r.restaurant_name}</td>
                <td style={s.td}>
                  <Check ok={r.cond_lms} />
                </td>
                <td style={s.td}>
                  <Check ok={r.cond_exam} />
                </td>
                <td style={s.td}>
                  <Check ok={r.cond_training} />
                </td>
                <td style={s.td}>
                  <Check ok={r.cond_skill_eval} />
                </td>
                <td style={s.td}>
                  <Check ok={r.cond_worked_1month} />
                </td>
                <td style={s.td}>
                  {r.status === 'eligible' || r.status === 'paid'
                    ? `${Number(r.amount).toLocaleString('vi-VN')}đ`
                    : '-'}
                </td>
                <td style={s.td}>
                  <span
                    style={{
                      padding: '2px 8px', borderRadius: 10, fontSize: 12,
                      background: colors.bg, color: colors.fg,
                    }}
                  >
                    {STATUS_LABELS[r.status] || r.status}
                  </span>
                </td>
                <td style={s.td}>
                  {isAdmin && r.status === 'eligible' && (
                    <button onClick={() => markPaid(r.id)}>Đã chi</button>
                  )}
                </td>
              </tr>
            )
          })}
          {rows.length === 0 && !loading && (
            <tr>
              <td style={s.td} colSpan={11}>
                Không có dữ liệu.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
