import { useEffect, useRef, useState } from 'react'

export default function SignaturePad({ label, existingUrl, value, onChange }) {
  const canvasRef = useRef(null)
  const stateRef = useRef({ drawing: false, last: { x: 0, y: 0 }, dirty: false })
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange
  const [mode, setMode] = useState(existingUrl && !value ? 'preview' : 'draw')

  // Gắn listener GỐC (không phải React synthetic) với passive:false để preventDefault chạy được
  // trên iOS → chặn cuộn trang, vẽ nét đúng điểm chạm. Đây là cách ký ổn định nhất trên mobile.
  useEffect(() => {
    if (mode !== 'draw') return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1

    function reset() {
      const rect = canvas.getBoundingClientRect()
      canvas.width = Math.max(1, Math.round(rect.width * dpr))
      canvas.height = Math.max(1, Math.round(rect.height * dpr))
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, rect.width, rect.height)
      ctx.lineWidth = 2
      ctx.lineCap = 'round'
      ctx.lineJoin = 'round'
      ctx.strokeStyle = '#111'
    }
    reset()

    function point(e) {
      const rect = canvas.getBoundingClientRect()
      const t = e.touches && e.touches[0] ? e.touches[0] : e
      return { x: t.clientX - rect.left, y: t.clientY - rect.top }
    }
    function down(e) {
      e.preventDefault()
      stateRef.current.drawing = true
      stateRef.current.last = point(e)
    }
    function move(e) {
      if (!stateRef.current.drawing) return
      e.preventDefault()
      const p = point(e)
      ctx.beginPath()
      ctx.moveTo(stateRef.current.last.x, stateRef.current.last.y)
      ctx.lineTo(p.x, p.y)
      ctx.stroke()
      stateRef.current.last = p
      stateRef.current.dirty = true
    }
    function up() {
      if (!stateRef.current.drawing) return
      stateRef.current.drawing = false
      if (stateRef.current.dirty) onChangeRef.current(canvas.toDataURL('image/png'))
    }

    const opts = { passive: false }
    const hasPointer = 'PointerEvent' in window
    if (hasPointer) {
      canvas.addEventListener('pointerdown', down, opts)
      canvas.addEventListener('pointermove', move, opts)
      window.addEventListener('pointerup', up)
    } else {
      canvas.addEventListener('touchstart', down, opts)
      canvas.addEventListener('touchmove', move, opts)
      window.addEventListener('touchend', up)
      canvas.addEventListener('mousedown', down)
      window.addEventListener('mousemove', move)
      window.addEventListener('mouseup', up)
    }
    return () => {
      if (hasPointer) {
        canvas.removeEventListener('pointerdown', down, opts)
        canvas.removeEventListener('pointermove', move, opts)
        window.removeEventListener('pointerup', up)
      } else {
        canvas.removeEventListener('touchstart', down, opts)
        canvas.removeEventListener('touchmove', move, opts)
        window.removeEventListener('touchend', up)
        canvas.removeEventListener('mousedown', down)
        window.removeEventListener('mousemove', move)
        window.removeEventListener('mouseup', up)
      }
    }
  }, [mode])

  function clear() {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const rect = canvas.getBoundingClientRect()
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, rect.width, rect.height)
    stateRef.current.dirty = false
    onChange('')
  }

  if (mode === 'preview') {
    return (
      <div style={{ textAlign: 'center', flex: '1 1 220px', minWidth: 0 }}>
        <img
          src={existingUrl}
          alt={label}
          style={{
            width: '100%', maxWidth: 320, height: 110, objectFit: 'contain',
            border: '1px solid #999', borderRadius: 6, background: '#fff',
          }}
        />
        <div style={{ marginTop: 4, fontSize: 13 }}>
          {label} <span style={{ color: 'green' }}>(đã ký)</span>
        </div>
        <button type="button" onClick={() => setMode('draw')} style={{ fontSize: 12 }}>
          Ký lại
        </button>
      </div>
    )
  }

  return (
    <div style={{ textAlign: 'center', flex: '1 1 220px', minWidth: 0 }}>
      <canvas
        ref={canvasRef}
        style={{
          width: '100%', maxWidth: 320, height: 110, display: 'block', margin: '0 auto',
          border: '1px solid #999', borderRadius: 6, touchAction: 'none', background: '#fff',
        }}
      />
      <div style={{ marginTop: 4, fontSize: 13 }}>
        {label} {value && <span style={{ color: 'green' }}>(đã ký)</span>}
      </div>
      <button type="button" onClick={clear} style={{ fontSize: 12 }}>
        Xóa
      </button>
    </div>
  )
}
