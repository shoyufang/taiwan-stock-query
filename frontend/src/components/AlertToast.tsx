import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useLiveQuotes, type LiveAlert } from '../lib/useLiveQuotes'
import styles from './AlertToast.module.css'

/** 任何頁面都會顯示的警示提示（網頁內通知）。 */
export function AlertToast() {
  const { data } = useLiveQuotes(['ALERTS'])
  const latest = data.ALERTS as LiveAlert | undefined
  const [shown, setShown] = useState<LiveAlert[]>([])

  useEffect(() => {
    if (!latest) return
    setShown((prev) => (prev.some((p) => p.at === latest.at && p.title === latest.title) ? prev : [latest, ...prev].slice(0, 3)))
    const t = window.setTimeout(() => setShown((prev) => prev.filter((p) => p !== latest)), 20_000)
    return () => window.clearTimeout(t)
  }, [latest])

  if (!shown.length) return null
  return (
    <div className={styles.wrap} role="status" aria-live="polite">
      {shown.map((a) => (
        <div key={`${a.at}-${a.title}`} className={styles.toast}>
          <div className={styles.body}>
            <div className={styles.title}>{a.title}</div>
            <div>{a.message}</div>
            {a.stock && (
              <Link to={`/stock/${a.stock}`} className={styles.link}>
                查看個股
              </Link>
            )}
          </div>
          <button type="button" className={styles.close} aria-label="關閉提示" onClick={() => setShown((prev) => prev.filter((p) => p !== a))}>
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}
