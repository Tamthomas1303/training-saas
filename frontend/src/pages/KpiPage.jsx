import { useEffect, useState } from 'react'
import NavBar from '../components/NavBar'
import Pager from '../components/Pager'
import PhotoSlot from '../components/PhotoSlot'
import SignaturePad from '../components/SignaturePad'
import api from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { usePaginatedList } from '../hooks/usePaginatedList'
import { submitGuarded } from '../utils/offlineQueue'
import * as s from './listPageStyles'

const SESSIONS_PAGE_SIZE = 20

function KpiSessionForm({ restaurants, defaultRestaurantId, onSaved }) {
  const [restaurantId, setRestaurantId] = useState(defaultRestaurantId || restaurants[0]?.id || '')
  const [topics, setTopics] = useState([])
  const [topic, setTopic] = useState('')
  const [documentId, setDocumentId] = useState(null)
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [participants, setParticipants] = useState([])
  const [participantSearch, setParticipantSearch] = useState('')
  const [participantResults, setParticipantResults] = useState([])
  const [photos, setPhotos] = useState({ img_tailieu: '', img_lythuyet: '', img_thuchanh: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [pdfUrl, setPdfUrl] = useState('')

  useEffect(() => {
    api.get('/kpi/topics/').then(({ data }) => setTopics(data))
  }, [])

  useEffect(() => {
    if (!participantSearch || !restaurantId) {
      setParticipantResults([])
      return
    }
    const timeout = setTimeout(() => {
      api
        .get('/employees/', { params: { search: participantSearch, restaurant: restaurantId, page_size: 10 } })
        .then(({ data }) => setParticipantResults(data.results))
    }, 300)
    return () => clearTimeout(timeout)
  }, [participantSearch, restaurantId])

  function handleTopicChange(e) {
    const value = e.target.value
    setTopic(value)
    const match = topics.find((t) => `${t.name}${t.category ? ` (${t.category})` : ''}` === value)
    setDocumentId(match ? match.id : null)
  }

  function addParticipant(emp) {
    if (participants.some((p) => p.employee_id === emp.id)) return
    setParticipants((prev) => [...prev, { employee_id: emp.id, name: emp.name, position: emp.position, sign: '' }])
    setParticipantSearch('')
    setParticipantResults([])
  }

  function removeParticipant(employeeId) {
    setParticipants((prev) => prev.filter((p) => p.employee_id !== employeeId))
  }

  function setParticipantSign(employeeId, value) {
    setParticipants((prev) =>
      prev.map((p) => (p.employee_id === employeeId ? { ...p, sign: value } : p))
    )
  }

  function resetForm() {
    setTopic('')
    setDocumentId(null)
    setNote('')
    setParticipants([])
    setPhotos({ img_tailieu: '', img_lythuyet: '', img_thuchanh: '' })
  }

  async function save() {
    setSaving(true)
    setError('')
    setMessage('')
    const payload = {
      restaurant: restaurantId,
      topic,
      document: documentId,
      date,
      note,
      participants: participants.map((p) => ({ employee: p.employee_id, sign: p.sign })),
      ...photos,
    }
    await submitGuarded(
      'kpi',
      (p) => api.post('/kpi/sessions/save/', p).then((r) => r.data),
      payload,
      {
        onOk: (data) => {
          setMessage(`Đã lưu buổi đào tạo (${data.participant_count} người tham gia).`)
          setPdfUrl(data.pdf_url || '')
          resetForm()
          onSaved?.()
        },
        onErr: setError,
        onQueued: () => setMessage('Mất mạng - đã lưu nháp offline, sẽ tự đồng bộ khi có mạng.'),
      }
    )
    setSaving(false)
  }

  const canPickRestaurant = !defaultRestaurantId

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 24 }}>
      <h3>Ghi buổi đào tạo KPI</h3>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: '#666' }}>Nhà hàng</label>
        {canPickRestaurant ? (
          <select value={restaurantId} onChange={(e) => setRestaurantId(e.target.value)} style={s.select}>
            {restaurants.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={restaurants.find((r) => r.id === Number(restaurantId))?.name || ''}
            disabled
            style={s.input}
          />
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: '#666' }}>Chủ đề đào tạo</label>
        <input
          list="kpi-topic-list"
          value={topic}
          onChange={handleTopicChange}
          placeholder="Gõ để tìm chủ đề..."
          style={{ ...s.input, width: '100%' }}
        />
        <datalist id="kpi-topic-list">
          {topics.map((t) => (
            <option key={t.id} value={`${t.name}${t.category ? ` (${t.category})` : ''}`} />
          ))}
        </datalist>
        {topics.length === 0 && (
          <div style={{ fontSize: 12, color: '#92400e' }}>
            Chưa có tài liệu chuẩn nào — vào màn Checklist / Tài liệu để thêm.
          </div>
        )}
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: '#666' }}>Ngày</label>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={s.input} />
      </div>

      <div style={{ marginBottom: 12 }}>
        <label style={{ display: 'block', fontSize: 13, color: '#666' }}>Người tham gia</label>
        <input
          value={participantSearch}
          onChange={(e) => setParticipantSearch(e.target.value)}
          placeholder="Tìm nhân sự theo mã / tên để thêm..."
          style={{ ...s.input, width: '100%' }}
        />
        {participantResults.length > 0 && (
          <div style={{ border: '1px solid #ddd', borderRadius: 6, marginTop: 4 }}>
            {participantResults.map((emp) => (
              <div
                key={emp.id}
                onClick={() => addParticipant(emp)}
                style={{ padding: 8, cursor: 'pointer', borderBottom: '1px solid #eee' }}
              >
                {emp.code} — {emp.name} ({emp.position})
              </div>
            ))}
          </div>
        )}
      </div>

      {participants.map((p) => (
        <div
          key={p.employee_id}
          style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 12, borderBottom: '1px solid #eee', paddingBottom: 12 }}
        >
          <div style={{ minWidth: 160 }}>
            <div style={{ fontWeight: 'bold' }}>{p.name}</div>
            <div style={{ fontSize: 12, color: '#666' }}>{p.position}</div>
            <button onClick={() => removeParticipant(p.employee_id)} style={{ fontSize: 12, marginTop: 4 }}>
              Xóa
            </button>
          </div>
          <SignaturePad
            label="Chữ ký"
            value={p.sign}
            onChange={(v) => setParticipantSign(p.employee_id, v)}
          />
        </div>
      ))}

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', margin: '16px 0' }}>
        <PhotoSlot label="Tài liệu" value={photos.img_tailieu} onChange={(v) => setPhotos((p) => ({ ...p, img_tailieu: v }))} />
        <PhotoSlot label="Lý thuyết" value={photos.img_lythuyet} onChange={(v) => setPhotos((p) => ({ ...p, img_lythuyet: v }))} />
        <PhotoSlot label="Thực hành" value={photos.img_thuchanh} onChange={(v) => setPhotos((p) => ({ ...p, img_thuchanh: v }))} />
      </div>

      <textarea
        placeholder="Ghi chú..."
        value={note}
        onChange={(e) => setNote(e.target.value)}
        style={{ width: '100%', minHeight: 60, marginBottom: 12 }}
      />

      <button disabled={saving} onClick={save}>
        Lưu buổi đào tạo & xuất PDF
      </button>

      {saving && <p>Đang lưu...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && (
        <p style={{ color: 'green' }}>
          {message}{' '}
          {pdfUrl && (
            <a href={pdfUrl} target="_blank" rel="noreferrer">
              Xem biên bản PDF
            </a>
          )}
        </p>
      )}
    </div>
  )
}

