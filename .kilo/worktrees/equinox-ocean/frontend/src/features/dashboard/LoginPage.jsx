import {
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  IconButton,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GavelIcon from '@mui/icons-material/Gavel';
import GroupsIcon from '@mui/icons-material/Groups';
import ShieldIcon from '@mui/icons-material/Shield';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../auth/store';
import { useThemeMode } from '../../theme/ThemeModeContext';

const FEATURES = [
  {
    icon: <AutoAwesomeIcon />,
    title: 'Ask AI Legal Research',
    body: 'Semantic search across your indexed precedents with cited, plain-language answers.',
  },
  {
    icon: <FactCheckIcon />,
    title: 'Contract Risk Audits',
    body: 'Automated clause findings, obligation mapping, and risk-tiered recommendations.',
  },
  {
    icon: <GroupsIcon />,
    title: 'Multi-Agent Simulations',
    body: 'Adversarial plaintiff, defense, and judicial agents argue plausible outcomes.',
  },
  {
    icon: <ShieldIcon />,
    title: 'Enterprise Guardrails',
    body: 'PII redaction, injection quarantine, policy-as-code RBAC, and full audit telemetry.',
  },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const authenticate = useAuthStore((s) => s.authenticate);
  const { toggle, mode } = useThemeMode();
  const [authMode, setAuthMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [org, setOrg] = useState('');
  const [error, setError] = useState('');

  async function submit(e) {
    e.preventDefault();
    setError('');
    if (!email.trim()) {
      setError('Please enter a valid email address');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }
    try {
      await authenticate(
        authMode,
        authMode === 'register'
          ? { email: email.trim(), password, organization_name: org.trim() || 'Default Organization' }
          : { email: email.trim(), password },
      );
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
  }

  function fillDemoAdmin() {
    setEmail('admin@jurislab.dev');
    setPassword('ChangeMe#2026');
    setAuthMode('login');
    setError('');
  }

  const isDark = mode === 'dark';

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        bgcolor: 'background.default',
      }}
    >
      {/* Brand showcase panel */}
      <Box
        sx={{
          display: { xs: 'none', lg: 'flex' },
          width: '46%',
          flexDirection: 'column',
          justifyContent: 'space-between',
          p: 6,
          color: '#fff',
          background: isDark
            ? 'radial-gradient(120% 120% at 0% 0%, #1e1b4b 0%, #0e1230 45%, #0a0f1e 100%)'
            : 'radial-gradient(120% 120% at 0% 0%, #312e81 0%, #4338ca 40%, #1d4ed8 100%)',
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Box
            sx={{
              width: 42,
              height: 42,
              borderRadius: 2.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'rgba(255,255,255,0.14)',
              backdropFilter: 'blur(8px)',
              boxShadow: '0 8px 20px rgba(0,0,0,0.25)',
            }}
          >
            <GavelIcon sx={{ fontSize: 24 }} />
          </Box>
          <Box>
            <Typography variant="h6" fontWeight={800} sx={{ lineHeight: 1.1 }}>
              JurisLab
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.7, letterSpacing: '0.08em', fontWeight: 700 }}>
              LEGAL INTELLIGENCE PLATFORM
            </Typography>
          </Box>
        </Stack>

        <Box>
          <Chip
            icon={<ShieldIcon sx={{ fontSize: '15px !important' }} />}
            label="AI-powered · SOC-grade guardrails"
            size="small"
            sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: '#fff', fontWeight: 700, mb: 2 }}
          />
          <Typography variant="h3" fontWeight={800} sx={{ letterSpacing: '-0.03em', lineHeight: 1.15, maxWidth: 440 }}>
            Legal intelligence for modern attorneys.
          </Typography>
          <Typography sx={{ opacity: 0.85, mt: 1.5, maxWidth: 460, fontSize: '0.95rem' }}>
            Research, audit, and rehearse your matters in one workspace backed by local-first, private inference.
          </Typography>
        </Box>

        <Stack spacing={2.5}>
          {FEATURES.map((f) => (
            <Stack key={f.title} direction="row" spacing={1.75} alignItems="flex-start" sx={{ maxWidth: 460 }}>
              <Box
                sx={{
                  width: 38,
                  height: 38,
                  flexShrink: 0,
                  borderRadius: 2,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'rgba(255,255,255,0.12)',
                }}
              >
                {f.icon}
              </Box>
              <Box>
                <Typography variant="subtitle2" fontWeight={700}>
                  {f.title}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.78, lineHeight: 1.5, display: 'block' }}>
                  {f.body}
                </Typography>
              </Box>
            </Stack>
          ))}
        </Stack>

        <Typography variant="caption" sx={{ opacity: 0.6 }}>
          Educational sandbox for legal simulation &amp; review — not legal advice.
        </Typography>
      </Box>

      {/* Auth panel */}
      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', p: { xs: 2, sm: 4 } }}>
        <IconButton
          onClick={toggle}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          sx={{ position: 'absolute', top: 20, right: 20, border: '1px solid', borderColor: 'divider', color: 'text.secondary' }}
          size="small"
        >
          {isDark ? <Brightness7Icon /> : <Brightness4Icon />}
        </IconButton>

        <Paper
          elevation={0}
          sx={{
            width: 420,
            maxWidth: '100%',
            p: { xs: 3, sm: 4.5 },
            borderRadius: 4,
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="h5" fontWeight={800} sx={{ letterSpacing: '-0.02em' }}>
              {authMode === 'login' ? 'Welcome back' : 'Create your account'}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {authMode === 'login'
                ? 'Sign in to your JurisLab workspace.'
                : 'Start a private legal intelligence workspace.'}
            </Typography>
          </Box>

          <Button
            size="small"
            variant="outlined"
            fullWidth
            onClick={fillDemoAdmin}
            sx={{ fontSize: '0.78rem', textTransform: 'none', borderRadius: 2, mb: 2.5, py: 1 }}
          >
            Use Demo Admin (admin@jurislab.dev)
          </Button>

          <form onSubmit={submit}>
            <TextField
              label="Email"
              fullWidth
              margin="dense"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              sx={{ mb: 1.5 }}
            />
            <TextField
              label="Password"
              type="password"
              fullWidth
              margin="dense"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helperText={authMode === 'register' ? 'Minimum 8 characters' : ''}
              autoComplete={authMode === 'register' ? 'new-password' : 'current-password'}
              sx={{ mb: 1.5 }}
            />
            {authMode === 'register' && (
              <TextField
                label="Organization name"
                fullWidth
                margin="dense"
                value={org}
                placeholder="Default Organization"
                onChange={(e) => setOrg(e.target.value)}
                sx={{ mb: 1.5 }}
              />
            )}

            {error && <Alert severity="error" sx={{ mt: 1, mb: 1 }}>{error}</Alert>}

            <Button type="submit" variant="contained" size="large" fullWidth sx={{ mt: 2.5, py: 1.3, borderRadius: 2 }}>
              {authMode === 'login' ? 'Sign in' : 'Create account'}
            </Button>
          </form>

          <Divider sx={{ my: 2.5 }} />

          <Button
            fullWidth
            onClick={() => {
              setAuthMode(authMode === 'login' ? 'register' : 'login');
              setError('');
            }}
            sx={{ textTransform: 'none', color: 'text.secondary' }}
          >
            {authMode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
          </Button>
        </Paper>
      </Box>
    </Box>
  );
}