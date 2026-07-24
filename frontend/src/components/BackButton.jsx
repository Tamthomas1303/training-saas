import { useNavigate } from 'react-router-dom'

// Nút quay lại Trung tâm (hub) — dùng cho các màn thuộc 4 miền (thẻ cha-con).
export default function BackButton({ to = '/hub', label = '← Quay lại Trung tâm' }) {
  const navigate = useNavigate()
  return (
    <button className="btn-outline btn-sm" style={{ marginBottom: 10 }} onClick={() => navigate(to)}>
      {label}
    </button>
  )
}
