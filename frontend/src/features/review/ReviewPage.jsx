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
  DialogContentText,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AssessmentIcon from '@mui/icons-material/Assessment';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import CloseIcon from '@mui/icons-material/Close';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlined';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import FolderSpecialOutlinedIcon from '@mui/icons-material/FolderSpecialOutlined';
import HelpOutlineIcon from '@mui/icons-material/HelpOutlineOutlined';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RuleFolderOutlinedIcon from '@mui/icons-material/RuleFolderOutlined';
import SearchIcon from '@mui/icons-material/Search';
import ShieldIcon from '@mui/icons-material/Shield';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import VisibilityIcon from '@mui/icons-material/Visibility';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../../api/client';
import DocumentUploader from '../../components/DocumentUploader';
import InspectDocumentDialog from '../../components/InspectDocumentDialog';
import { EmptyState, SectionCard } from '../../components/ui';

function getSynthesizedSummary(active) {
  if (active?.executive_summary && active.executive_summary.trim()) {
    return active.executive_summary;
  }
  const findings = active?.findings || [];
  const highRisks = findings.filter((f) => f.risk_level === 'high');
  const medRisks = findings.filter((f) => f.risk_level === 'medium');
  const obligations = findings.filter((f) => f.obligation);

  const parts = [
    `### Executive Audit Summary\n\nComprehensive legal audit completed for **${active?.template_name || 'Legal Contract'}**. A total of **${findings.length} contractual provisions** were systematically extracted and evaluated against jurisdictional risk standards.`,
  ];

  if (highRisks.length > 0) {
    const clauseTypes = [...new Set(highRisks.map((f) => f.clause_type))].join(', ');
    parts.push(
      `🔴 **Critical Risk Exposures (${highRisks.length})**: Significant contractual risk identified in **${clauseTypes}**. These provisions require targeted redlining to mitigate unilateral liabilities or asymmetric termination rights.`
    );
  } else {
    parts.push(`🟢 **Risk Profile**: No critical high-risk clauses were flagged. Provisions generally adhere to standard commercial conventions.`);
  }

  if (medRisks.length > 0) {
    parts.push(`🟡 **Operational Considerations (${medRisks.length})**: Medium-risk clauses require attorney review regarding governance, liability caps, and notice requirements.`);
  }

  if (obligations.length > 0) {
    parts.push(`📋 **Obligation Load (${obligations.length})**: Identified mandatory affirmative covenants and compliance duties that should be indexed into contract lifecycle monitoring.`);
  }

  parts.push(`*Recommendation*: Review flagged high-risk clauses and address proposed redlines prior to formal contract execution.`);
  return parts.join('\n\n');
}

