/** 迷你走勢線（最近約一個月）。顏色依期間漲跌：紅漲綠跌。 */
export function Sparkline({ values, width = 96, height = 28, label, period = '近一個月' }: { values: number[]; width?: number; height?: number; label: string; period?: string }) {
  if (values.length < 2) return null
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  const span = hi - lo || 1
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${(height - 2 - ((v - lo) / span) * (height - 4)).toFixed(1)}`).join(' ')
  const up = values[values.length - 1] >= values[0]
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} ${period}走勢${up ? '上升' : '下降'}`}>
      <polyline points={pts} fill="none" stroke={up ? 'var(--up)' : 'var(--down)'} strokeWidth="1.5" />
    </svg>
  )
}
