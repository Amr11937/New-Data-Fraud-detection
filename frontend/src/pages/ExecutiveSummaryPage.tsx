import { useState } from 'react';
import { Card, CardContent, Grid, Stack, Typography } from '@mui/material';
import ReactECharts from 'echarts-for-react';
import { DateRangeFilter } from '@/components/DateRangeFilter';
import { KpiCard } from '@/components/KpiCard';
import { useAnalyticsWindows, useDailyTrend, useKpis, useRiskDistribution } from '@/hooks/useDashboard';
import type { DateRange } from '@/types';

export function ExecutiveSummaryPage() {
  const [range, setRange] = useState<DateRange>({ dateFrom: null, dateTo: null });

  const { data: kpis } = useKpis(range);
  const { data: daily } = useDailyTrend(range);
  const { data: windows } = useAnalyticsWindows();
  const { data: riskDist } = useRiskDistribution();

  const trendOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['Avg risk', 'Sessions'] },
    xAxis: { type: 'category', data: daily?.map((d) => d.date) ?? [] },
    yAxis: [{ type: 'value', name: 'Risk' }, { type: 'value', name: 'Sessions' }],
    series: [
      { name: 'Avg risk', type: 'line', data: daily?.map((d) => d.average_risk) ?? [], yAxisIndex: 0 },
      { name: 'Sessions', type: 'bar', data: daily?.map((d) => d.total_sessions) ?? [], yAxisIndex: 1 },
    ],
  };

  const riskOption = {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: riskDist?.map((r) => r.label) ?? [] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: riskDist?.map((r) => r.count) ?? [], name: 'Subscribers' }],
  };

  return (
    <Stack spacing={3}>
      <DateRangeFilter value={range} onChange={setRange} />

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard label="Total subscribers" value={kpis?.total_subscribers ?? '—'} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard label="Total sessions" value={kpis?.total_sessions?.toLocaleString() ?? '—'} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard label="Average risk" value={kpis?.average_risk?.toFixed(1) ?? '—'} />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            label="Block / Review"
            value={`${kpis?.block_count ?? 0} / ${kpis?.review_count ?? 0}`}
            subtext={`of ${kpis?.total_sessions ?? 0} rows`}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                {windows?.last_7_days.label ?? 'Last 7 days'}
              </Typography>
              <Typography variant="h5">{windows?.last_7_days.total_subscribers ?? '—'} subscribers</Typography>
              <Typography variant="body2" color="text.secondary">
                {windows?.last_7_days.block_count ?? 0} blocked · {windows?.last_7_days.review_count ?? 0} for review
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                {windows?.last_30_days.label ?? 'Last 30 days'}
              </Typography>
              <Typography variant="h5">{windows?.last_30_days.total_subscribers ?? '—'} subscribers</Typography>
              <Typography variant="body2" color="text.secondary">
                {windows?.last_30_days.block_count ?? 0} blocked · {windows?.last_30_days.review_count ?? 0} for review
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            Daily risk & session trend
          </Typography>
          <ReactECharts option={trendOption} style={{ height: 320 }} notMerge />
        </CardContent>
      </Card>

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            Subscribers by risk band (per-subscriber max score)
          </Typography>
          <ReactECharts option={riskOption} style={{ height: 280 }} notMerge />
        </CardContent>
      </Card>
    </Stack>
  );
}
