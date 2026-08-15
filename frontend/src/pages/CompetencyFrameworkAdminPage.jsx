import { useState } from 'react'
import AppShell from '../components/AppShell'
import Table from '../components/Table'
import api from '../api/client'
import { usePaginatedList } from '../hooks/usePaginatedList'
import * as s from './listPageStyles'

function ImportCard({ title, hint, endpoint, onDone }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function upload() {
    if (!file) {
      setError('Chọn file CSV.')
      return
    }
    setUploading(true)
    setError('')
    setResult(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await api.post(endpoint, formData)
      setResult(data)
      onDone?.()
    } catch (err) {
      setError(err.response?.data?.detail || 'Import thất bại.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="card" style={{ flex: '1 1 320px', minWidth: 280 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      <p className="muted-note">{hint}</p>
      <input type="file" accept=".csv" onChange={(e) => setFile(e.target.files[0] || null)} />
      <div style={{ marginTop: 8 }}>
        <button onClick={upload} disabled={uploading}>Import</button>
      </div>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {result && (
        <div style={{ marginTop: 8, fontSize: 13 }}>
          <div style={{ color: 'var(--forest-dark)' }}>
            Đã ghi {result.targets_written ?? result.weights_written} dòng
            {result.positions ? ` (${result.positions} vị trí)` : ''}.
          </div>
          {(result.warnings || []).map((w, i) => (
            <div key={i} className="muted-note">⚠ {w}</div>
          ))}
        </div>
      )}
    </div>
  )
}

function FrameworkTree({ refreshKey }) {
  const { data: groups } = usePaginatedList('/dashboard/competency-groups/', { page_size: 50, refreshKey })
  const { data: competencies } = usePaginatedList('/dashboard/competencies/', { page_size: 200, refreshKey })

  return (
    <div>
      {groups.results.map((g) => (
        <div key={g.id} style={{ marginBottom: 10 }}>
          <strong>{g.code} — {g.name}</strong>
          <span className="muted-note"> ({g.competencies_count} năng lực)</span>
          <ul style={{ margin: '4px 0 0 20px' }}>
            {competencies.results.filter((c) => c.group === g.id).map((c) => (
              <li key={c.id}>{c.name}</li>
            ))}
          </ul>
        </div>
      ))}
      {groups.results.length === 0 && <p className="muted-note">Chưa có nhóm năng lực nào.</p>}
    </div>
  )
}

function AddGroupForm({ onAdded }) {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')

  async function save() {
    if (!code.trim() || !name.trim()) {
      setError('Nhập mã và tên nhóm.')
      return
    }
    try {
      await api.post('/dashboard/competency-groups/', { code: code.trim(), name: name.trim() })
      setCode('')
      setName('')
      setError('')
      onAdded()
    } catch (err) {
      setError(err.response?.data?.detail || 'Không tạo được nhóm.')
    }
  }

  return (
    <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
      <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Mã (vd E)" style={{ ...s.input, width: 80 }} />
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tên nhóm..." style={{ ...s.input, flex: 1, minWidth: 160 }} />
      <button onClick={save}>+ Thêm nhóm</button>
      {error && <span style={{ color: 'var(--danger)' }}>{error}</span>}
    </div>
  )
}

function PositionLookup() {
  const [position, setPosition] = useState('')
  const [targets, setTargets] = useState([])
  const [weights, setWeights] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)

  async function search() {
    if (!position.trim()) return
    setLoading(true)
    try {
      const [t, w] = await Promise.all([
        api.get('/dashboard/position-targets/', { params: { position: position.trim(), page_size: 100 } }),
        api.get('/dashboard/position-weights/', { params: { position: position.trim(), page_size: 20 } }),
      ])
      setTargets(t.data.results)
      setWeights(w.data.results)
      setSearched(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>Xem cấu hình theo vị trí</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          value={position} onChange={(e) => setPosition(e.target.value)}
          placeholder="Tên vị trí (đúng như trong file, vd 'NV Phục vụ')" style={{ ...s.input, flex: 1 }}
        />
        <button onClick={search} disabled={loading}>Xem</button>
      </div>
      {weights.length > 0 && (
        <p className="muted-note">
          Trọng số nhóm: {weights.map((w) => `${w.group_code} ${w.weight}%`).join(' · ')}
        </p>
      )}
      {targets.length > 0 && (
        <Table>
          <thead><tr><th>Nhóm</th><th>Năng lực</th><th>Điểm mục tiêu</th></tr></thead>
          <tbody>
            {targets.map((t) => (
              <tr key={t.id}><td>{t.group_code}</td><td>{t.competency_name}</td><td>{t.target_score}</td></tr>
            ))}
          </tbody>
        </Table>
      )}
      {searched && !loading && targets.length === 0 && weights.length === 0 && (
        <p className="muted-note">
          Không tìm thấy vị trí phù hợp. Kiểm tra lại tên vị trí đã import (không phân biệt hoa/thường/dấu cách).
        </p>
      )}
    </div>
  )
}

export default function CompetencyFrameworkAdminPage() {
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <AppShell>
      <h2>Khung năng lực</h2>
      <p className="muted-note">
        Nhập điểm mục tiêu + trọng số theo vị trí bằng cách xuất 2 sheet của file khung năng lực (v0.5) ra
        CSV rồi import ở đây. Import lại không tạo trùng (ghi đè theo vị trí + năng lực/nhóm).
      </p>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
        <ImportCard
          title="Import mục tiêu theo vị trí"
          hint='Xuất CSV từ sheet "Muc tieu theo vi tri".'
          endpoint="/dashboard/import/targets/"
          onDone={() => setRefreshKey((k) => k + 1)}
        />
        <ImportCard
          title="Import trọng số nhóm"
          hint='Xuất CSV từ sheet "Trong so nhom".'
          endpoint="/dashboard/import/weights/"
          onDone={() => setRefreshKey((k) => k + 1)}
        />
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Nhóm & năng lực</h3>
        <FrameworkTree refreshKey={refreshKey} />
        <AddGroupForm onAdded={() => setRefreshKey((k) => k + 1)} />
      </div>

      <PositionLookup />
    </AppShell>
  )
}