export default function KpiPage() {
  const { user } = useAuth()
  const [restaurantFilter, setRestaurantFilter] = useState('')
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)

  const { data: restaurantOptions } = usePaginatedList('/restaurants/', { page_size: 100 })
  const { data: sessions, loading } = usePaginatedList('/kpi/sessions/', {
    restaurant: restaurantFilter || undefined,
    page,
    page_size: SESSIONS_PAGE_SIZE,
    refreshKey,
  })

  return (
    <div style={s.page}>
      <NavBar />
      <h2>KPI đào tạo</h2>

      {restaurantOptions.results.length > 0 && (
        <KpiSessionForm
          restaurants={restaurantOptions.results}
          defaultRestaurantId={user?.restaurant || null}
          onSaved={() => setRefreshKey((k) => k + 1)}
        />
      )}

      <h3>Danh sách buổi đã ghi</h3>
      <div style={s.toolbar}>
        <select value={restaurantFilter} onChange={(e) => { setRestaurantFilter(e.target.value); setPage(1) }} style={s.select}>
          <option value="">Tất cả nhà hàng</option>
          {restaurantOptions.results.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name}
            </option>
          ))}
        </select>
      </div>

      {loading && <p>Đang tải...</p>}
      <table style={s.table}>
        <thead>
          <tr>
            <th style={s.th}>Ngày</th>
            <th style={s.th}>Nhà hàng</th>
            <th style={s.th}>Chủ đề</th>
            <th style={s.th}>Người ĐT</th>
            <th style={s.th}>SL</th>
            <th style={s.th}>Biên bản</th>
          </tr>
        </thead>
        <tbody>
          {sessions.results.map((sess) => (
            <tr key={sess.id}>
              <td style={s.td}>{sess.date}</td>
              <td style={s.td}>{sess.restaurant_name}</td>
              <td style={s.td}>{sess.topic}</td>
              <td style={s.td}>{sess.trainer_name}</td>
              <td style={s.td}>{sess.participant_count}</td>
              <td style={s.td}>
                {sess.pdf_url ? (
                  <a href={sess.pdf_url} target="_blank" rel="noreferrer">
                    Xem
                  </a>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          ))}
          {sessions.results.length === 0 && (
            <tr>
              <td style={s.td} colSpan={6}>
                Không có dữ liệu.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager page={page} pageSize={SESSIONS_PAGE_SIZE} count={sessions.count} onChange={setPage} />
    </div>
  )
}
