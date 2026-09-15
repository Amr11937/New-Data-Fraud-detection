import { useState } from 'react';
import { Alert, Collapse, IconButton, Stack } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import { useWebSocket } from '@/hooks/useWebSocket';

export function AlertBanner() {
  const { recentAlerts, clearAlerts } = useWebSocket();
  const [dismissed, setDismissed] = useState(false);

  const latest = recentAlerts[0];
  const show = !!latest && !dismissed;

  return (
    <Collapse in={show}>
      {latest && (
        <Alert
          severity={latest.decision === 'BLOCK' ? 'error' : 'warning'}
          onClose={() => setDismissed(true)}
          action={
            <IconButton
              size="small"
              onClick={() => {
                clearAlerts();
                setDismissed(true);
              }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          }
          sx={{ mb: 2 }}
        >
          <Stack direction="row" spacing={1} alignItems="baseline">
            <strong>{latest.decision}</strong>
            <span>
              subscriber {latest.subscriber_id} scored {latest.final_score?.toFixed(2)}
              {latest.triggered_rules ? ` (${latest.triggered_rules})` : ''}
            </span>
          </Stack>
        </Alert>
      )}
    </Collapse>
  );
}
