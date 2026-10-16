import { NavLink, Outlet } from 'react-router'
import type { MarketModeState } from '../lib/useMarketMode'
import { useHealth, type HealthStatus } from '../lib/useHealth'
import { AlertToast } from './AlertToast'
import styles from './AppShell.module.css'

export const NAV_ITEMS = [
  { to: '/', label: '市場總覽', end: true },
  { to: '/stock/2330', label: '個股' },
  { to: '/watchlist', label: '自選股' },
  { to: '/screener', label: '選股' },
  { to: '/global', label: '全球市場' },
  { to: '/portfolio', label: '投資組合' },
  { to: '/calendar', label: '行事曆' },
  { to: '/ai', label: 'AI 助理' },
]

const HEALTH_LABEL: Record<HealthStatus, string> = {
  loading: '檢查中',
  ok: '系統正常',
  degraded: '部分異常',
  offline: '無法連線',
}

function formatUntil(d: Date): string {
  return d.toLocaleString('zh-TW', { timeZone: 'Asia/Taipei', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false })
}

export function AppShell({ market }: { market: MarketModeState }) {
  const health = useHealth()
  const { mode, isManual, manualUntil, setMode } = market

  return (
    <>
      <header className={styles.header}>
        <div className={styles.brand}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M3 17l5-6 4 4 8-10" />
            <path d="M3 21h18" />
          </svg>
          台股看盤
        </div>
        <nav className={styles.nav} aria-label="主選單">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? styles.navLinkActive : styles.navLink)}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className={styles.tools}>
          <div className={styles.mode} role="group" aria-label="檢視模式">
            <button type="button" className={styles.modeBtn} aria-pressed={mode === 'live'} onClick={() => setMode('live')}>
              盤中
            </button>
            <button type="button" className={styles.modeBtn} aria-pressed={mode === 'close'} onClick={() => setMode('close')}>
              盤後報告
            </button>
          </div>
          <span className={styles.modeHint}>
            {isManual && manualUntil ? `手動，${formatUntil(manualUntil)} 恢復自動` : '依交易時間自動切換'}
          </span>
          <NavLink to="/status" className={styles.health} role="status">
            <span className={styles.dot} data-status={health.status} aria-hidden="true" />
            {HEALTH_LABEL[health.status]}
          </NavLink>
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
      <AlertToast />
    </>
  )
}
