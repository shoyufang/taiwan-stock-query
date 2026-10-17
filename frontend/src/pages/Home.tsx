import { useHealth } from '../lib/useHealth'
import type { Mode } from '../lib/marketMode'
import styles from './ComingSoon.module.css'

const MODE_LABEL: Record<Mode, string> = { live: '盤中（深色終端機）', close: '盤後報告' }

export function Home({ mode }: { mode: Mode }) {
  const health = useHealth()
  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <section className={styles.box} aria-labelledby="sys-title">
        <h2 id="sys-title" className={styles.title} style={{ fontSize: 18 }}>
          系統狀態
        </h2>
        <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '6px 20px', margin: 0 }}>
          <dt className={styles.text}>目前模式</dt>
          <dd style={{ margin: 0 }}>{MODE_LABEL[mode]}</dd>
          <dt className={styles.text}>API</dt>
          <dd style={{ margin: 0 }} className="num">{health.components?.api ?? health.status}</dd>
          <dt className={styles.text}>Redis</dt>
          <dd style={{ margin: 0 }} className="num">{health.components?.redis ?? '—'}</dd>
          <dt className={styles.text}>版本</dt>
          <dd style={{ margin: 0 }} className="num">{health.version ?? '—'}</dd>
          <dt className={styles.text}>伺服器時間</dt>
          <dd style={{ margin: 0 }} className="num">{health.time ?? '—'}</dd>
        </dl>
      </section>
    </div>
  )
}
