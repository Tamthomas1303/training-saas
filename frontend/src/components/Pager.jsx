export default function Pager({ page, pageSize, count, onChange }) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize))

  if (totalPages <= 1) return null

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12 }}>
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>
        « Trước
      </button>
      <span>
        Trang {page}/{totalPages} ({count} kết quả)
      </span>
      <button disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
        Sau »
      </button>
    </div>
  )
}
