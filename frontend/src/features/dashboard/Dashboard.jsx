import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GavelIcon from '@mui/icons-material/Gavel';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import SecurityIcon from '@mui/icons-material/Security';

import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FolderSpecialIcon from '@mui/icons-material/FolderSpecial';
import PsychologyIcon from '@mui/icons-material/Psychology';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { EmptyState, SectionCard, StatTile } from '../../components/ui';

export default function Dashboard() {
  const theme = useTheme();
  const navigate = useNavigate();
  const isDark = theme.palette.mode === 'dark';

  const [loading, setLoading] = useState(true);
  const [dashboardData, setDashboardData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [readyData, setReadyData] = useState(null);
  const [recentDocs, setRecentDocs] = useState([]);
  const [recentReviews, setRecentReviews] = useState([]);
  const [applyOpen, setApplyOpen] = useState(false);
  const [applyReviews, setApplyReviews] = useState([]);
  const [applyReviewId, setApplyReviewId] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState(null);
  const [applyError, setApplyError] = useState('');

  useEffect(() => {
    let mounted = true;

    Promise.allSettled([
      api('/analytics/dashboard'),
      api('/health'),
      api('/ready'),
      api('/documents?limit=5'),
      api('/reviews?limit=5'),
    ]).then(([dashRes, healthRes, readyRes, docsRes, reviewsRes]) => {
      if (!mounted) return;
      if (dashRes.status === 'fulfilled' && dashRes.value) {
        setDashboardData(dashRes.value);
      }
      if (healthRes.status === 'fulfilled' && healthRes.value) {
        setHealthData(healthRes.value);
      }
      if (readyRes.status === 'fulfilled' && readyRes.value) {
        setReadyData(readyRes.value);
      }
      if (docsRes.status === 'fulfilled' && docsRes.value?.documents) {
        setRecentDocs(docsRes.value.documents.slice(0, 5));
      }
      if (reviewsRes.status === 'fulfilled' && reviewsRes.value?.reviews) {
        setRecentReviews(reviewsRes.value.reviews.slice(0, 5));
      }
      setLoading(false);
    });

    return () => {
      mounted = false;
    };
  }, []);

  const kpis = dashboardData?.kpis || {};
  const insights = dashboardData?.insights || {};
  const clusters = insights.document_clusters || {};
  const jurisdictions = clusters.by_jurisdiction || {};
  const domains = clusters.by_domain || {};

  const totalDocs = kpis.documents ?? 0;
  const totalReviews = kpis.reviews ?? 0;
  const totalSims = kpis.simulations ?? 0;
  const totalSearches = kpis.knowledge_searches ?? 0;
  const simCompletionRate = kpis.simulation_completion_rate ?? 0;
  const reviewPublishRate = kpis.reviews_published_rate ?? 0;

  const primary = theme.palette.primary.main;

  const remediation = kpis.contract_remediation || {};
  const impl = remediation.implementation || {};
  const totalFindings = remediation.findings ?? 0;
  const nonGrounded = remediation.non_grounded ?? 0;
  const nonGroundedPct = remediation.non_grounded_pct ?? 0;
  const manualReview = remediation.manual_review ?? 0;
  const manualReviewPct = remediation.manual_review_pct ?? 0;
  const kmConfirmed = remediation.km_confirmed ?? 0;
  const highOpen = remediation.open_high_risk ?? 0;
  const inProgress = impl.in_progress ?? remediation.in_progress ?? 0;
  const applied = impl.applied ?? 0;
  const progressPct = remediation.remediation_progress_pct ?? 0;
  const pendingHighRisk = remediation.pending_high_risk_reviews ?? 0;

  const openApply = async () => {
    setApplyOpen(true);
    setApplyError('');
    setApplyResult(null);
    if (applyReviews.length > 0) return;
    try {
      const res = await api('/reviews?limit=50');
      const list = Array.isArray(res?.reviews) ? res.reviews : Array.isArray(res) ? res : [];
      setApplyReviews(list);
      if (list.length && !applyReviewId) setApplyReviewId(list[0].id);
    } catch (err) {
      setApplyError(err?.message || 'Could not load contract audits.');
    }
  };

  const runApply = async () => {
    if (!applyReviewId) return;
    setApplying(true);
    setApplyError('');
    try {
      const res = await api(`/reviews/${applyReviewId}/apply`, { method: 'POST' });
      setApplyResult(res);
      // refresh metrics so the in-progress / remediated counts move immediately
      api('/analytics/dashboard')
        .then((d) => {
          if (d) setDashboardData(d);
        })
        .catch(() => {});
      api('/reviews?limit=5')
        .then((r) => {
          if (r?.reviews) setRecentReviews(r.reviews.slice(0, 5));
        })
        .catch(() => {});
    } catch (err) {
      setApplyError(err?.message || 'Could not apply this audit to the contract.');
    } finally {
      setApplying(false);
    }
  };

  const downloadApplied = () => {
    if (!applyResult?.markdown) return;
    const blob = new Blob([applyResult.markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = applyResult.filename || 'remediated-contract.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Box sx={{ width: '100%', pb: 4 }}>
      {/* Streamlined Command Bar */}
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
        <Stack direction="row" spacing={1.5} sx={{
          alignItems: "center"
        }}>
          <Typography
            variant="subtitle1"
            sx={{
              fontWeight: 800,
              letterSpacing: '-0.01em'
            }}>
            Command Center
          </Typography>
          <Chip
            icon={<CheckCircleIcon sx={{ fontSize: '15px !important', color: 'success.light' }} />}
            label="Systems Healthy"
            size="small"
            variant="outlined"
            sx={{
              borderColor: isDark ? 'rgba(74,222,128,0.4)' : 'rgba(22,163,74,0.5)',
              color: isDark ? '#86efac' : '#15803d',
              fontWeight: 650,
              fontSize: '0.72rem',
              height: 24,
            }}
          />
        </Stack>

        <Stack direction="row" spacing={1} sx={{
          alignItems: "center"
        }}>
          <Button
            size="small"
            variant="contained"
            startIcon={<CloudUploadIcon sx={{ fontSize: 16 }} />}
            onClick={() => navigate('/hub')}
            sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
          >
            Open Hub
          </Button>
          <Button
            size="small"
            variant="outlined"
            startIcon={<FactCheckIcon sx={{ fontSize: 16 }} />}
            onClick={() => navigate('/review')}
            sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
          >
            Review
          </Button>
        </Stack>
      </Paper>

      {/* KPI Metric Tiles */}
      <Box
        sx={{
          display: 'grid',
          gap: 2.5,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', xl: 'repeat(4, 1fr)' },
          mb: 3.5,
        }}
      >
        <StatTile
          label="Indexed Contracts"
          value={totalDocs}
          icon={<MenuBookIcon />}
          color={primary}
          sub={<span><b>{totalSearches}</b> semantic searches executed</span>}
          footer="Explore Knowledge Hub"
          onClick={() => navigate('/hub')}
          loading={loading}
          ariaLabel="Indexed Contracts"
        />
        <StatTile
          label="Contract Audits"
          value={totalReviews}
          icon={<FactCheckIcon />}
          color="#d97706"
          sub={<span><b>{reviewPublishRate}%</b> published audit reports</span>}
          footer="Open Audit Workspace"
          onClick={() => navigate('/review')}
          loading={loading}
          ariaLabel="Contract Audits"
        />
        <StatTile
          label="Simulations"
          value={totalSims}
          icon={<GavelIcon />}
          color="#8b5cf6"
          sub={<span><b>{kpis.simulation_turns ?? 0}</b> adversarial turns ({simCompletionRate}% completed)</span>}
          footer="View Simulations"
          onClick={() => navigate('/simulations')}
          loading={loading}
          ariaLabel="Simulations"
        />
        <StatTile
          label="Case Studies & Scenarios"
          value={(kpis.case_studies ?? 0) + (kpis.scenarios ?? 0)}
          icon={<FolderSpecialIcon />}
          color="#0d9488"
          sub={<span><b>{kpis.knowledge_collections ?? 0}</b> collections · <b>{kpis.scenarios ?? 0}</b> scenarios</span>}
          footer="Deep Analytics"
          onClick={() => navigate('/analytics')}
          loading={loading}
          ariaLabel="Case Studies & Scenarios"
        />
      </Box>

      {/* Main grid */}
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 2fr) minmax(0, 1fr)' } }}>
        {/* Left column */}
        <Box sx={{ minWidth: 0 }}>
          {/* Practice Intelligence */}
          <SectionCard
            icon={<PsychologyIcon color="primary" />}
            title="Practice Intelligence & Coverage"
            action={
              <Button size="small" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/analytics')} sx={{ textTransform: 'none' }}>
                Detailed Analytics
              </Button>
            }
            sx={{ mb: 3 }}
          >
            {/* Top Intelligence Metrics Ribbon */}
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' },
                gap: 1.5,
                mb: 2.25,
                p: 1.5,
                borderRadius: 2,
                bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 700,
                    fontSize: '0.68rem',
                    textTransform: 'uppercase'
                  }}>
                  Jurisdictions
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 800,
                    color: "primary.main",
                    mt: 0.25,
                    lineHeight: 1.2
                  }}>
                  {Object.keys(jurisdictions).length || (totalDocs > 0 ? 1 : 0)}
                </Typography>
              </Box>
              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 700,
                    fontSize: '0.68rem',
                    textTransform: 'uppercase'
                  }}>
                  Domains
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 800,
                    color: "secondary.main",
                    mt: 0.25,
                    lineHeight: 1.2
                  }}>
                  {Object.keys(domains).length || (totalDocs > 0 ? 1 : 0)}
                </Typography>
              </Box>
              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 700,
                    fontSize: '0.68rem',
                    textTransform: 'uppercase'
                  }}>
                  Precedents
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 800,
                    mt: 0.25,
                    lineHeight: 1.2
                  }}>
                  {totalDocs}
                </Typography>
              </Box>
              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 700,
                    fontSize: '0.68rem',
                    textTransform: 'uppercase'
                  }}>
                  Audit Coverage
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 800,
                    color: "success.main",
                    mt: 0.25,
                    lineHeight: 1.2
                  }}>
                  {totalDocs > 0 ? `${Math.min(100, Math.round((totalReviews / totalDocs) * 100))}%` : '0%'}
                </Typography>
              </Box>
            </Box>

            <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Indexed Jurisdictions
                </Typography>
                {Object.keys(jurisdictions).length > 0 ? (
                  <Stack spacing={1.25} sx={{ mt: 1.25 }}>
                    {Object.entries(jurisdictions).map(([jur, count]) => {
                      const pct = totalDocs > 0 ? Math.round((count / totalDocs) * 100) : 0;
                      return (
                        <Box key={jur}>
                          <Stack
                            direction="row"
                            sx={{
                              justifyContent: "space-between",
                              alignItems: "center",
                              mb: 0.5
                            }}>
                            <Typography
                              variant="body2"
                              noWrap
                              sx={{
                                fontWeight: 600,
                                mr: 2,
                                minWidth: 0
                              }}>
                              {jur === 'unspecified' ? 'General / Global' : jur}
                            </Typography>
                            <Typography
                              variant="body2"
                              sx={{
                                color: "text.secondary",
                                fontSize: '0.8rem',
                                flexShrink: 0,
                                whiteSpace: 'nowrap'
                              }}>
                              {count} doc{count > 1 ? 's' : ''} ({pct}%)
                            </Typography>
                          </Stack>
                          <LinearProgress variant="determinate" value={pct} sx={{ height: 6, borderRadius: 3 }} />
                        </Box>
                      );
                    })}
                  </Stack>
                ) : (
                  <Typography
                    variant="body2"
                    sx={{
                      color: "text.secondary",
                      mt: 1.25,
                      fontSize: '0.84rem'
                    }}>
                    No jurisdiction data yet. Ingest documents in Knowledge Hub.
                  </Typography>
                )}
              </Box>

              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Contract Domains & Topics
                </Typography>
                {Object.entries(domains).length > 0 || Object.keys(insights.community_topics || {}).length > 0 ? (
                  <Stack
                    direction="row"
                    sx={{
                      flexWrap: "wrap",
                      gap: 0.75,
                      mt: 1.25
                    }}>
                    {Object.entries(domains).map(([dom, count]) => (
                      <Chip
                        key={dom}
                        label={`${dom === 'unspecified' ? 'General' : dom} (${count})`}
                        size="small"
                        color="secondary"
                        variant={isDark ? 'filled' : 'outlined'}
                        sx={{ fontWeight: 600, height: 24, fontSize: '0.72rem' }}
                      />
                    ))}
                    {Object.entries(insights.community_topics || {}).map(([topic, count]) => (
                      <Chip
                        key={topic}
                        label={`#${topic} (${count})`}
                        size="small"
                        variant="outlined"
                        sx={{ fontSize: '0.72rem', fontWeight: 550, height: 24 }}
                      />
                    ))}
                  </Stack>
                ) : (
                  <Typography
                    variant="body2"
                    sx={{
                      color: "text.secondary",
                      mt: 1.25,
                      fontSize: '0.84rem'
                    }}>
                    No domain tags mapped.
                  </Typography>
                )}
              </Box>
            </Box>

            {/* Strategic AI Recommendation - Spanning Full Width */}
            <Box
              sx={{
                mt: 2.25,
                p: 1.75,
                borderRadius: 2.5,
                bgcolor: isDark ? 'rgba(99,102,241,0.08)' : 'rgba(79,70,229,0.04)',
                border: '1px solid',
                borderColor: isDark ? 'rgba(99,102,241,0.3)' : 'rgba(79,70,229,0.2)',
              }}
            >
              <Stack direction="row" spacing={1.5} sx={{
                alignItems: "flex-start"
              }}>
                <AutoAwesomeIcon color="primary" sx={{ fontSize: 18, mt: 0.2, flexShrink: 0 }} />
                <Box>
                  <Typography
                    variant="caption"
                    color="primary"
                    sx={{
                      fontWeight: 750,
                      letterSpacing: "0.04em"
                    }}>
                    STRATEGIC AI RECOMMENDATION
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.25, fontSize: '0.85rem', lineHeight: 1.45 }}>
                    {insights.coverage_gap || 'Coverage appears representative of ingested materials.'}
                  </Typography>
                  {Array.isArray(insights.suggested_new_scenarios) && insights.suggested_new_scenarios.length > 0 && (
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        display: "block",
                        mt: 0.5,
                        fontSize: '0.78rem'
                      }}>
                      Suggested scenario: <b>{insights.suggested_new_scenarios[0]}</b>
                    </Typography>
                  )}
                </Box>
              </Stack>
            </Box>
          </SectionCard>

          {/* Contract Remediation */}
          <SectionCard
            icon={<SecurityIcon color="primary" />}
            title="Contract Remediation"
            action={
              <Button size="small" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/review')} sx={{ textTransform: 'none' }}>
                Open Review Workspace
              </Button>
            }
            sx={{ mb: 3 }}
          >
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', md: 'repeat(5, 1fr)' },
                gap: 1.5,
                p: 1.5,
                borderRadius: 2,
                bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
                border: '1px solid',
                borderColor: 'divider',
                mb: 2,
              }}
            >
              <MiniStat label="High-risk open (KM)" value={highOpen} color={highOpen > 0 ? '#dc2626' : '#16a34a'} />
              <MiniStat label="KM-confirmed" value={kmConfirmed} color="#16a34a" />
              <MiniStat
                label="Manual review (no KM)"
                value={manualReview}
                color={manualReview > 0 ? '#d97706' : '#16a34a'}
              />
              <MiniStat label="Implementation in progress" value={inProgress} color="#d97706" />
              <MiniStat label="Remediated" value={applied} color="#16a34a" />
            </Box>

            {/* KM vs manual-review indicator */}
            <Box sx={{ mb: 2 }}>
              <Stack
                direction="row"
                sx={{
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  mb: 0.5
                }}>
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 800,
                    color: "text.secondary",
                    letterSpacing: "0.05em"
                  }}>
                  KM SUPPORT QUALITY
                </Typography>
                <Typography variant="caption" color={manualReview > 0 ? 'warning.main' : 'success.main'}>
                  <b>{manualReview}</b> of {totalFindings} need manual review ({manualReviewPct}%) · {kmConfirmed} KM-confirmed
                </Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={totalFindings ? Math.min(100, (kmConfirmed / totalFindings) * 100) : 100}
                color={manualReviewPct > 25 ? 'warning' : 'success'}
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  display: "block",
                  mt: 0.6
                }}>
                {manualReview > 0
                  ? 'Manual-review advisories were suggested by the model but lack Knowledge Hub artefact support — they are not counted as confirmed risks.'
                  : 'Confirmed risks are backed by Knowledge Hub artefacts (statutes, precedents, policies).'}
              </Typography>
            </Box>

            {/* Document-span grounding (separate from KM) */}
            <Box sx={{ mb: 2 }}>
              <Stack
                direction="row"
                sx={{
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  mb: 0.5
                }}>
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 800,
                    color: "text.secondary",
                    letterSpacing: "0.05em"
                  }}>
                  DOCUMENT SPAN GROUNDING
                </Typography>
                <Typography variant="caption" color={nonGrounded > 0 ? 'warning.main' : 'success.main'}>
                  <b>{nonGrounded}</b> of {totalFindings} not found in source text ({nonGroundedPct}%)
                </Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={Math.min(100, 100 - nonGroundedPct)}
                color={nonGroundedPct > 10 ? 'warning' : 'success'}
                sx={{ height: 8, borderRadius: 4 }}
              />
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  display: "block",
                  mt: 0.6
                }}>
                {nonGrounded > 0
                  ? 'These excerpts could not be located in the contract text — verify before relying on them.'
                  : 'Every finding excerpt is located in the source contract text.'}
              </Typography>
            </Box>

            {/* Remediation progress */}
            <Box sx={{ mb: 2 }}>
              <Stack
                direction="row"
                sx={{
                  justifyContent: "space-between",
                  alignItems: "baseline",
                  mb: 0.5
                }}>
                <Typography
                  variant="caption"
                  sx={{
                    fontWeight: 800,
                    color: "text.secondary",
                    letterSpacing: "0.05em"
                  }}>
                  REMEDIATION PROGRESS
                </Typography>
                <Typography variant="caption" sx={{
                  color: "text.secondary"
                }}>
                  {applied} of {remediation.actionable ?? 0} proposed changes applied ({progressPct}%)
                  {pendingHighRisk > 0 ? ` · ${pendingHighRisk} audit${pendingHighRisk > 1 ? 's' : ''} still carry open high risk` : ''}
                </Typography>
              </Stack>
              <LinearProgress
                variant="determinate"
                value={Math.min(100, progressPct)}
                color={progressPct >= 70 ? 'success' : 'primary'}
                sx={{ height: 8, borderRadius: 4 }}
              />
            </Box>

            <Stack direction="row" spacing={1} useFlexGap sx={{
              flexWrap: "wrap"
            }}>
              <Button
                variant="contained"
                size="small"
                startIcon={<AutoAwesomeIcon sx={{ fontSize: 16 }} />}
                onClick={openApply}
                sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
              >
                Apply on existing contract
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<FactCheckIcon sx={{ fontSize: 16 }} />}
                onClick={() => navigate('/review')}
                sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
              >
                Track implementation
              </Button>
            </Stack>
          </SectionCard>

          {/* Recent Contracts */}
          <SectionCard
            icon={<MenuBookIcon color="primary" />}
            title="Recently Ingested Contracts"
            action={
              <Button size="small" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/hub')} sx={{ textTransform: 'none' }}>
                View All in Hub
              </Button>
            }
          >
            {recentDocs.length > 0 ? (
              <TableContainer sx={{ mx: -2.5, width: 'calc(100% + 40px)', px: 2.5 }}>
                <Table size="small" sx={{ minWidth: 560 }}>
                  <TableHead>
                    <TableRow sx={{ '& th': { fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' } }}>
                      <TableCell sx={{ color: 'text.secondary' }}>Document Title</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>Type</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>Jurisdiction</TableCell>
                      <TableCell sx={{ color: 'text.secondary' }}>Status</TableCell>
                      <TableCell align="right" sx={{ color: 'text.secondary' }}>Action</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {recentDocs.map((doc) => (
                      <TableRow key={doc.id} hover sx={{ '&:last-child td': { borderBottom: 0 } }}>
                        <TableCell>
                          <Typography variant="body2" sx={{
                            fontWeight: 650
                          }}>
                            {doc.title || doc.filename || 'Untitled Document'}
                          </Typography>
                          {doc.filename && doc.title && (
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                display: "block"
                              }}>
                              {doc.filename}
                            </Typography>
                          )}
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={doc.doc_type || 'contract'}
                            size="small"
                            variant="outlined"
                            sx={{ textTransform: 'capitalize', fontSize: '0.75rem', fontWeight: 550 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" sx={{
                            color: "text.secondary"
                          }}>
                            {doc.jurisdiction || 'Global'}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={doc.status || 'indexed'}
                            size="small"
                            color="success"
                            sx={{ height: 22, fontSize: '0.7rem', fontWeight: 700 }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Button size="small" variant="text" onClick={() => navigate('/hub')} sx={{ textTransform: 'none', py: 0.2, px: 1.5 }}>
                            Inspect
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <EmptyState
                icon={<CloudUploadIcon sx={{ fontSize: 40 }} />}
                title="No documents have been indexed yet."
                body="Upload your first precedent to start building your knowledge library."
                action={
                  <Button variant="contained" startIcon={<CloudUploadIcon />} onClick={() => navigate('/hub')} sx={{ textTransform: 'none' }}>
                    Upload Your First Precedent
                  </Button>
                }
              />
            )}
          </SectionCard>
        </Box>

        {/* Right column */}
        <Box sx={{ minWidth: 0 }}>
          {/* Engine Telemetry */}
          <SectionCard
            icon={<SecurityIcon color="primary" />}
            title="Engine Telemetry"
            sx={{ mb: 3 }}
          >
            <Stack spacing={2.25}>
              <EngineRow
                title="JurisFlow API"
                caption="FastAPI · SQLite ACID Engine"
                chip={
                  <Chip
                    icon={<CheckCircleIcon sx={{ fontSize: '14px !important' }} />}
                    label={healthData?.status === 'ok' ? 'Healthy' : 'Connecting'}
                    size="small"
                    color={healthData?.status === 'ok' ? 'success' : 'warning'}
                    sx={{ fontWeight: 650, height: 24, fontSize: '0.75rem' }}
                  />
                }
              />
              <EngineRow
                title="OCR Ingestion"
                caption={readyData?.ocr_provider === 'tesseract' ? 'Tesseract Engine (0.35s/p)' : 'Dual Vision OCR'}
                chip={
                  <Chip
                    label={readyData?.ocr_enabled ? 'Active' : 'Standby'}
                    size="small"
                    color={readyData?.ocr_enabled ? 'primary' : 'default'}
                    sx={{ fontWeight: 650, height: 24, fontSize: '0.75rem' }}
                  />
                }
              />
              <EngineRow
                title="Vector Database"
                caption={readyData?.vector_provider === 'qdrant' ? 'Qdrant Vector Cluster' : 'Embedded Embeddings'}
                chip={
                  <Chip label="Ready" size="small" color="success" sx={{ fontWeight: 650, height: 24, fontSize: '0.75rem' }} />
                }
              />
              <EngineRow
                title="LLM Reasoning Engine"
                caption={readyData?.llm_provider || 'Ollama / Granite 3.2'}
                chip={
                  <Chip label="Connected" size="small" color="info" sx={{ fontWeight: 650, height: 24, fontSize: '0.75rem' }} />
                }
              />
              <EngineRow
                title="OPA Security Policies"
                caption="Strict Rego RBAC Guardrails"
                chip={
                  <Chip
                    label={readyData?.opa_self_check ? 'Enforced' : 'Verified'}
                    size="small"
                    color="success"
                    sx={{ fontWeight: 650, height: 24, fontSize: '0.75rem' }}
                  />
                }
              />
            </Stack>

            <Button
              fullWidth
              variant="outlined"
              size="small"
              onClick={() => navigate('/settings')}
              sx={{ mt: 3, py: 1, textTransform: 'none', borderRadius: 2 }}
            >
              Configure System &amp; AI Models
            </Button>
          </SectionCard>

          {/* Recent Audits */}
          <SectionCard
            icon={<FactCheckIcon color="primary" />}
            title="Recent Audits"
            action={
              <Button size="small" endIcon={<ArrowForwardIcon />} onClick={() => navigate('/review')} sx={{ textTransform: 'none' }}>
                Review Hub
              </Button>
            }
          >
            {recentReviews.length > 0 ? (
              <Stack spacing={1.5}>
                {recentReviews.map((rev) => {
                  const riskColor = rev.risk_level === 'high' ? 'error' : rev.risk_level === 'medium' ? 'warning' : 'success';
                  return (
                    <Paper
                      key={rev.id}
                      elevation={0}
                      sx={{
                        p: 1.75,
                        borderRadius: 2.5,
                        bgcolor: isDark ? 'rgba(148,163,184,0.05)' : 'rgba(15,23,42,0.02)',
                        border: '1px solid',
                        borderColor: 'divider',
                        '&:hover': { borderColor: 'primary.main' },
                      }}
                    >
                      <Stack
                        direction="row"
                        spacing={2.5}
                        sx={{
                          justifyContent: "space-between",
                          alignItems: "center",
                          mb: 0.5
                        }}>
                        <Typography
                          variant="body2"
                          noWrap
                          title={rev.template_name || 'Standard Contract Review'}
                          sx={{
                            fontWeight: 700,
                            minWidth: 0,
                            flex: 1,
                            pr: 2
                          }}>
                          {rev.template_name || 'Standard Contract Review'}
                        </Typography>
                        <Chip
                          label={`${rev.risk_level || 'low'} risk`}
                          size="small"
                          color={riskColor}
                          sx={{ textTransform: 'capitalize', height: 22, fontSize: '0.7rem', fontWeight: 700, flexShrink: 0, ml: 2 }}
                        />
                      </Stack>
                      <Typography
                        variant="caption"
                        sx={{
                          color: "text.secondary",
                          display: "block",
                          mt: 0.6
                        }}>
                        Status: <b>{rev.status}</b> · Balance score: <b>{rev.balance_score ?? '0.85'}</b>
                      </Typography>
                      {rev.executive_summary && (
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            mt: 0.5,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            lineHeight: 1.5
                          }}>
                          {rev.executive_summary}
                        </Typography>
                      )}
                    </Paper>
                  );
                })}
              </Stack>
            ) : (
              <EmptyState
                icon={<FactCheckIcon sx={{ fontSize: 36 }} />}
                title="No contract reviews generated yet."
                body="Run your first audit from Document Review."
                action={
                  <Button size="small" variant="outlined" onClick={() => navigate('/review')} sx={{ textTransform: 'none' }}>
                    Start New Review
                  </Button>
                }
              />
            )}
          </SectionCard>
        </Box>
      </Box>

      {/* APPLY ON EXISTING CONTRACT */}
      <Dialog open={applyOpen} onClose={() => setApplyOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ pb: 1 }}>
          <Stack direction="row" spacing={1.25} sx={{
            alignItems: "center"
          }}>
            <AutoAwesomeIcon color="primary" />
            <Typography variant="h6" sx={{
              fontWeight: 800
            }}>
              Apply on existing contract
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 2.5 }}>
          {applyResult ? (
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} useFlexGap sx={{
                flexWrap: "wrap"
              }}>
                <Chip
                  size="small"
                  color="success"
                  label={`${applyResult.summary?.applied ?? applyResult.applied ?? 0} risks remediated`}
                  sx={{ fontWeight: 700 }}
                />
                <Chip size="small" variant="outlined" label={`${applyResult.summary?.in_progress ?? 0} in progress`} />
                <Chip
                  size="small"
                  variant="outlined"
                  label={`${applyResult.summary?.not_started ?? 0} awaiting implementation`}
                />
                <Chip
                  size="small"
                  variant="outlined"
                  label={`${applyResult.summary?.amendments ?? 0} amendments merged`}
                />
              </Stack>
              <Box
                component="pre"
                sx={{
                  m: 0,
                  p: 2,
                  maxHeight: 420,
                  overflow: 'auto',
                  borderRadius: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                  bgcolor: isDark ? 'rgba(0,0,0,0.3)' : 'rgba(15,23,42,0.03)',
                  fontSize: '0.76rem',
                  lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}
              >
                {applyResult.markdown}
              </Box>
            </Stack>
          ) : (
            <Stack spacing={2}>
              {applyError && (
                <Alert severity="error" onClose={() => setApplyError('')}>
                  {applyError}
                </Alert>
              )}
              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  lineHeight: 1.6
                }}>
                Pick a contract audit. Every finding that has a proposed redline is merged into
                the source contract text and marked ✅ remediated; findings you left in progress
                keep their ⏳ marker. The merged file is downloadable.
              </Typography>
              <Select
                fullWidth
                size="small"
                value={applyReviewId}
                onChange={(e) => setApplyReviewId(e.target.value)}
                displayEmpty
                aria-label="Contract audit to apply"
              >
                {applyReviews.length === 0 && (
                  <MenuItem value="">No contract audits available yet</MenuItem>
                )}
                {applyReviews.map((r) => (
                  <MenuItem key={r.id} value={r.id}>
                    {r.template_name || 'Contract audit'} · {r.risk_level || 'low'} risk ·{' '}
                    {r.status || 'draft'}
                  </MenuItem>
                ))}
              </Select>
              {applying && <LinearProgress />}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          {applyResult ? (
            <>
              <Button size="small" variant="outlined" onClick={() => setApplyResult(null)} sx={{ textTransform: 'none' }}>
                Back
              </Button>
              <Button size="small" variant="outlined" onClick={downloadApplied} sx={{ textTransform: 'none' }}>
                Download .md
              </Button>
              <Button size="small" variant="contained" onClick={() => setApplyOpen(false)} sx={{ textTransform: 'none' }}>
                Done
              </Button>
            </>
          ) : (
            <>
              <Button size="small" variant="outlined" onClick={() => setApplyOpen(false)} sx={{ textTransform: 'none' }}>
                Cancel
              </Button>
              <Button
                size="small"
                variant="contained"
                disabled={!applyReviewId || applying}
                onClick={runApply}
                startIcon={applying ? <CircularProgress size={14} color="inherit" /> : <AutoAwesomeIcon sx={{ fontSize: 16 }} />}
                sx={{ textTransform: 'none' }}
              >
                {applying ? 'Applying…' : 'Apply & generate'}
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <CircularProgress size={22} />
        </Box>
      )}
    </Box>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <Box>
      <Typography
        variant="caption"
        sx={{
          color: "text.secondary",
          fontWeight: 700,
          fontSize: '0.68rem',
          textTransform: 'uppercase',
          display: 'block'
        }}>
        {label}
      </Typography>
      <Typography
        variant="h6"
        sx={{
          fontWeight: 800,
          color,
          mt: 0.25,
          lineHeight: 1.2
        }}>
        {value}
      </Typography>
    </Box>
  );
}

function EngineRow({ title, caption, chip }) {
  return (
    <Stack
      direction="row"
      spacing={2}
      sx={{
        justifyContent: "space-between",
        alignItems: "center"
      }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" sx={{
          fontWeight: 650
        }}>
          {title}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            color: "text.secondary",
            display: 'block',
            lineHeight: 1.4
          }}>
          {caption}
        </Typography>
      </Box>
      {chip}
    </Stack>
  );
}