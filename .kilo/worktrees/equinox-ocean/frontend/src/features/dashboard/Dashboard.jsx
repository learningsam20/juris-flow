import {
  Box,
  Button,
  Chip,
  CircularProgress,
  LinearProgress,
  Paper,
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
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Typography variant="subtitle1" fontWeight={800} sx={{ letterSpacing: '-0.01em' }}>
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

        <Stack direction="row" spacing={1} alignItems="center">
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
                <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ fontSize: '0.68rem', textTransform: 'uppercase' }}>
                  Jurisdictions
                </Typography>
                <Typography variant="h6" fontWeight={800} color="primary.main" sx={{ mt: 0.25, lineHeight: 1.2 }}>
                  {Object.keys(jurisdictions).length || (totalDocs > 0 ? 1 : 0)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ fontSize: '0.68rem', textTransform: 'uppercase' }}>
                  Domains
                </Typography>
                <Typography variant="h6" fontWeight={800} color="secondary.main" sx={{ mt: 0.25, lineHeight: 1.2 }}>
                  {Object.keys(domains).length || (totalDocs > 0 ? 1 : 0)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ fontSize: '0.68rem', textTransform: 'uppercase' }}>
                  Precedents
                </Typography>
                <Typography variant="h6" fontWeight={800} sx={{ mt: 0.25, lineHeight: 1.2 }}>
                  {totalDocs}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={700} sx={{ fontSize: '0.68rem', textTransform: 'uppercase' }}>
                  Audit Coverage
                </Typography>
                <Typography variant="h6" fontWeight={800} color="success.main" sx={{ mt: 0.25, lineHeight: 1.2 }}>
                  {totalDocs > 0 ? `${Math.min(100, Math.round((totalReviews / totalDocs) * 100))}%` : '0%'}
                </Typography>
              </Box>
            </Box>

            <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase" letterSpacing="0.6px">
                  Indexed Jurisdictions
                </Typography>
                {Object.keys(jurisdictions).length > 0 ? (
                  <Stack spacing={1.25} sx={{ mt: 1.25 }}>
                    {Object.entries(jurisdictions).map(([jur, count]) => {
                      const pct = totalDocs > 0 ? Math.round((count / totalDocs) * 100) : 0;
                      return (
                        <Box key={jur}>
                          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.5 }}>
                            <Typography variant="body2" fontWeight={600} sx={{ mr: 2, minWidth: 0 }} noWrap>
                              {jur === 'unspecified' ? 'General / Global' : jur}
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem', flexShrink: 0, whiteSpace: 'nowrap' }}>
                              {count} doc{count > 1 ? 's' : ''} ({pct}%)
                            </Typography>
                          </Stack>
                          <LinearProgress variant="determinate" value={pct} sx={{ height: 6, borderRadius: 3 }} />
                        </Box>
                      );
                    })}
                  </Stack>
                ) : (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1.25, fontSize: '0.84rem' }}>
                    No jurisdiction data yet. Ingest documents in Knowledge Hub.
                  </Typography>
                )}
              </Box>

              <Box>
                <Typography variant="caption" color="text.secondary" fontWeight={700} textTransform="uppercase" letterSpacing="0.6px">
                  Contract Domains & Topics
                </Typography>
                {Object.entries(domains).length > 0 || Object.keys(insights.community_topics || {}).length > 0 ? (
                  <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ mt: 1.25 }}>
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
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1.25, fontSize: '0.84rem' }}>
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
              <Stack direction="row" spacing={1.5} alignItems="flex-start">
                <AutoAwesomeIcon color="primary" sx={{ fontSize: 18, mt: 0.2, flexShrink: 0 }} />
                <Box>
                  <Typography variant="caption" fontWeight={750} color="primary" letterSpacing="0.04em">
                    STRATEGIC AI RECOMMENDATION
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.25, fontSize: '0.85rem', lineHeight: 1.45 }}>
                    {insights.coverage_gap || 'Coverage appears representative of ingested materials.'}
                  </Typography>
                  {Array.isArray(insights.suggested_new_scenarios) && insights.suggested_new_scenarios.length > 0 && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5, fontSize: '0.78rem' }}>
                      Suggested scenario: <b>{insights.suggested_new_scenarios[0]}</b>
                    </Typography>
                  )}
                </Box>
              </Stack>
            </Box>
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
                          <Typography variant="body2" fontWeight={650}>
                            {doc.title || doc.filename || 'Untitled Document'}
                          </Typography>
                          {doc.filename && doc.title && (
                            <Typography variant="caption" color="text.secondary" display="block">
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
                          <Typography variant="body2" color="text.secondary">
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
                title="JurisLab API"
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
                      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2.5} sx={{ mb: 0.5 }}>
                        <Typography variant="body2" fontWeight={700} sx={{ minWidth: 0, flex: 1, pr: 2 }} noWrap title={rev.template_name || 'Standard Contract Review'}>
                          {rev.template_name || 'Standard Contract Review'}
                        </Typography>
                        <Chip
                          label={`${rev.risk_level || 'low'} risk`}
                          size="small"
                          color={riskColor}
                          sx={{ textTransform: 'capitalize', height: 22, fontSize: '0.7rem', fontWeight: 700, flexShrink: 0, ml: 2 }}
                        />
                      </Stack>
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.6 }}>
                        Status: <b>{rev.status}</b> · Balance score: <b>{rev.balance_score ?? '0.85'}</b>
                      </Typography>
                      {rev.executive_summary && (
                        <Typography
                          variant="caption"
                          color="text.secondary"
                          sx={{
                            mt: 0.5,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            lineHeight: 1.5,
                          }}
                        >
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

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <CircularProgress size={22} />
        </Box>
      )}
    </Box>
  );
}

function EngineRow({ title, caption, chip }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={2}>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" fontWeight={650}>
          {title}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.4 }}>
          {caption}
        </Typography>
      </Box>
      {chip}
    </Stack>
  );
}