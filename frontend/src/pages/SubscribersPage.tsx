import { useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import {
  AppBar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Container,
  Dialog,
  Grid,
  IconButton,
  MenuItem,
  Paper,
  Slide,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Toolbar,
  Tooltip,
  Typography,
} from '@mui/material';
import type { TransitionProps } from '@mui/material/transitions';
import { forwardRef, type ReactElement, type Ref } from 'react';
import { KpiCard } from '@/components/KpiCard';
import CloseIcon from '@mui/icons-material/Close';
import DownloadIcon from '@mui/icons-material/Download';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import { DateRangeFilter } from '@/components/DateRangeFilter';
import { DecisionBadge } from '@/components/DecisionBadge';
import { useSubscriberDetail, useSubscribers } from '@/hooks/useDashboard';
import { downloadPdfReport } from '@/services/api';
import { useDateRange } from '@/context/DateRangeContext';

const FullScreenTransition = forwardRef(function FullScreenTransition(
  props: TransitionProps & { children: ReactElement },
  ref: Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...props} />;
});

// Plain-language meaning of each rule (see backend/app/config/rules.yaml for the checks behind them).
const RULE_DESCRIPTIONS: Record<string, string> = {
  rule_01: 'Unusually high total data usage in a day.',
  rule_02: 'Unusually high download volume in a day.',
  rule_03: 'Unusually high upload volume in a day.',
  rule_04: 'Unusually large average data usage per session.',
  rule_05: 'Unusually high number of sessions in a day.',
  rule_06: 'Too many different offers or packages used in a single day.',
  rule_07: 'Download-to-upload ratio is unusually high.',
};

const RISK_LEVEL_COLORS: Record<string, string> = {
  Critical: '#D32F2F',
  High: '#F59E0B',
  Medium: '#4F9F2F',
  Low: '#4F9F2F',
  Normal: '#4F9F2F',
};

// Fallback when a date has no per-package risk: a package counts as high-risk when the
// subscriber's average risk score on the days it was active is in the High band (70+).
const HIGH_RISK_PACKAGE_SCORE = 70;

function formatHoursMinutes(totalMinutes: number): string {
  const rounded = Math.round(totalMinutes);
  const h = Math.floor(rounded / 60);
  const m = rounded % 60;
  return `${h.toLocaleString()} h ${m} min`;
}

function toCsv(rows: Record<string, unknown>[]): string {
  if (rows.length === 0) return '';
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];
  for (const row of rows) {
    lines.push(headers.map((h) => JSON.stringify(row[h] ?? '')).join(','));
  }
  return lines.join('\n');
}

