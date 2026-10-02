import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { keyframes } from '@mui/system';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import RadarIcon from '@mui/icons-material/Radar';
import BoltIcon from '@mui/icons-material/Bolt';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { useAuth } from '@/auth/AuthContext';
import logoFull from '@/assets/logo-full.png';

const float = keyframes`
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(30px, -40px, 0) scale(1.08); }
`;
const sweep = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;
const rise = keyframes`
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
`;

const FEATURES = [
  { icon: <RadarIcon />, title: 'Real-time detection', text: 'Live fraud alerts streamed as subscriber sessions are scored.' },
  { icon: <PsychologyIcon />, title: 'Ensemble AI scoring', text: 'Isolation Forest plus calibrated rules, explained per subscriber.' },
  { icon: <BoltIcon />, title: 'Act in seconds', text: 'Triage high-risk accounts and export evidence in a click.' },
];

function LogoCard({ width }: { width: number }) {
  return (
    <Box sx={{ position: 'relative', width, maxWidth: '100%', lineHeight: 0 }}>
      {/* soft colour wash behind the logo: blue on the left, warm amber on the right */}
      <Box
        sx={{
          position: 'absolute',
          inset: '-18% -22% -14% -22%',
          background: [
            'radial-gradient(ellipse 46% 52% at 32% 44%, rgba(59,130,246,0.55) 0%, rgba(59,130,246,0) 100%)',
            'radial-gradient(ellipse 30% 40% at 76% 48%, rgba(245,166,66,0.38) 0%, rgba(245,166,66,0) 100%)',
          ].join(','),
          filter: 'blur(26px)',
          pointerEvents: 'none',
        }}
      />
      <Box
        component="img"
        src={logoFull}
        alt="FraudVision AI"
        sx={{ position: 'relative', width: '100%', height: 'auto', display: 'block' }}
      />
    </Box>
  );
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={from} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.');
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', bgcolor: 'background.default', overflow: 'hidden' }}>
      {/* ---------- Brand panel ---------- */}
      <Box
        sx={{
          position: 'relative',
          flex: 1.1,
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: { md: 6, lg: 8 },
          overflow: 'hidden',
          background: 'linear-gradient(160deg, #0B1B3F 0%, #0A1128 55%, #160B33 100%)',
          borderRight: '1px solid rgba(148, 163, 184, 0.12)',
        }}
      >
        {/* glowing orbs */}
        <Box sx={{ position: 'absolute', top: -120, left: -100, width: 420, height: 420, borderRadius: '50%', background: 'radial-gradient(circle, rgba(37,99,235,0.55), transparent 70%)', filter: 'blur(20px)', animation: `${float} 14s ease-in-out infinite` }} />
        <Box sx={{ position: 'absolute', bottom: -140, right: -80, width: 460, height: 460, borderRadius: '50%', background: 'radial-gradient(circle, rgba(124,58,237,0.5), transparent 70%)', filter: 'blur(24px)', animation: `${float} 18s ease-in-out infinite reverse` }} />
        {/* grid texture */}
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            backgroundImage:
              'linear-gradient(rgba(148,163,184,0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.07) 1px, transparent 1px)',
            backgroundSize: '44px 44px',
            maskImage: 'radial-gradient(ellipse at center, #000 30%, transparent 75%)',
            WebkitMaskImage: 'radial-gradient(ellipse at center, #000 30%, transparent 75%)',
          }}
        />
        {/* radar sweep */}
        <Box
          sx={{
            position: 'absolute',
            right: -160,
            top: '50%',
            width: 520,
            height: 520,
            mt: '-260px',
            borderRadius: '50%',
            border: '1px solid rgba(96,165,250,0.25)',
            boxShadow: 'inset 0 0 0 80px rgba(96,165,250,0.03), inset 0 0 0 81px rgba(96,165,250,0.18), inset 0 0 0 160px rgba(96,165,250,0.03), inset 0 0 0 161px rgba(96,165,250,0.15)',
            opacity: 0.8,
            '&::after': {
              content: '""',
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              background: 'conic-gradient(from 0deg, rgba(96,165,250,0.35), transparent 28%)',
              animation: `${sweep} 7s linear infinite`,
            },
          }}
        />

        <Box sx={{ position: 'relative' }}>
          <LogoCard width={400} />
        </Box>

        <Box sx={{ position: 'relative', maxWidth: 520 }}>
          <Typography
            variant="h3"
            sx={{
              fontWeight: 700,
              letterSpacing: '-0.03em',
              lineHeight: 1.1,
              mb: 2,
              background: 'linear-gradient(90deg, #fff 0%, #93C5FD 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            See fraud before it costs you.
          </Typography>
          <Typography sx={{ color: 'rgba(226,232,240,0.72)', fontSize: 17, mb: 5 }}>
            AI-driven risk intelligence for telecom subscribers, built for fraud analysts who need answers now.
          </Typography>
          <Stack spacing={2.5}>
            {FEATURES.map((f, i) => (
              <Stack
                key={f.title}
                direction="row"
                spacing={2}
                alignItems="flex-start"
                sx={{ animation: `${rise} 0.7s ease both`, animationDelay: `${0.15 + i * 0.12}s` }}
              >
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    flexShrink: 0,
                    borderRadius: 1.5,
                    display: 'grid',
                    placeItems: 'center',
                    color: '#93C5FD',
                    bgcolor: 'rgba(37,99,235,0.18)',
                    border: '1px solid rgba(96,165,250,0.3)',
                  }}
                >
                  {f.icon}
                </Box>
                <Box>
                  <Typography sx={{ fontWeight: 600 }}>{f.title}</Typography>
                  <Typography variant="body2" sx={{ color: 'rgba(226,232,240,0.6)' }}>
                    {f.text}
                  </Typography>
                </Box>
              </Stack>
            ))}
          </Stack>
        </Box>

        <Typography variant="caption" sx={{ position: 'relative', color: 'rgba(226,232,240,0.45)' }}>
          © {new Date().getFullYear()} FraudVision AI. Authorized personnel only.
        </Typography>
      </Box>

      {/* ---------- Sign-in panel ---------- */}
      <Box
        sx={{
          position: 'relative',
          flex: 1,
          minWidth: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
          background: { xs: 'linear-gradient(160deg, #0B1B3F 0%, #060D1A 60%)', md: 'transparent' },
        }}
      >
        <Box
          component="form"
          onSubmit={onSubmit}
          noValidate
          sx={{
            width: '100%',
            maxWidth: 420,
            p: { xs: 3, sm: 5 },
            borderRadius: 4,
            bgcolor: 'rgba(15, 23, 42, 0.72)',
            backdropFilter: 'blur(14px)',
            border: '1px solid rgba(148, 163, 184, 0.16)',
            boxShadow: '0 24px 60px rgba(0,0,0,0.45), 0 0 0 1px rgba(37,99,235,0.08)',
            animation: `${rise} 0.6s ease both`,
          }}
        >
          <Stack alignItems="center" spacing={1.5} sx={{ mb: 4, textAlign: 'center' }}>
            <Box sx={{ display: { xs: 'block', md: 'none' } }}>
              <LogoCard width={260} />
            </Box>
            <Typography variant="h4" sx={{ fontWeight: 700, letterSpacing: '-0.02em' }}>
              Welcome back
            </Typography>
            <Typography sx={{ color: 'text.secondary' }}>Sign in to FraudVision AI</Typography>
          </Stack>

          {error && (
            <Alert severity="error" variant="outlined" sx={{ mb: 2.5 }} role="alert">
              {error}
            </Alert>
          )}

          <Stack spacing={2.5}>
            <TextField
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              required
              fullWidth
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <PersonOutlineIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              fullWidth
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <LockOutlinedIcon fontSize="small" />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      onClick={() => setShowPassword((s) => !s)}
                      onMouseDown={(e) => e.preventDefault()}
                      edge="end"
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              disabled={submitting || !username.trim() || !password}
              sx={{
                py: 1.5,
                fontWeight: 700,
                textTransform: 'none',
                fontSize: 16,
                background: 'linear-gradient(90deg, #2563EB 0%, #7C3AED 100%)',
                boxShadow: '0 10px 26px rgba(37,99,235,0.4)',
                '&:hover': { background: 'linear-gradient(90deg, #1D4ED8 0%, #6D28D9 100%)' },
                '&.Mui-disabled': { opacity: 0.5, color: '#fff' },
              }}
            >
              {submitting ? <CircularProgress size={24} color="inherit" /> : 'Sign in'}
            </Button>
          </Stack>

          <Typography variant="caption" sx={{ display: 'block', mt: 3, textAlign: 'center', color: 'text.secondary' }}>
            Authorized personnel only.
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
