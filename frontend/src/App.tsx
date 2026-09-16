import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material';

import MainLayout from '@/layouts/MainLayout';
import { ExecutiveSummaryPage } from '@/pages/ExecutiveSummaryPage';
import { SubscribersPage } from '@/pages/SubscribersPage';
import { RiskAnalyticsPage } from '@/pages/RiskAnalyticsPage';
import { SystemHealthPage } from '@/pages/SystemHealthPage';
import { DemaskPage } from '@/pages/DemaskPage';

const theme = createTheme({
  palette: {
    mode: 'dark',
    background: { default: '#060D1A', paper: '#0F172A' },
    primary: { main: '#2563EB' },
    secondary: { main: '#7C3AED' },
  },
  typography: { fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif' },
  shape: { borderRadius: 8 },
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<MainLayout />}>
              <Route index element={<ExecutiveSummaryPage />} />
              <Route path="subscribers" element={<SubscribersPage />} />
              <Route path="risk" element={<RiskAnalyticsPage />} />
              <Route path="health" element={<SystemHealthPage />} />
              <Route path="demask" element={<DemaskPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
