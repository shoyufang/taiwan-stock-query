import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { useMarketMode } from './lib/useMarketMode'
import { CalendarPage } from './pages/CalendarPage'
import { ComingSoon } from './pages/ComingSoon'
import { Home } from './pages/Home'
import { Overview } from './pages/Overview'
import { GlobalPage } from './pages/GlobalPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { ScreenerPage } from './pages/ScreenerPage'
import { StockPage } from './pages/StockPage'
import { WatchlistPage } from './pages/WatchlistPage'

// AI 頁含 Markdown 套件，分開打包、進頁才載入
const AiPage = lazy(() => import('./pages/AiPage').then((m) => ({ default: m.AiPage })))

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
            <Route path="portfolio" element={<PortfolioPage mode={market.mode} />} />
            <Route path="calendar" element={<CalendarPage />} />
            <Route path="ai" element={<Suspense fallback={null}><AiPage /></Suspense>} />
            <Route path="status" element={<Home mode={market.mode} />} />
            <Route path="*" element={<ComingSoon title="找不到頁面" phase="—" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
