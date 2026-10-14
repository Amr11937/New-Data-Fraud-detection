import { Card, CardContent, Stack, Typography } from '@mui/material';
import type { ReactNode } from 'react';

export function KpiCard({
  label,
  value,
  subtext,
  icon,
  accent,
}: {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: ReactNode;
  accent?: string;
}) {
  return (
    <Card
      variant="outlined"
      sx={{ height: '100%', ...(accent && { borderColor: accent, borderWidth: 2 }) }}
    >
      <CardContent>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="body2" color="text.secondary">
            {label}
          </Typography>
          {icon}
        </Stack>
        <Typography variant="h4" sx={{ mt: 1, fontWeight: 500, ...(accent && { color: accent }) }}>
          {value}
        </Typography>
        {subtext && (
          <Typography variant="caption" color="text.secondary">
            {subtext}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}
