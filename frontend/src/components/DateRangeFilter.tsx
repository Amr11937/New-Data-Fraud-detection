import { useMemo } from 'react';
import { Box, Button, ButtonGroup, Stack, Tooltip, Typography } from '@mui/material';
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

type DayCounts = { subscriber: number; package: number };
type DayWithDataProps = PickersDayProps<Dayjs> & { dataDates: Map<string, DayCounts> };

// Green = subscriber dataset, blue = per-package dataset. A date in both is green with a blue dot.
function HighlightedDay(props: DayWithDataProps) {
  const { dataDates, day, outsideCurrentMonth, ...other } = props;
  const counts = outsideCurrentMonth ? undefined : dataDates.get(day.format('YYYY-MM-DD'));
  const hasSubscriber = !!counts && counts.subscriber > 0;
  const hasPackage = !!counts && counts.package > 0;

  const dayEl = (
    <PickersDay
      {...other}
      day={day}
      outsideCurrentMonth={outsideCurrentMonth}
      sx={
        hasSubscriber || hasPackage
          ? {
              bgcolor: hasSubscriber ? 'success.main' : 'primary.main',
              color: hasSubscriber ? 'success.contrastText' : 'primary.contrastText',
              fontWeight: 700,
              position: 'relative',
              '&:hover, &:focus': { bgcolor: hasSubscriber ? 'success.dark' : 'primary.dark' },
              ...(hasSubscriber &&
                hasPackage && {
                  '&::after': {
                    content: '""',
                    position: 'absolute',
                    bottom: 3,
                    left: '50%',
                    width: 5,
                    height: 5,
                    ml: '-2.5px',
                    borderRadius: '50%',
                    bgcolor: 'primary.light',
                    border: '1px solid #fff',
                  },
                }),
            }
          : undefined
      }
    />
  );

  if (!counts || (!hasSubscriber && !hasPackage)) return dayEl;

  const lines = [
    hasSubscriber ? `Subscriber data: ${counts.subscriber.toLocaleString()} records` : null,
    hasPackage ? `Package data: ${counts.package.toLocaleString()} records` : null,
  ].filter(Boolean);

  return (
    <Tooltip title={<>{lines.map((l) => <div key={l as string}>{l}</div>)}</>} arrow>
      {dayEl}
    </Tooltip>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <Stack direction="row" spacing={0.5} alignItems="center">
      <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: color }} />
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Stack>
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
    const map = new Map<string, DayCounts>();
    calendarData?.dates.forEach((d) => map.set(d.date, { subscriber: d.record_count, package: d.package_record_count ?? 0 }));
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
      <LegendDot color="success.main" label="Subscriber data" />
      <LegendDot color="primary.main" label="Package data" />
    </Stack>
  );
}
