import { useQuery } from '@tanstack/react-query';
import * as api from '@/services/api';
import type { DateRange } from '@/types';

export function useKpis(range: DateRange) {
  return useQuery({
    queryKey: ['kpis', range.dateFrom, range.dateTo],
    queryFn: () => api.fetchKpis(range.dateFrom, range.dateTo),
  });
}

export function useDailyTrend(range: DateRange) {
  return useQuery({
    queryKey: ['daily-trend', range.dateFrom, range.dateTo],
    queryFn: () => api.fetchDailyTrend(range.dateFrom, range.dateTo),
  });
}

export function useAnalyticsWindows() {
  return useQuery({
    queryKey: ['analytics-windows'],
    queryFn: api.fetchAnalyticsWindows,
  });
}

export function useRiskDistribution() {
  return useQuery({
    queryKey: ['risk-distribution'],
    queryFn: api.fetchRiskDistribution,
  });
}

export function usePackageStats() {
  return useQuery({
    queryKey: ['package-stats'],
    queryFn: api.fetchPackageStats,
  });
}

export function useRuleStatistics(range: DateRange) {
  return useQuery({
    queryKey: ['rule-statistics', range.dateFrom, range.dateTo],
    queryFn: () => api.fetchRuleStatistics(range.dateFrom, range.dateTo),
  });
}

export function useSystemHealth() {
  return useQuery({
    queryKey: ['system-health'],
    queryFn: api.fetchSystemHealth,
    refetchInterval: 15_000,
  });
}

export function useSubscribers(params: {
  dateFrom?: string | null;
  dateTo?: string | null;
  search?: string;
  decision?: string;
  page: number;
  pageSize: number;
}) {
  return useQuery({
    queryKey: ['subscribers', params],
    queryFn: () => api.fetchSubscribers(params),
  });
}

export function useSubscriberDetail(subscriberId: string | null) {
  return useQuery({
    queryKey: ['subscriber-detail', subscriberId],
    queryFn: () => api.fetchSubscriberDetail(subscriberId as string),
    enabled: !!subscriberId,
  });
}
