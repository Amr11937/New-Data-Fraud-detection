import { useMemo, useState } from 'react';
import {
  Box,
  Button,
  Drawer,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import { DateRangeFilter } from '@/components/DateRangeFilter';
import { DecisionBadge } from '@/components/DecisionBadge';
import { useSubscriberDetail, useSubscribers } from '@/hooks/useDashboard';
import { downloadPdfReport } from '@/services/api';
import type { DateRange } from '@/types';

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

      <Drawer anchor="right" open={!!selected} onClose={() => setSelected(null)}>
        <Box sx={{ width: 420, p: 3 }}>
          {detail && (
            <Stack spacing={2}>
              <Typography variant="h6">{detail.subscriber_id}</Typography>
              <Typography variant="body2" color="text.secondary">
                Account {detail.account_num ?? '—'} · last seen {detail.latest_session_date}
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <DecisionBadge decision={detail.latest_decision} />
                <Typography variant="body2">
                  final score {detail.latest_final_score?.toFixed(3) ?? '—'}
                </Typography>
              </Stack>
              <Typography variant="body2">
                Max risk {detail.maximum_risk_score.toFixed(1)} · avg risk {detail.average_risk_score.toFixed(1)} ·{' '}
                {detail.history_days} days of history
              </Typography>
              <Typography variant="body2">Offer: {detail.offer_name ?? '—'}</Typography>
              <Typography variant="body2">
                Latest triggered rules: {detail.triggered_rules_latest.join(', ') || 'none'}
              </Typography>

              <Typography variant="subtitle2" sx={{ mt: 2 }}>
                Score history ({historyChartData.length} days)
              </Typography>
              <TableContainer sx={{ maxHeight: 320 }}>
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
        </Box>
      </Drawer>
    </Stack>
  );
}
