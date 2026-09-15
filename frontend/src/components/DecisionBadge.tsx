import { Chip } from '@mui/material';
import type { Decision } from '@/types';

const COLORS: Record<Decision, 'success' | 'warning' | 'error'> = {
  ALLOW: 'success',
  REVIEW: 'warning',
  BLOCK: 'error',
};

export function DecisionBadge({ decision }: { decision: Decision | null | undefined }) {
  if (!decision) return <Chip label="N/A" size="small" variant="outlined" />;
  return <Chip label={decision} color={COLORS[decision]} size="small" />;
}
