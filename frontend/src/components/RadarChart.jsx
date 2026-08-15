import { useEffect, useRef } from 'react'
import {
  Chart, RadarController, RadialLinearScale, PointElement, LineElement, Filler, Legend, Tooltip,
} from 'chart.js'

Chart.register(RadarController, RadialLinearScale, PointElement, LineElement, Filler, Legend, Tooltip)

// Radar Thuc te vs Muc tieu (Dashboard Phan A muc 4) - dung truc tiep chart.js (khong qua
// react-chartjs-2) de khong them lop bao ngoai, dung quy uoc "it phu thuoc" cua repo nay.
export default function RadarChart({ labels, actual, target, height = 320 }) {
  const canvasRef = useRef(null)
  const chartRef = useRef(null)

  // Tao 1 lan khi mount, huy khi unmount - tach rieng khoi cap nhat du lieu de tranh ve/huy
  // chart moi moi lan props doi (giat hinh) va tranh cap nhat vao 1 chart da bi destroy.
  useEffect(() => {
    if (!canvasRef.current) return undefined
    chartRef.current = new Chart(canvasRef.current, {
      type: 'radar',
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { r: { min: 0, max: 100, ticks: { stepSize: 20 } } },
        plugins: { legend: { position: 'bottom' } },
      },
    })
    return () => {
      chartRef.current?.destroy()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!chartRef.current) return
    const datasets = [
      {
        label: 'Thực tế',
        data: actual.map((v) => v ?? 0),
        borderColor: '#2E6F40',
        backgroundColor: 'rgba(46, 111, 64, 0.25)',
        pointBackgroundColor: '#2E6F40',
      },
    ]
    if (target && target.some((v) => v !== null && v !== undefined)) {
      datasets.push({
        label: 'Mục tiêu',
        data: target.map((v) => v ?? 0),
        borderColor: '#8a8a8a',
        backgroundColor: 'rgba(138, 138, 138, 0.12)',
        pointBackgroundColor: '#8a8a8a',
        borderDash: [6, 4],
      })
    }
    chartRef.current.data.labels = labels
    chartRef.current.data.datasets = datasets
    chartRef.current.update()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(labels), JSON.stringify(actual), JSON.stringify(target)])

  return (
    <div style={{ height, position: 'relative' }}>
      <canvas ref={canvasRef} />
    </div>
  )
}