export default function ReviewPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const [docs, setDocs] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [intelligence, setIntelligence] = useState(null);
  const [busyIds, setBusyIds] = useState(() => new Set());
  const [msg, setMsg] = useState('');
  const [msgSeverity, setMsgSeverity] = useState('info');
  const [tab, setTab] = useState(1); // Default to Document repository
  const [active, setActive] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [inspect, setInspect] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedClauseId, setCopiedClauseId] = useState(null);
  const [remediatingId, setRemediatingId] = useState(null);

  const handleCopyClause = (text, id) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedClauseId(id);
    setTimeout(() => setCopiedClauseId(null), 2000);
  };

  const handleProposeChange = async (findingId, stance = 'balanced') => {
    if (!active?.id || !findingId) return;
    setRemediatingId(findingId);
    try {
      const res = await api(`/reviews/${active.id}/findings/${findingId}/propose-change`, {
        method: 'POST',
        body: { stance },
      });
      if (res?.proposed_change) {
        setActive((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            findings: (prev.findings || []).map((f) =>
              f.id === findingId
                ? { ...f, proposed_change: res.proposed_change, change_rationale: res.change_rationale }
                : f
            ),
          };
        });
      }
    } catch {
      /* no-op */
    } finally {
      setRemediatingId(null);
    }
  };

  const [docSearch, setDocSearch] = useState('');
  const [docFilter, setDocFilter] = useState('all'); // 'all' | 'audited' | 'pending'
  const [docCategoryFilter, setDocCategoryFilter] = useState('all'); // 'all' | 'knowledge_artefact' | 'contract_review'
  const [selectedVuln, setSelectedVuln] = useState(null); // Systemic vulnerability details dialog
  const [findingRiskFilter, setFindingRiskFilter] = useState('all'); // 'all' | 'high' | 'medium' | 'low' | 'obligation' | 'manual_review' | 'km_confirmed'
  const [guidelines, setGuidelines] = useState(null);
  const [guidelinesOpen, setGuidelinesOpen] = useState(false);
  const [guidelinesLoading, setGuidelinesLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const refreshReviews = async () => {
    try {
      const [r, intel] = await Promise.all([
        api('/reviews').catch(() => ({ reviews: [] })),
        api('/reviews/intelligence').catch(() => null),
      ]);
      const list = Array.isArray(r?.reviews) ? r.reviews : Array.isArray(r) ? r : [];
      setReviews(list);
      if (intel) setIntelligence(intel);
    } catch {
      /* no-op */
    }
  };

  const refreshDocs = async () => {
    try {
      const d = await api('/documents').catch(() => ({ documents: [] }));
      const list = Array.isArray(d?.documents) ? d.documents : Array.isArray(d) ? d : [];
      setDocs(list);
    } catch {
      /* no-op */
    }
  };

  useEffect(() => {
    Promise.all([refreshDocs(), refreshReviews()]).finally(() => {
      setPageLoading(false);
    });
  }, []);

  const markBusy = (id) => setBusyIds((prev) => new Set(prev).add(id));
  const markDone = (id) =>
    setBusyIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

  const openGuidelines = async () => {
    setGuidelinesOpen(true);
    if (guidelines || guidelinesLoading) return;
    setGuidelinesLoading(true);
    try {
      const res = await api('/reviews/risk-guidelines');
      setGuidelines(res || null);
    } catch (err) {
      setMsg(err?.message || 'Could not load the risk flagging guidelines.');
      setMsgSeverity('error');
    } finally {
      setGuidelinesLoading(false);
    }
  };

  // Remediation tracking: not_started | in_progress | applied (dashboard markers)
  async function handleStatusChange(findingId, status) {
    if (!active?.id || !findingId) return;
    const previous = (active.findings || []).find((f) => f.id === findingId);
    setActive((prev) =>
      prev
        ? {
            ...prev,
            findings: (prev.findings || []).map((f) =>
              f.id === findingId ? { ...f, implementation_status: status } : f
            ),
          }
        : prev
    );
    try {
      await api(`/reviews/${active.id}/findings/${findingId}/implementation-status`, {
        method: 'PATCH',
        body: { status },
      });
      setMsg(`Marked as ${status.replace('_', ' ')}`);
      setMsgSeverity('success');
    } catch (err) {
      setActive((prev) =>
        prev
          ? {
              ...prev,
              findings: (prev.findings || []).map((f) =>
                f.id === findingId
                  ? { ...f, implementation_status: previous?.implementation_status || 'not_started' }
                  : f
              ),
            }
          : prev
      );
      setMsg(err?.message || 'Could not update the implementation status.');
      setMsgSeverity('error');
    }
  }

  async function runReview(id) {
    if (busyIds.has(id)) return;
    markBusy(id);
    setMsg('Analyzing clauses, obligations, and risk levels...');
    setMsgSeverity('info');
    try {
      const created = await api('/reviews', { method: 'POST', body: { document_id: id } });
      let consecutiveErrors = 0;
      const maxErrors = 6;

      const poll = async () => {
        try {
          const job = await api(`/reviews/jobs/${created.job_id}`);
          consecutiveErrors = 0; // reset on successful poll
          if (job.status === 'completed') {
            markDone(id);
            setMsg('Contract review generated successfully.');
            setMsgSeverity('success');
            await refreshReviews();
            const reviewId = job.review_id || job.result?.review_id;
            if (reviewId) {
              const detail = await api(`/reviews/${reviewId}`);
              setActive(detail);
              setActiveTab(0);
              setTab(2); // Jump to Audit reports tab
            }
          } else if (job.status === 'failed') {
            markDone(id);
            setMsg(`Review failed: ${job.error || 'Processing error'}`);
            setMsgSeverity('error');
          } else {
            setTimeout(poll, 1500);
          }
        } catch (e) {
          consecutiveErrors += 1;
          if (consecutiveErrors < maxErrors) {
            // Retry on temporary 404 or network glitch
            setTimeout(poll, 2000);
          } else {
            markDone(id);
            setMsg(`Failed to poll job: ${e.message}`);
            setMsgSeverity('error');
          }
        }
      };
      poll();
    } catch (err) {
      markDone(id);
      setMsg(`Review failed: ${err.message}`);
      setMsgSeverity('error');
    }
  }

  async function openReview(review) {
    try {
      const detail = await api(`/reviews/${review.id}`);
      setInspect(null);
      setActive(detail);
      setActiveTab(0);
      setTab(2); // Switch to Audit reports tab
    } catch (err) {
      setMsg(`Failed to load review: ${err.message}`);
      setMsgSeverity('error');
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.kind === 'doc') {
        await api(`/documents/${deleteTarget.id}`, { method: 'DELETE' });
        setMsg('Document deleted successfully.');
        if (inspect?.docId === deleteTarget.id) setInspect(null);
        await Promise.all([refreshDocs(), refreshReviews()]);
      } else {
        await api(`/reviews/${deleteTarget.id}`, { method: 'DELETE' });
        if (active?.id === deleteTarget.id) setActive(null);
        setMsg('Review successfully deleted.');
        await refreshReviews();
      }
      setMsgSeverity('success');
      setDeleteTarget(null);
    } catch (err) {
      setMsg(`Failed to delete: ${err.message}`);
      setMsgSeverity('error');
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleToggleDocCategory(doc) {
    const current = (doc.document_category || doc.doc_category) === 'contract_review' ? 'contract_review' : 'knowledge_artefact';
    const next = current === 'contract_review' ? 'knowledge_artefact' : 'contract_review';
    try {
      await api(`/documents/${doc.id}`, {
        method: 'PATCH',
        body: { doc_category: next },
      });
      setDocs((prev) =>
        prev.map((d) => (d.id === doc.id ? { ...d, document_category: next, doc_category: next } : d))
      );
      setMsg(`Reclassified "${doc.title || doc.filename}" as ${next === 'contract_review' ? 'Contract Review' : 'Knowledge Artefact'}`);
      setMsgSeverity('success');
    } catch (err) {
      setMsg(`Failed to reclassify document: ${err.message}`);
      setMsgSeverity('error');
    }
  }

  function handleCopyReport() {
    if (!active?.markdown_report) return;
    navigator.clipboard.writeText(active.markdown_report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  }

  const safeDocs = Array.isArray(docs) ? docs : [];
  const safeReviews = Array.isArray(reviews) ? reviews : [];
  const docMap = Object.fromEntries(safeDocs.map((d) => [d.id, d.title || d.filename || d.id]));

  const getRiskChip = (level) => {
    const l = (level || 'low').toLowerCase();
    const cfg =
      l === 'high'
        ? { label: 'High Risk', color: 'error' }
        : l === 'medium'
        ? { label: 'Medium Risk', color: 'warning' }
        : { label: 'Low Risk', color: 'success' };
    return (
      <Chip
        label={cfg.label}
        size="small"
        color={cfg.color}
        variant="outlined"
        sx={{
          fontWeight: 700,
          height: 22,
          fontSize: '0.7rem',
          borderRadius: 1.25,
          lineHeight: '20px',
        }}
      />
    );
  };

  // Base documents matching search & category
  const baseCategoryDocs = safeDocs.filter((d) => {
    const matchesSearch =
      !docSearch ||
      (d.title || '').toLowerCase().includes(docSearch.toLowerCase()) ||
      (d.filename || '').toLowerCase().includes(docSearch.toLowerCase()) ||
      (d.jurisdiction || '').toLowerCase().includes(docSearch.toLowerCase()) ||
      (d.domain || '').toLowerCase().includes(docSearch.toLowerCase());
    if (!matchesSearch) return false;

    const cat =
      d.document_category ||
      d.doc_category ||
      (['contract', 'agreement', 'nda', 'lease'].includes(d.doc_type)
        ? 'contract_review'
        : 'knowledge_artefact');
    if (docCategoryFilter !== 'all' && cat !== docCategoryFilter) {
      return false;
    }
    return true;
  });

  const auditedDocsCount = baseCategoryDocs.filter((d) =>
    safeReviews.some((r) => String(r.document_id) === String(d.id))
  ).length;

  const pendingDocsCount = baseCategoryDocs.length - auditedDocsCount;

  // Filtered documents for repository grid
  const filteredDocs = baseCategoryDocs.filter((d) => {
    const hasAudit = safeReviews.some((r) => String(r.document_id) === String(d.id));
    if (docFilter === 'audited') return hasAudit;
    if (docFilter === 'pending') return !hasAudit;
    return true;
  });

  if (pageLoading) {
    return (
      <Box sx={{ width: '100%', py: 14, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress size={42} thickness={4} />
        <Typography
          variant="body2"
          sx={{
            color: "text.secondary",
            mt: 2.5,
            fontWeight: 650,
            letterSpacing: '0.02em'
          }}>
          Loading document repository &amp; audit intelligence...
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', pb: 4 }}>
      {/* Global Status Message */}
      {msg && (
        <Alert severity={msgSeverity} onClose={() => setMsg('')} sx={{ mb: 2, borderRadius: 2 }}>
          {msg}
        </Alert>
      )}

      {/* Modern Compact Navigation Tabs (No bulky PageHeader) */}
      <Paper
        elevation={0}
        variant="outlined"
        sx={{
          mb: 2.5,
          borderRadius: 3,
          bgcolor: 'background.paper',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          px: { xs: 1, sm: 2 },
          py: 0.5,
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Tabs
          value={tab}
          onChange={(_, val) => setTab(val)}
          sx={{ '& .MuiTab-root': { py: 1.5, minHeight: 48 } }}
          aria-label="Document review key tabs"
        >
          <Tab
            label="Upload"
            icon={<CloudUploadIcon />}
            iconPosition="start"
            sx={{ textTransform: 'none', fontWeight: 650, fontSize: '0.9rem' }}
          />
          <Tab
            label={`Document repository (${docs.length})`}
            icon={<InsertDriveFileIcon />}
            iconPosition="start"
            sx={{ textTransform: 'none', fontWeight: 650, fontSize: '0.9rem' }}
          />
          <Tab
            label={`Audit reports (${reviews.length})`}
            icon={<FactCheckIcon />}
            iconPosition="start"
            sx={{ textTransform: 'none', fontWeight: 650, fontSize: '0.9rem' }}
          />
        </Tabs>

        {busyIds.size > 0 && (
          <Stack
            direction="row"
            spacing={1}
            sx={{
              alignItems: "center",
              pr: 1.5
            }}>
            <CircularProgress size={16} />
            <Typography variant="caption" color="primary" sx={{
              fontWeight: 650
            }}>
              {busyIds.size === 1 ? 'Running 1 audit...' : `Running ${busyIds.size} audits...`}
            </Typography>
          </Stack>
        )}
      </Paper>

      {/* TAB 0: UPLOAD */}
      {tab === 0 && (
        <SectionCard
          icon={<CloudUploadIcon color="primary" />}
          title="Upload Documents"
          action={
            <Chip
              label={`${docs.length} contracts currently indexed`}
              size="small"
              color="primary"
              variant="outlined"
              sx={{ fontWeight: 650 }}
            />
          }
        >
          <Typography
            variant="body2"
            sx={{
              color: "text.secondary",
              mb: 2.5
            }}>
            Upload legal contracts, schedules, or entire folders. Files will be parsed, chunked, and indexed with
            semantic vectors for instant search and automated audit analysis.
          </Typography>
          <DocumentUploader
            onUploaded={() => {
              refreshDocs();
              setTab(1); // Switch to Document repository upon upload
            }}
          />
        </SectionCard>
      )}

      {/* TAB 1: DOCUMENT REPOSITORY (Grid with 1-click jump to audit report) */}
      {tab === 1 && (
        <Box>
          {/* Controls Bar: Search & Status Filters */}
          <Paper
            elevation={0}
            variant="outlined"
            sx={{
              p: 1.5,
              mb: 2.5,
              borderRadius: 2.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 1.5,
            }}
          >
            <TextField
              size="small"
              placeholder="Search documents by title, filename, jurisdiction..."
              value={docSearch}
              onChange={(e) => setDocSearch(e.target.value)}
              sx={{ minWidth: { xs: '100%', sm: 320 }, bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)' }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                }
              }}
            />

            <Stack
              direction="row"
              spacing={0.75}
              sx={{
                alignItems: "center",
                flexWrap: "wrap",
                gap: 0.75
              }}>
              <Chip
                icon={<LayersOutlinedIcon sx={{ fontSize: '13px !important' }} />}
                label="All Types"
                size="small"
                onClick={() => setDocCategoryFilter('all')}
                color={docCategoryFilter === 'all' ? 'primary' : 'default'}
                variant={docCategoryFilter === 'all' ? 'filled' : 'outlined'}
                sx={{ fontWeight: 650, cursor: 'pointer', height: 22, fontSize: '0.7rem', borderRadius: 1.25 }}
              />
              <Chip
                icon={<DescriptionOutlinedIcon sx={{ fontSize: '13px !important' }} />}
                label="Contracts"
                size="small"
                onClick={() => setDocCategoryFilter('contract_review')}
                color={docCategoryFilter === 'contract_review' ? 'info' : 'default'}
                variant={docCategoryFilter === 'contract_review' ? 'filled' : 'outlined'}
                sx={{ fontWeight: 650, cursor: 'pointer', height: 22, fontSize: '0.7rem', borderRadius: 1.25 }}
              />
              <Chip
                icon={<FolderSpecialOutlinedIcon sx={{ fontSize: '13px !important' }} />}
                label="Knowledge Base"
                size="small"
                onClick={() => setDocCategoryFilter('knowledge_artefact')}
                color={docCategoryFilter === 'knowledge_artefact' ? 'success' : 'default'}
                variant={docCategoryFilter === 'knowledge_artefact' ? 'filled' : 'outlined'}
                sx={{ fontWeight: 650, cursor: 'pointer', height: 22, fontSize: '0.7rem', borderRadius: 1.25 }}
              />

              <Divider orientation="vertical" flexItem sx={{ mx: 0.5, height: 16, alignSelf: 'center' }} />

              <Chip
                icon={<RuleFolderOutlinedIcon sx={{ fontSize: '13px !important' }} />}
                label={`All (${baseCategoryDocs.length})`}
                size="small"
                onClick={() => setDocFilter('all')}
                color={docFilter === 'all' ? 'secondary' : 'default'}
                variant={docFilter === 'all' ? 'filled' : 'outlined'}
                sx={{ fontWeight: 650, cursor: 'pointer', height: 22, fontSize: '0.7rem', borderRadius: 1.25 }}
              />
              <Chip
                icon={<CheckCircleOutlineIcon sx={{ fontSize: '13px !important' }} />}
                label={`Audited (${auditedDocsCount})`}
                size="small"
                onClick={() => setDocFilter('audited')}
                color={docFilter === 'audited' ? 'secondary' : 'default'}
                variant={docFilter === 'audited' ? 'filled' : 'outlined'}
                sx={{ fontWeight: 650, cursor: 'pointer', height: 22, fontSize: '0.7rem', borderRadius: 1.25 }}
              />
              <Chip
                icon={<HourglassEmptyIcon sx={{ fontSize: '13px !important' }} />}
                label={`Pending (${pendingDocsCount})`}
                size="small"
                onClick={() => setDocFilter('pending')}
                color={docFilter === 'pending' ? 'secondary' : 'default'}
                variant={docFilter === 'pending' ? 'filled' : 'outlined'}
                sx={{ fontWeight: 650, cursor: 'pointer', height: 22, fontSize: '0.7rem', borderRadius: 1.25 }}
              />

              <Button
                size="small"
                variant="outlined"
                startIcon={<CloudUploadIcon sx={{ fontSize: 13 }} />}
                onClick={() => setTab(0)}
                sx={{ textTransform: 'none', ml: 0.5, borderRadius: 1.25, height: 22, fontSize: '0.7rem', px: 1.2 }}
              >
                Upload New
              </Button>
            </Stack>
          </Paper>

          {filteredDocs.length === 0 ? (
            <EmptyState
              icon={<InsertDriveFileIcon sx={{ fontSize: 48 }} />}
              title={docs.length === 0 ? 'No documents in repository' : 'No matching documents found'}
              body={
                docs.length === 0 ? (
                  <span>
                    Upload contracts in the <b>Upload</b> tab to populate your repository.
                  </span>
                ) : (
                  'Try adjusting your search query or status filter.'
                )
              }
              action={
                docs.length === 0 && (
                  <Button variant="contained" startIcon={<CloudUploadIcon />} onClick={() => setTab(0)} sx={{ mt: 1 }}>
                    Go to Upload
                  </Button>
                )
              }
            />
          ) : (
            <Grid container spacing={2.5}>
              {filteredDocs.map((d) => {
                const docReports = safeReviews.filter((r) => String(r.document_id) === String(d.id));
                const latestReport = docReports[0];
                const isAudited = docReports.length > 0;
                const isReviewing = busyIds.has(d.id);

                return (
                  <Grid key={d.id} sx={{ display: 'flex' }} size={{xs: 12, sm: 6, lg: 4}}>
                    <Card
                      elevation={0}
                      sx={{
                        width: '100%',
                        height: '100%',
                        minHeight: 285,
                        borderRadius: 3,
                        border: '1px solid',
                        borderColor: isAudited && latestReport.risk_level === 'high' ? 'error.light' : 'divider',
                        display: 'flex',
                        flexDirection: 'column',
                        transition: 'all 0.18s ease-in-out',
                        bgcolor: 'background.paper',
                        '&:hover': {
                          borderColor: 'primary.main',
                          boxShadow: isDark
                            ? '0 8px 24px -10px rgba(99,102,241,0.3)'
                            : '0 8px 24px -10px rgba(79,70,229,0.2)',
                          transform: 'translateY(-2px)',
                        },
                      }}
                    >
                      <CardContent sx={{ p: 2.25, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                        {/* Top Header: Title on Left, Risk Badge on Right */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1.5, mb: 0.75 }}>
                          <Box sx={{ minWidth: 0, flex: 1 }}>
                            <Typography
                              variant="subtitle1"
                              title={d.title || d.filename}
                              sx={{
                                fontWeight: 750,
                                lineHeight: 1.3,
                                fontSize: '0.92rem',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                minHeight: '2.6em'
                              }}>
                              {d.title || d.filename || 'Untitled Contract'}
                            </Typography>
                          </Box>
                          <Box sx={{ flexShrink: 0, mt: 0.25 }}>
                            {isAudited ? (
                              getRiskChip(latestReport.risk_level)
                            ) : (
                              <Chip
                                label="Pending Audit"
                                size="small"
                                variant="outlined"
                                sx={{
                                  fontWeight: 650,
                                  fontSize: '0.7rem',
                                  height: 22,
                                  color: 'text.secondary',
                                  borderColor: 'divider',
                                  borderRadius: 1.25,
                                  lineHeight: '20px',
                                }}
                              />
                            )}
                          </Box>
                        </Box>

                        {/* Document Description immediately following title */}
                        <Typography
                          variant="body2"
                          title={d.description || d.filename || ''}
                          sx={{
                            color: "text.secondary",
                            fontSize: '0.78rem',
                            lineHeight: 1.4,
                            display: '-webkit-box',
                            WebkitLineClamp: 1,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            minHeight: '1.4em',
                            mb: 1.25
                          }}>
                          {d.description || (d.filename && d.filename !== d.title ? d.filename : 'Precedent document ready for automated clause review')}
                        </Typography>

                        {/* Metadata Tags: Type, Jurisdiction, Domain, Size */}
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.75, mb: 2, minHeight: 48, alignContent: 'flex-start' }}>
                          <Chip
                            size="small"
                            label={d.doc_type ? `Type: ${d.doc_type.toUpperCase()}` : 'Type: CONTRACT'}
                            sx={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              height: 22,
                              bgcolor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                              color: 'text.secondary',
                              borderRadius: 1.25,
                            }}
                          />
                          <Chip
                            size="small"
                            label={`Jurisdiction: ${d.jurisdiction || 'Global'}`}
                            variant="outlined"
                            color="primary"
                            sx={{
                              fontSize: '0.7rem',
                              height: 22,
                              textTransform: 'capitalize',
                              borderRadius: 1.25,
                              lineHeight: '20px',
                            }}
                          />
                          <Chip
                            size="small"
                            label={`Domain: ${d.domain ? d.domain.replace(/_/g, ' ') : 'commercial'}`}
                            variant="outlined"
                            sx={{
                              fontSize: '0.7rem',
                              height: 22,
                              textTransform: 'capitalize',
                              borderRadius: 1.25,
                              lineHeight: '20px',
                            }}
                          />
                          {d.size_bytes && (
                            <Chip
                              size="small"
                              label={`Size: ${Math.round(d.size_bytes / 1024)} KB`}
                              variant="outlined"
                              sx={{
                                fontSize: '0.68rem',
                                height: 22,
                                color: 'text.secondary',
                                borderRadius: 1.25,
                                lineHeight: '20px',
                              }}
                            />
                          )}
                        </Box>

                        {/* Telemetry / Status Box: Fixed exact height (46px) so all cards are same sized */}
                        {isAudited ? (
                          <Box
                            sx={{
                              mt: 'auto',
                              height: 46,
                              px: 2,
                              borderRadius: 2,
                              bgcolor: isDark ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
                              border: '1px solid',
                              borderColor: 'divider',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              boxSizing: 'border-box',
                            }}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="caption"
                                sx={{
                                  color: "text.secondary",
                                  fontSize: '0.68rem',
                                  fontWeight: 750,
                                  letterSpacing: '0.04em'
                                }}>
                                BALANCE SCORE:
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: 850,
                                  color: "primary.main",
                                  fontSize: '0.9rem'
                                }}>
                                {latestReport.balance_score !== undefined && latestReport.balance_score !== null ? latestReport.balance_score : '0.85'}
                              </Typography>
                            </Box>

                            <Divider orientation="vertical" flexItem sx={{ height: 18, alignSelf: 'center', mx: 0.5 }} />

                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="caption"
                                sx={{
                                  color: "text.secondary",
                                  fontSize: '0.68rem',
                                  fontWeight: 750,
                                  letterSpacing: '0.04em'
                                }}>
                                OBLIGATIONS:
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: 850,
                                  fontSize: '0.9rem'
                                }}>
                                {latestReport.obligation_load ?? 0}
                              </Typography>
                            </Box>
                          </Box>
                        ) : (
                          <Box
                            sx={{
                              mt: 'auto',
                              height: 46,
                              px: 2,
                              borderRadius: 2,
                              bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.015)',
                              border: '1px dashed',
                              borderColor: 'divider',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              boxSizing: 'border-box',
                            }}
                          >
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                fontStyle: 'italic',
                                fontSize: '0.74rem'
                              }}>
                              Pending audit · Run clause analysis below
                            </Typography>
                          </Box>
                        )}
                      </CardContent>

                      <Divider />

                      {/* Card Footer: Exact 48px height across all cards, borderless action buttons */}
                      <Box sx={{ height: 48, px: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', boxSizing: 'border-box' }}>
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            fontSize: '0.72rem'
                          }}>
                          {d.created_at ? new Date(d.created_at).toLocaleDateString() : 'Indexed'}
                        </Typography>

                        <Stack direction="row" spacing={0.5} sx={{
                          alignItems: "center"
                        }}>
                          {isAudited ? (
                            <Tooltip title="View Full Audit Report">
                              <IconButton
                                size="small"
                                color="primary"
                                onClick={() => openReview(latestReport)}
                                sx={{
                                  bgcolor: isDark ? 'rgba(99,102,241,0.12)' : 'rgba(79,70,229,0.08)',
                                  '&:hover': { bgcolor: 'primary.main', color: '#fff' },
                                }}
                                aria-label="View audit report"
                              >
                                <FactCheckIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          ) : (
                            <Tooltip title={isReviewing ? 'Running Audit…' : 'Run Automated Audit'}>
                              <span>
                                <IconButton
                                  size="small"
                                  color="primary"
                                  disabled={isReviewing}
                                  onClick={() => runReview(d.id)}
                                  sx={{
                                    bgcolor: 'primary.main',
                                    color: '#fff',
                                    '&:hover': { bgcolor: 'primary.dark' },
                                    '&.Mui-disabled': { bgcolor: 'action.disabledBackground' },
                                  }}
                                  aria-label="Run automated audit"
                                >
                                  {isReviewing ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon fontSize="small" />}
                                </IconButton>
                              </span>
                            </Tooltip>
                          )}

                          <Tooltip title="Inspect Raw Chunks & Text">
                            <IconButton
                              size="small"
                              onClick={() => setInspect({ docId: d.id, docHint: d.title, filenameHint: d.filename })}
                              sx={{
                                color: 'text.secondary',
                                '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
                              }}
                              aria-label="Inspect document"
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>

                          <Tooltip title="Delete Document">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => setDeleteTarget({ kind: 'doc', id: d.id, name: d.title || d.filename || 'this document' })}
                              sx={{
                                color: 'error.main',
                                '&:hover': { bgcolor: 'error.lighter' },
                              }}
                              aria-label="Delete document"
                            >
                              <DeleteOutlineIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Stack>
                      </Box>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          )}
        </Box>
      )}

      {/* TAB 2: AUDIT REPORTS & CROSS-REPORT INTELLIGENCE */}
      {tab === 2 && (
        <Box>
          {/* Cross-Report Aggregate Intelligence Banner */}
          {intelligence && (
            <Paper
              elevation={0}
              sx={{
                p: { xs: 2, md: 3 },
                mb: 3,
                borderRadius: 3,
                border: '1px solid',
                borderColor: isDark ? 'rgba(129,140,248,0.35)' : 'rgba(79,70,229,0.2)',
                background: isDark
                  ? 'linear-gradient(135deg, rgba(23,32,58,0.95) 0%, rgba(49,46,129,0.45) 100%)'
                  : 'linear-gradient(135deg, #f5f7ff 0%, #eef2ff 60%, #e0e7ff 100%)',
              }}
            >
              <Stack
                direction="row"
                sx={{
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: 1.5,
                  mb: 2
                }}>
                <Stack direction="row" spacing={1.25} sx={{
                  alignItems: "center"
                }}>
                  <AssessmentIcon color="primary" sx={{ fontSize: 26 }} />
                  <Box>
                    <Typography
                      variant="h6"
                      sx={{
                        fontWeight: 800,
                        letterSpacing: '-0.01em',
                        lineHeight: 1.2
                      }}>
                      Portfolio Audit Intelligence
                    </Typography>
                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      Synthesized cross-document analysis across all {intelligence.total_reviews} completed contract audits.
                    </Typography>
                  </Box>
                </Stack>

                <Chip
                  icon={<ShieldIcon fontSize="small" />}
                  label={`Portfolio Status: ${intelligence.health_status}`}
                  color={intelligence.risk_distribution.high > 0 ? 'error' : 'success'}
                  variant="filled"
                  sx={{ fontWeight: 700, fontSize: '0.76rem' }}
                />
              </Stack>

              {/* Portfolio Key Metrics Grid */}
              <Grid container spacing={2} sx={{ mb: 2.5 }}>
                <Grid size={{xs: 6, sm: 3}}>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.75,
                      borderRadius: 2.5,
                      bgcolor: isDark ? 'rgba(15,23,42,0.6)' : 'rgba(255,255,255,0.7)',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontWeight: 650,
                        display: "block"
                      }}>
                      AUDIT COVERAGE
                    </Typography>
                    <Typography
                      variant="h5"
                      sx={{
                        fontWeight: 800,
                        color: "primary.main",
                        mt: 0.5
                      }}>
                      {intelligence.coverage_percentage}%
                    </Typography>
                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      {intelligence.audited_documents} of {intelligence.total_documents} contracts reviewed
                    </Typography>
                  </Paper>
                </Grid>

                <Grid size={{xs: 6, sm: 3}}>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.75,
                      borderRadius: 2.5,
                      bgcolor: isDark ? 'rgba(15,23,42,0.6)' : 'rgba(255,255,255,0.7)',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontWeight: 650,
                        display: "block"
                      }}>
                      AVG BALANCE SCORE
                    </Typography>
                    <Typography
                      variant="h5"
                      sx={{
                        fontWeight: 800,
                        mt: 0.5
                      }}>
                      {intelligence.avg_balance_score}
                    </Typography>
                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      {intelligence.avg_balance_score >= 0.75 ? 'Healthy bilateral equity' : 'One-sided contractual burden'}
                    </Typography>
                  </Paper>
                </Grid>

                <Grid size={{xs: 6, sm: 3}}>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.75,
                      borderRadius: 2.5,
                      bgcolor: isDark ? 'rgba(15,23,42,0.6)' : 'rgba(255,255,255,0.7)',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontWeight: 650,
                        display: "block"
                      }}>
                      ACTIVE OBLIGATIONS
                    </Typography>
                    <Typography
                      variant="h5"
                      sx={{
                        fontWeight: 800,
                        mt: 0.5
                      }}>
                      {intelligence.total_obligations}
                    </Typography>
                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      Avg {intelligence.avg_obligations_per_doc} obligations per contract
                    </Typography>
                  </Paper>
                </Grid>

                <Grid size={{xs: 6, sm: 3}}>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1.75,
                      borderRadius: 2.5,
                      bgcolor: isDark ? 'rgba(15,23,42,0.6)' : 'rgba(255,255,255,0.7)',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontWeight: 650,
                        display: "block"
                      }}>
                      RISK DISTRIBUTION
                    </Typography>
                    <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          color: "error.main",
                          fontWeight: 750
                        }}>
                        {intelligence.risk_distribution.high} High
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          color: "warning.main",
                          fontWeight: 750
                        }}>
                        {intelligence.risk_distribution.medium} Med
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          color: "success.main",
                          fontWeight: 750
                        }}>
                        {intelligence.risk_distribution.low} Low
                      </Typography>
                    </Stack>
                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      Tiered risk classifications
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              {/* Cross-Document Systemic Vulnerabilities */}
              {intelligence.top_vulnerabilities?.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{
                      fontWeight: 750,
                      mb: 1,
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em'
                    }}>
                    Top Systemic Clause Vulnerabilities Across Corpus
                  </Typography>
                  <Grid container spacing={1.5}>
                    {intelligence.top_vulnerabilities.map((vuln) => (
                      <Grid key={vuln.clause_type} sx={{ display: 'flex' }} size={{xs: 12, sm: 6, md: 3}}>
                        <Card
                          elevation={0}
                          onClick={() => setSelectedVuln(vuln)}
                          sx={{
                            p: 1.75,
                            width: '100%',
                            borderRadius: 2.5,
                            bgcolor: isDark ? 'rgba(15,23,42,0.5)' : '#ffffff',
                            border: '1px solid',
                            borderColor: vuln.high_risk > 0 ? 'error.light' : 'divider',
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
                            transition: 'all 0.18s ease-in-out',
                            '&:hover': {
                              borderColor: 'primary.main',
                              transform: 'translateY(-2px)',
                              boxShadow: isDark
                                ? '0 6px 18px -6px rgba(99,102,241,0.25)'
                                : '0 6px 18px -6px rgba(79,70,229,0.18)',
                            },
                          }}
                        >
                          <Box>
                            <Stack
                              direction="row"
                              sx={{
                                justifyContent: "space-between",
                                alignItems: "center",
                                mb: 1
                              }}>
                              <Typography
                                variant="subtitle2"
                                sx={{
                                  fontWeight: 750,
                                  textTransform: 'capitalize'
                                }}>
                                {vuln.clause_type ? vuln.clause_type.replace(/_/g, ' ') : 'General'}
                              </Typography>
                              {vuln.high_risk > 0 ? (
                                <Chip label={`${vuln.high_risk} High Risk`} size="small" color="error" sx={{ height: 20, fontSize: '0.68rem', fontWeight: 700 }} />
                              ) : (
                                <Chip label={`${vuln.total} flags`} size="small" variant="outlined" sx={{ height: 20, fontSize: '0.68rem', fontWeight: 600 }} />
                              )}
                            </Stack>
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                mt: 0.75,
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                lineHeight: 1.4,
                                fontSize: '0.74rem',
                                minHeight: '2.8em',
                                mb: 1
                              }}>
                              {vuln.sample_explanation || 'Identified cross-contract compliance or risk variance in precedents.'}
                            </Typography>
                          </Box>
                          <Box sx={{ mt: 'auto', pt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px dashed', borderColor: 'divider' }}>
                            <Typography
                              variant="caption"
                              sx={{
                                color: "primary.main",
                                fontWeight: 650,
                                fontSize: '0.72rem'
                              }}>
                              Inspect details &amp; contracts →
                            </Typography>
                            <Chip label={`${vuln.total} flags`} size="small" sx={{ height: 18, fontSize: '0.65rem' }} />
                          </Box>
                        </Card>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
            </Paper>
          )}

          {/* Generated Audits List */}
          <SectionCard
            icon={<FactCheckIcon color="primary" />}
            title={`Individual Audit Reports (${reviews.length})`}
            action={
              reviews.length > 0 && (
                <Chip
                  icon={<TrendingUpIcon fontSize="small" />}
                  label="Click any report to view comprehensive findings"
                  size="small"
                  variant="outlined"
                  sx={{ fontWeight: 600, fontSize: '0.72rem' }}
                />
              )
            }
          >
            {reviews.length === 0 ? (
              <EmptyState
                icon={<FactCheckIcon sx={{ fontSize: 44 }} />}
                title="No audit reports generated yet."
                body={
                  <span>
                    Head over to <b>Document repository</b> and click <b>Run Audit</b> on any contract.
                  </span>
                }
                action={
                  <Button variant="contained" onClick={() => setTab(1)} sx={{ mt: 1 }}>
                    Go to Document Repository
                  </Button>
                }
              />
            ) : (
              <Stack spacing={1.5}>
                {reviews.map((r) => {
                  const findingsCount = r.findings_count ?? (r.findings ? r.findings.length : 0);
                  const isSelected = active?.id === r.id;
                  return (
                    <Card
                      key={r.id}
                      elevation={0}
                      onClick={() => openReview(r)}
                      sx={{
                        borderRadius: 2.5,
                        border: '1px solid',
                        borderColor: isSelected ? 'primary.main' : 'divider',
                        bgcolor: isSelected
                          ? isDark
                            ? 'rgba(99,102,241,0.1)'
                            : 'rgba(79,70,229,0.05)'
                          : isDark
                          ? 'rgba(148,163,184,0.04)'
                          : '#fff',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        '&:hover': {
                          borderColor: 'primary.main',
                          boxShadow: isDark
                            ? '0 6px 18px -6px rgba(99,102,241,0.25)'
                            : '0 6px 18px -6px rgba(79,70,229,0.18)',
                        },
                      }}
                    >
                      <CardContent sx={{ p: 2 }}>
                        <Stack
                          direction="row"
                          sx={{
                            justifyContent: "space-between",
                            alignItems: "center",
                            flexWrap: "wrap",
                            gap: 1
                          }}>
                          <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                            <Typography variant="subtitle1" noWrap sx={{
                              fontWeight: 750
                            }}>
                              {r.template_name || 'Automated Legal Risk Audit'}
                            </Typography>
                            <Typography
                              variant="caption"
                              noWrap
                              sx={{
                                color: "text.secondary",
                                display: "block"
                              }}>
                              Document: <b>{docMap[r.document_id] || 'Contract'}</b>
                              {r.generated_at && ` · ${new Date(r.generated_at).toLocaleDateString()}`}
                            </Typography>
                          </Box>

                          <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                              alignItems: "center",
                              flexWrap: "wrap"
                            }}>
                            {getRiskChip(r.risk_level)}
                            <Chip
                              label={`Obligations: ${r.obligation_load ?? 0}`}
                              size="small"
                              variant="outlined"
                              sx={{ height: 22, fontSize: '0.72rem', fontWeight: 600 }}
                            />
                            <Chip
                              label={`${findingsCount} finding${findingsCount !== 1 ? 's' : ''}`}
                              size="small"
                              variant="outlined"
                              sx={{ height: 22, fontSize: '0.72rem', fontWeight: 550 }}
                            />
                          </Stack>

                          <Stack direction="row" spacing={1} onClick={(e) => e.stopPropagation()} sx={{
                            alignItems: "center"
                          }}>
                            <Tooltip title={isSelected ? 'Currently Inspecting' : 'Inspect Audit Report'}>
                              <IconButton
                                size="small"
                                color={isSelected ? 'primary' : 'default'}
                                onClick={() => openReview(r)}
                                sx={{
                                  border: '1px solid',
                                  borderColor: isSelected ? 'primary.main' : 'divider',
                                  bgcolor: isSelected ? (isDark ? 'rgba(99,102,241,0.2)' : 'rgba(79,70,229,0.1)') : 'transparent',
                                }}
                                aria-label="Inspect report"
                              >
                                <VisibilityIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>

                            <Tooltip title="Delete Review">
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() =>
                                  setDeleteTarget({
                                    kind: 'review',
                                    id: r.id,
                                    name: docMap[r.document_id] || r.template_name || 'this report',
                                  })
                                }
                                sx={{ border: '1px solid', borderColor: 'divider' }}
                                aria-label="Delete review"
                              >
                                <DeleteOutlineIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        </Stack>

                        {r.top_findings && r.top_findings.length > 0 && (
                          <Box sx={{ mt: 1.5, pt: 1.25, borderTop: '1px dashed', borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                fontWeight: 700,
                                fontSize: '0.68rem',
                                mr: 0.5,
                                letterSpacing: '0.02em'
                              }}>
                              FLAGGED VULNERABILITIES:
                            </Typography>
                            {r.top_findings.map((tf, idx) => (
                              <Chip
                                key={idx}
                                label={`${(tf.clause_type || 'General').replace(/_/g, ' ')} · ${tf.risk_level}`}
                                size="small"
                                color={tf.risk_level === 'high' ? 'error' : tf.risk_level === 'medium' ? 'warning' : 'default'}
                                variant="outlined"
                                sx={{
                                  height: 22,
                                  fontSize: '0.68rem',
                                  fontWeight: 650,
                                  textTransform: 'capitalize',
                                  cursor: 'pointer',
                                  borderRadius: 1.25,
                                  lineHeight: '20px',
                                  '&:hover': { bgcolor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)' },
                                }}
                              />
                            ))}
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </Stack>
            )}
          </SectionCard>
        </Box>
      )}

      {/* INSPECT DOCUMENT MODAL */}
      <InspectDocumentDialog
        open={Boolean(inspect)}
        docId={inspect?.docId}
        docHint={inspect?.docHint}
        filenameHint={inspect?.filenameHint}
        onClose={() => setInspect(null)}
        reports={reviews}
        onOpenReport={openReview}
        onDelete={(d) => {
          setInspect(null);
          setDeleteTarget({ kind: 'doc', id: d.id, name: d.title || d.filename || 'this document' });
        }}
        toast={(m) => setMsg(m)}
      />

      {/* SYSTEMIC VULNERABILITY DEEP-DIVE MODAL */}
      <Dialog
        open={Boolean(selectedVuln)}
        onClose={() => setSelectedVuln(null)}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: { sx: { borderRadius: 3, p: 1 } }
        }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Stack
            direction="row"
            sx={{
              justifyContent: "space-between",
              alignItems: "flex-start"
            }}>
            <Box>
              <Stack
                direction="row"
                spacing={1}
                sx={{
                  alignItems: "center",
                  mb: 0.5
                }}>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 750,
                    textTransform: 'capitalize'
                  }}>
                  Clause Vulnerability: {selectedVuln?.clause_type}
                </Typography>
                {selectedVuln?.high_risk > 0 ? (
                  <Chip label="High Severity" color="error" size="small" sx={{ fontWeight: 700, height: 22, fontSize: '0.7rem' }} />
                ) : (
                  <Chip label="Monitored Risk" color="warning" size="small" sx={{ fontWeight: 700, height: 22, fontSize: '0.7rem' }} />
                )}
              </Stack>
              <Typography variant="caption" sx={{
                color: "text.secondary"
              }}>
                Corpus-wide intelligence analysis · {selectedVuln?.total} total occurrences detected
              </Typography>
            </Box>
            <IconButton size="small" onClick={() => setSelectedVuln(null)} aria-label="Close dialog">
              <CloseIcon />
            </IconButton>
          </Stack>
        </DialogTitle>

        <DialogContent dividers sx={{ p: 2.5 }}>
          {/* Key Metrics Strip */}
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' }, gap: 1.5, mb: 2.5 }}>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  fontWeight: 700
                }}>TOTAL FLAGS</Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 800,
                  mt: 0.2
                }}>{selectedVuln?.total ?? 0}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
              <Typography
                variant="caption"
                sx={{
                  color: "error.main",
                  fontWeight: 700
                }}>HIGH RISK</Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 800,
                  color: "error.main",
                  mt: 0.2
                }}>{selectedVuln?.high_risk ?? 0}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
              <Typography
                variant="caption"
                sx={{
                  color: "warning.main",
                  fontWeight: 700
                }}>MEDIUM RISK</Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 800,
                  color: "warning.main",
                  mt: 0.2
                }}>{selectedVuln?.medium_risk ?? 0}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
              <Typography
                variant="caption"
                sx={{
                  color: "primary.main",
                  fontWeight: 700
                }}>OBLIGATIONS</Typography>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 800,
                  color: "primary.main",
                  mt: 0.2
                }}>{selectedVuln?.obligations ?? 0}</Typography>
            </Paper>
          </Box>

          {/* Legal Risk Exposition */}
          <Box sx={{ mb: 2.5, p: 2, borderRadius: 2, bgcolor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', border: '1px solid', borderColor: 'divider' }}>
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 750,
                mb: 0.5
              }}>
              Clause Analysis &amp; Exposure
            </Typography>
            <Typography variant="body2" sx={{ lineHeight: 1.6, color: 'text.secondary' }}>
              {selectedVuln?.sample_explanation || 'This clause type frequently exposes the organization to un-capped liabilities, unilateral termination risks, or onerous non-standard covenants across multiple precedents.'}
            </Typography>
          </Box>

          {/* Affected Documents & Reports */}
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 750,
              mb: 1.25
            }}>
            Affected Documents in Your Library
          </Typography>
          {(() => {
            const serverAffected = selectedVuln?.affected_contracts || [];
            if (serverAffected.length > 0) {
              return (
                <Stack spacing={1.25}>
                  {serverAffected.map((item, idx) => (
                    <Paper key={item.review_id || idx} variant="outlined" sx={{ p: 1.75, borderRadius: 2 }}>
                      <Stack
                        direction="row"
                        spacing={2}
                        sx={{
                          justifyContent: "space-between",
                          alignItems: "center"
                        }}>
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                              alignItems: "center",
                              mb: 0.5
                            }}>
                            <Typography variant="body2" noWrap sx={{
                              fontWeight: 750
                            }}>
                              {item.document_name || 'Contract Precedent'}
                            </Typography>
                            {getRiskChip(item.risk_level)}
                          </Stack>
                          {item.clause_text && (
                            <Typography
                              variant="caption"
                              sx={{
                                display: 'block',
                                fontFamily: 'monospace',
                                bgcolor: isDark ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.03)',
                                p: 0.75,
                                borderRadius: 1,
                                fontSize: '0.72rem',
                                color: 'text.secondary',
                                mb: 0.5,
                              }}
                              noWrap
                            >
                              “{item.clause_text}”
                            </Typography>
                          )}
                          {item.explanation && (
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.secondary",
                                display: 'block'
                              }}>
                              <b>Risk:</b> {item.explanation}
                            </Typography>
                          )}
                        </Box>
                        <Button
                          size="small"
                          variant="contained"
                          onClick={() => {
                            setSelectedVuln(null);
                            openReview({ id: item.review_id, document_id: item.document_id });
                          }}
                          sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: '0.75rem', whiteSpace: 'nowrap', flexShrink: 0 }}
                        >
                          View Audit Report
                        </Button>
                      </Stack>
                    </Paper>
                  ))}
                </Stack>
              );
            }

            const clientAffected = safeReviews.filter((r) =>
              (r.findings || []).some(
                (f) => (f.clause_type || '').toLowerCase() === (selectedVuln?.clause_type || '').toLowerCase()
              )
            );
            if (clientAffected.length === 0) {
              return (
                <Typography
                  variant="body2"
                  sx={{
                    color: "text.secondary",
                    fontStyle: 'italic',
                    py: 1
                  }}>No individual reviews have direct line-item references to this clause type in the current subset.
                                  </Typography>
              );
            }
            return (
              <Stack spacing={1.25}>
                {clientAffected.map((rev) => {
                  const matchingFindings = (rev.findings || []).filter(
                    (f) => (f.clause_type || '').toLowerCase() === (selectedVuln?.clause_type || '').toLowerCase()
                  );
                  return (
                    <Paper key={rev.id} variant="outlined" sx={{ p: 1.75, borderRadius: 2 }}>
                      <Stack
                        direction="row"
                        spacing={2}
                        sx={{
                          justifyContent: "space-between",
                          alignItems: "center"
                        }}>
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography variant="body2" noWrap sx={{
                            fontWeight: 700
                          }}>
                            {docMap[rev.document_id] || rev.template_name || 'Contract Precedent'}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "text.secondary",
                              display: "block"
                            }}>
                            {matchingFindings.length} flagged clause(s) · {rev.risk_level?.toUpperCase()} risk level
                          </Typography>
                          {matchingFindings[0]?.explanation && (
                            <Typography
                              variant="caption"
                              noWrap
                              sx={{
                                color: "text.secondary",
                                fontStyle: 'italic',
                                display: 'block',
                                mt: 0.25
                              }}>
                              “{matchingFindings[0].explanation}”
                            </Typography>
                          )}
                        </Box>
                        <Button
                          size="small"
                          variant="contained"
                          onClick={() => {
                            setSelectedVuln(null);
                            openReview(rev);
                          }}
                          sx={{ textTransform: 'none', borderRadius: 1.5, fontSize: '0.75rem', whiteSpace: 'nowrap', flexShrink: 0 }}
                        >
                          View Audit Report
                        </Button>
                      </Stack>
                    </Paper>
                  );
                })}
              </Stack>
            );
          })()}
        </DialogContent>

        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setSelectedVuln(null)} variant="outlined" size="small" sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* REVIEW DETAILS MODAL (Full Report Viewer) */}
      <Dialog
        open={Boolean(active)}
        onClose={() => setActive(null)}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: { sx: { borderRadius: 3, p: 1, maxHeight: '88vh' } }
        }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Stack
            direction="row"
            sx={{
              justifyContent: "space-between",
              alignItems: "flex-start"
            }}>
            <Box>
              <Stack
                direction="row"
                spacing={1}
                sx={{
                  alignItems: "center",
                  mb: 0.5
                }}>
                <Typography variant="h6" sx={{
                  fontWeight: 750
                }}>
                  {active?.template_name || 'Contract Risk Audit'}
                </Typography>
                {getRiskChip(active?.risk_level)}
              </Stack>
              <Typography variant="body2" sx={{
                color: "text.secondary"
              }}>
                Document: <b>{docMap[active?.document_id] || active?.document_id || 'Contract'}</b>
                {active?.generated_at && ` · Generated on ${new Date(active.generated_at).toLocaleString()}`}
              </Typography>
            </Box>
            <IconButton onClick={() => setActive(null)} size="small" aria-label="Close dialog">
              <CloseIcon />
            </IconButton>
          </Stack>
        </DialogTitle>

        <DialogContent dividers sx={{ p: 3 }}>
          {/* Key Metrics Header */}
          <Paper
            elevation={0}
            sx={{
              p: 2,
              mb: 3,
              borderRadius: 2.5,
              bgcolor: isDark ? 'rgba(148,163,184,0.05)' : 'rgba(15,23,42,0.02)',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Grid container spacing={2} sx={{ mb: 2.5 }}>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Confirmed Risk
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    textTransform: 'capitalize',
                    mt: 0.2
                  }}>
                  {active?.risk_level || 'Low'}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Balance Score
                </Typography>
                <Typography
                  variant="h6"
                  color="primary"
                  sx={{
                    fontWeight: 700,
                    mt: 0.2
                  }}>
                  {active?.balance_score !== undefined && active?.balance_score !== null ? active.balance_score : '0.85'}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  KM-Confirmed
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    color: "success.main",
                    mt: 0.2
                  }}>
                  {active?.support_metrics?.km_confirmed
                    ?? (active?.findings || []).filter((f) => f.support_status === 'km_confirmed').length}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Manual Review
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    color: "warning.main",
                    mt: 0.2
                  }}>
                  {active?.support_metrics?.manual_review
                    ?? (active?.findings || []).filter((f) => f.support_status === 'manual_review').length}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Clause Findings
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    mt: 0.2
                  }}>
                  {active?.findings?.length ?? 0}
                </Typography>
              </Grid>
              <Grid size={{ xs: 6, sm: 4, md: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    fontWeight: 650,
                    textTransform: "uppercase",
                    letterSpacing: "0.6px"
                  }}>
                  Proposed Amendments
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 700,
                    color: "success.main",
                    mt: 0.2
                  }}>
                  {active?.findings?.filter((f) => f.proposed_change)?.length ?? 0}
                </Typography>
              </Grid>
            </Grid>
          </Paper>

          <Tabs
            value={activeTab}
            onChange={(e, val) => setActiveTab(val)}
            sx={{ mb: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}
          >
            <Tab label="Executive Summary & Findings" sx={{ textTransform: 'none', fontWeight: 650 }} />
            <Tab label="Full Audit Report (Markdown)" sx={{ textTransform: 'none', fontWeight: 650 }} />
          </Tabs>

          {activeTab === 0 && (
            <Box>
              <Box
                sx={{
                  mb: 3,
                  p: 2.5,
                  borderRadius: 3,
                  bgcolor: isDark ? 'rgba(79, 70, 229, 0.08)' : 'rgba(79, 70, 229, 0.04)',
                  border: '1px solid',
                  borderColor: isDark ? 'rgba(129, 140, 248, 0.25)' : 'rgba(79, 70, 229, 0.18)',
                  boxShadow: isDark
                    ? '0 4px 20px -8px rgba(0, 0, 0, 0.5)'
                    : '0 4px 20px -8px rgba(79, 70, 229, 0.08)',
                }}
              >
                <Stack
                  direction="row"
                  spacing={1}
                  sx={{
                    alignItems: "center",
                    mb: 1.5
                  }}>
                  <AssessmentIcon color="primary" fontSize="small" />
                  <Typography
                    variant="subtitle2"
                    color="primary"
                    sx={{
                      fontWeight: 800,
                      letterSpacing: '0.04em'
                    }}>
                    EXECUTIVE AUDIT SUMMARY
                  </Typography>
                  <Chip
                    label={active?.risk_level ? `${active.risk_level.toUpperCase()} RISK` : 'AUDITED'}
                    size="small"
                    color={active?.risk_level === 'high' ? 'error' : active?.risk_level === 'medium' ? 'warning' : 'success'}
                    sx={{ fontWeight: 700, fontSize: '0.7rem', height: 22 }}
                  />
                </Stack>
                <Box
                  sx={{
                    '& p': { lineHeight: 1.7, my: 0.5, fontSize: '0.92rem' },
                    '& ul': { pl: 2.5, my: 0.5 },
                    '& li': { my: 0.5, lineHeight: 1.6, fontSize: '0.9rem' },
                    '& h3': { fontSize: '1.05rem', fontWeight: 750, mb: 1 },
                    '& strong': { color: isDark ? '#e2e8f0' : '#1e293b' },
                  }}
                >
                  <ReactMarkdown>{getSynthesizedSummary(active)}</ReactMarkdown>
                </Box>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
                <Typography variant="subtitle1" sx={{
                  fontWeight: 750
                }}>
                  Clause Findings &amp; Exposure Analysis ({active?.findings?.length ?? 0})
                </Typography>
                <Stack direction="row" spacing={0.75} sx={{
                  flexWrap: "wrap"
                }}>
                  <Chip
                    label={`All (${active?.findings?.length ?? 0})`}
                    size="small"
                    onClick={() => setFindingRiskFilter('all')}
                    color={findingRiskFilter === 'all' ? 'primary' : 'default'}
                    variant={findingRiskFilter === 'all' ? 'filled' : 'outlined'}
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                  <Chip
                    label={`High (${(active?.findings || []).filter((f) => f.risk_level === 'high').length})`}
                    size="small"
                    onClick={() => setFindingRiskFilter('high')}
                    color={findingRiskFilter === 'high' ? 'error' : 'default'}
                    variant={findingRiskFilter === 'high' ? 'filled' : 'outlined'}
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                  <Chip
                    label={`Medium (${(active?.findings || []).filter((f) => f.risk_level === 'medium').length})`}
                    size="small"
                    onClick={() => setFindingRiskFilter('medium')}
                    color={findingRiskFilter === 'medium' ? 'warning' : 'default'}
                    variant={findingRiskFilter === 'medium' ? 'filled' : 'outlined'}
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                  <Chip
                    label={`Obligations (${(active?.findings || []).filter((f) => f.obligation).length})`}
                    size="small"
                    onClick={() => setFindingRiskFilter('obligation')}
                    color={findingRiskFilter === 'obligation' ? 'info' : 'default'}
                    variant={findingRiskFilter === 'obligation' ? 'filled' : 'outlined'}
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                  <Chip
                    label={`KM-confirmed (${(active?.findings || []).filter((f) => f.support_status === 'km_confirmed').length})`}
                    size="small"
                    onClick={() => setFindingRiskFilter('km_confirmed')}
                    color={findingRiskFilter === 'km_confirmed' ? 'success' : 'default'}
                    variant={findingRiskFilter === 'km_confirmed' ? 'filled' : 'outlined'}
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                  <Chip
                    label={`Manual review (${(active?.findings || []).filter((f) => f.support_status === 'manual_review').length})`}
                    size="small"
                    onClick={() => setFindingRiskFilter('manual_review')}
                    color={findingRiskFilter === 'manual_review' ? 'warning' : 'default'}
                    variant={findingRiskFilter === 'manual_review' ? 'filled' : 'outlined'}
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                  <Chip
                    label="Flagging guidelines"
                    size="small"
                    icon={<HelpOutlineIcon sx={{ fontSize: '15px !important' }} />}
                    onClick={openGuidelines}
                    variant="outlined"
                    color="info"
                    sx={{ height: 22, fontSize: '0.7rem', fontWeight: 650, cursor: 'pointer' }}
                  />
                </Stack>
              </Box>

              {(() => {
                const displayedFindings = (active?.findings ?? []).filter((f) => {
                  if (findingRiskFilter === 'high') return f.risk_level === 'high' && f.support_status !== 'manual_review';
                  if (findingRiskFilter === 'medium') return f.risk_level === 'medium' && f.support_status !== 'manual_review';
                  if (findingRiskFilter === 'low') return f.risk_level === 'low' && f.support_status !== 'manual_review';
                  if (findingRiskFilter === 'obligation') return Boolean(f.obligation);
                  if (findingRiskFilter === 'manual_review') return f.support_status === 'manual_review';
                  if (findingRiskFilter === 'km_confirmed') return f.support_status === 'km_confirmed';
                  return true;
                });

                if (displayedFindings.length === 0) {
                  return (
                    <Typography
                      variant="body2"
                      sx={{
                        color: "text.secondary",
                        fontStyle: 'italic',
                        py: 2
                      }}>No clause findings match the selected filter.
                                          </Typography>
                  );
                }

                return (
                  <Stack spacing={2}>
                    {displayedFindings.map((f, i) => (
                      <Paper
                        key={f.id || i}
                        elevation={0}
                        sx={{
                          p: 2,
                          borderRadius: 2.5,
                          border: '1px solid',
                          borderColor: f.risk_level === 'high' ? 'error.light' : 'divider',
                          bgcolor: isDark ? 'rgba(148,163,184,0.03)' : 'rgba(15,23,42,0.015)',
                        }}
                      >
                        <Stack
                          direction="row"
                          sx={{
                            justifyContent: "space-between",
                            alignItems: "center",
                            mb: 1
                          }}>
                          <Stack direction="row" spacing={1} sx={{
                            alignItems: "center"
                          }}>
                            <Typography
                              variant="subtitle2"
                              sx={{
                                fontWeight: 750,
                                textTransform: 'capitalize'
                              }}>
                              {(f.clause_type || 'General Clause').replace(/_/g, ' ')}
                            </Typography>
                            {getRiskChip(f.risk_level)}
                            {f.support_status === 'km_confirmed' && (
                              <Chip label="KM-confirmed" size="small" color="success" variant="outlined" sx={{ height: 20, fontSize: '0.68rem', fontWeight: 650 }} />
                            )}
                            {f.support_status === 'manual_review' && (
                              <Chip
                                label={`Manual review${f.suggested_risk_level ? ` · was ${f.suggested_risk_level}` : ''}`}
                                size="small"
                                color="warning"
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.68rem', fontWeight: 650 }}
                              />
                            )}
                            {(f.support_status === 'doc_ungrounded' || f.grounded === false) && (
                              <Chip label="Not in source text" size="small" color="default" variant="outlined" sx={{ height: 20, fontSize: '0.68rem', fontWeight: 650 }} />
                            )}
                            {f.obligation && (
                              <Chip label="Obligation" size="small" variant="outlined" color="primary" sx={{ height: 20, fontSize: '0.68rem', fontWeight: 650 }} />
                            )}
                          </Stack>
                          <FormControl size="small" sx={{ minWidth: 142 }}>
                            <Select
                              value={f.implementation_status || 'not_started'}
                              onChange={(e) => handleStatusChange(f.id, e.target.value)}
                              displayEmpty
                              aria-label={`Implementation status for ${f.clause_type || 'clause'} finding`}
                              sx={{
                                height: 26,
                                fontSize: '0.72rem',
                                fontWeight: 650,
                                '& .MuiOutlinedInput-notchedOutline': {
                                  borderColor:
                                    f.implementation_status === 'applied'
                                      ? 'success.main'
                                      : f.implementation_status === 'in_progress'
                                        ? 'warning.main'
                                        : 'divider',
                                },
                              }}
                            >
                              <MenuItem value="not_started">📝 Not started</MenuItem>
                              <MenuItem value="in_progress">⏳ Implementation in progress</MenuItem>
                              <MenuItem value="applied">✅ Applied</MenuItem>
                            </Select>
                          </FormControl>
                        </Stack>

                    {f.text && (
                      <Box
                        sx={{
                          p: 1.5,
                          mb: 1.5,
                          borderRadius: 2,
                          bgcolor: isDark ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.03)',
                          borderLeft: '3px solid',
                          borderLeftColor: f.risk_level === 'high' ? 'error.main' : 'primary.main',
                          fontFamily: 'monospace',
                          fontSize: '0.84rem',
                          lineHeight: 1.5,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {f.text}
                      </Box>
                    )}

                    {f.explanation && (
                      <Typography variant="body2" sx={{ mb: 1, color: 'text.secondary', lineHeight: 1.5 }}>
                        <b>Risk Analysis:</b> {f.explanation}
                      </Typography>
                    )}

                    {f.risk_rationale && (
                      <Typography variant="body2" sx={{ mb: 0.75, lineHeight: 1.55 }}>
                        <b>Why flagged {f.risk_level}:</b> {f.risk_rationale}
                      </Typography>
                    )}

                    {f.recommended_action && (
                      <Typography variant="body2" sx={{ mb: 1, lineHeight: 1.55 }}>
                        <b>Recommended action:</b> {f.recommended_action}
                      </Typography>
                    )}

                    {f.plain_language && (
                      <Typography variant="body2" sx={{ color: 'text.secondary', lineHeight: 1.5, mb: f.proposed_change ? 1.5 : 0 }}>
                        <b>Plain Language:</b> {f.plain_language}
                      </Typography>
                    )}

                    {f.proposed_change && (
                      <Box
                        sx={{
                          mt: 1.5,
                          p: 2,
                          borderRadius: 2,
                          bgcolor: isDark ? 'rgba(16, 185, 129, 0.08)' : 'rgba(16, 185, 129, 0.04)',
                          border: '1px solid',
                          borderColor: isDark ? 'rgba(16, 185, 129, 0.28)' : 'rgba(16, 185, 129, 0.35)',
                        }}
                      >
                        <Stack
                          direction="row"
                          sx={{
                            justifyContent: "space-between",
                            alignItems: "center",
                            mb: 1.25
                          }}>
                          <Stack direction="row" spacing={1} sx={{
                            alignItems: "center"
                          }}>
                            <AutoFixHighIcon fontSize="small" color="success" />
                            <Typography
                              variant="subtitle2"
                              sx={{
                                fontWeight: 750,
                                color: "success.main"
                              }}>
                              Proposed Contract Modification
                            </Typography>
                            <Chip
                              label="Contextual Redline"
                              size="small"
                              color="success"
                              variant="outlined"
                              sx={{ height: 20, fontSize: '0.68rem', fontWeight: 650 }}
                            />
                          </Stack>
                          <Tooltip title={copiedClauseId === (f.id || i) ? 'Copied Language!' : 'Copy Proposed Language'}>
                            <IconButton
                              size="small"
                              color="success"
                              onClick={() => handleCopyClause(f.proposed_change, f.id || i)}
                              sx={{
                                bgcolor: isDark ? 'rgba(16, 185, 129, 0.12)' : 'rgba(16, 185, 129, 0.08)',
                                '&:hover': { bgcolor: 'success.main', color: '#fff' },
                              }}
                              aria-label="Copy proposed language"
                            >
                              {copiedClauseId === (f.id || i) ? <CheckCircleIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
                            </IconButton>
                          </Tooltip>
                        </Stack>

                        <Box
                          sx={{
                            p: 1.5,
                            mb: 1.25,
                            borderRadius: 1.5,
                            bgcolor: isDark ? 'rgba(0,0,0,0.35)' : 'rgba(255,255,255,0.85)',
                            border: '1px dashed',
                            borderColor: isDark ? 'rgba(16, 185, 129, 0.4)' : 'rgba(16, 185, 129, 0.45)',
                            fontFamily: 'monospace',
                            fontSize: '0.84rem',
                            lineHeight: 1.6,
                            color: isDark ? '#a7f3d0' : '#065f46',
                          }}
                        >
                          “{f.proposed_change}”
                        </Box>

                        {f.change_rationale && (
                          <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.82rem', lineHeight: 1.5 }}>
                            <b>Strategic Rationale in Contract Context:</b> {f.change_rationale}
                          </Typography>
                        )}
                      </Box>
                    )}

                    {!f.proposed_change && f.id && (
                      <Box sx={{ mt: 1.5, pt: 1, borderTop: '1px dashed', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            fontWeight: 650
                          }}>
                          Generate contextual remediation:
                        </Typography>
                        <Stack direction="row" spacing={1}>
                          <Button
                            size="small"
                            variant="outlined"
                            color="primary"
                            startIcon={<AutoFixHighIcon fontSize="small" />}
                            disabled={remediatingId === f.id}
                            onClick={() => handleProposeChange(f.id, 'balanced')}
                            sx={{ textTransform: 'none', fontSize: '0.75rem', borderRadius: 1.5 }}
                          >
                            {remediatingId === f.id ? 'Generating...' : 'Balanced Redline'}
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            color="info"
                            startIcon={<AutoFixHighIcon fontSize="small" />}
                            disabled={remediatingId === f.id}
                            onClick={() => handleProposeChange(f.id, 'protective')}
                            sx={{ textTransform: 'none', fontSize: '0.75rem', borderRadius: 1.5 }}
                          >
                            {remediatingId === f.id ? 'Generating...' : 'Protective Redline'}
                          </Button>
                        </Stack>
                      </Box>
                    )}
                  </Paper>
                ))}
                  </Stack>
                );
          })()}
            </Box>
          )}

          {activeTab === 1 && (
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                <Tooltip title={copied ? 'Report Copied to Clipboard!' : 'Copy Markdown Report'}>
                  <IconButton
                    size="small"
                    color="primary"
                    onClick={handleCopyReport}
                    sx={{
                      bgcolor: isDark ? 'rgba(99,102,241,0.12)' : 'rgba(79,70,229,0.08)',
                      '&:hover': { bgcolor: 'primary.main', color: '#fff' },
                    }}
                    aria-label="Copy Markdown report"
                  >
                    {copied ? <CheckCircleIcon fontSize="small" color="success" /> : <ContentCopyIcon fontSize="small" />}
                  </IconButton>
                </Tooltip>
              </Box>
              <Paper
                elevation={0}
                variant="outlined"
                sx={{
                  p: 3,
                  borderRadius: 2.5,
                  bgcolor: isDark ? 'rgba(15,23,42,0.4)' : '#fafafa',
                  maxHeight: '58vh',
                  overflowY: 'auto',
                  border: '1px solid',
                  borderColor: 'divider',
                  '& h1, & h2, & h3': { fontWeight: 750, letterSpacing: '-0.02em', my: 1.5 },
                  '& p': { lineHeight: 1.7, my: 1, fontSize: '0.92rem' },
                  '& ul, & ol': { pl: 3, my: 1 },
                  '& li': { my: 0.5, lineHeight: 1.6 },
                  '& blockquote': {
                    borderLeft: '3px solid #4f46e5',
                    pl: 2,
                    py: 0.5,
                    my: 1.5,
                    color: 'text.secondary',
                    bgcolor: isDark ? 'rgba(79,70,229,0.08)' : 'rgba(79,70,229,0.04)',
                    borderRadius: '0 8px 8px 0',
                  },
                }}
              >
                <ReactMarkdown>{active?.markdown_report || 'No markdown report available.'}</ReactMarkdown>
              </Paper>
            </Box>
          )}
        </DialogContent>

        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setActive(null)} variant="outlined" size="small" sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}>
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* RISK FLAGGING GUIDELINES DIALOG */}
      <Dialog open={guidelinesOpen} onClose={() => setGuidelinesOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ pb: 1 }}>
          <Stack direction="row" spacing={1.25} sx={{
            alignItems: "center"
          }}>
            <HelpOutlineIcon color="info" />
            <Typography variant="h6" sx={{
              fontWeight: 800
            }}>
              Risk Flagging Guidelines
            </Typography>
          </Stack>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 2.5 }}>
          {guidelinesLoading ? (
            <Stack
              sx={{
                alignItems: "center",
                py: 5
              }}>
              <CircularProgress size={28} />
            </Stack>
          ) : !guidelines ? (
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              The guidelines could not be loaded right now. Try again in a moment.
            </Typography>
          ) : (
            <Stack spacing={2.25}>
              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  lineHeight: 1.65
                }}>
                Every risk badge below comes from grading the clause against these rules. The LLM
                is given this same ruleset as worked examples, and the result is re-checked
                against the document before the finding is saved.
              </Typography>

              {(guidelines.levels || []).map((lvl) => {
                const color = lvl.level === 'high' ? 'error' : lvl.level === 'medium' ? 'warning' : 'success';
                return (
                  <Box
                    key={lvl.level}
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      border: '1px solid',
                      borderColor: `${color}.light`,
                      bgcolor: isDark ? 'rgba(148,163,184,0.04)' : 'rgba(15,23,42,0.02)',
                    }}
                  >
                    <Stack
                      direction="row"
                      spacing={1}
                      sx={{
                        alignItems: "center",
                        mb: 1
                      }}>
                      <Chip
                        size="small"
                        label={`${lvl.flag} ${lvl.label}`}
                        color={color}
                        sx={{ fontWeight: 750, height: 22, fontSize: '0.72rem' }}
                      />
                    </Stack>
                    <Typography variant="body2" sx={{ mb: 1.5, lineHeight: 1.6 }}>
                      {lvl.summary}
                    </Typography>

                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: 800,
                        display: "block",
                        mb: 0.5
                      }}>
                      Clause types
                    </Typography>
                    <Stack
                      direction="row"
                      spacing={0.5}
                      useFlexGap
                      sx={{
                        flexWrap: "wrap",
                        gap: 0.5,
                        mb: 1.5
                      }}>
                      {(lvl.clause_types || []).map((t) => (
                        <Chip
                          key={t}
                          size="small"
                          variant="outlined"
                          label={t.replace(/_/g, ' ')}
                          sx={{ height: 20, fontSize: '0.68rem', textTransform: 'capitalize' }}
                        />
                      ))}
                    </Stack>

                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: 800,
                        display: "block",
                        mb: 0.5
                      }}>
                      Flagged when
                    </Typography>
                    <Box
                      component="ul"
                      sx={{
                        pl: 2.5,
                        mt: 0,
                        mb: 1.5,
                        '& li': { fontSize: '0.82rem', lineHeight: 1.55, color: 'text.secondary', mb: 0.4 },
                      }}
                    >
                      {(lvl.triggers || []).map((t, i) => (
                        <li key={i}>{t}</li>
                      ))}
                    </Box>

                    {lvl.why_it_matters && Object.keys(lvl.why_it_matters).length > 0 && (
                      <>
                        <Typography
                          variant="caption"
                          sx={{
                            fontWeight: 800,
                            display: "block",
                            mb: 0.5
                          }}>
                          Why these clauses matter
                        </Typography>
                        <Box
                          component="ul"
                          sx={{
                            pl: 2.5,
                            mt: 0,
                            mb: 1.5,
                            '& li': { fontSize: '0.82rem', lineHeight: 1.55, color: 'text.secondary', mb: 0.4 },
                          }}
                        >
                          {Object.entries(lvl.why_it_matters).map(([k, v]) => (
                            <li key={k}>
                              <b>{k.replace(/_/g, ' ')}:</b> {v}
                            </li>
                          ))}
                        </Box>
                      </>
                    )}

                    <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
                      <b>Action:</b> {lvl.recommended_action}
                    </Typography>
                  </Box>
                );
              })}

              <Box>
                <Typography
                  variant="subtitle2"
                  sx={{
                    fontWeight: 800,
                    mb: 1
                  }}>
                  How a level is assigned
                </Typography>
                <Box
                  component="ul"
                  sx={{
                    pl: 2.5,
                    mt: 0,
                    '& li': { fontSize: '0.84rem', lineHeight: 1.6, mb: 0.75, color: 'text.secondary' },
                  }}
                >
                  {(guidelines.assignment_rules || []).map((r, i) => (
                    <li key={i}>
                      <b style={{ color: 'inherit' }}>{r.rule}.</b> {r.detail}
                    </li>
                  ))}
                </Box>
              </Box>

              <Typography variant="caption" sx={{
                color: "text.secondary"
              }}>
                {guidelines.disclaimer}
              </Typography>
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button
            onClick={() => setGuidelinesOpen(false)}
            variant="outlined"
            size="small"
            sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* CONFIRM DELETE DIALOG */}
      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to permanently delete <b>{deleteTarget?.name}</b>? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDeleteTarget(null)} variant="outlined" size="small" disabled={isDeleting} sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}>
            Cancel
          </Button>
          <Button
            onClick={handleDelete}
            color="error"
            variant="contained"
            disabled={isDeleting}
            sx={{ textTransform: 'none', borderRadius: 2, px: 2.5, fontWeight: 650 }}
          >
            {isDeleting ? 'Deleting…' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}