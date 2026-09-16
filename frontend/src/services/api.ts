/**
 * Axios API client for the merged PCRF + Broadband FMS dashboard.
 *
 * During development (npm run dev), vite.config.ts proxies /api/* to
 * http://localhost:8000. In production the React build is served by
 * the FastAPI backend itself (see backend/app/main.py), so relative
 * paths work without any proxy either way.
 */
import axios from 'axios';
import type {
  AnalyticsWindowsResponse,
  DailyPoint,
  KpiResponse,
  PackageStatsResponse,
  RiskBand,
  RuleStatisticsResponse,
  ScoreRequest,
  ScoreResponse,
  SubscriberDetail,
  SubscriberListResponse,
  SystemHealthResponse,
} from '@/types';

const api = axios.create({
  baseURL: '',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    let detail = error.response?.data?.detail;

    // Blob-response endpoints (e.g. Demask CSV downloads) carry JSON error
    // bodies as a Blob instead of parsed JSON -- read it before falling back.
    if (detail === undefined && error.response?.data instanceof Blob) {
      try {
        const parsed = JSON.parse(await error.response.data.text());
        detail = parsed.detail;
      } catch {
        // not JSON -- ignore and fall through to the generic message below
      }
    }

    const message =
      (typeof detail === 'string' ? detail : detail?.message) ||
      error.response?.data?.message ||
      error.message ||
      'Unknown error';
    return Promise.reject(new Error(message));
  }
);

function buildParams(params: Record<string, string | number | boolean | null | undefined>) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') p.append(k, String(v));
  });
  return p;
}

// ---------------------------------------------------------------------------
// KPIs / analytics
// ---------------------------------------------------------------------------

export const fetchKpis = async (dateFrom?: string | null, dateTo?: string | null): Promise<KpiResponse> => {
  const { data } = await api.get('/api/kpis', { params: buildParams({ date_from: dateFrom, date_to: dateTo }) });
  return data;
};

export const fetchDailyTrend = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<DailyPoint[]> => {
  const { data } = await api.get('/api/analytics/daily', {
    params: buildParams({ date_from: dateFrom, date_to: dateTo }),
  });
  return data;
};

export const fetchAnalyticsWindows = async (): Promise<AnalyticsWindowsResponse> => {
  const { data } = await api.get('/api/analytics/windows');
  return data;
};

export const fetchRiskDistribution = async (): Promise<RiskBand[]> => {
  const { data } = await api.get('/api/analytics/risk-distribution');
  return data;
};

export const fetchPackageStats = async (): Promise<PackageStatsResponse> => {
  const { data } = await api.get('/api/analytics/packages');
  return data;
};

export const fetchRuleStatistics = async (
  dateFrom?: string | null,
  dateTo?: string | null
): Promise<RuleStatisticsResponse> => {
  const { data } = await api.get('/api/analytics/rule-statistics', {
    params: buildParams({ date_from: dateFrom, date_to: dateTo }),
  });
  return data;
};

export const fetchSystemHealth = async (): Promise<SystemHealthResponse> => {
  const { data } = await api.get('/api/system-health');
  return data;
};

// ---------------------------------------------------------------------------
// Subscribers
// ---------------------------------------------------------------------------

export const fetchSubscribers = async (params: {
  dateFrom?: string | null;
  dateTo?: string | null;
  search?: string;
  decision?: string;
  minRisk?: number;
  maxRisk?: number;
  page?: number;
  pageSize?: number;
}): Promise<SubscriberListResponse> => {
  const { data } = await api.get('/api/subscribers', {
    params: buildParams({
      date_from: params.dateFrom,
      date_to: params.dateTo,
      search: params.search,
      decision: params.decision,
      min_risk: params.minRisk,
      max_risk: params.maxRisk,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 25,
    }),
  });
  return data;
};

export const fetchSubscriberDetail = async (subscriberId: string): Promise<SubscriberDetail> => {
  const { data } = await api.get(`/api/subscribers/${encodeURIComponent(subscriberId)}`);
  return data;
};

// ---------------------------------------------------------------------------
// Scoring / reports
// ---------------------------------------------------------------------------

export const scoreSubscriber = async (payload: ScoreRequest): Promise<ScoreResponse> => {
  const { data } = await api.post('/api/score', payload);
  return data;
};

export const downloadPdfReport = (dateFrom: string, dateTo: string): void => {
  const params = buildParams({ date_from: dateFrom, date_to: dateTo });
  window.open(`/api/report/pdf?${params.toString()}`, '_blank');
};

export default api;
