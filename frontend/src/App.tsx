import { BrowserRouter, Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { useMarketMode } from './lib/useMarketMode'
import { ComingSoon } from './pages/ComingSoon'
import { Home } from './pages/Home'

export function App() {
  const market = useMarketMode()
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell market={market} />}>
          <Route index element={<Home mode={market.mode} />} />
          <Route path="stock/:code" element={<ComingSoon title="個股" phase="P3" />} />
          <Route path="watchlist" element={<ComingSoon title="自選股" phase="P4" />} />
          <Route path="screener" element={<ComingSoon title="選股" phase="P5" />} />
          <Route path="global" element={<ComingSoon title="全球市場" phase="P5" />} />
          <Route path="calendar" element={<ComingSoon title="行事曆" phase="P5" />} />
          <Route path="ai" element={<ComingSoon title="AI 助理" phase="P5" />} />
          <Route path="*" element={<ComingSoon title="找不到頁面" phase="—" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
