import { arrow, direction, fmtFixed, fmtInt, fmtPct, fmtPrice, fmtSigned, fmtYi } from '../lib/format'
import { isToday, useLiveQuotes, type LiveIndex, type LiveScanner, type ScannerRow } from '../lib/useLiveQuotes'
import styles from './LivePanel.module.css'

const INDEX = 'IX0001'

/** 盤中即時區塊：加權指數推播（含漲跌家數、累計成交金額）＋每分鐘排行。 */
export function LivePanel({ closeDate }: { closeDate: string }) {
  const { data, status } = useLiveQuotes([INDEX, 'SCANNER'])
  const idx = data[INDEX] as LiveIndex | undefined
  const scan = data.SCANNER as LiveScanner | undefined
  const live = idx && isToday(idx.time)

  if (!live) {
    return (
      <p className={styles.notice} role="status">
        {status === 'open' ? '尚未收到今日即時行情（休市中、尚未開盤，或行情服務待命）。' : '即時行情連線中…'}
        以下為 {closeDate} 收盤資料。
      </p>
    )
  }

  return (
    <section className={styles.panel} aria-label="盤中即時">
      <div className={styles.head}>
        <span className={styles.badge}>
          <span className={styles.pulse} aria-hidden="true" />
          即時
        </span>
        <span className="num">{idx.time.slice(11, 19)}</span>
      </div>
      <div className={styles.grid}>
        <div className={styles.cell}>
          <div className={styles.label}>加權指數</div>
          <div className={`${styles.big} num ${direction(idx.change)}`}>{fmtFixed(idx.close)}</div>
          <div className={`num ${direction(idx.change)}`}>
            {arrow(idx.change)} {fmtSigned(idx.change, 2)}（{fmtPct(idx.change_pct)}）
          </div>
          <div className={`${styles.sub} num`}>
            高 {fmtFixed(idx.high)}　低 {fmtFixed(idx.low)}
          </div>
        </div>
        <div className={styles.cell}>
          <div className={styles.label}>累計成交金額</div>
          <div className={`${styles.big} num`}>{idx.amount_sum != null ? fmtYi(idx.amount_sum) : '—'}<span className={styles.unit}> 億</span></div>
        </div>
        <div className={styles.cell}>
          <div className={styles.label}>漲 / 平 / 跌（家數）</div>
          <div className={`${styles.big} num`}>
            <span className="up">{fmtInt(idx.raise_count ?? 0)}</span> / {fmtInt(idx.flat_count ?? 0)} /{' '}
            <span className="down">{fmtInt(idx.fall_count ?? 0)}</span>
          </div>
          <div className={styles.sub}>
            漲停 {idx.limit_up_count ?? '—'}・跌停 {idx.limit_down_count ?? '—'}
          </div>
        </div>
      </div>
      {scan && isToday(scan.time) && (
        <div className={styles.ranks}>
          <RankTable title="成交金額" rows={scan.amount} showAmount />
          <RankTable title="漲幅" rows={scan.gainers} />
          <RankTable title="跌幅" rows={scan.losers} />
          <p className={styles.sub}>排行每分鐘更新，{scan.time.slice(11, 16)}</p>
        </div>
      )}
    </section>
  )
}

function RankTable({ title, rows, showAmount }: { title: string; rows: ScannerRow[]; showAmount?: boolean }) {
  return (
    <div className={styles.rank}>
      <h3 className={styles.rankTitle}>{title}</h3>
      <table className={styles.table}>
        <tbody>
          {rows.slice(0, 8).map((r) => (
            <tr key={r.code}>
              <td>
                <span className={`${styles.code} num`}>{r.code}</span>
                {r.name}
              </td>
              <td className="num">{fmtPrice(r.close)}</td>
              <td className={`num ${direction(r.change_pct)}`}>{fmtPct(r.change_pct)}</td>
              {showAmount && <td className="num">{fmtYi(r.total_amount, 1)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
