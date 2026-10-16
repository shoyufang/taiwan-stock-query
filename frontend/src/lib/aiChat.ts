export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  steps?: string[]
  error?: boolean
}

export type AiEvent =
  | { type: 'status'; text: string }
  | { type: 'tool'; name: string; args: Record<string, unknown> }
  | { type: 'answer'; text: string; model: string }
  | { type: 'error'; text: string }

/** 把收到的文字片段切成完整的 SSE 事件；回傳解析出的事件與尚未完整的剩餘字串。 */
export function parseSse(buffer: string): { events: AiEvent[]; rest: string } {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  const events: AiEvent[] = []
  for (const part of parts) {
    const data = part
      .split('\n')
      .filter((l) => l.startsWith('data:'))
      .map((l) => l.slice(5).trim())
      .join('')
    if (!data) continue
    try {
      events.push(JSON.parse(data) as AiEvent)
    } catch {
      // 不完整或非 JSON 的片段直接略過
    }
  }
  return { events, rest }
}

const TOOL_LABEL: Record<string, string> = {
  site_market_overview: '市場總覽',
  site_stock: '個股資料',
  site_watchlist: '自選股',
  site_portfolio: '投資組合',
  site_calendar: '行事曆',
  get_company_profile: '公司基本資料',
  get_company_monthly_revenue: '月營收',
  get_company_income_statement: '損益表',
  get_company_balance_sheet: '資產負債表',
  get_company_dividend: '股利',
  get_company_major_news: '重大訊息',
  get_stock_valuation_ratios: '本益比／殖利率',
  get_industry_peers: '同業',
  get_company_eps_statistics: 'EPS',
  get_stock_history: '歷史股價',
  get_technical_indicators: '技術指標',
  get_realtime_quote: '即時報價',
  get_twse_institutional_investors_by_stock: '三大法人',
  get_margin_balance: '融資融券',
  get_foreign_holdings: '外資持股',
  get_shareholding_distribution: '集保股權分散',
  get_investor_conferences: '法說會',
  get_dividend_rights_schedule: '除權息',
  get_twse_news: '證交所新聞',
  get_etf_holdings: 'ETF 成分股',
  get_etf_info: 'ETF 資訊',
  get_business_cycle_indicators: '景氣燈號',
  get_futures_institutional: '期貨法人',
  get_put_call_ratio: '選擇權 P/C 比',
}

export function toolLabel(name: string, args: Record<string, unknown>): string {
  const label = TOOL_LABEL[name] ?? name
  const code = args.code ?? args.stock_code ?? args.symbol
  return typeof code === 'string' && code ? `查詢${label}（${code}）` : `查詢${label}`
}
