import { useEffect, useRef, useState } from 'react'

export default function SignaturePad({ label, existingUrl, value, onChange }) {
  const canvasRef = useRef(null)
  const drawingRef = useRef(false)
  const [mode, setMode] = useState(existingUrl && !value ? 'preview' : 'draw')

  useEffect(() => {
    if (mode !== 'draw') return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.lineWidth = 2
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#111'
  }, [mode])

  function pos(e) {
    const rect = canvasRef.current.getBoundingClientRect()
    const clientX = e.touches ? e.touches[0].clientX : e.clientX
    const clientY = e.touches ? e.touches[0].clientY : e.clientY
    return { x: clientX - rect.left, y: clientY - rect.top }
  }

  function start(e) {
    drawingRef.current = true
    const { x, y } = pos(e)
    const ctx = canvasRef.current.getContext('2d')
    ctx.beginPath()
    ctx.moveTo(x, y)
  }

  function move(e) {
    if (!drawingRef.current) return
    e.preventDefault()
    const { x, y } = pos(e)
    const ctx = canvasRef.current.getContext('2d')
    ctx.lineTo(x, y)
    ctx.stroke()
  }

  function end() {
    if (!drawingRef.current) return
    drawingRef.current = false
    onChange(canvasRef.current.toDataURL('image/png'))
  }

  function clear() {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    onChange('')
  }

  if (mode === 'preview') {
    return (
      <div style={{ textAlign: 'center' }}>
        <img
          src={existingUrl}
          alt={label}
          style={{ width: 220, height: 100, objectFit: 'contain', border: '1px solid #999', borderRadius: 6, background: '#fff' }}
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
    <div style={{ textAlign: 'center' }}>
      <canvas
        ref={canvasRef}
        width={220}
        height={100}
        style={{ border: '1px solid #999', borderRadius: 6, touchAction: 'none', background: '#fff' }}
        onMouseDown={start}
        onMouseMove={move}
        onMouseUp={end}
        onMouseLeave={end}
        onTouchStart={start}
        onTouchMove={move}
        onTouchEnd={end}
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
