import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { Alert, Card, CardContent, Grid, MenuItem, TextField, Typography } from '@mui/material';
import { KpiCard } from '@/components/KpiCard';
import type { PackageUsagePoint, SubscriberDetailPoint } from '@/types';

export const ALL_PACKAGES = '';

const MAX_TREND_LINES = 8;

const fmt = (v: number) => v.toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 });

/**
 * Package-wise usage for one subscriber, from the per-package dataset
 * (subscriber_package_daily). "Attributed" usage is what the package dataset
 * assigns to a package; "unattributed" is the rest of the subscriber's daily
 * total (including days the package dataset does not cover).
 */
export function PackageUsageAnalysis({
  history,
  usage,
  selected,
  onSelect,
}: {
  history: SubscriberDetailPoint[];
  usage: PackageUsagePoint[];
  selected: string;
  onSelect: (pkg: string) => void;
}) {
  const stats = useMemo(() => {
    const byPackage = new Map<string, { download: number; upload: number; sessions: number }>();
    const attributedByDate = new Map<string, number>();
    for (const u of usage) {
      const cur = byPackage.get(u.package_name) ?? { download: 0, upload: 0, sessions: 0 };
      cur.download += u.download_gb;
      cur.upload += u.upload_gb;
      cur.sessions += u.sessions_per_day ?? 0;
      byPackage.set(u.package_name, cur);
      attributedByDate.set(u.session_date, (attributedByDate.get(u.session_date) ?? 0) + u.total_usage_gb);
    }
    const packages = [...byPackage.entries()]
      .map(([name, v]) => ({ name, ...v, total: v.download + v.upload }))
      .sort((a, b) => b.total - a.total);

    const attributed = packages.reduce((s, p) => s + p.total, 0);
    const sessions = packages.reduce((s, p) => s + p.sessions, 0);

    // Per day, whatever the subscriber used beyond the package dataset is unattributed.
    let unattributed = 0;
    for (const h of history) {
      const total = (h.total_input_gb ?? 0) + (h.total_output_gb ?? 0);
      unattributed += Math.max(0, total - (attributedByDate.get(h.session_date) ?? 0));
    }
    return { packages, attributed, unattributed, sessions };
  }, [history, usage]);

  const dates = useMemo(() => [...new Set(usage.map((u) => u.session_date))].sort(), [usage]);

  const barOption = {
    color: ['#0072BC', '#6CB33F'],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (v: number) => `${v.toFixed(3)} GB`,
    },
    legend: { data: ['Download', 'Upload'] },
    grid: { left: 170, right: 24, top: 40, bottom: 30 },
    xAxis: { type: 'value', name: 'GB' },
    yAxis: {
      type: 'category',
      inverse: true,
      data: stats.packages.map((p) => p.name),
      axisLabel: { width: 150, overflow: 'truncate' },
    },
    series: [
      { name: 'Download', type: 'bar', stack: 'usage', data: stats.packages.map((p) => Number(p.download.toFixed(3))) },
      { name: 'Upload', type: 'bar', stack: 'usage', data: stats.packages.map((p) => Number(p.upload.toFixed(3))) },
    ],
  };

  const trendPackages = selected ? [selected] : stats.packages.slice(0, MAX_TREND_LINES).map((p) => p.name);
  const trendOption = {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v.toFixed(3)} GB` },
    legend: { data: trendPackages, type: 'scroll' },
    grid: { left: 60, right: 24, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'GB' },
    series: trendPackages.map((name) => ({
      name,
      type: 'line',
      symbolSize: 8,
      data: dates.map((d) =>
        Number(
          usage
            .filter((u) => u.session_date === d && u.package_name === name)
            .reduce((s, u) => s + u.total_usage_gb, 0)
            .toFixed(3)
        )
      ),
    })),
  };

  if (usage.length === 0) {
    return (
      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle1" fontWeight={700} gutterBottom>
            Package-wise Usage Analysis
          </Typography>
          <Alert severity="info" variant="outlined">
            No per-package usage was found for this subscriber in the package dataset, so none of its usage can be
            attributed to a package.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle1" fontWeight={700} gutterBottom>
          Package-wise Usage Analysis
        </Typography>
        <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
          Usage is attributed from the per-package dataset ({dates[0]} to {dates[dates.length - 1]}). Anything the
          subscriber used outside it is shown as unattributed.
        </Alert>

        <Grid container spacing={2} sx={{ mb: 2 }}>
          {[
            { label: 'ATTRIBUTED GB', value: fmt(stats.attributed) },
            { label: 'UNATTRIBUTED GB', value: fmt(stats.unattributed) },
            { label: 'PACKAGES', value: stats.packages.length.toLocaleString() },
            { label: 'SESSIONS', value: stats.sessions.toLocaleString() },
          ].map((tile) => (
            <Grid item xs={6} md={3} key={tile.label}>
              <KpiCard label={tile.label} value={tile.value} />
            </Grid>
          ))}
        </Grid>

        <TextField
          select
          size="small"
          label="Package detail"
          value={selected}
          onChange={(e) => onSelect(e.target.value)}
          sx={{ minWidth: 280, mb: 2 }}
        >
          <MenuItem value={ALL_PACKAGES}>All packages</MenuItem>
          {stats.packages.map((p) => (
            <MenuItem key={p.name} value={p.name}>
              {p.name}
            </MenuItem>
          ))}
        </TextField>

        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" gutterBottom>
              Package-wise Data Consumption
            </Typography>
            <ReactECharts
              option={barOption}
              style={{ height: Math.max(220, 90 + stats.packages.length * 36) }}
              notMerge
            />
          </Grid>
          <Grid item xs={12} md={6}>
            <Typography variant="subtitle2" gutterBottom>
              Daily Package Usage Trend
              {!selected && stats.packages.length > MAX_TREND_LINES ? ` (top ${MAX_TREND_LINES} packages)` : ''}
            </Typography>
            <ReactECharts option={trendOption} style={{ height: 320 }} notMerge />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}
