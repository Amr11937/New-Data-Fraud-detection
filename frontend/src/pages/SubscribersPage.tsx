import { useMemo, useState } from 'react';
import {
  AppBar,
  Box,
  Button,
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
import type { DateRange } from '@/types';

const FullScreenTransition = forwardRef(function FullScreenTransition(
  props: TransitionProps & { children: ReactElement },
  ref: Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...props} />;
});

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
  const [range, setRange] = useState<DateRange>({ dateFrom: null, dateTo: null });
  const [search, setSearch] = useState('');
  const [decision, setDecision] = useState('');
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<string | null>(null);

  const { data, isLoading } = useSubscribers({
    dateFrom: range.dateFrom,
    dateTo: range.dateTo,
    search: search || undefined,
    decision: decision || undefined,
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
        <Box sx={{ flexGrow: 1 }} />
        <Button startIcon={<DownloadIcon />} onClick={handleExportCsv} disabled={!data?.items.length}>
          Export CSV
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
              <TableCell align="right">Risk</TableCell>
              <TableCell align="right">Final score</TableCell>
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

              <Stack direction="row" spacing={1} alignItems="center">
                <DecisionBadge decision={detail.latest_decision} />
                <Typography variant="body2">
                  Latest triggered rules: {detail.triggered_rules_latest.join(', ') || 'none'}
                </Typography>
              </Stack>

              <Grid container spacing={2}>
                {[
                  { label: 'Account', value: detail.account_num ?? '—' },
                  { label: 'Latest date', value: detail.latest_session_date },
                  { label: 'Maximum risk', value: `${detail.maximum_risk_score.toFixed(2)} / 100` },
                  { label: 'Average risk', value: detail.average_risk_score.toFixed(2) },
                  {
                    label: 'Score range',
                    value: `${((detail.latest_final_score ?? detail.maximum_risk_score / 100) * 100).toFixed(2)} score`,
                  },
                  { label: 'Sessions / day', value: detail.sessions_per_day.toLocaleString() },
                  { label: 'Daily usage', value: `${detail.daily_usage_gb.toFixed(2)} GB` },
                  { label: 'Avg session usage', value: `${(detail.average_session_usage_gb ?? 0).toFixed(2)} GB` },
                  {
                    label: 'Duration',
                    value: `${(detail.total_duration_minutes ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} min`,
                  },
                  {
                    label: 'Avg session duration',
                    value: `${(detail.average_session_duration_minutes ?? 0).toFixed(2)} min`,
                  },
                  { label: 'Input', value: `${(detail.total_input_gb ?? 0).toFixed(2)} GB` },
                  { label: 'Output', value: `${(detail.total_output_gb ?? 0).toFixed(2)} GB` },
                  { label: 'Offer encoding', value: detail.offer_name ?? '—' },
                  { label: 'Available history days', value: detail.history_days },
                  { label: 'Total source records', value: '—' },
                  { label: 'Risk level', value: detail.risk_level },
                ].map((tile) => (
                  <Grid item xs={6} sm={4} md={3} key={tile.label}>
                    <KpiCard label={tile.label.toUpperCase()} value={tile.value} />
                  </Grid>
                ))}
              </Grid>

              <Typography variant="subtitle2" sx={{ mt: 2 }}>
                Score history ({historyChartData.length} days)
              </Typography>
              <TableContainer sx={{ maxHeight: 420 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>Date</TableCell>
                      <TableCell align="right">Risk</TableCell>
                      <TableCell>Decision</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {historyChartData.map((h) => (
                      <TableRow key={h.session_date}>
                        <TableCell>{h.session_date}</TableCell>
                        <TableCell align="right">{h.risk_score_0_100.toFixed(1)}</TableCell>
                        <TableCell>
                          <DecisionBadge decision={h.decision} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Stack>
          )}
        </Container>
      </Dialog>
    </Stack>
  );
}
