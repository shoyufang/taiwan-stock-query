import { useCallback, useEffect, useState } from 'react'
import { autoMode, nextBoundary, resolveMode, type Mode, type ModeOverride } from './marketMode'

const STORAGE_KEY = 'twstock.modeOverride'

function readOverride(): ModeOverride | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as ModeOverride) : null
  } catch {
    return null
  }
}

function writeOverride(value: ModeOverride | null) {
  try {
    if (value) localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // 私密瀏覽或儲存被封鎖時，手動切換只在本次有效
  }
}

export interface MarketModeState {
  mode: Mode
  isManual: boolean
  manualUntil: Date | null
  setMode: (mode: Mode) => void
}

export function useMarketMode(): MarketModeState {
  const [now, setNow] = useState(() => new Date())
  const [override, setOverride] = useState<ModeOverride | null>(readOverride)

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  const mode = resolveMode(now, override)
  const active = override && new Date(override.until).getTime() > now.getTime() ? override : null

  useEffect(() => {
    document.documentElement.dataset.mode = mode
  }, [mode])

  const setMode = useCallback((next: Mode) => {
    const current = new Date()
    const value = next === autoMode(current) ? null : { mode: next, until: nextBoundary(current).toISOString() }
    writeOverride(value)
    setOverride(value)
    setNow(current)
  }, [])

  return { mode, isManual: active !== null, manualUntil: active ? new Date(active.until) : null, setMode }
}
