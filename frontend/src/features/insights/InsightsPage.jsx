import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import DescriptionIcon from '@mui/icons-material/Description';
import DownloadIcon from '@mui/icons-material/Download';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GavelIcon from '@mui/icons-material/Gavel';
import InsertChartIcon from '@mui/icons-material/InsertChart';
import RefreshIcon from '@mui/icons-material/Refresh';
import ScheduleIcon from '@mui/icons-material/Schedule';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import { EmptyState, PageHeader, SectionCard, StatTile } from '../../components/ui';

const TIMELINE_ORDER = ['immediate', '30_days', '90_days', '180_days'];

const PRIORITY_COLOR = {
  critical: 'error',
  high: 'error',
  medium: 'warning',
  low: 'info',
};

function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString();
}

function downloadMarkdown(report) {
  const blob = new Blob([report.markdown || ''], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `insights-report-${(report.id || 'latest').slice(0, 8)}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function InsightsPage() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api('/analytics/insights-report');
      setReport(res?.report || null);
    } catch (err) {
      setError(err.message || 'Failed to load the insights report.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const generate = useCallback(
    async (force) => {
      setGenerating(true);
      setError('');
      try {
        const res = await api(`/analytics/insights-report/generate?force=${force ? 'true' : 'false'}`, {
          method: 'POST',
        });
        setReport(res?.report || null);
      } catch (err) {
        setError(err.message || 'Report generation failed.');
      } finally {
        setGenerating(false);
      }
    },
    []
  );

  const kpis = report?.source_metrics?.kpis || {};
  const risk = report?.source_metrics?.risk_signals || {};
  const labels = report?.timeline_labels || {};
  const byTimeline = TIMELINE_ORDER.map((key) => ({
    key,
    label: labels[key] || key.replace('_', ' '),
    items: (report?.recommendations || []).filter((r) => r.timeline === key),
  })).filter((t) => t.items.length > 0);

  const bestPractices = report?.best_practices || [];
  const gaps = report?.needs_improvement || [];

  return (
    <Box>
      <PageHeader
        eyebrow="Contract Operations"
        title="Insights Report"
        subtitle="LLM recommender analysis of your dashboard and analytics: recommendations phased by timeline, best practices already followed, and gaps that need improvement."
        icon={<AutoAwesomeIcon fontSize="small" />}
        actions={
          <>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              disabled={!report?.markdown}
              onClick={() => downloadMarkdown(report)}
            >
              Download .md
            </Button>
            <Button
              variant="contained"
              startIcon={generating ? <CircularProgress size={16} color="inherit" /> : <RefreshIcon />}
              disabled={generating}
              onClick={() => generate(Boolean(report))}
            >
              {report ? 'Regenerate' : 'Generate report'}
            </Button>
          </>
        }
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2.5, borderRadius: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {loading ? (
        <Stack
          sx={{
            alignItems: "center",
            py: 8
          }}>
          <CircularProgress />
        </Stack>
      ) : !report ? (
        <EmptyState
          icon={<InsertChartIcon sx={{ fontSize: 46 }} />}
          title="No insights report yet"
          body="Generate a report to turn your current dashboard metrics into phased recommendations, best practices and improvement areas."
          action={
            <Button
              variant="contained"
              startIcon={generating ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
              disabled={generating}
              onClick={() => generate(false)}
            >
              Generate report
            </Button>
          }
        />
      ) : (
        <Stack spacing={2.5}>
          {report.generated_by === 'rules' && (
            <Alert severity="warning" sx={{ borderRadius: 2 }}>
              <b>Rule-based report.</b> The LLM recommender agent was unavailable
              {report.llm_error ? ` (${report.llm_error})` : ''}, so this report was produced from
              deterministic thresholds. Regenerate once the model endpoint is reachable.
            </Alert>
          )}

          <Stack
            direction="row"
            spacing={1}
            useFlexGap
            sx={{
              flexWrap: "wrap",
              alignItems: 'center'
            }}>
            <Chip
              size="small"
              icon={report.generated_by === 'llm' ? <AutoAwesomeIcon /> : <WarningAmberIcon />}
              label={report.generated_by === 'llm' ? 'LLM recommender agent' : 'Rule-based fallback'}
              color={report.generated_by === 'llm' ? 'primary' : 'warning'}
              variant="outlined"
              sx={{ fontWeight: 700, height: 24 }}
            />
            <Chip
              size="small"
              icon={<ScheduleIcon />}
              label={`Generated ${fmtDate(report.generated_at)}`}
              variant="outlined"
              sx={{ height: 24 }}
            />
            {report.cached && <Chip size="small" label="Cached" variant="outlined" sx={{ height: 24 }} />}
            {report.model && (
              <Chip size="small" label={report.model} variant="outlined" sx={{ height: 24 }} />
            )}
          </Stack>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' },
              gap: 2,
            }}
          >
            <StatTile label="Documents" value={kpis.documents ?? 0} icon={<DescriptionIcon />} color="primary.main" />
            <StatTile label="Audits" value={kpis.reviews ?? 0} icon={<FactCheckIcon />} color="info.main" />
            <StatTile
              label="Coverage"
              value={`${risk.coverage_percentage ?? 0}%`}
              icon={<InsertChartIcon />}
              color="warning.main"
            />
            <StatTile
              label="Publish Rate"
              value={`${risk.publish_rate_percentage ?? 0}%`}
              icon={<CheckCircleOutlineIcon />}
              color="success.main"
            />
            <StatTile
              label="Simulations"
              value={kpis.simulations ?? 0}
              icon={<GavelIcon />}
              color="secondary.main"
            />
            <StatTile
              label="Completion"
              value={`${kpis.simulation_completion_rate ?? 0}%`}
              icon={<AutoAwesomeIcon />}
              color="success.main"
            />
          </Box>

          <SectionCard icon={<AutoAwesomeIcon color="primary" />} title="Executive Summary">
            <Typography variant="body1" sx={{ lineHeight: 1.75, color: 'text.secondary' }}>
              {report.executive_summary}
            </Typography>
          </SectionCard>

          <SectionCard
            icon={<ScheduleIcon color="primary" />}
            title="Recommendations by Timeline"
            action={
              <Chip
                size="small"
                label={`${(report.recommendations || []).length} actions`}
                variant="outlined"
                sx={{ height: 24 }}
              />
            }
          >
            <Stack spacing={2.5}>
              {byTimeline.map((timeline) => (
                <Box key={timeline.key}>
                  <Stack
                    direction="row"
                    spacing={1}
                    sx={{
                      alignItems: "center",
                      mb: 1.25
                    }}>
                    <ScheduleIcon fontSize="small" color="action" />
                    <Typography variant="subtitle2" sx={{
                      fontWeight: 800
                    }}>
                      {timeline.label}
                    </Typography>
                    <Chip size="small" label={timeline.items.length} sx={{ height: 20, fontSize: '0.7rem' }} />
                  </Stack>
                  <Stack spacing={1.25}>
                    {timeline.items.map((item, idx) => (
                      <Box
                        key={`${timeline.key}-${idx}`}
                        sx={{
                          p: 1.75,
                          borderRadius: 2,
                          border: '1px solid',
                          borderColor: 'divider',
                          bgcolor: (t) =>
                            t.palette.mode === 'dark' ? 'rgba(148,163,184,0.04)' : 'rgba(15,23,42,0.02)',
                        }}
                      >
                        <Stack
                          direction="row"
                          spacing={1}
                          useFlexGap
                          sx={{
                            alignItems: "center",
                            flexWrap: "wrap",
                            mb: 0.75
                          }}>
                          <Typography variant="subtitle2" sx={{
                            fontWeight: 750
                          }}>
                            {item.title}
                          </Typography>
                          <Chip
                            size="small"
                            label={item.priority}
                            color={PRIORITY_COLOR[item.priority] || 'default'}
                            variant="outlined"
                            sx={{ height: 20, fontSize: '0.66rem', fontWeight: 700, textTransform: 'capitalize' }}
                          />
                          <Chip
                            size="small"
                            label={(item.category || 'operations').replace(/_/g, ' ')}
                            variant="outlined"
                            sx={{ height: 20, fontSize: '0.66rem', textTransform: 'capitalize' }}
                          />
                        </Stack>
                        <Typography
                          variant="body2"
                          sx={{
                            color: "text.secondary",
                            lineHeight: 1.6
                          }}>
                          {item.detail}
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                  {timeline.key !== byTimeline[byTimeline.length - 1].key && <Divider sx={{ mt: 2.5 }} />}
                </Box>
              ))}
            </Stack>
          </SectionCard>

          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' },
              gap: 2.5,
            }}
          >
            <SectionCard
              icon={<CheckCircleOutlineIcon color="success" />}
              title="Best Practices Followed"
              sx={{ borderColor: 'success.light' }}
            >
              <Stack spacing={1.25}>
                {bestPractices.length === 0 && (
                  <Typography variant="body2" sx={{
                    color: "text.secondary"
                  }}>
                    No best practices were identified in this metric pack.
                  </Typography>
                )}
                {bestPractices.map((item, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      p: 1.75,
                      borderRadius: 2,
                      border: '1px solid',
                      borderColor: 'success.light',
                      bgcolor: (t) =>
                        t.palette.mode === 'dark' ? 'rgba(16,185,129,0.07)' : 'rgba(16,185,129,0.05)',
                    }}
                  >
                    <Typography
                      variant="subtitle2"
                      sx={{
                        fontWeight: 750,
                        color: "success.main",
                        mb: 0.5
                      }}>
                      {item.title}
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{
                        color: "text.secondary",
                        lineHeight: 1.6
                      }}>
                      {item.evidence}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </SectionCard>

            <SectionCard
              icon={<WarningAmberIcon color="warning" />}
              title="Needs Improvement"
              sx={{ borderColor: 'warning.light' }}
            >
              <Stack spacing={1.25}>
                {gaps.length === 0 && (
                  <Typography variant="body2" sx={{
                    color: "text.secondary"
                  }}>
                    No improvement areas were identified in this metric pack.
                  </Typography>
                )}
                {gaps.map((item, idx) => (
                  <Box
                    key={idx}
                    sx={{
                      p: 1.75,
                      borderRadius: 2,
                      border: '1px solid',
                      borderColor: 'warning.light',
                      bgcolor: (t) =>
                        t.palette.mode === 'dark' ? 'rgba(245,158,11,0.07)' : 'rgba(245,158,11,0.06)',
                    }}
                  >
                    <Stack
                      direction="row"
                      spacing={1}
                      useFlexGap
                      sx={{
                        alignItems: "center",
                        flexWrap: "wrap",
                        mb: 0.5
                      }}>
                      <Typography variant="subtitle2" sx={{
                        fontWeight: 750
                      }}>
                        {item.title}
                      </Typography>
                      <Chip
                        size="small"
                        label={labels[item.timeline] || item.timeline}
                        sx={{ height: 20, fontSize: '0.66rem' }}
                      />
                    </Stack>
                    <Typography
                      variant="body2"
                      sx={{
                        color: "text.secondary",
                        lineHeight: 1.6
                      }}>
                      {item.gap}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.75, lineHeight: 1.6 }}>
                      <b>Fix:</b> {item.recommendation}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </SectionCard>
          </Box>

          <Typography variant="caption" sx={{
            color: "text.secondary"
          }}>
            Derived from dashboard KPIs, audit risk signals, coverage insights, activity and
            telemetry. Educational and informational only — not legal advice.
          </Typography>
        </Stack>
      )}
    </Box>
  );
}
