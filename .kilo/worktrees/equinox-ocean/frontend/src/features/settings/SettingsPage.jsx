import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  Switch,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import BusinessIcon from '@mui/icons-material/Business';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import GroupIcon from '@mui/icons-material/Group';
import LightModeIcon from '@mui/icons-material/LightMode';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import PersonIcon from '@mui/icons-material/Person';
import RefreshIcon from '@mui/icons-material/Refresh';
import SaveIcon from '@mui/icons-material/Save';
import SecurityIcon from '@mui/icons-material/Security';
import ShieldIcon from '@mui/icons-material/Shield';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SpeedIcon from '@mui/icons-material/Speed';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { useAuthStore } from '../../auth/store';
import { useThemeMode } from '../../theme/ThemeModeContext';

const JURISDICTIONS = ['Singapore', 'US-Federal', 'Delaware', 'California', 'New York', 'UK', 'EU'];
const DOMAINS = ['corporate', 'employment', 'commercial', 'intellectual_property', 'compliance', 'landlord_tenant'];

export default function SettingsPage() {
  const theme = useTheme();
  const { mode, toggle: toggleTheme } = useThemeMode();
  const authUser = useAuthStore((s) => s.user);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toastMsg, setToastMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  // User Profile State
  const [fullName, setFullName] = useState(authUser?.full_name || '');
  const [defaultJurisdiction, setDefaultJurisdiction] = useState('Singapore');
  const [defaultDomain, setDefaultDomain] = useState('corporate');
  const [preferredModel, setPreferredModel] = useState('gemma4:latest');
  const [alertSimulation, setAlertSimulation] = useState(true);
  const [alertOcr, setAlertOcr] = useState(true);
  const [alertSecurity, setAlertSecurity] = useState(true);

  // Organization State
  const [org, setOrg] = useState(null);
  const [orgName, setOrgName] = useState('');
  const [autoPiiRedaction, setAutoPiiRedaction] = useState(true);
  const [quarantineInjections, setQuarantineInjections] = useState(true);
  const [strictGuardrails, setStrictGuardrails] = useState(true);
  const [retentionDays, setRetentionDays] = useState('365');

  // AI & Ops Infrastructure State
  const [opsData, setOpsData] = useState(null);

  // Team & Users State
  const [users, setUsers] = useState([]);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviting, setInviting] = useState(false);

  // Load live data
  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const [meRes, orgRes, readyRes] = await Promise.allSettled([
        fetchMe(),
        api('/users/organization'),
        api('/ready'),
      ]);

      if (meRes.status === 'fulfilled' && meRes.value) {
        const u = meRes.value;
        setFullName(u.full_name || '');
        if (u.profile) {
          if (u.profile.default_jurisdiction) setDefaultJurisdiction(u.profile.default_jurisdiction);
          if (u.profile.default_domain) setDefaultDomain(u.profile.default_domain);
          if (u.profile.alert_simulation !== undefined) setAlertSimulation(u.profile.alert_simulation);
          if (u.profile.alert_ocr !== undefined) setAlertOcr(u.profile.alert_ocr);
          if (u.profile.alert_security !== undefined) setAlertSecurity(u.profile.alert_security);
        }
      }

      if (orgRes.status === 'fulfilled' && orgRes.value) {
        const o = orgRes.value;
        setOrg(o);
        setOrgName(o.name || '');
        if (o.settings) {
          if (o.settings.auto_pii_redaction !== undefined) setAutoPiiRedaction(o.settings.auto_pii_redaction);
          if (o.settings.quarantine_injections !== undefined) setQuarantineInjections(o.settings.quarantine_injections);
          if (o.settings.strict_guardrails !== undefined) setStrictGuardrails(o.settings.strict_guardrails);
          if (o.settings.retention_days) setRetentionDays(String(o.settings.retention_days));
        }
      }

      if (readyRes.status === 'fulfilled' && readyRes.value) {
        setOpsData(readyRes.value);
        if (readyRes.value.ask_llm_model) {
          setPreferredModel(readyRes.value.ask_llm_model);
        }
      }

      // Try loading team if user is admin
      try {
        const usersRes = await api('/users');
        setUsers(usersRes.users || []);
      } catch {
        // non-admin member will not have permission, ignore
      }
    } catch (err) {
      setErrorMsg(`Failed loading settings: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [fetchMe]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Copy helper
  function copyToClipboard(text, label = 'Copied') {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setToastMsg(`${label} copied to clipboard`);
  }

  // Save Profile Preferences
  async function handleSaveProfile(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        full_name: fullName,
        profile: {
          default_jurisdiction: defaultJurisdiction,
          default_domain: defaultDomain,
          alert_simulation: alertSimulation,
          alert_ocr: alertOcr,
          alert_security: alertSecurity,
        },
      };
      await api('/auth/profile', { method: 'PATCH', body: payload });
      await fetchMe();
      setToastMsg('Profile & preferences saved successfully');
    } catch (err) {
      setErrorMsg(`Failed saving profile: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveModelPreference() {
    setSaving(true);
    try {
      await api('/config', {
        method: 'PATCH',
        body: { ask_llm_model: preferredModel },
      });
      setToastMsg('Preferred LLM model saved');
      setErrorMsg('');
    } catch (err) {
      setErrorMsg(`Failed saving model preference: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  // Save Organization Governance
  async function handleSaveOrg(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        name: orgName.trim(),
        settings: {
          auto_pii_redaction: autoPiiRedaction,
          quarantine_injections: quarantineInjections,
          strict_guardrails: strictGuardrails,
          retention_days: Number(retentionDays),
        },
      };
      const updated = await api('/users/organization', { method: 'PATCH', body: payload });
      setOrg(updated);
      await fetchMe();
      setToastMsg('Organization governance policies updated');
    } catch (err) {
      setErrorMsg(`Failed saving organization: ${err.message}`);
    } finally {
      setSaving(false);
    }
  }

  // Invite Team Member
  async function handleInviteUser(e) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      await api('/users/invite', { method: 'POST', body: { email: inviteEmail.trim() } });
      setToastMsg(`Invitation dispatched to ${inviteEmail}`);
      setInviteEmail('');
      setShowInviteModal(false);
      const usersRes = await api('/users');
      setUsers(usersRes.users || []);
    } catch (err) {
      setErrorMsg(`Failed inviting user: ${err.message}`);
    } finally {
      setInviting(false);
    }
  }

  const userRole = authUser?.platform_role || 'member';
  const isAdmin = userRole === 'org_admin' || userRole === 'platform_admin';
  const organizationName = org?.name || authUser?.organization?.name || 'JurisLab Organization';

  return (
    <Box sx={{ width: '100%', pb: 4 }}>
      {/* Streamlined Settings Bar */}
      <Paper
        elevation={0}
        variant="outlined"
        sx={{
          p: 1.5,
          px: 2,
          mb: 2,
          borderRadius: 2.5,
          bgcolor: 'background.paper',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1.5,
        }}
      >
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography variant="subtitle1" component="h1" fontWeight={800} sx={{ letterSpacing: '-0.01em' }}>
            Settings & Administration
          </Typography>
          <Chip icon={<CheckCircleIcon color="success" />} label="System Operational" size="small" variant="outlined" sx={{ height: 24, fontSize: '0.72rem' }} />
          <Chip label={userRole.toUpperCase()} size="small" color="primary" sx={{ height: 24, fontSize: '0.72rem', fontWeight: 600 }} />
        </Stack>

        <Button
          variant="outlined"
          size="small"
          startIcon={<RefreshIcon />}
          onClick={loadData}
          disabled={loading}
          sx={{ borderRadius: 2, textTransform: 'none' }}
        >
          Refresh
        </Button>
      </Paper>

      {/* Global Errors */}
      {errorMsg && (
        <Alert severity="error" onClose={() => setErrorMsg('')} sx={{ mb: 3, borderRadius: 2 }}>
          {errorMsg}
        </Alert>
      )}

      {/* Navigation Tabs */}
      <Paper elevation={0} variant="outlined" sx={{ mb: 3, borderRadius: 3, overflow: 'hidden' }}>
        <Tabs
          value={activeTab}
          onChange={(_, val) => setActiveTab(val)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ px: 2, borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}
        >
          <Tab icon={<PersonIcon />} iconPosition="start" label="Profile & Preferences" />
          <Tab icon={<BusinessIcon />} iconPosition="start" label="Organization & Governance" />
          <Tab icon={<SmartToyIcon />} iconPosition="start" label="AI & OCR Infrastructure" />
          {isAdmin && <Tab icon={<GroupIcon />} iconPosition="start" label={`Team & Roles (${users.length})`} />}
        </Tabs>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}>
            <CircularProgress />
          </Box>
        ) : (
          <Box sx={{ p: { xs: 2, sm: 3 } }}>
            {/* TAB 0: User Profile & Preferences */}
            {activeTab === 0 && (
              <form onSubmit={handleSaveProfile}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                      <CardContent>
                        <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <PersonIcon color="primary" fontSize="small" /> Personal Identity
                        </Typography>
                        <Divider sx={{ my: 1.5 }} />

                        <Stack spacing={2.5}>
                          <TextField
                            label="Full Name"
                            fullWidth
                            size="small"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder="e.g. Elena Rostova"
                          />

                          <TextField
                            label="Email Address"
                            fullWidth
                            size="small"
                            value={authUser?.email || ''}
                            disabled
                            helperText="Managed by corporate single sign-on"
                          />

                          <TextField
                            label="User Identifier (ID)"
                            fullWidth
                            size="small"
                            value={authUser?.id || ''}
                            disabled
                            InputProps={{
                              endAdornment: (
                                <InputAdornment position="end">
                                  <IconButton size="small" onClick={() => copyToClipboard(authUser?.id, 'User ID')}>
                                    <ContentCopyIcon fontSize="small" />
                                  </IconButton>
                                </InputAdornment>
                              ),
                            }}
                          />
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                      <CardContent>
                        <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <SpeedIcon color="primary" fontSize="small" /> Practice Defaults
                        </Typography>
                        <Divider sx={{ my: 1.5 }} />

                        <Stack spacing={2.5}>
                          <FormControl fullWidth size="small">
                            <InputLabel>Primary Jurisdiction Preference</InputLabel>
                            <Select
                              value={defaultJurisdiction}
                              label="Primary Jurisdiction Preference"
                              onChange={(e) => setDefaultJurisdiction(e.target.value)}
                            >
                              {JURISDICTIONS.map((j) => (
                                <MenuItem key={j} value={j}>{j}</MenuItem>
                              ))}
                            </Select>
                          </FormControl>

                          <FormControl fullWidth size="small">
                            <InputLabel>Primary Legal Domain</InputLabel>
                            <Select
                              value={defaultDomain}
                              label="Primary Legal Domain"
                              onChange={(e) => setDefaultDomain(e.target.value)}
                            >
                              {DOMAINS.map((d) => (
                                <MenuItem key={d} value={d}>{d}</MenuItem>
                              ))}
                            </Select>
                          </FormControl>

                          <Box sx={{ pt: 1 }}>
                            <Typography variant="subtitle2" gutterBottom>
                              Interface Theme
                            </Typography>
                            <Stack direction="row" spacing={2} alignItems="center">
                              <Button
                                variant={mode === 'light' ? 'contained' : 'outlined'}
                                startIcon={<LightModeIcon />}
                                size="small"
                                onClick={mode === 'dark' ? toggleTheme : undefined}
                                sx={{ borderRadius: 2, textTransform: 'none' }}
                              >
                                Light
                              </Button>
                              <Button
                                variant={mode === 'dark' ? 'contained' : 'outlined'}
                                startIcon={<DarkModeIcon />}
                                size="small"
                                onClick={mode === 'light' ? toggleTheme : undefined}
                                sx={{ borderRadius: 2, textTransform: 'none' }}
                              >
                                Dark
                              </Button>
                            </Stack>
                          </Box>
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12}>
                    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5 }}>
                      <CardContent>
                        <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <ShieldIcon color="primary" fontSize="small" /> Notification & Alert Preferences
                        </Typography>
                        <Divider sx={{ my: 1.5 }} />

                        <Grid container spacing={2}>
                          <Grid item xs={12} sm={4}>
                            <FormControlLabel
                              control={<Switch checked={alertSimulation} onChange={(e) => setAlertSimulation(e.target.checked)} color="primary" />}
                              label="Simulation Turn Updates"
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              Notify when an AI participant produces a response
                            </Typography>
                          </Grid>
                          <Grid item xs={12} sm={4}>
                            <FormControlLabel
                              control={<Switch checked={alertOcr} onChange={(e) => setAlertOcr(e.target.checked)} color="primary" />}
                              label="OCR Ingestion Alerts"
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              Notify when document OCR & embeddings complete
                            </Typography>
                          </Grid>
                          <Grid item xs={12} sm={4}>
                            <FormControlLabel
                              control={<Switch checked={alertSecurity} onChange={(e) => setAlertSecurity(e.target.checked)} color="primary" />}
                              label="Security & Guardrail Alerts"
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              Alert on PII detection or injection quarantines
                            </Typography>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12}>
                    <Stack direction="row" justifyContent="flex-end">
                      <Button
                        type="submit"
                        variant="contained"
                        disabled={saving}
                        startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SaveIcon />}
                        sx={{ borderRadius: 2, px: 3, textTransform: 'none', fontWeight: 600 }}
                      >
                        {saving ? 'Saving...' : 'Save Profile Changes'}
                      </Button>
                    </Stack>
                  </Grid>
                </Grid>
              </form>
            )}

            {/* TAB 1: Organization & Governance */}
            {activeTab === 1 && (
              <form onSubmit={handleSaveOrg}>
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                      <CardContent>
                        <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <BusinessIcon color="primary" fontSize="small" /> Organization Identity
                        </Typography>
                        <Divider sx={{ my: 1.5 }} />

                        <Stack spacing={2.5}>
                          <TextField
                            label="Organization Name"
                            fullWidth
                            size="small"
                            value={orgName}
                            onChange={(e) => setOrgName(e.target.value)}
                            disabled={!isAdmin}
                            placeholder="e.g. Acme Corp Legal Department"
                          />

                          <TextField
                            label="Organization ID"
                            fullWidth
                            size="small"
                            value={org?.id || authUser?.organization_id || ''}
                            disabled
                            InputProps={{
                              endAdornment: (
                                <InputAdornment position="end">
                                  <IconButton size="small" onClick={() => copyToClipboard(org?.id, 'Organization ID')}>
                                    <ContentCopyIcon fontSize="small" />
                                  </IconButton>
                                </InputAdornment>
                              ),
                            }}
                          />

                          <Stack direction="row" spacing={2} alignItems="center">
                            <Typography variant="body2" color="text.secondary">Subscription Tier:</Typography>
                            <Chip label={(org?.subscription_tier || 'Free Developer').toUpperCase()} color="success" size="small" sx={{ fontWeight: 600 }} />
                          </Stack>
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                      <CardContent>
                        <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <SecurityIcon color="primary" fontSize="small" /> Document Quotas & Retention
                        </Typography>
                        <Divider sx={{ my: 1.5 }} />

                        <Stack spacing={2.5}>
                          <FormControl fullWidth size="small">
                            <InputLabel>Document Retention Period</InputLabel>
                            <Select
                              value={retentionDays}
                              label="Document Retention Period"
                              onChange={(e) => setRetentionDays(e.target.value)}
                              disabled={!isAdmin}
                            >
                              <MenuItem value="30">30 Days (Ephemeral)</MenuItem>
                              <MenuItem value="90">90 Days (Quarterly Audit)</MenuItem>
                              <MenuItem value="365">1 Year (Standard Legal)</MenuItem>
                              <MenuItem value="1825">5 Years (Statutory)</MenuItem>
                              <MenuItem value="0">Indefinite Retention</MenuItem>
                            </Select>
                          </FormControl>

                          <TextField
                            label="Max Upload Size per Document"
                            fullWidth
                            size="small"
                            value="25 Megabytes (MB)"
                            disabled
                          />

                          <TextField
                            label="Max OCR Extraction Pages"
                            fullWidth
                            size="small"
                            value="50 Pages per Document"
                            disabled
                          />
                        </Stack>
                      </CardContent>
                    </Card>
                  </Grid>

                  <Grid item xs={12}>
                    <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5 }}>
                      <CardContent>
                        <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <ShieldIcon color="primary" fontSize="small" /> Ingestion & Retrieval Guardrails (PRD §15.3)
                        </Typography>
                        <Divider sx={{ my: 1.5 }} />

                        <Grid container spacing={3}>
                          <Grid item xs={12} md={4}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={autoPiiRedaction}
                                  onChange={(e) => setAutoPiiRedaction(e.target.checked)}
                                  disabled={!isAdmin}
                                  color="primary"
                                />
                              }
                              label="Automatic PII Redaction"
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              Scans and redacts Social Security numbers, tax IDs, and credit card numbers prior to vectorstore indexing.
                            </Typography>
                          </Grid>

                          <Grid item xs={12} md={4}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={quarantineInjections}
                                  onChange={(e) => setQuarantineInjections(e.target.checked)}
                                  disabled={!isAdmin}
                                  color="primary"
                                />
                              }
                              label="Prompt Injection Quarantine"
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              Isolates adversarial prompt injection strings in contracts, preventing subversion of simulation agents.
                            </Typography>
                          </Grid>

                          <Grid item xs={12} md={4}>
                            <FormControlLabel
                              control={
                                <Switch
                                  checked={strictGuardrails}
                                  onChange={(e) => setStrictGuardrails(e.target.checked)}
                                  disabled={!isAdmin}
                                  color="primary"
                                />
                              }
                              label="Multi-Tenant Boundaries"
                            />
                            <Typography variant="caption" color="text.secondary" display="block">
                              Enforces cryptographic organization separation at the vector search and database query layers.
                            </Typography>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  </Grid>

                  {isAdmin && (
                    <Grid item xs={12}>
                      <Stack direction="row" justifyContent="flex-end">
                        <Button
                          type="submit"
                          variant="contained"
                          disabled={saving}
                          startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SaveIcon />}
                          sx={{ borderRadius: 2, px: 3, textTransform: 'none', fontWeight: 600 }}
                        >
                          {saving ? 'Updating...' : 'Save Organization Policy'}
                        </Button>
                      </Stack>
                    </Grid>
                  )}
                </Grid>
              </form>
            )}

            {/* TAB 2: AI & OCR Infrastructure */}
            {activeTab === 2 && (
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <SmartToyIcon color="primary" fontSize="small" /> Large Language Model (LLM)
                      </Typography>
                      <Divider sx={{ my: 1.5 }} />

                      <Stack spacing={2}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Active Provider:</Typography>
                          <Chip label={opsData?.llm_provider || 'ollama'} color="primary" size="small" sx={{ fontWeight: 600 }} />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Local Host Endpoint:</Typography>
                          <Typography variant="body2" fontWeight={600}>{opsData?.ollama_base_url || 'http://localhost:11434'}</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Default Model (Review & Sim):</Typography>
                          <Typography variant="body2" fontWeight={600}>{opsData?.llm_model || '—'}</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Ask AI Model:</Typography>
                          <Typography variant="body2" fontWeight={600}>{opsData?.ask_llm_model || '—'}</Typography>
                        </Box>
                        <Box sx={{ pt: 1 }}>
                          <Typography variant="subtitle2" gutterBottom>
                            Preferred model for Ask AI
                          </Typography>
                          <FormControl fullWidth size="small">
                            <InputLabel id="preferred-llm-model-label">Preferred LLM model</InputLabel>
                            <Select
                              labelId="preferred-llm-model-label"
                              value={preferredModel}
                              label="Preferred LLM model"
                              onChange={(e) => setPreferredModel(e.target.value)}
                            >
                              <MenuItem value="gemma4:latest">gemma4:latest (Fastest overall)</MenuItem>
                              <MenuItem value="llama3.2:latest">llama3.2:latest (Balanced)</MenuItem>
                              <MenuItem value="granite4.2:8b">granite4.2:8b (Reasoning)</MenuItem>
                            </Select>
                          </FormControl>
                          <Button
                            variant="contained"
                            size="small"
                            onClick={handleSaveModelPreference}
                            disabled={saving}
                            sx={{ mt: 1.5, borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
                          >
                            {saving ? 'Saving...' : 'Save model preference'}
                          </Button>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Inference Mode:</Typography>
                          <Chip
                            label={opsData?.llm_temperature !== undefined ? `Deterministic (Temp ${opsData.llm_temperature})` : 'Deterministic'}
                            size="small"
                            variant="outlined"
                          />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Judge Deliberation Effort:</Typography>
                          <Chip
                            label={(opsData?.sim_judge_effort || 'High').toUpperCase()}
                            size="small"
                            color={(opsData?.sim_judge_effort || '').toLowerCase() === 'low' ? 'default' : 'primary'}
                            variant="outlined"
                          />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Exchanges Before Judge Ruling:</Typography>
                          <Typography variant="body2" fontWeight={600}>{opsData?.sim_judge_max_rounds ? `${opsData.sim_judge_max_rounds} conversations` : '—'}</Typography>
                        </Box>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <SpeedIcon color="primary" fontSize="small" /> Vision & OCR Ingestion Engine
                      </Typography>
                      <Divider sx={{ my: 1.5 }} />

                      <Stack spacing={2}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">OCR Provider:</Typography>
                          <Chip label={opsData?.ocr_provider?.toUpperCase() || 'TESSERACT'} color="success" size="small" sx={{ fontWeight: 600 }} />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Engine Status:</Typography>
                          <Chip label={opsData?.ocr_enabled ? 'Active & Enabled' : 'Disabled'} color={opsData?.ocr_enabled ? 'success' : 'default'} size="small" variant="outlined" />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Benchmark Performance:</Typography>
                          <Typography variant="body2" fontWeight={600}>~0.35s / scanned page</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Max OCR Pages / Document:</Typography>
                          <Typography variant="body2" fontWeight={600}>{opsData?.ocr_max_pages ? `${opsData.ocr_max_pages} pages` : '—'}</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Vision LLM Fallback:</Typography>
                          <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{opsData?.ocr_vision_model || '—'}</Typography>
                        </Box>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <ShieldIcon color="primary" fontSize="small" /> Embeddings & Vector Database
                      </Typography>
                      <Divider sx={{ my: 1.5 }} />

                      <Stack spacing={2}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Vector Store Adapter:</Typography>
                          <Chip label={opsData?.vector_provider || 'qdrant'} color="primary" size="small" sx={{ fontWeight: 600 }} />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Embedding Dimensions:</Typography>
                          <Typography variant="body2" fontWeight={600}>384 Dimensions</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Distance Metric:</Typography>
                          <Typography variant="body2" fontWeight={600}>Cosine Similarity</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Search Strategy:</Typography>
                          <Chip label="Hybrid Semantic + Full-Text" size="small" variant="outlined" />
                        </Box>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>

                <Grid item xs={12} md={6}>
                  <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2.5, height: '100%' }}>
                    <CardContent>
                      <Typography variant="h6" fontWeight={600} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <SecurityIcon color="primary" fontSize="small" /> Policy Engine & Telemetry
                      </Typography>
                      <Divider sx={{ my: 1.5 }} />

                      <Stack spacing={2}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">OPA Mode:</Typography>
                          <Chip label={opsData?.opa_mode || 'embedded'} color="primary" size="small" variant="outlined" />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">OPA RBAC Self-Check:</Typography>
                          <Chip
                            label={opsData?.opa_self_check ? 'Passed (Enforced)' : 'Warning'}
                            color={opsData?.opa_self_check ? 'success' : 'warning'}
                            size="small"
                            sx={{ fontWeight: 600 }}
                          />
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Distributed Tracing:</Typography>
                          <Typography variant="body2" fontWeight={600}>OpenTelemetry (OTel)</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body2" color="text.secondary">Task Queue Status:</Typography>
                          <Typography variant="body2" fontWeight={600}>
                            {opsData?.queue ? `${opsData.queue.running} active / ${opsData.queue.queued} queued` : 'Operational'}
                          </Typography>
                        </Box>
                      </Stack>
                    </CardContent>
                  </Card>
                </Grid>
              </Grid>
            )}

            {/* TAB 3: Team & Roles */}
            {activeTab === 3 && isAdmin && (
              <Box>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                  <Box>
                    <Typography variant="h6" fontWeight={600}>
                      Organization Members ({users.length})
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Active team members with platform and module authorization for {organizationName}.
                    </Typography>
                  </Box>
                  <Button
                    variant="contained"
                    startIcon={<PersonAddIcon />}
                    size="small"
                    onClick={() => setShowInviteModal(true)}
                    sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 600 }}
                  >
                    Invite Member
                  </Button>
                </Stack>

                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                  <Table size="medium">
                    <TableHead>
                      <TableRow sx={{ bgcolor: theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.02)' }}>
                        <TableCell sx={{ fontWeight: 600 }}>Member</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Platform Role</TableCell>
                        <TableCell sx={{ fontWeight: 600 }}>Module Permissions</TableCell>
                        <TableCell sx={{ fontWeight: 600 }} align="right">Status</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {users.map((u) => (
                        <TableRow key={u.id} hover>
                          <TableCell>
                            <Typography variant="subtitle2" fontWeight={600}>
                              {u.full_name || 'Team Member'}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {u.email}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={u.platform_role}
                              color={u.platform_role === 'org_admin' ? 'primary' : 'default'}
                              variant={u.platform_role === 'org_admin' ? 'filled' : 'outlined'}
                            />
                          </TableCell>
                          <TableCell>
                            <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5}>
                              {(u.module_roles || []).map((mr) => (
                                <Chip key={mr} label={mr} size="small" variant="outlined" sx={{ fontSize: '0.75rem' }} />
                              ))}
                              {(!u.module_roles || u.module_roles.length === 0) && (
                                <Typography variant="caption" color="text.secondary">Standard Access</Typography>
                              )}
                            </Stack>
                          </TableCell>
                          <TableCell align="right">
                            <Chip
                              size="small"
                              label={u.is_active ? 'Active' : 'Pending Invite'}
                              color={u.is_active ? 'success' : 'warning'}
                              variant="outlined"
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Box>
            )}
          </Box>
        )}
      </Paper>

      {/* Invite Member Dialog */}
      <Dialog
        open={showInviteModal}
        onClose={() => setShowInviteModal(false)}
        maxWidth="xs"
        fullWidth
        PaperProps={{ sx: { borderRadius: 3, p: 1 } }}
      >
        <form onSubmit={handleInviteUser}>
          <DialogTitle>Invite Organization Member</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Send an invitation link to a colleague to join <b>{organizationName}</b>.
            </Typography>
            <TextField
              label="Colleague Email Address"
              fullWidth
              size="small"
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="e.g. associate@firm.com"
            />
          </DialogContent>
          <DialogActions sx={{ px: 3, pb: 2 }}>
            <Button onClick={() => setShowInviteModal(false)} variant="text">
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={!inviteEmail || inviting}
              startIcon={inviting ? <CircularProgress size={18} color="inherit" /> : <PersonAddIcon />}
              sx={{ borderRadius: 2 }}
            >
              {inviting ? 'Inviting...' : 'Send Invite'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* Toast Notification */}
      <Snackbar
        open={Boolean(toastMsg)}
        autoHideDuration={3000}
        onClose={() => setToastMsg('')}
        message={toastMsg}
      />
    </Box>
  );
}