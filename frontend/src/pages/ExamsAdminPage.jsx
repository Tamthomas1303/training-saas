import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Badge from '../components/Badge'
import FilterBar from '../components/FilterBar'
import Pager from '../components/Pager'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

const STATUS_VARIANTS = { draft: 'neutral', published: 'success', archived: 'warning' }

export default function ExamsAdminPage() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')

  const { data, loading } = usePaginatedList('/exams/assessments/', {
    status: statusFilter || undefined, page, page_size: PAGE_SIZE, refreshKey,
  })

  async function createAssessment() {
    if (!title.trim()) {
      setError('Nhập tên đề thi.')
      return
    }
    setError('')
    try {
      const { data } = await api.post('/exams/assessments/', { title: title.trim() })
      setTitle('')
      setCreating(false)
      setRefreshKey((k) => k + 1)
      navigate(`/exams-admin/${data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không tạo được đề thi.')
    }
  }

  return (
    <AppShell>
      <h2>Đề thi</h2>

      <div style={{ marginBottom: 16 }}>
        {!creating ? (
          <button onClick={() => setCreating(true)}>+ Tạo đề thi</button>
        ) : (
          <div className="card" style={{ maxWidth: 480 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Tên đề thi..."
                style={{ ...s.input, flex: 1 }}
                autoFocus
              />
              <button onClick={createAssessment}>Tạo</button>
              <button className="btn-outline" onClick={() => { setCreating(false); setError('') }}>
                Hủy
              </button>
            </div>
            {error && <p style={{ color: 'var(--danger)', marginBottom: 0 }}>{error}</p>}
          </div>
        )}
      </div>

      <FilterBar>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} style={s.select}>
          <option value="">Tất cả trạng thái</option>
          <option value="draft">Nháp</option>
          <option value="published">Xuất bản</option>
          <option value="archived">Lưu trữ</option>
        </select>
      </FilterBar>

      {loading && <p className="muted-note">Đang tải...</p>}
      <Table>
        <thead>
          <tr>
            <th>Tên đề thi</th>
            <th>Trạng thái</th>
            <th>Số câu</th>
            <th>Đã gán</th>
            <th>Điểm đạt</th>
          </tr>
        </thead>
        <tbody>
          {data.results.map((a) => (
            <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/exams-admin/${a.id}`)}>
              <td>{a.title}</td>
              <td><Badge variant={STATUS_VARIANTS[a.status] || 'neutral'}>{a.status_display}</Badge></td>
              <td>{a.questions_count}</td>
              <td>{a.assigned_count}</td>
              <td>{a.pass_mark}%</td>
            </tr>
          ))}
          {data.results.length === 0 && (
            <tr>
              <td colSpan={5} className="muted-note">Chưa có đề thi nào.</td>
            </tr>
          )}
        </tbody>
      </Table>
      <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
    </AppShell>
  )
}
