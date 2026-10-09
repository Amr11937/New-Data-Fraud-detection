import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CssBaseline, ThemeProvider, createTheme } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';

import MainLayout from '@/layouts/MainLayout';
import { ExecutiveSummaryPage } from '@/pages/ExecutiveSummaryPage';
import { SubscribersPage } from '@/pages/SubscribersPage';
import { RiskAnalyticsPage } from '@/pages/RiskAnalyticsPage';
import { SystemHealthPage } from '@/pages/SystemHealthPage';
import { DemaskPage } from '@/pages/DemaskPage';
import { LoginPage } from '@/pages/LoginPage';
import { AuthProvider, RequireAuth } from '@/auth/AuthContext';

const theme = createTheme({
  palette: {
    mode: 'light',
    background: { default: '#F2F6FB', paper: '#FFFFFF' },
    primary: { main: '#0072BC', dark: '#004F8C', light: '#3D9BDB', contrastText: '#FFFFFF' },
    secondary: { main: '#6CB33F', dark: '#4F9226', contrastText: '#FFFFFF' },
    success: { main: '#4F9F2F' },
    warning: { main: '#F59E0B' },
    error: { main: '#D32F2F' },
    text: { primary: '#1B2A3B', secondary: '#5B6B7D' },
    divider: '#DCE5EF',
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
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <BrowserRouter>
            <AuthProvider>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/login" element={<LoginPage />} />
                <Route
                  path="/dashboard"
                  element={
                    <RequireAuth>
                      <MainLayout />
                    </RequireAuth>
                  }
                >
                  <Route index element={<ExecutiveSummaryPage />} />
                  <Route path="subscribers" element={<SubscribersPage />} />
                  <Route path="risk" element={<RiskAnalyticsPage />} />
                  <Route path="health" element={<SystemHealthPage />} />
                  <Route path="demask" element={<DemaskPage />} />
                </Route>
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </AuthProvider>
          </BrowserRouter>
        </LocalizationProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
