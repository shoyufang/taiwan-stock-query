import { useEffect, useRef, useState } from 'react'

// 與 backend/app/quote/normalize.py 對應
export interface LiveStock {
  kind: 'stock'
  code: string
  time: string
  close: number
  change: number
  change_pct: number
  high: number
  low: number
  total_volume: number
  total_amount: number
  bid: [number, number][]
  ask: [number, number][]
}

export interface LiveIndex {
  kind: 'index'
  code: string
  time: string
  close: number
  change: number
  change_pct: number
  high: number
  low: number
  amount_sum: number | null
  raise_count: number | null
  limit_up_count: number | null
  flat_count: number | null
  fall_count: number | null
  limit_down_count: number | null
}

export interface ScannerRow {
  code: string
  name: string
  close: number
  change: number
  change_pct: number
  total_amount: number
}

export interface LiveScanner {
  kind: 'scanner'
  code: 'SCANNER'
  time: string
  amount: ScannerRow[]
  gainers: ScannerRow[]
  losers: ScannerRow[]
}

export type LiveMessage = LiveStock | LiveIndex | LiveScanner
export type LiveStatus = 'connecting' | 'open' | 'closed'

function wsUrl(): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
}

/** 訂閱即時行情。斷線自動重連（1 秒起、最長 30 秒）。 */
export function useLiveQuotes(codes: string[], enabled = true) {
  const [data, setData] = useState<Record<string, LiveMessage>>({})
  const [status, setStatus] = useState<LiveStatus>('connecting')
  const key = codes.join(',')
  const retry = useRef(1000)

  useEffect(() => {
    if (!enabled || !key) return
    let ws: WebSocket | null = null
    let timer: number | undefined
    let stopped = false

    const connect = () => {
      setStatus('connecting')
      ws = new WebSocket(wsUrl())
      ws.onopen = () => {
        retry.current = 1000
        setStatus('open')
        ws?.send(JSON.stringify({ op: 'subscribe', codes: key.split(',') }))
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data) as LiveMessage
          setData((prev) => ({ ...prev, [msg.code]: msg }))
        } catch {
          // 忽略無法解析的訊息
        }
      }
      ws.onclose = () => {
        setStatus('closed')
        if (stopped) return
        timer = window.setTimeout(connect, retry.current)
        retry.current = Math.min(retry.current * 2, 30_000)
      }
    }
    connect()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      ws?.close()
    }
  }, [key, enabled])

  return { data, status }
}

/** 推播時間是否為今天（台北），避免把上次交易日的最後一筆當成即時。 */
export function isToday(iso: string | undefined, now = new Date()): boolean {
  if (!iso) return false
  const today = new Date(now.getTime() + 8 * 3600_000).toISOString().slice(0, 10)
  return iso.slice(0, 10) === today
}
