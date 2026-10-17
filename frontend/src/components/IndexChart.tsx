import { monthStarts, niceScale } from '../lib/chartScale'
import { fmtInt, fmtPrice } from '../lib/format'
import styles from './IndexChart.module.css'

const W = 800
const H = 300

export function IndexChart({ series, label }: { series: { date: string; close: number }[]; label: string }) {
  if (series.length < 2) return <p className={styles.empty}>走勢資料不足</p>
  const closes = series.map((p) => p.close)
  const scale = niceScale(closes)
  const y = (v: number) => H - ((v - scale.min) / (scale.max - scale.min)) * H
  const x = (i: number) => (i / (series.length - 1)) * W
  const line = series.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.close).toFixed(1)}`).join(' ')
  const area = `${line} L${W},${H} L0,${H} Z`
  const first = series[0]
  const last = series[series.length - 1]
  const hi = series.reduce((a, b) => (b.close > a.close ? b : a))
  const desc = `${label}，${first.date} 至 ${last.date}，由 ${fmtPrice(first.close)} 到 ${fmtPrice(last.close)}，區間高點 ${fmtPrice(hi.close)}`

  return (
    <div className={styles.wrap}>
      <div className={styles.plot}>
        {scale.ticks.map((t) => (
          <div key={t} className={styles.grid} style={{ top: `${(y(t) / H) * 100}%` }}>
            <span className={`${styles.tick} num`}>{fmtInt(t)}</span>
          </div>
        ))}
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={styles.svg} role="img" aria-label={desc}>
          <path d={area} className={styles.area} />
          <path d={line} className={styles.line} vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div className={styles.months} aria-hidden="true">
        {monthStarts(series.map((p) => p.date)).map((m) => (
          <span key={m.index} style={{ left: `${(m.index / (series.length - 1)) * 100}%` }}>
            {m.label}
          </span>
        ))}
      </div>
    </div>
  )
}
