import { useMemo } from 'react';
import { Button, ButtonGroup, Stack, Tooltip } from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { PickersDay, type PickersDayProps } from '@mui/x-date-pickers/PickersDay';
import dayjs, { type Dayjs } from 'dayjs';
import { useCalendarDates } from '@/hooks/useDashboard';
import type { DateRange } from '@/types';

const PRESETS: { label: string; days: number | null }[] = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: 'All', days: null },
];

type DayWithDataProps = PickersDayProps<Dayjs> & { dataDates: Map<string, number> };

function HighlightedDay(props: DayWithDataProps) {
  const { dataDates, day, outsideCurrentMonth, ...other } = props;
  const recordCount = outsideCurrentMonth ? undefined : dataDates.get(day.format('YYYY-MM-DD'));
  const hasData = recordCount !== undefined;

  const dayEl = (
    <PickersDay
      {...other}
      day={day}
      outsideCurrentMonth={outsideCurrentMonth}
      sx={
        hasData
          ? {
              bgcolor: 'success.main',
              color: 'success.contrastText',
              fontWeight: 700,
              '&:hover, &:focus': { bgcolor: 'success.dark' },
            }
          : undefined
      }
    />
  );

  if (!hasData) return dayEl;

  return (
    <Tooltip title={`${recordCount.toLocaleString()} record${recordCount === 1 ? '' : 's'}`} arrow>
      {dayEl}
    </Tooltip>
  );
}

export function DateRangeFilter({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (range: DateRange) => void;
}) {
  const { data: calendarData } = useCalendarDates();

  const dataDates = useMemo(() => {
    const map = new Map<string, number>();
    calendarData?.dates.forEach((d) => map.set(d.date, d.record_count));
    return map;
  }, [calendarData]);

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
      <DatePicker
        label="From"
        value={value.dateFrom ? dayjs(value.dateFrom) : null}
        onChange={(newValue) => onChange({ ...value, dateFrom: newValue ? newValue.format('YYYY-MM-DD') : null })}
        slots={{ day: HighlightedDay as any }}
        slotProps={{ textField: { size: 'small' }, day: { dataDates } as any }}
      />
      <DatePicker
        label="To"
        value={value.dateTo ? dayjs(value.dateTo) : null}
        onChange={(newValue) => onChange({ ...value, dateTo: newValue ? newValue.format('YYYY-MM-DD') : null })}
        slots={{ day: HighlightedDay as any }}
        slotProps={{ textField: { size: 'small' }, day: { dataDates } as any }}
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
