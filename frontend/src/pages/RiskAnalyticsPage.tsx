import { useState } from 'react';
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
import { usePackageStats, useRuleStatistics } from '@/hooks/useDashboard';
import type { DateRange } from '@/types';

export function RiskAnalyticsPage() {
  const [range, setRange] = useState<DateRange>({ dateFrom: null, dateTo: null });
  const { data: ruleStats } = useRuleStatistics(range);
  const { data: packageStats } = usePackageStats();

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
    </Stack>
  );
}
