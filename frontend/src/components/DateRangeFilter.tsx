import { Button, ButtonGroup, Stack, TextField } from '@mui/material';
import dayjs from 'dayjs';
import type { DateRange } from '@/types';

const PRESETS: { label: string; days: number | null }[] = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: 'All', days: null },
];

export function DateRangeFilter({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
}) {
  const applyPreset = (days: number | null) => {
    if (days === null) {
      onChange({ dateFrom: null, dateTo: null });
      return;
    }
    const dateTo = dayjs().format('YYYY-MM-DD');
    const dateFrom = dayjs().subtract(days - 1, 'day').format('YYYY-MM-DD');
    onChange({ dateFrom, dateTo });
  };

  return (
    <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
      <TextField
        label="From"
        type="date"
        size="small"
        value={value.dateFrom ?? ''}
        onChange={(e) => onChange({ ...value, dateFrom: e.target.value || null })}
        InputLabelProps={{ shrink: true }}
      />
      <TextField
        label="To"
        type="date"
        size="small"
        value={value.dateTo ?? ''}
        onChange={(e) => onChange({ ...value, dateTo: e.target.value || null })}
        InputLabelProps={{ shrink: true }}
      />
      <ButtonGroup size="small" variant="outlined">
        {PRESETS.map((p) => (
          <Button key={p.label} onClick={() => applyPreset(p.days)}>
            {p.label}
          </Button>
        ))}
      </ButtonGroup>
    </Stack>
  );
}
