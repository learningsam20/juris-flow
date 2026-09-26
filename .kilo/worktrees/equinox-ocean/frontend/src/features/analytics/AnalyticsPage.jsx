import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  InputAdornment,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import AssessmentIcon from '@mui/icons-material/Assessment';
import BarChartIcon from '@mui/icons-material/BarChart';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DataObjectIcon from '@mui/icons-material/DataObject';
import DescriptionIcon from '@mui/icons-material/Description';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GavelIcon from '@mui/icons-material/Gavel';
import HistoryIcon from '@mui/icons-material/History';
import MonitorHeartIcon from '@mui/icons-material/MonitorHeart';
import PsychologyIcon from '@mui/icons-material/Psychology';
import SearchIcon from '@mui/icons-material/Search';
import SpeedIcon from '@mui/icons-material/Speed';
import TimerIcon from '@mui/icons-material/Timer';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { EmptyState, SectionCard, StatTile } from '../../components/ui';

function formatDuration(ms) {
  if (ms === null || ms === undefined) return '—';
  const v = Number(ms);
  if (Number.isNaN(v) || v < 0) return '—';
  if (v < 1) return '<1 ms';
  if (v < 1000) return `${Math.round(v)} ms`;
  return `${(v / 1000).toFixed(2)} s`;
}

