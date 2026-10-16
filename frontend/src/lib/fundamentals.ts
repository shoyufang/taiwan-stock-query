import { useQuery } from '@tanstack/react-query'
import { NotFoundError } from './api'

export interface IncomeQuarter {
  date: string
  quarter: string
  revenue: number | null
  gross_profit: number | null
  operating_income: number | null
  net_income: number | null
  eps: number | null
  gross_margin: number | null
  operating_margin: number | null
  net_margin: number | null
  revenue_yoy: number | null
}

export interface BalanceQuarter {
  date: string
  quarter: string
  total_assets: number | null
  liabilities: number | null
  equity: number | null
  debt_ratio: number | null
  current_ratio: number | null
  book_value_per_share: number | null
}

export interface DividendYear {
  year: number
  cash: number
  stock: number
  times: number
  ex_dates: string[]
  eps: number | null
  payout: number | null
}

export interface PeRiver {
  multiples: number[]
  percentiles: number[]
  series: { date: string; close: number; bands: number[] }[]
  current_pe: number
  start: string
  end: string
}

export interface PeerRow {
  code: string
  name: string
  close: number | null
  change_pct: number | null
  pe: number | null
  pb: number | null
  dividend_yield: number | null
  foreign_streak: number | null
  value_e8: number | null
}

export interface PeersData {
  industry: string
  asof: string
  count: number
  median_pe: number | null
  rows: PeerRow[]
}

export interface FundamentalsData {
  code: string
  generated_at: string
  income: IncomeQuarter[]
  eps_ttm: number | null
  balance: BalanceQuarter[]
  dividends: DividendYear[]
  river: PeRiver | null
  peers: PeersData | null
  units: { amount: string; eps: string; margin: string }
  sources: string[]
}

export async function fetchFundamentals(code: string): Promise<FundamentalsData> {
  const res = await fetch(`/api/stock/${encodeURIComponent(code)}/fundamentals`)
  if (res.status === 404) throw new NotFoundError(code)
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export function useFundamentals(code: string, enabled: boolean) {
  return useQuery({
    queryKey: ['fundamentals', code],
    queryFn: () => fetchFundamentals(code),
    enabled,
    staleTime: 30 * 60_000,
    retry: (n, e) => !(e instanceof NotFoundError) && n < 2,
  })
}
