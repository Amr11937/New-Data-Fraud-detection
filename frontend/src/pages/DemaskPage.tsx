import { useEffect, useState } from 'react';
import type { AxiosProgressEvent } from 'axios';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DownloadIcon from '@mui/icons-material/Download';

import { fetchEncryptionMethods, runEncryption, runMapping, type DemaskResult } from '@/services/demaskApi';
import type { DemaskMethod } from '@/types';

function FilePickerField({
  label,
  helper,
  file,
  onChange,
}: {
  label: string;
  helper: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <Stack spacing={0.5}>
      <Typography variant="body2" fontWeight={600}>
        {label}
      </Typography>
      <Button
        component="label"
        variant="outlined"
        startIcon={<UploadFileIcon />}
        sx={{ justifyContent: 'flex-start' }}
      >
        {file ? file.name : 'Choose file'}
        <input
          type="file"
          accept=".csv"
          hidden
          onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        />
      </Button>
      <Typography variant="caption" color="text.secondary">
        {helper}
      </Typography>
    </Stack>
  );
}

function ResultCard({ result, onReset }: { result: DemaskResult; onReset: () => void }) {
  const handleDownload = () => {
    const url = URL.createObjectURL(result.blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = result.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle1" fontWeight={700} color="success.main" gutterBottom>
          Processing complete
        </Typography>
        <Table size="small">
          <TableBody>
            <TableRow>
              <TableCell>Total records</TableCell>
              <TableCell align="right">{result.stats.total.toLocaleString()}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Processed</TableCell>
              <TableCell align="right">{result.stats.processed.toLocaleString()}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Unmapped / unprocessed</TableCell>
              <TableCell align="right">{result.stats.unprocessed.toLocaleString()}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Errors</TableCell>
              <TableCell align="right">{result.stats.errors.toLocaleString()}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <Stack direction="row" spacing={2} justifyContent="space-between" sx={{ mt: 3 }}>
          <Button variant="outlined" onClick={onReset}>
            Process another file
          </Button>
          <Button variant="contained" startIcon={<DownloadIcon />} onClick={handleDownload}>
            Download {result.filename}
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

export function DemaskPage() {
  const [method, setMethod] = useState<DemaskMethod>('mapping');
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DemaskResult | null>(null);

  // Mapping form state
  const [inputFile, setInputFile] = useState<File | null>(null);
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [inputIdCol, setInputIdCol] = useState('subscriber_id');
  const [mappingMaskedCol, setMappingMaskedCol] = useState('masked_subscriber_id');
  const [mappingOriginalCol, setMappingOriginalCol] = useState('original_subscriber_id');

  // Encryption form state
  const [encInputFile, setEncInputFile] = useState<File | null>(null);
  const [encIdCol, setEncIdCol] = useState('subscriber_id');
  const [encMethod, setEncMethod] = useState('');
  const [encMethods, setEncMethods] = useState<string[]>([]);
  const [encConfigured, setEncConfigured] = useState(false);

  useEffect(() => {
    if (method !== 'encryption' || encMethods.length > 0) return;
    fetchEncryptionMethods()
      .then((data) => {
        setEncMethods(data.methods);
        setEncConfigured(data.configured);
        setEncMethod(data.default ?? data.methods[0] ?? '');
      })
      .catch(() => {
        setEncMethods([]);
        setEncConfigured(false);
      });
  }, [method, encMethods.length]);

  const handleProgress = (event: AxiosProgressEvent) => {
    if (event.total) setProgress(Math.round((event.loaded / event.total) * 100));
  };

  const reset = () => {
    setResult(null);
    setError(null);
    setProgress(null);
  };

  const submitMapping = async () => {
    if (!inputFile || !mappingFile || !inputIdCol || !mappingMaskedCol || !mappingOriginalCol) {
      setError('Please select both CSV files and fill in all column names.');
      return;
    }
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      const res = await runMapping(
        { inputFile, mappingFile, inputIdCol, mappingMaskedCol, mappingOriginalCol },
        handleProgress
      );
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setProgress(null);
    }
  };

  const submitEncryption = async () => {
    if (!encInputFile || !encIdCol || !encMethod) {
      setError('Please select the input CSV, subscriber ID column, and encryption method.');
      return;
    }
    setError(null);
    setResult(null);
    setProgress(0);
    try {
      const res = await runEncryption(
        { inputFile: encInputFile, subscriberIdCol: encIdCol, encryptionMethod: encMethod },
        handleProgress
      );
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setProgress(null);
    }
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h6">Demask</Typography>
        <Typography variant="body2" color="text.secondary">
          Batch-convert masked subscriber IDs back to originals, via a mapping CSV or a
          decryption provider.
        </Typography>
      </Box>

      <Card variant="outlined">
        <CardContent>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Processing method
          </Typography>
          <ToggleButtonGroup
            exclusive
            value={method}
            onChange={(_, value) => {
              if (value) {
                setMethod(value);
                reset();
              }
            }}
          >
            <ToggleButton value="mapping">Mapping</ToggleButton>
            <ToggleButton value="encryption">Encryption</ToggleButton>
          </ToggleButtonGroup>
        </CardContent>
      </Card>

      {method === 'mapping' && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="body2" fontWeight={600} gutterBottom>
              Upload files
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FilePickerField
                  label="Input CSV"
                  helper="CSV file containing masked subscriber IDs"
                  file={inputFile}
                  onChange={setInputFile}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <FilePickerField
                  label="Mapping CSV"
                  helper="CSV file with masked -> original ID mapping"
                  file={mappingFile}
                  onChange={setMappingFile}
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  size="small"
                  label="Input subscriber ID column"
                  value={inputIdCol}
                  onChange={(e) => setInputIdCol(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  size="small"
                  label="Mapping masked ID column"
                  value={mappingMaskedCol}
                  onChange={(e) => setMappingMaskedCol(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={4}>
                <TextField
                  fullWidth
                  size="small"
                  label="Mapping original ID column"
                  value={mappingOriginalCol}
                  onChange={(e) => setMappingOriginalCol(e.target.value)}
                />
              </Grid>
            </Grid>
            <Stack direction="row" justifyContent="flex-end" sx={{ mt: 2 }}>
              <Button variant="contained" onClick={submitMapping} disabled={progress !== null}>
                Process CSV
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}

      {method === 'encryption' && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="body2" fontWeight={600} gutterBottom>
              Upload file
            </Typography>
            <Alert severity={encConfigured ? 'success' : 'info'} sx={{ mb: 2 }}>
              {encConfigured
                ? `Encryption provider ready. Active provider defaults to "${encMethod}".`
                : 'No ENCRYPTION_KEY configured on the backend -- set it in backend/.env to enable decryption.'}
            </Alert>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <FilePickerField
                  label="Input CSV"
                  helper="CSV file containing encrypted subscriber IDs"
                  file={encInputFile}
                  onChange={setEncInputFile}
                />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  fullWidth
                  size="small"
                  label="Subscriber ID column"
                  value={encIdCol}
                  onChange={(e) => setEncIdCol(e.target.value)}
                />
              </Grid>
              <Grid item xs={12} sm={3}>
                <TextField
                  fullWidth
                  select
                  size="small"
                  label="Encryption method"
                  value={encMethod}
                  disabled={encMethods.length === 0}
                  onChange={(e) => setEncMethod(e.target.value)}
                >
                  {encMethods.length === 0 && <MenuItem value="">No providers configured</MenuItem>}
                  {encMethods.map((m) => (
                    <MenuItem key={m} value={m}>
                      {m}
                    </MenuItem>
                  ))}
                </TextField>
              </Grid>
            </Grid>
            <Stack direction="row" justifyContent="flex-end" sx={{ mt: 2 }}>
              <Button
                variant="contained"
                onClick={submitEncryption}
                disabled={progress !== null || encMethods.length === 0}
              >
                Process CSV
              </Button>
            </Stack>
          </CardContent>
        </Card>
      )}

      {progress !== null && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="body2" gutterBottom>
              Processing…
            </Typography>
            <LinearProgress variant={progress > 0 ? 'determinate' : 'indeterminate'} value={progress} />
          </CardContent>
        </Card>
      )}

      {error && <Alert severity="error">{error}</Alert>}

      {result && <ResultCard result={result} onReset={reset} />}
    </Stack>
  );
}
