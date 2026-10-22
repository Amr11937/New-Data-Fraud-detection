import {
  Card,
  CardContent,
  Grid,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import ReactECharts from 'echarts-for-react';
import { DateRangeFilter } from '@/components/DateRangeFilter';
import { usePackageRisk, usePackageStats, useRuleStatistics } from '@/hooks/useDashboard';
import { useDateRange } from '@/context/DateRangeContext';

export function RiskAnalyticsPage() {
  const { range, setRange } = useDateRange();
  const { data: ruleStats } = useRuleStatistics(range);
  const { data: packageStats } = usePackageStats();
  const { data: packageRisk } = usePackageRisk(range);

  const packagePieOption = {
    tooltip: { trigger: 'item' },
    series: [
      {
        type: 'pie',
        radius: '65%',
        data: (packageStats?.distribution ?? []).slice(0, 10).map((p) => ({ name: p.name, value: p.value })),
      },
    ],
  };

  const topPackages = [...(packageRisk?.packages ?? [])].reverse();
  const packageRiskOption = {
    color: ['#D32F2F'],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 190, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value', name: 'Average risk score', min: 0, max: 100 },
    yAxis: { type: 'category', data: topPackages.map((p) => p.package_name), axisLabel: { width: 170, overflow: 'truncate' } },
    series: [{ type: 'bar', data: topPackages.map((p) => p.average_risk) }],
  };

  const packageDailyOption = {
    color: ['#4F9F2F', '#F59E0B', '#D32F2F'],
    tooltip: { trigger: 'axis' },
    legend: { data: ['Low', 'Medium', 'High'] },
    grid: { left: 70, right: 24, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: packageRisk?.daily.map((d) => d.date) ?? [] },
    yAxis: { type: 'value', name: 'Package records' },
    series: [
      { name: 'Low', type: 'bar', data: packageRisk?.daily.map((d) => d.low_count) ?? [] },
      { name: 'Medium', type: 'bar', data: packageRisk?.daily.map((d) => d.medium_count) ?? [] },
      { name: 'High', type: 'bar', data: packageRisk?.daily.map((d) => d.high_count) ?? [] },
    ],
  };

  return (
    <Stack spacing={3}>
      <DateRangeFilter value={range} onChange={setRange} />

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" gutterBottom>
            Rule trigger statistics
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            Trigger counts only -- true/false-positive rates need labeled fraud outcomes, which this dataset
            doesn't have yet.
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Rule</TableCell>
                  <TableCell>Feature</TableCell>
                  <TableCell align="right">Threshold</TableCell>
                  <TableCell align="right">Points</TableCell>
                  <TableCell align="right">Triggers</TableCell>
                  <TableCell align="right">Trigger rate</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(ruleStats?.rules ?? []).map((r) => (
                  <TableRow key={r.rule_id}>
                    <TableCell>{r.rule_id}</TableCell>
                    <TableCell>{r.feature}</TableCell>
                    <TableCell align="right">{r.upper_limit}</TableCell>
                    <TableCell align="right">{r.points}</TableCell>
                    <TableCell align="right">{r.trigger_count.toLocaleString()}</TableCell>
                    <TableCell align="right">{(r.trigger_rate * 100).toFixed(1)}%</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Top offers by subscriber count
              </Typography>
              <ReactECharts option={packagePieOption} style={{ height: 320 }} notMerge />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Decision totals in range
              </Typography>
              <Stack spacing={1} sx={{ mt: 2 }}>
                <Typography>Allow: {ruleStats?.allow_count ?? 0}</Typography>
                <Typography>Review: {ruleStats?.review_count ?? 0}</Typography>
                <Typography>Block: {ruleStats?.block_count ?? 0}</Typography>
                <Typography color="text.secondary">Total rows: {ruleStats?.total_rows ?? 0}</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {packageRisk?.available && (
        <>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Package risk
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                Each package gets its own risk score. Showing the 15 packages with the highest average risk in the
                selected dates.
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <ReactECharts option={packageRiskOption} style={{ height: 420 }} notMerge />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 420 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell>Package</TableCell>
                          <TableCell align="right">Avg risk</TableCell>
                          <TableCell align="right">High-risk records</TableCell>
                          <TableCell align="right">Records</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {packageRisk.packages.map((p) => (
                          <TableRow key={p.package_name}>
                            <TableCell>{p.package_name}</TableCell>
                            <TableCell align="right">{p.average_risk.toFixed(1)}</TableCell>
                            <TableCell align="right" sx={{ color: p.high_count > 0 ? 'error.main' : undefined, fontWeight: p.high_count > 0 ? 600 : undefined }}>
                              {p.high_count.toLocaleString()}
                            </TableCell>
                            <TableCell align="right">{p.row_count.toLocaleString()}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Package risk by day (low / medium / high records)
              </Typography>
              <ReactECharts option={packageDailyOption} style={{ height: 320 }} notMerge />
            </CardContent>
          </Card>
        </>
      )}
    </Stack>
  );
}
