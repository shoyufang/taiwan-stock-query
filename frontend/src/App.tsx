import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { useMarketMode } from './lib/useMarketMode'
import { CalendarPage } from './pages/CalendarPage'
import { ComingSoon } from './pages/ComingSoon'
import { Home } from './pages/Home'
import { Overview } from './pages/Overview'
import { GlobalPage } from './pages/GlobalPage'
import { ScreenerPage } from './pages/ScreenerPage'
import { StockPage } from './pages/StockPage'
import { WatchlistPage } from './pages/WatchlistPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: true } },
})

export function App() {
  const market = useMarketMode()
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell market={market} />}>
            <Route index element={<Overview mode={market.mode} />} />
            <Route path="stock/:code" element={<StockPage mode={market.mode} />} />
            <Route path="watchlist" element={<WatchlistPage mode={market.mode} />} />
            <Route path="screener" element={<ScreenerPage />} />
            <Route path="global" element={<GlobalPage mode={market.mode} />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="ai" element={<ComingSoon title="AI 助理" phase="P5" />} />
            <Route path="status" element={<Home mode={market.mode} />} />
            <Route path="*" element={<ComingSoon title="找不到頁面" phase="—" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
