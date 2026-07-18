import { useEffect, useRef, useState } from 'react'

export default function SignaturePad({ label, existingUrl, value, onChange }) {
  const canvasRef = useRef(null)
  const drawingRef = useRef(false)
  const lastRef = useRef({ x: 0, y: 0 })
  const [mode, setMode] = useState(existingUrl && !value ? 'preview' : 'draw')

  // Set buffer canvas theo kích thước hiển thị thực tế × devicePixelRatio → nét mượt + toạ độ
  // ký khớp đúng điểm chạm (canvas co giãn 100% bề rộng, không cố định 220px như trước).
  useEffect(() => {
    if (mode !== 'draw') return
    const canvas = canvasRef.current
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = Math.max(1, Math.round(rect.width * dpr))
    canvas.height = Math.max(1, Math.round(rect.height * dpr))
    const ctx = canvas.getContext('2d')
    ctx.scale(dpr, dpr)
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, rect.width, rect.height)
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#111'
  }, [mode])

  function pos(e) {
    const rect = canvasRef.current.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }

  function start(e) {
    e.preventDefault()
    canvasRef.current.setPointerCapture?.(e.pointerId)
    drawingRef.current = true
    lastRef.current = pos(e)
  }

  function move(e) {
    if (!drawingRef.current) return
    e.preventDefault()
    const p = pos(e)
    const ctx = canvasRef.current.getContext('2d')
    ctx.beginPath()
    ctx.moveTo(lastRef.current.x, lastRef.current.y)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    lastRef.current = p
  }

  function end() {
    if (!drawingRef.current) return
    drawingRef.current = false
    onChange(canvasRef.current.toDataURL('image/png'))
  }

  function clear() {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const rect = canvas.getBoundingClientRect()
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, rect.width, rect.height)
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
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerCancel={end}
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
