import { Card, CardContent, Chip, Grid, Stack, Typography } from '@mui/material';
import { useSystemHealth } from '@/hooks/useDashboard';

export function SystemHealthPage() {
  const { data, isLoading } = useSystemHealth();

  return (
    <Stack spacing={3}>
      <Typography variant="h6">System health</Typography>
      <Typography variant="body2" color="text.secondary">
        Refreshes every 15 seconds.
      </Typography>

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Database
              </Typography>
              <Chip
                sx={{ mt: 1 }}
                label={isLoading ? '…' : data?.database ?? 'unknown'}
                color={data?.database === 'connected' ? 'success' : 'error'}
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Model version
              </Typography>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {data?.model_version ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Active WebSocket connections
              </Typography>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {data?.websocket_connections ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Latest ingested session date
              </Typography>
              <Typography variant="h6" sx={{ mt: 1 }}>
                {data?.latest_session_date ?? '—'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Card variant="outlined">
        <CardContent>
          <Typography variant="body2" color="text.secondary">
            Rule engine: {data?.rule_engine_active_rules ?? '—'} active rules loaded from
            app/config/rules.yaml.
          </Typography>
        </CardContent>
      </Card>
    </Stack>
  );
}