export function SubscribersPage() {
  const { range, setRange } = useDateRange();
  const [search, setSearch] = useState('');
  const [decision, setDecision] = useState('');
  const [minRisk, setMinRisk] = useState('');
  const [maxRisk, setMaxRisk] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<string | null>(null);

  const { data, isLoading } = useSubscribers({
    dateFrom: range.dateFrom,
    dateTo: range.dateTo,
    search: search || undefined,
    decision: decision || undefined,
    minRisk: minRisk === '' ? undefined : Number(minRisk),
    maxRisk: maxRisk === '' ? undefined : Number(maxRisk),
    page: page + 1,
    pageSize,
  });
  const { data: detail } = useSubscriberDetail(selected);

  const canExportPdf = !!range.dateFrom && !!range.dateTo;

  const handleExportCsv = () => {
    if (!data) return;
    const csv = toCsv(data.items as unknown as Record<string, unknown>[]);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'subscribers.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const historyChartData = useMemo(() => detail?.history ?? [], [detail]);

  const totalSessions = useMemo(
    () => historyChartData.reduce((sum, h) => sum + (h.sessions_per_day ?? 0), 0),
    [historyChartData]
  );
  const avgSessionsPerDay = historyChartData.length ? totalSessions / historyChartData.length : 0;

  // Red package tags: use the real per-package risk when we have it for that date;
  // otherwise fall back to the subscriber's average risk on the days the package was active.
  const packageRiskByDate = useMemo(() => {
    const m = new Map<string, Map<string, { score: number; level: string | null }>>();
    for (const h of historyChartData) {
      if (!h.package_risks?.length) continue;
      m.set(
        h.session_date,
        new Map(h.package_risks.map((p) => [p.package_name, { score: p.risk_score_0_100, level: p.risk_level }]))
      );
    }
    return m;
  }, [historyChartData]);

  const fallbackHighRiskPackages = useMemo(() => {
    const stats = new Map<string, { sum: number; n: number }>();
    for (const h of historyChartData) {
      for (const p of (h.offer_name ?? '').split(',').map((x) => x.trim()).filter(Boolean)) {
        const cur = stats.get(p) ?? { sum: 0, n: 0 };
        cur.sum += h.risk_score_0_100;
        cur.n += 1;
        stats.set(p, cur);
      }
    }
    const flagged = new Set<string>();
    stats.forEach((v, p) => {
      if (v.sum / v.n >= HIGH_RISK_PACKAGE_SCORE) flagged.add(p);
    });
    return flagged;
  }, [historyChartData]);

  const usageOption = {
    color: ['#0072BC', '#6CB33F'],
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => `${v.toFixed(2)} GB` },
    legend: { data: ['Download', 'Upload'] },
    grid: { left: 60, right: 24, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: historyChartData.map((h) => h.session_date) },
    yAxis: { type: 'value', name: 'GB' },
    series: [
      {
        name: 'Download',
        type: 'bar',
        data: historyChartData.map((h) => Number((h.total_input_gb ?? 0).toFixed(2))),
      },
      {
        name: 'Upload',
        type: 'bar',
        data: historyChartData.map((h) => Number((h.total_output_gb ?? 0).toFixed(2))),
      },
    ],
  };

  const durationOption = {
    color: ['#6CB33F'],
    tooltip: {
      trigger: 'axis',
      formatter: (params: { axisValue: string; value: number }[]) =>
        `${params[0].axisValue}<br/>Duration: <b>${formatHoursMinutes(params[0].value)}</b>`,
    },
    grid: { left: 80, right: 24, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: historyChartData.map((h) => h.session_date) },
    yAxis: {
      type: 'value',
      name: 'Hours',
      axisLabel: { formatter: (v: number) => `${Math.round(v / 60).toLocaleString()} h` },
    },
    series: [
      {
        name: 'Duration (min)',
        type: 'bar',
        data: historyChartData.map((h) => Number((h.total_duration_minutes ?? 0).toFixed(2))),
      },
    ],
  };

  const historyOption = {
    color: ['#0072BC'],
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 24, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: historyChartData.map((h) => h.session_date) },
    yAxis: { type: 'value', name: 'Risk score', min: 0, max: 100 },
    series: [
      {
        name: 'Risk score',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        areaStyle: { opacity: 0.12 },
        data: historyChartData.map((h) => Number(h.risk_score_0_100.toFixed(2))),
      },
    ],
  };

  return (
    <Stack spacing={2}>
      <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
        <DateRangeFilter value={range} onChange={setRange} />
        <TextField
          label="Search subscriber / account"
          size="small"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <TextField
          label="Decision"
          size="small"
          select
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">All</MenuItem>
          <MenuItem value="ALLOW">Allow</MenuItem>
          <MenuItem value="REVIEW">Review</MenuItem>
          <MenuItem value="BLOCK">Block</MenuItem>
        </TextField>
        <TextField
          label="Min risk score"
          size="small"
          type="number"
          value={minRisk}
          onChange={(e) => {
            setMinRisk(e.target.value);
            setPage(0);
          }}
          inputProps={{ min: 0, max: 100, step: 1 }}
          sx={{ width: 130 }}
        />
        <TextField
          label="Max risk score"
          size="small"
          type="number"
          value={maxRisk}
          onChange={(e) => {
            setMaxRisk(e.target.value);
            setPage(0);
          }}
          inputProps={{ min: 0, max: 100, step: 1 }}
          sx={{ width: 130 }}
        />
        <Box sx={{ flexGrow: 1 }} />
        <Button startIcon={<DownloadIcon />} onClick={handleExportCsv} disabled={!data?.items.length}>
          Download CSV
        </Button>
        <Button
          startIcon={<PictureAsPdfIcon />}
          onClick={() => range.dateFrom && range.dateTo && downloadPdfReport(range.dateFrom, range.dateTo)}
          disabled={!canExportPdf}
          title={canExportPdf ? '' : 'Pick a date range to export a PDF'}
        >
          Export PDF
        </Button>
      </Stack>

      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Subscriber</TableCell>
              <TableCell>Account</TableCell>
              <TableCell>Date</TableCell>
              <TableCell align="right">Risk prediction</TableCell>
              <TableCell align="right">Risk score</TableCell>
              <TableCell>Decision</TableCell>
              <TableCell>Triggered rules</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(data?.items ?? []).map((row) => (
              <TableRow
                key={`${row.subscriber_id}-${row.session_date}`}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => setSelected(row.subscriber_id)}
              >
                <TableCell>{row.subscriber_id}</TableCell>
                <TableCell>{row.account_num ?? '—'}</TableCell>
                <TableCell>{row.session_date}</TableCell>
                <TableCell align="right">{row.risk_score_0_100.toFixed(1)}</TableCell>
                <TableCell align="right">{row.final_score?.toFixed(3) ?? '—'}</TableCell>
                <TableCell>
                  <DecisionBadge decision={row.decision} />
                </TableCell>
                <TableCell>{row.triggered_rules.join(', ') || '—'}</TableCell>
              </TableRow>
            ))}
            {!isLoading && (data?.items.length ?? 0) === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Typography color="text.secondary">No subscribers match these filters.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
        <TablePagination
          component="div"
          count={data?.total ?? 0}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={pageSize}
          onRowsPerPageChange={(e) => {
            setPageSize(parseInt(e.target.value, 10));
            setPage(0);
          }}
          rowsPerPageOptions={[25, 50, 100]}
        />
      </TableContainer>

      <Dialog
        fullScreen
        open={!!selected}
        onClose={() => setSelected(null)}
        TransitionComponent={FullScreenTransition}
      >
        <AppBar position="sticky" color="default" elevation={1}>
          <Toolbar>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              Subscriber {detail?.subscriber_id ?? selected}
            </Typography>
            <IconButton edge="end" onClick={() => setSelected(null)} aria-label="close">
              <CloseIcon />
            </IconButton>
          </Toolbar>
        </AppBar>

        <Container maxWidth="lg" sx={{ py: 3 }}>
          {detail && (
            <Stack spacing={2}>
              <Box>
                <Typography variant="overline" color="text.secondary">
                  Selected subscriber
                </Typography>
                <Typography variant="h5">{detail.subscriber_id}</Typography>
                <Typography variant="body2" color="text.secondary">
                  Original subscriber and account identifiers are shown.
                </Typography>
              </Box>

              <Stack spacing={1}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <DecisionBadge decision={detail.latest_decision} />
                  <Typography variant="body2">
                    Latest triggered rules: {detail.triggered_rules_latest.join(', ') || 'none'}
                  </Typography>
                </Stack>
                <Typography variant="caption" color="text.secondary">
                  Triggered rules are checks that flag usage well above what is typical for a day. The more rules a
                  subscriber triggers, the higher the risk.
                </Typography>
                {detail.triggered_rules_latest.length > 0 && (
                  <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                    {detail.triggered_rules_latest.map((rule) => (
                      <Typography component="li" variant="body2" key={rule}>
                        <b>{rule}</b> – {RULE_DESCRIPTIONS[rule] ?? 'Usage flagged by a risk rule.'}
                      </Typography>
                    ))}
                  </Box>
                )}
              </Stack>

              <Grid container spacing={2}>
                {[
                  { label: 'Account', value: detail.account_num ?? '—' },
                  { label: 'Latest date', value: detail.latest_session_date },
                  { label: 'Maximum risk', value: `${detail.maximum_risk_score.toFixed(2)} / 100` },
                  { label: 'Average risk', value: detail.average_risk_score.toFixed(2) },
                  { label: 'Total sessions', value: totalSessions.toLocaleString() },
                  { label: 'Avg usage per session', value: `${(detail.average_session_usage_gb ?? 0).toFixed(2)} GB` },
                  { label: 'Avg session count per day', value: avgSessionsPerDay.toLocaleString(undefined, { maximumFractionDigits: 1 }) },
                  { label: 'Download', value: `${(detail.total_input_gb ?? 0).toFixed(2)} GB` },
                  { label: 'Upload', value: `${(detail.total_output_gb ?? 0).toFixed(2)} GB` },
                  { label: 'Available history days', value: detail.history_days },
                  { label: 'Total source records', value: '—' },
                  { label: 'Risk level', value: detail.risk_level, accent: RISK_LEVEL_COLORS[detail.risk_level] ?? RISK_LEVEL_COLORS.Normal },
                ].map((tile) => (
                  <Grid item xs={6} sm={4} md={3} key={tile.label}>
                    <KpiCard label={tile.label.toUpperCase()} value={tile.value} accent={(tile as { accent?: string }).accent} />
                  </Grid>
                ))}
              </Grid>

              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle2" gutterBottom>
                    Daily usage by day (download vs upload, GB)
                  </Typography>
                  <ReactECharts option={usageOption} style={{ height: 320 }} notMerge />
                </CardContent>
              </Card>

              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle2" gutterBottom>
                    Packages by date
                  </Typography>
                  <Stack spacing={1.5} sx={{ maxHeight: 360, overflowY: 'auto', pr: 1 }}>
                    {historyChartData.map((h) => (
                      <Stack key={h.session_date} direction={{ xs: 'column', sm: 'row' }} spacing={1.5} alignItems={{ sm: 'flex-start' }}>
                        <Typography variant="body2" fontWeight={600} sx={{ minWidth: 100, pt: 0.5 }}>
                          {h.session_date}
                        </Typography>
                        <Stack direction="row" flexWrap="wrap" useFlexGap spacing={1}>
                          {(h.offer_name ?? '')
                            .split(',')
                            .map((p) => p.trim())
                            .filter(Boolean)
                            .map((p) => {
                              const real = packageRiskByDate.get(h.session_date)?.get(p);
                              const isHigh = real ? real.level === 'HIGH' : fallbackHighRiskPackages.has(p);
                              return (
                                <Tooltip key={p} title={real ? `Package risk ${real.score.toFixed(1)} (${real.level ?? 'n/a'})` : ''}>
                                  <Chip
                                    label={real ? `${p} · ${real.score.toFixed(0)}` : p}
                                    size="small"
                                    variant="outlined"
                                    color={isHigh ? 'error' : 'primary'}
                                    sx={{
                                      height: 'auto',
                                      '& .MuiChip-label': { whiteSpace: 'normal', py: 0.5 },
                                      ...(isHigh && { borderWidth: 2, fontWeight: 600 }),
                                    }}
                                  />
                                </Tooltip>
                              );
                            })}
                          {!h.offer_name && <Typography variant="body2" color="text.secondary">—</Typography>}
                        </Stack>
                      </Stack>
                    ))}
                  </Stack>
                </CardContent>
              </Card>

              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle2" gutterBottom>
                    Risk score by day ({historyChartData.length} days)
                  </Typography>
                  <ReactECharts option={historyOption} style={{ height: 320 }} notMerge />
                </CardContent>
              </Card>

              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle2" gutterBottom>
                    Duration by day (hours & minutes)
                  </Typography>
                  <ReactECharts option={durationOption} style={{ height: 320 }} notMerge />
                </CardContent>
              </Card>
            </Stack>
          )}
        </Container>
      </Dialog>
    </Stack>
  );
}
