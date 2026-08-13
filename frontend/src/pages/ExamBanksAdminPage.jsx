import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/AppShell'
import Pager from '../components/Pager'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

const PAGE_SIZE = 20

export default function ExamBanksAdminPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  const { data, loading } = usePaginatedList('/exams/banks/', { page, page_size: PAGE_SIZE, refreshKey })

  async function createBank() {
    if (!name.trim()) {
      setError('Nhập tên ngân hàng câu hỏi.')
      return
    }
    setError('')
    try {
      const { data } = await api.post('/exams/banks/', { name: name.trim() })
      setName('')
      setCreating(false)
      setRefreshKey((k) => k + 1)
      navigate(`/exam-banks/${data.id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Không tạo được ngân hàng câu hỏi.')
    }
  }

  return (
    <AppShell>
      <h2>Ngân hàng câu hỏi</h2>

      <div style={{ marginBottom: 16 }}>
        {!creating ? (
          <button onClick={() => setCreating(true)}>+ Tạo ngân hàng câu hỏi</button>
        ) : (
          <div className="card" style={{ maxWidth: 480 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Tên ngân hàng câu hỏi..."
                style={{ ...s.input, flex: 1 }}
                autoFocus
              />
              <button onClick={createBank}>Tạo</button>
              <button className="btn-outline" onClick={() => { setCreating(false); setError('') }}>
                Hủy
              </button>
            </div>
            {error && <p style={{ color: 'var(--danger)', marginBottom: 0 }}>{error}</p>}
          </div>
        )}
      </div>

      {loading && <p className="muted-note">Đang tải...</p>}
      <Table>
        <thead>
          <tr>
            <th>Tên</th>
            <th>Danh mục</th>
            <th>Số câu hỏi</th>
          </tr>
        </thead>
        <tbody>
          {data.results.map((b) => (
            <tr key={b.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/exam-banks/${b.id}`)}>
              <td>{b.name}</td>
              <td>{b.category}</td>
              <td>{b.questions_count}</td>
            </tr>
          ))}
          {data.results.length === 0 && (
            <tr>
              <td colSpan={3} className="muted-note">
                Chưa có ngân hàng câu hỏi nào.
              </td>
            </tr>
          )}
        </tbody>
      </Table>
      <Pager page={page} pageSize={PAGE_SIZE} count={data.count} onChange={setPage} />
    </AppShell>
  )
}
