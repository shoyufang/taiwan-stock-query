import { useEffect, useState } from 'react'

export type HealthStatus = 'loading' | 'ok' | 'degraded' | 'offline'

export interface Health {
  status: HealthStatus
  version?: string
  time?: string
  components?: Record<string, string>
}

export function useHealth(intervalMs = 30_000): Health {
  const [health, setHealth] = useState<Health>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const res = await fetch('/api/health', { cache: 'no-store' })
        const body = await res.json()
        if (!cancelled) setHealth({ ...body, status: res.ok ? 'ok' : 'degraded' })
      } catch {
        if (!cancelled) setHealth({ status: 'offline' })
      }
    }
    check()
    const id = window.setInterval(check, intervalMs)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [intervalMs])

  return health
}
