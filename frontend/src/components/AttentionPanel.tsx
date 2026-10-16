import { Link } from 'react-router'
import { fmtMonthDay, fmtPrice } from '../lib/format'
import { periodText, useAttention } from '../lib/attention'
import styles from './AttentionPanel.module.css'

/** 市場總覽：處置股（處置中與即將開始）與最近交易日注意股，上市＋上櫃普通股。 */
export function AttentionPanel() {
  const q = useAttention()
  if (!q.data) return q.isError ? <p className={styles.muted}>處置／注意股：{(q.error as Error).message}</p> : null
  const d = q.data
  return (
    <section aria-labelledby="att-h" className={styles.wrap}>
      <h2 id="att-h" className={styles.h2}>
        處置股與注意股
      </h2>
      <div className={styles.cols}>
        <div>
          <h3 className={styles.h3}>處置中（{d.disposition.length}）</h3>
          {d.disposition.length === 0 ? (
            <p className={styles.muted}>目前沒有處置中的普通股。</p>
          ) : (
            <div className={styles.tableBox}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">股票</th>
                    <th scope="col">期間</th>
                    <th scope="col">撮合</th>
                  </tr>
                </thead>
                <tbody>
                  {d.disposition.map((x) => (
                    <tr key={x.code} className={x.start > d.today ? styles.upcoming : ''}>
                      <td>
                        <Link to={`/stock/${x.code}`} className={styles.stock}>
                          <span className={`${styles.code} num`}>{x.code}</span>
                          {x.name}
                        </Link>
                        <span className={styles.market}>{x.market}</span>
                      </td>
                      <td className="num">
                        {periodText(x)}
                        {x.start > d.today && <span className={styles.soon}> 即將</span>}
                      </td>
                      <td className={styles.muted}>{x.match.replace('約每 ', '').replace(' 分鐘撮合一次', ' 分') || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div>
          <h3 className={styles.h3}>
            注意股（{fmtMonthDay(d.asof)}，{d.notice.length}）
          </h3>
          {d.notice.length === 0 ? (
            <p className={styles.muted}>當日沒有注意股。</p>
          ) : (
            <div className={styles.tableBox}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">股票</th>
                    <th scope="col">收盤</th>
                    <th scope="col">原因</th>
                  </tr>
                </thead>
                <tbody>
                  {d.notice.map((x) => (
                    <tr key={`${x.market}${x.code}`}>
                      <td>
                        <Link to={`/stock/${x.code}`} className={styles.stock}>
                          <span className={`${styles.code} num`}>{x.code}</span>
                          {x.name}
                        </Link>
                        <span className={styles.market}>{x.market}</span>
                      </td>
                      <td className="num">{x.close != null ? fmtPrice(x.close) : '—'}</td>
                      <td className={styles.reason} title={x.reason}>
                        {x.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
      <p className={styles.muted}>
        {d.note}處置期間交易採人工管制撮合，買賣需預收款券。資料：{d.sources.join('、')}。
      </p>
    </section>
  )
}