export default function AnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [events, setEvents] = useState([]);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [eventSearch, setEventSearch] = useState('');
  const [searchingServer, setSearchingServer] = useState(false);
  const [selectedPayloadEvent, setSelectedPayloadEvent] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let mounted = true;
    Promise.allSettled([api('/analytics/dashboard'), api('/analytics/events?limit=250')]).then(([dashRes, eventsRes]) => {
      if (!mounted) return;
      if (dashRes.status === 'fulfilled' && dashRes.value) setData(dashRes.value);
      if (eventsRes.status === 'fulfilled' && eventsRes.value?.events) setEvents(eventsRes.value.events);
      setLoading(false);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const handleServerSearch = async (term = eventSearch) => {
    setSearchingServer(true);
    try {
      const res = await api(`/analytics/events?q=${encodeURIComponent(term.trim())}&limit=250`);
      if (res?.events) {
        setEvents(res.events);
        setPage(0);
      }
    } catch (err) {
      console.error('Failed to search events from server', err);
    } finally {
      setSearchingServer(false);
    }
  };

  const handleClearSearch = () => {
    setEventSearch('');
    setPage(0);
    api('/analytics/events?limit=250').then((res) => {
      if (res?.events) setEvents(res.events);
    });
  };

  const filteredEvents = useMemo(() => {
    const q = eventSearch.trim().toLowerCase();
    if (!q) return events;
    return events.filter((evt) => {
      const typeMatch = evt.type?.toLowerCase().includes(q);
      const modMatch = evt.module?.toLowerCase().includes(q);
      const corrMatch = evt.correlation_id?.toLowerCase().includes(q);
      const userMatch = evt.user_id?.toLowerCase().includes(q);
      const payloadStr = evt.payload ? JSON.stringify(evt.payload).toLowerCase() : '';
      const payloadMatch = payloadStr.includes(q);
      return typeMatch || modMatch || corrMatch || userMatch || payloadMatch;
    });
  }, [events, eventSearch]);

  const kpis = data?.kpis || {};
  const insights = data?.insights || {};
  const telemetry = data?.telemetry || {};
  const clusters = insights.document_clusters || {};
  const jurisdictions = clusters.by_jurisdiction || {};
  const domains = clusters.by_domain || {};
  const types = clusters.by_type || {};
  const totalDocs = kpis.documents ?? 0;

  const statCards = [
    {
      title: 'Indexed Precedents',
      value: kpis.documents ?? 0,
      sub: `${kpis.knowledge_collections ?? 0} collections configured`,
      icon: <DescriptionIcon />,
      color: '#4f46e5',
    },
    {
      title: 'Contract Reviews',
      value: kpis.reviews ?? 0,
      sub: `${kpis.reviews_published_rate ?? 0}% published audits`,
      icon: <FactCheckIcon />,
      color: '#f59e0b',
    },
    {
      title: 'Adversarial Simulations',
      value: kpis.simulations ?? 0,
      sub: `${kpis.simulation_completion_rate ?? 0}% completed rate`,
      icon: <GavelIcon />,
      color: '#a855f7',
    },
    {
      title: 'Negotiation Turns',
      value: kpis.simulation_turns ?? 0,
      sub: `${kpis.avg_turns_per_simulation ?? 0} avg turns / sim`,
      icon: <AssessmentIcon />,
      color: '#14b8a6',
    },
    {
      title: 'Semantic Searches',
      value: kpis.knowledge_searches ?? 0,
      sub: 'Vector queries & citations',
      icon: <SearchIcon />,
      color: '#0ea5e9',
    },
    {
      title: 'Strategic Scenarios',
      value: kpis.scenarios ?? 0,
      sub: `${kpis.case_studies ?? 0} case studies generated`,
      icon: <PsychologyIcon />,
      color: '#ec4899',
    },
  ];

  const renderCluster = (obj, labelMap, color = 'primary') => (
    <Stack spacing={2} sx={{ mt: 1 }}>
      {Object.entries(obj).map(([key, count]) => {
        const pct = totalDocs > 0 ? Math.round((count / totalDocs) * 100) : 0;
        return (
          <Box key={key}>
            <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
              <Typography variant="body2" fontWeight={500}>
                {labelMap[key] || key}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {count} ({pct}%)
              </Typography>
            </Stack>
            <LinearProgress variant="determinate" value={pct} color={color} sx={{ height: 6, borderRadius: 3 }} />
          </Box>
        );
      })}
    </Stack>
  );

  return (
    <Box sx={{ width: '100%', pb: 4 }}>
      {/* Streamlined Analytics Bar */}
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
          <AnalyticsIcon color="primary" />
          <Typography variant="subtitle1" fontWeight={800} sx={{ letterSpacing: '-0.01em' }}>
            Analytics & Performance Intelligence
          </Typography>
        </Stack>

        {loading ? (
          <CircularProgress size={20} />
        ) : (
          <Chip
            icon={<MonitorHeartIcon />}
            label={`${telemetry.total_events ?? 0} events`}
            size="small"
            color="primary"
            variant="outlined"
            sx={{ fontWeight: 650, fontSize: '0.72rem' }}
          />
        )}
      </Paper>

      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {statCards.map((card) => (
          <Grid item xs={12} sm={6} md={4} key={card.title}>
            <StatTile label={card.title} value={card.value} sub={card.sub} icon={card.icon} color={card.color} loading={loading} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={4}>
          <SectionCard icon={<GavelIcon color="primary" />} title="Jurisdiction Distribution">
            <Divider sx={{ mb: 2 }} />
            {Object.keys(jurisdictions).length > 0 ? (
              renderCluster(jurisdictions, { unspecified: 'General / Global' }, 'primary')
            ) : (
              <EmptyState icon={<DescriptionIcon sx={{ fontSize: 32 }} />} title="No jurisdiction records." />
            )}
          </SectionCard>
        </Grid>

        <Grid item xs={12} md={4}>
          <SectionCard icon={<PsychologyIcon color="secondary" />} title="Practice Domains">
            <Divider sx={{ mb: 2 }} />
            {Object.keys(domains).length > 0 ? (
              renderCluster(domains, { unspecified: 'General Contract' }, 'secondary')
            ) : (
              <EmptyState icon={<DescriptionIcon sx={{ fontSize: 32 }} />} title="No domain records." />
            )}
          </SectionCard>
        </Grid>

        <Grid item xs={12} md={4}>
          <SectionCard icon={<FactCheckIcon color="success" />} title="Document Classifications">
            <Divider sx={{ mb: 2 }} />
            {Object.keys(types).length > 0 ? (
              <Stack spacing={2} sx={{ mt: 1 }}>
                {Object.entries(types).map(([tp, count]) => {
                  const pct = totalDocs > 0 ? Math.round((count / totalDocs) * 100) : 0;
                  return (
                    <Box key={tp}>
                      <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                        <Typography variant="body2" fontWeight={500} textTransform="capitalize">
                          {tp}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {count} ({pct}%)
                        </Typography>
                      </Stack>
                      <LinearProgress variant="determinate" value={pct} color="success" sx={{ height: 6, borderRadius: 3 }} />
                    </Box>
                  );
                })}
              </Stack>
            ) : (
              <EmptyState icon={<DescriptionIcon sx={{ fontSize: 32 }} />} title="No classification records." />
            )}
          </SectionCard>
        </Grid>
      </Grid>

      <SectionCard
        icon={<MonitorHeartIcon color="primary" />}
        title="Telemetry Activity"
        action={
          <Chip size="small" label={`${telemetry.total_events ?? 0} events recorded`} color="primary" variant="outlined" sx={{ fontWeight: 600 }} />
        }
        sx={{ mb: 3 }}
      >
        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
              By Module
            </Typography>
            {Object.keys(telemetry.by_module || {}).length > 0 ? (
              <Stack spacing={1}>
                {Object.entries(telemetry.by_module).map(([mod, count]) => {
                  const total = telemetry.total_events || 0;
                  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                  return (
                    <Box key={mod}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Typography variant="body2" fontWeight={500} textTransform="capitalize">
                            {mod}
                          </Typography>
                          <Chip size="small" label={count} sx={{ height: 18, fontSize: '0.68rem' }} />
                        </Stack>
                        <Typography variant="caption" color="text.secondary">
                          {pct}%
                        </Typography>
                      </Stack>
                      <LinearProgress variant="determinate" value={pct} sx={{ height: 6, borderRadius: 3 }} />
                    </Box>
                  );
                })}
              </Stack>
            ) : (
              <EmptyState icon={<MonitorHeartIcon sx={{ fontSize: 32 }} />} title="No telemetry yet." />
            )}
          </Grid>

          <Grid item xs={12} md={7}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2" fontWeight={700}>
                Telemetry by Action Type
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Relative frequency of system events
              </Typography>
            </Stack>

            {Object.keys(telemetry.by_event_type || {}).length > 0 ? (
              <Box sx={{ pt: 1 }}>
                {/* Visual Column Chart for Telemetry by Action Type */}
                {(() => {
                  const entries = Object.entries(telemetry.by_event_type);
                  const maxCount = Math.max(...entries.map(([, c]) => c), 1);
                  const total = telemetry.total_events || entries.reduce((acc, [, c]) => acc + c, 0);

                  return (
                    <Box
                      sx={{
                        p: 2,
                        borderRadius: 2.5,
                        bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)'),
                        border: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      {/* Column Bars Area */}
                      <Box
                        sx={{
                          height: 160,
                          display: 'flex',
                          alignItems: 'flex-end',
                          gap: { xs: 1, sm: 1.75 },
                          borderBottom: '2px solid',
                          borderColor: 'divider',
                          pb: 0.5,
                          px: 1,
                          overflowX: 'auto',
                        }}
                      >
                        {entries.map(([type, count]) => {
                          const heightPct = Math.max(6, Math.round((count / maxCount) * 100));
                          const sharePct = total > 0 ? ((count / total) * 100).toFixed(1) : '0';

                          return (
                            <Tooltip
                              key={type}
                              arrow
                              placement="top"
                              title={
                                <Box sx={{ p: 0.5, textAlign: 'center' }}>
                                  <Typography variant="caption" fontWeight={700} display="block">
                                    {type}
                                  </Typography>
                                  <Typography variant="caption">
                                    {count.toLocaleString()} occurrences ({sharePct}% of total)
                                  </Typography>
                                </Box>
                              }
                            >
                              <Box
                                sx={{
                                  flex: 1,
                                  minWidth: 44,
                                  maxWidth: 72,
                                  height: '100%',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  justifyContent: 'flex-end',
                                  alignItems: 'center',
                                  cursor: 'pointer',
                                  '&:hover .col-bar': {
                                    transform: 'scaleY(1.03)',
                                    filter: 'brightness(1.18)',
                                    boxShadow: '0 4px 12px rgba(99,102,241,0.4)',
                                  },
                                }}
                              >
                                {/* Count Badge on Top */}
                                <Typography
                                  variant="caption"
                                  fontWeight={750}
                                  sx={{
                                    fontSize: '0.7rem',
                                    color: 'text.secondary',
                                    mb: 0.5,
                                  }}
                                >
                                  {count}
                                </Typography>

                                {/* The Animated Vertical Column */}
                                <Box
                                  className="col-bar"
                                  sx={{
                                    width: '100%',
                                    height: `${heightPct}%`,
                                    background: (t) =>
                                      t.palette.mode === 'dark'
                                        ? 'linear-gradient(180deg, #818cf8 0%, #4f46e5 100%)'
                                        : 'linear-gradient(180deg, #6366f1 0%, #4338ca 100%)',
                                    borderRadius: '6px 6px 0 0',
                                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                    transformOrigin: 'bottom',
                                  }}
                                />
                              </Box>
                            </Tooltip>
                          );
                        })}
                      </Box>

                      {/* X-Axis Category Labels */}
                      <Box
                        sx={{
                          display: 'flex',
                          gap: { xs: 1, sm: 1.75 },
                          px: 1,
                          pt: 1,
                          overflowX: 'auto',
                        }}
                      >
                        {entries.map(([type]) => {
                          const shortName = type.includes('.') ? type.split('.').slice(-1)[0] : type;
                          return (
                            <Tooltip key={`label-${type}`} title={type} arrow>
                              <Box
                                sx={{
                                  flex: 1,
                                  minWidth: 44,
                                  maxWidth: 72,
                                  textAlign: 'center',
                                }}
                              >
                                <Typography
                                  variant="caption"
                                  fontFamily="monospace"
                                  fontWeight={600}
                                  sx={{
                                    fontSize: '0.67rem',
                                    color: 'text.secondary',
                                    textTransform: 'capitalize',
                                    display: 'block',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {shortName}
                                </Typography>
                              </Box>
                            </Tooltip>
                          );
                        })}
                      </Box>
                    </Box>
                  );
                })()}
              </Box>
            ) : (
              <EmptyState
                icon={<HistoryIcon sx={{ fontSize: 32 }} />}
                title="No telemetry events yet"
                body="Interact with Ask AI, document review, searches, and simulations to populate this view."
              />
            )}
          </Grid>
        </Grid>
      </SectionCard>

      {/* Time Taken & Latency Performance Analysis */}
      {(() => {
        const latencyStats = telemetry.latency_stats || {};
        const eventDurations = events
          .map((e) => Number(e.payload?.duration_ms))
          .filter((d) => !Number.isNaN(d) && d >= 0);

        const totalTimed = latencyStats.total_timed_events ?? eventDurations.length;
        const avgDur = latencyStats.avg_duration_ms ?? (eventDurations.length ? Math.round(eventDurations.reduce((a, b) => a + b, 0) / eventDurations.length) : 0);
        const p95Dur = latencyStats.p95_duration_ms ?? (eventDurations.length ? [...eventDurations].sort((a, b) => a - b)[Math.floor(eventDurations.length * 0.95)] : 0);
        const maxDur = latencyStats.max_duration_ms ?? (eventDurations.length ? Math.max(...eventDurations) : 0);

        const avgByType = latencyStats.avg_by_type || {};
        const typeEntries = Object.entries(avgByType);
        const maxTypeDur = Math.max(...typeEntries.map(([, d]) => d), 1);

        return (
          <SectionCard
            icon={<TimerIcon color="primary" />}
            title="Execution Latency & Time Analysis"
            action={
              <Chip
                size="small"
                icon={<SpeedIcon sx={{ fontSize: '14px !important' }} />}
                label={`${totalTimed} timed operations`}
                color="primary"
                variant="outlined"
                sx={{ fontWeight: 650 }}
              />
            }
            sx={{ mb: 3 }}
          >
            <Grid container spacing={2.5} sx={{ mb: 3 }}>
              <Grid item xs={6} sm={3}>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    borderRadius: 2.5,
                    textAlign: 'center',
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(99,102,241,0.06)' : 'rgba(79,70,229,0.03)'),
                    borderColor: 'primary.light',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase" letterSpacing={0.5}>
                    Average Latency
                  </Typography>
                  <Typography variant="h5" fontWeight={800} color="primary" sx={{ mt: 0.5 }}>
                    {formatDuration(avgDur)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Mean operation time
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    borderRadius: 2.5,
                    textAlign: 'center',
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(245,158,11,0.06)' : 'rgba(245,158,11,0.03)'),
                    borderColor: 'warning.light',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase" letterSpacing={0.5}>
                    P95 Tail Latency
                  </Typography>
                  <Typography variant="h5" fontWeight={800} sx={{ mt: 0.5, color: '#f59e0b' }}>
                    {formatDuration(p95Dur)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    95% of calls faster than
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    borderRadius: 2.5,
                    textAlign: 'center',
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(16,185,129,0.06)' : 'rgba(16,185,129,0.03)'),
                    borderColor: 'success.light',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase" letterSpacing={0.5}>
                    Minimum Latency
                  </Typography>
                  <Typography variant="h5" fontWeight={800} sx={{ mt: 0.5, color: '#10b981' }}>
                    {formatDuration(latencyStats.min_duration_ms ?? 1)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Fastest execution
                  </Typography>
                </Paper>
              </Grid>

              <Grid item xs={6} sm={3}>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 2,
                    borderRadius: 2.5,
                    textAlign: 'center',
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(239,68,68,0.06)' : 'rgba(239,68,68,0.03)'),
                    borderColor: 'error.light',
                  }}
                >
                  <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase" letterSpacing={0.5}>
                    Peak Duration
                  </Typography>
                  <Typography variant="h5" fontWeight={800} sx={{ mt: 0.5, color: '#ef4444' }}>
                    {formatDuration(maxDur)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Worst-case roundtrip
                  </Typography>
                </Paper>
              </Grid>
            </Grid>

            {/* Time Taken Breakdown by Operation Type */}
            {typeEntries.length > 0 ? (
              <Box>
                <Typography variant="subtitle2" fontWeight={750} sx={{ mb: 1.5 }}>
                  Mean Duration by Operation Type
                </Typography>
                <Stack spacing={1.5}>
                  {typeEntries.map(([opType, dur]) => {
                    const pct = Math.max(5, Math.round((dur / maxTypeDur) * 100));
                    const isFast = dur < 300;
                    const isMedium = dur >= 300 && dur < 1500;
                    const color = isFast ? '#10b981' : isMedium ? '#f59e0b' : '#6366f1';

                    return (
                      <Box key={opType}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                          <Typography variant="body2" fontFamily="monospace" fontWeight={600}>
                            {opType}
                          </Typography>
                          <Chip
                            size="small"
                            label={formatDuration(dur)}
                            sx={{
                              height: 20,
                              fontWeight: 700,
                              fontSize: '0.7rem',
                              bgcolor: `${color}15`,
                              color: color,
                              border: `1px solid ${color}40`,
                            }}
                          />
                        </Stack>
                        <LinearProgress
                          variant="determinate"
                          value={pct}
                          sx={{
                            height: 7,
                            borderRadius: 3.5,
                            bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)'),
                            '& .MuiLinearProgress-bar': {
                              bgcolor: color,
                              borderRadius: 3.5,
                            },
                          }}
                        />
                      </Box>
                    );
                  })}
                </Stack>
              </Box>
            ) : null}
          </SectionCard>
        );
      })()}

      <SectionCard
        icon={<HistoryIcon color="primary" />}
        title="Audit & Telemetry Event Stream"
        action={
          <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap">
            <TextField
              size="small"
              placeholder="Search payload, type, module..."
              value={eventSearch}
              onChange={(e) => {
                setEventSearch(e.target.value);
                setPage(0);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleServerSearch();
              }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                  </InputAdornment>
                ),
                endAdornment: eventSearch ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={handleClearSearch} sx={{ p: 0.25 }}>
                      <CloseIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  </InputAdornment>
                ) : null,
                sx: {
                  height: 32,
                  fontSize: '0.8rem',
                  width: { xs: 200, sm: 260 },
                  bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)'),
                },
              }}
            />
            <Tooltip title="Execute database search for this query across all recorded telemetry">
              <span>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => handleServerSearch()}
                  disabled={searchingServer}
                  sx={{ height: 32, minWidth: 32, px: 1.5, fontSize: '0.75rem', fontWeight: 600 }}
                >
                  {searchingServer ? <CircularProgress size={14} /> : 'Search DB'}
                </Button>
              </span>
            </Tooltip>
            <Chip
              size="small"
              label={
                eventSearch.trim()
                  ? `${filteredEvents.length} / ${events.length}`
                  : `${events.length} events`
              }
              color={eventSearch.trim() ? 'primary' : 'default'}
              variant="outlined"
              sx={{ height: 26, fontSize: '0.72rem', fontWeight: 650 }}
            />
          </Stack>
        }
      >
        {filteredEvents.length > 0 ? (
          <>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 650 }}>Timestamp</TableCell>
                    <TableCell sx={{ fontWeight: 650 }}>Module</TableCell>
                    <TableCell sx={{ fontWeight: 650 }}>Event Type</TableCell>
                    <TableCell sx={{ fontWeight: 650 }}>Duration</TableCell>
                    <TableCell sx={{ fontWeight: 650 }}>Correlation ID</TableCell>
                    <TableCell sx={{ fontWeight: 650 }}>Payload Details</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredEvents
                    .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                    .map((evt) => (
                      <TableRow key={evt.id} hover>
                        <TableCell>
                          <Typography variant="caption" color="text.secondary">
                            {evt.created_at ? new Date(evt.created_at).toLocaleString() : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label={evt.module || 'system'} size="small" variant="outlined" sx={{ height: 22, fontSize: '0.7rem' }} />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {evt.type}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={formatDuration(evt.payload?.duration_ms)}
                            size="small"
                            variant="outlined"
                            color="primary"
                            sx={{ height: 22, fontSize: '0.7rem' }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                            {evt.correlation_id ? evt.correlation_id.substring(0, 8) : '—'}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ maxWidth: 320 }}>
                          {evt.payload && Object.keys(evt.payload).length > 0 ? (
                            <Stack direction="row" alignItems="center" spacing={0.8}>
                              <Tooltip title="Click to inspect full payload" arrow>
                                <Box
                                  component="button"
                                  onClick={() => {
                                    setCopied(false);
                                    setSelectedPayloadEvent(evt);
                                  }}
                                  sx={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    background: 'none',
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1,
                                    px: 1,
                                    py: 0.3,
                                    cursor: 'pointer',
                                    textAlign: 'left',
                                    fontFamily: 'monospace',
                                    fontSize: '0.74rem',
                                    color: 'text.secondary',
                                    maxWidth: 220,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    transition: 'all 0.15s ease-in-out',
                                    '&:hover': {
                                      borderColor: 'primary.main',
                                      color: 'primary.main',
                                      bgcolor: (t) =>
                                        t.palette.mode === 'dark'
                                          ? 'rgba(99, 102, 241, 0.1)'
                                          : 'rgba(99, 102, 241, 0.05)',
                                    },
                                  }}
                                >
                                  {JSON.stringify(evt.payload)}
                                </Box>
                              </Tooltip>
                              <Tooltip title="Inspect Full Payload">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setCopied(false);
                                    setSelectedPayloadEvent(evt);
                                  }}
                                  sx={{
                                    p: 0.4,
                                    color: 'primary.main',
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1,
                                    '&:hover': { bgcolor: 'primary.main', color: '#fff' },
                                  }}
                                >
                                  <DataObjectIcon sx={{ fontSize: 15 }} />
                                </IconButton>
                              </Tooltip>
                            </Stack>
                          ) : (
                            <Typography variant="caption" color="text.secondary">
                              —
                            </Typography>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </TableContainer>

            <TablePagination
              rowsPerPageOptions={[5, 10, 25, 50]}
              component="div"
              count={filteredEvents.length}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={(e, newPage) => setPage(newPage)}
              onRowsPerPageChange={(e) => {
                setRowsPerPage(parseInt(e.target.value, 10));
                setPage(0);
              }}
              sx={{ borderTop: '1px solid', borderColor: 'divider' }}
            />
          </>
        ) : (
          <Box sx={{ py: 4, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {eventSearch.trim()
                ? `No telemetry events found matching "${eventSearch}".`
                : 'No telemetry events recorded yet.'}
            </Typography>
            {eventSearch.trim() && (
              <Button size="small" onClick={handleClearSearch} startIcon={<CloseIcon fontSize="small" />}>
                Clear Search Filter
              </Button>
            )}
          </Box>
        )}
      </SectionCard>

      {/* Full Payload Inspector Dialog */}
      <Dialog
        open={Boolean(selectedPayloadEvent)}
        onClose={() => setSelectedPayloadEvent(null)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 3, p: 0.5 },
        }}
      >
        <DialogTitle sx={{ pb: 1.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <DataObjectIcon color="primary" />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>
                  Telemetry Event Payload
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {selectedPayloadEvent?.type} •{' '}
                  {selectedPayloadEvent?.created_at
                    ? new Date(selectedPayloadEvent.created_at).toLocaleString()
                    : ''}
                </Typography>
              </Box>
            </Stack>
            <IconButton size="small" onClick={() => setSelectedPayloadEvent(null)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Stack>
        </DialogTitle>
        <DialogContent dividers sx={{ py: 2 }}>
          {selectedPayloadEvent && (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                <Chip
                  label={`Module: ${selectedPayloadEvent.module || 'system'}`}
                  size="small"
                  variant="outlined"
                />
                <Chip
                  label={`Type: ${selectedPayloadEvent.type}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
                {selectedPayloadEvent.correlation_id && (
                  <Chip
                    label={`Correlation: ${selectedPayloadEvent.correlation_id}`}
                    size="small"
                    variant="outlined"
                    sx={{ fontFamily: 'monospace' }}
                  />
                )}
                {selectedPayloadEvent.payload?.duration_ms !== undefined && (
                  <Chip
                    label={`Duration: ${formatDuration(selectedPayloadEvent.payload.duration_ms)}`}
                    size="small"
                    color="secondary"
                    variant="outlined"
                  />
                )}
              </Stack>

              <Box sx={{ position: 'relative' }}>
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    p: 2,
                    borderRadius: 2,
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'grey.900' : 'grey.100'),
                    color: (t) => (t.palette.mode === 'dark' ? '#93c5fd' : '#1e293b'),
                    fontFamily: 'monospace',
                    fontSize: '0.82rem',
                    lineHeight: 1.55,
                    overflowX: 'auto',
                    maxHeight: 460,
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  {JSON.stringify(selectedPayloadEvent.payload, null, 2)}
                </Box>
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 1.5, justifyContent: 'space-between' }}>
          <Button
            startIcon={copied ? <CheckIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
            onClick={() => {
              if (selectedPayloadEvent?.payload) {
                navigator.clipboard.writeText(JSON.stringify(selectedPayloadEvent.payload, null, 2));
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }
            }}
            color={copied ? 'success' : 'inherit'}
            size="small"
          >
            {copied ? 'Copied to Clipboard!' : 'Copy Payload JSON'}
          </Button>
          <Button onClick={() => setSelectedPayloadEvent(null)} variant="outlined" size="small">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}