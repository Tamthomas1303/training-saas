import { Component } from 'react'

// Prompt_Fix_TrangTrang_MapUndefined.md (Phan 1) - CHAN loi render o 1 man khong duoc phep danh
// sap TOAN BO app (truoc day khong co ErrorBoundary nao - 1 loi .map tren undefined o 1 trang
// (vd /employees) lam trang ca man hinh, mat luon sidebar). Bat buoc la class component - React
// CHUA co hook tuong duong cho getDerivedStateFromError/componentDidCatch.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary bắt được lỗi render:', error, info?.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div style={{ padding: 24, maxWidth: 560, margin: '40px auto', textAlign: 'center' }}>
        <div style={{ fontSize: 40, marginBottom: 8 }}>⚠️</div>
        <h3 style={{ margin: '0 0 8px' }}>Có lỗi hiển thị ở màn này</h3>
        <p className="muted-note" style={{ marginBottom: 16 }}>
          Bạn có thể thử tải lại trang, hoặc chuyển sang màn khác từ menu.
        </p>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          <button onClick={() => window.location.reload()}>Tải lại</button>
          {/* Dieu huong thuc (khong phai SPA Link) - dam bao thoat duoc man loi ngay ca khi
              sidebar khong con tren cay render (xem ghi chu chon vi tri boc trong App.jsx). */}
          <a
            href="/dashboard" className="btn-outline"
            style={{
              display: 'inline-flex', alignItems: 'center', padding: '8px 14px',
              borderRadius: 8, textDecoration: 'none', fontSize: '0.9rem',
            }}
          >
            Về Trang chủ
          </a>
        </div>
        {import.meta.env.DEV && (
          <pre style={{
            marginTop: 20, textAlign: 'left', fontSize: 12, whiteSpace: 'pre-wrap',
            background: 'var(--card-bg-subtle, #f4f4f4)', padding: 12, borderRadius: 6,
            maxHeight: 300, overflow: 'auto',
          }}>
            {String(this.state.error?.stack || this.state.error)}
          </pre>
        )}
      </div>
    )
  }
}
