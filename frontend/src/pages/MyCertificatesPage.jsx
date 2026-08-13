import { useEffect, useState } from 'react'
import AppShell from '../components/AppShell'
import api from '../api/client'

export default function MyCertificatesPage() {
  const [certificates, setCertificates] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/integration/my-certificates/')
      .then(({ data }) => setCertificates(data))
      .catch((err) => setError(err.response?.data?.detail || 'Không tải được danh sách chứng chỉ.'))
  }, [])

  return (
    <AppShell>
      <h2>Chứng chỉ của tôi</h2>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      {!error && !certificates && <p className="muted-note">Đang tải...</p>}
      {certificates && certificates.length === 0 && <p className="muted-note">Bạn chưa có chứng chỉ nào.</p>}

      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>
        {certificates?.map((c) => (
          <div key={c.id} className="card">
            <strong>{c.program_name || c.ref_type_display}</strong>
            <div className="muted-note" style={{ fontSize: 12, margin: '4px 0 8px' }}>
              Mã: {c.code} · Ngày cấp: {c.issue_date}
            </div>
            {c.pdf_url && (
              <a href={c.pdf_url} target="_blank" rel="noreferrer">
                <button>Tải PDF</button>
              </a>
            )}
          </div>
        ))}
      </div>
    </AppShell>
  )
}
