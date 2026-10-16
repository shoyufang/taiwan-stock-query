import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'
import { AppShell } from './components/AppShell'
import { useMarketMode } from './lib/useMarketMode'
import { ComingSoon } from './pages/ComingSoon'
import { Home } from './pages/Home'
import { Overview } from './pages/Overview'

// 首頁（市場總覽）同步載入，其餘頁面依路由分包（Code-Splitting），降低首次載入體積
const StockPage = lazy(() => import('./pages/StockPage').then((m) => ({ default: m.StockPage })))
const WatchlistPage = lazy(() => import('./pages/WatchlistPage').then((m) => ({ default: m.WatchlistPage })))
const ScreenerPage = lazy(() => import('./pages/ScreenerPage').then((m) => ({ default: m.ScreenerPage })))
const GlobalPage = lazy(() => import('./pages/GlobalPage').then((m) => ({ default: m.GlobalPage })))
const PortfolioPage = lazy(() => import('./pages/PortfolioPage').then((m) => ({ default: m.PortfolioPage })))
const CalendarPage = lazy(() => import('./pages/CalendarPage').then((m) => ({ default: m.CalendarPage })))
const AiPage = lazy(() => import('./pages/AiPage').then((m) => ({ default: m.AiPage })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: true } },
})

export function App() {
  const market = useMarketMode()
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={null}>
          <Routes>
            <Route element={<AppShell market={market} />}>
              <Route index element={<Overview mode={market.mode} />} />
              <Route path="stock/:code" element={<StockPage mode={market.mode} />} />
              <Route path="watchlist" element={<WatchlistPage mode={market.mode} />} />
              <Route path="screener" element={<ScreenerPage />} />
              <Route path="global" element={<GlobalPage mode={market.mode} />} />
              <Route path="portfolio" element={<PortfolioPage mode={market.mode} />} />
              <Route path="calendar" element={<CalendarPage />} />
              <Route path="ai" element={<AiPage />} />
              <Route path="status" element={<Home mode={market.mode} />} />
              <Route path="*" element={<ComingSoon title="找不到頁面" phase="—" />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

