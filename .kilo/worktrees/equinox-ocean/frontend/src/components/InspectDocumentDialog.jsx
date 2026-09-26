import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  Typography,
  useTheme,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlined';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import SearchIcon from '@mui/icons-material/Search';
import VisibilityIcon from '@mui/icons-material/Visibility';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { TextField } from '@mui/material';
import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import DocumentContent from './DocumentContent';

function RiskChip({ level }) {
  const l = (level || 'low').toLowerCase();
  if (l === 'high') {
    return <Chip label="High Risk" size="small" color="error" icon={<ErrorOutlineIcon />} sx={{ fontWeight: 600 }} />;
  }
  if (l === 'medium') {
    return <Chip label="Medium Risk" size="small" color="warning" icon={<WarningAmberIcon />} sx={{ fontWeight: 600 }} />;
  }
  return <Chip label="Low Risk" size="small" color="success" icon={<InfoOutlinedIcon />} sx={{ fontWeight: 600 }} />;
}

/**
 * Shared document inspector used by the Knowledge Hub (search results) and the
 * Document Review > Manage tab. Renders extracted text as markdown when the
 * file is markdown, surfaces document-specific audit reports (when a `reports`
 * array is passed), and lists linked scenarios/simulations.
 */
export default function InspectDocumentDialog({
  open,
  docId,
  docHint,
  filenameHint,
  onClose,
  onDelete,
  reports,
  onOpenReport,
  toast,
}) {
  const theme = useTheme();
  const hasReports = Array.isArray(reports);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState(0);
  const [showFull, setShowFull] = useState(false);
  const [search, setSearch] = useState('');
  const [activeMatch, setActiveMatch] = useState(0);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!open || !docId) return undefined;
    let cancelled = false;
    setLoading(true);
    setDetail(null);
    setTab(0);
    setShowFull(false);
    setSearch('');
    setActiveMatch(0);
    api(`/documents/${docId}/detail`)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => toast?.(`Could not load document details: ${err.message}`))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, docId, toast]);

  const text = (detail?.text || '').length > 4000 && !showFull ? (detail?.text || '').slice(0, 4000) : detail?.text || '';
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q || !text) return [];
    const out = [];
    let from = 0;
    let idx;
    while ((idx = text.toLowerCase().indexOf(q, from)) !== -1) {
      out.push({ start: idx, end: idx + q.length });
      from = idx + q.length;
    }
    return out;
  }, [search, text]);

  useEffect(() => {
    if (!search.trim()) return;
    if (text !== detail?.text) setShowFull((prev) => prev || true);
  }, [search, text, detail]);

  useEffect(() => {
    const el = scrollRef.current?.querySelector(`[data-midx="${activeMatch}"]`);
    const container = scrollRef.current;
    if (!el || !container) return;
    const r = el.getBoundingClientRect();
    const cr = container.getBoundingClientRect();
    container.scrollTop += r.top - cr.top - container.clientHeight / 2;
  }, [activeMatch, matches]);

  function renderHighlighted() {
    if (!search.trim() || matches.length === 0) return null;
    return (
      <Box
        component="pre"
        sx={{
          m: 0,
          fontFamily: 'monospace',
          fontSize: '0.85rem',
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {matches.reduce((nodes, m, i) => {
          const prevEnd = i === 0 ? 0 : matches[i - 1].end;
          if (m.start > prevEnd) nodes.push(text.slice(prevEnd, m.start));
          nodes.push(
            <mark
              key={i}
              data-midx={i}
              style={{
                backgroundColor: i === activeMatch ? '#ff9800' : '#fff176',
                color: '#1c110a',
              }}
            >
              {text.slice(m.start, m.end)}
            </mark>
          );
          return nodes;
        }, [])}
        {matches.length > 0 && matches[matches.length - 1].end < text.length
          ? text.slice(matches[matches.length - 1].end)
          : null}
      </Box>
    );
  }

  const sections = ['content'];
  if (hasReports) sections.push('reports');
  sections.push('linked');
  const active = sections[tab] || 'content';

  const title = detail?.title || detail?.filename || docHint || 'Document Detail';
  const filename = detail?.filename || detail?.metadata_visibility?.filename || filenameHint || title;
  const docReports = hasReports ? reports.filter((r) => r.document_id === docId) : [];

  function copyText(text, label = 'Excerpt') {
    if (!text) return;
    navigator.clipboard.writeText(text);
    toast?.(`${label} copied to clipboard`);
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{ sx: { borderRadius: 3, p: 1 } }}
    >
      {detail && (
        <>
          <DialogTitle sx={{ pb: 1 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
              <Box>
                <Typography variant="h6" fontWeight={700}>
                  {title}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Filename: <b>{filename}</b> · ID: {detail.id}
                </Typography>
              </Box>
              <IconButton onClick={onClose} size="small" aria-label="close detail dialog">
                <CloseIcon />
              </IconButton>
            </Stack>

            <Stack direction="row" spacing={1} flexWrap="wrap" sx={{ mt: 1 }}>
              {(detail.document_category || detail.doc_category) && (
                <Chip
                  size="small"
                  label={(detail.document_category || detail.doc_category) === 'contract_review' ? 'Contract Review' : 'Knowledge Artefact'}
                  color={(detail.document_category || detail.doc_category) === 'contract_review' ? 'info' : 'success'}
                  variant="outlined"
                  sx={{ fontWeight: 650 }}
                />
              )}
              {detail.doc_type && <Chip size="small" label={detail.doc_type} />}
              {detail.jurisdiction && <Chip size="small" label={detail.jurisdiction} color="primary" />}
              {detail.domain && <Chip size="small" label={detail.domain} />}
              <Chip size="small" label={detail.status} color="success" variant="outlined" />
            </Stack>
          </DialogTitle>

          <Tabs
            value={tab}
            onChange={(_, val) => setTab(val)}
            sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab label="Extracted Content" />
            {hasReports && <Tab label={`Audit Reports (${docReports.length})`} />}
            <Tab label="Linked Scenarios & Insights" />
          </Tabs>

          <DialogContent sx={{ minHeight: 320, p: 3 }}>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress />
              </Box>
            ) : active === 'content' ? (
              <Box>
                <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                  {detail.text && detail.text.length > 4000 && !showFull ? (
                    <Typography variant="subtitle2" color="text.secondary">
                      Extracted content — showing first 4,000 of {detail.text.length} characters:
                    </Typography>
                  ) : (
                    <Typography variant="subtitle2" color="text.secondary">
                      Extracted content ({detail.text ? `${detail.text.length} characters` : '0 characters'}):
                    </Typography>
                  )}
                  {detail.text && detail.text.length > 4000 && !showFull ? (
                    <Button size="small" onClick={() => setShowFull(true)} sx={{ textTransform: 'none' }}>
                      Show full content
                    </Button>
                  ) : (
                    detail.text && (
                      <Button
                        size="small"
                        startIcon={<ContentCopyIcon fontSize="small" />}
                        onClick={() => copyText(detail.text, 'Document content')}
                        sx={{ textTransform: 'none' }}
                      >
                        Copy All Text
                      </Button>
                    )
                  )}
                </Stack>
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                  <TextField
                    size="small"
                    fullWidth
                    placeholder="Search within this document…"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setActiveMatch(0);
                    }}
                    sx={{ bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)', borderRadius: 1.5 }}
                    InputProps={{
                      startAdornment: <SearchIcon fontSize="small" color="disabled" />,
                      endAdornment: search ? (
                        <IconButton size="small" onClick={() => { setSearch(''); setActiveMatch(0); }} aria-label="clear search">
                          <CloseIcon fontSize="small" />
                        </IconButton>
                      ) : null,
                    }}
                  />
                  {matches.length > 0 && (
                    <>
                      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
                        {activeMatch + 1} / {matches.length}
                      </Typography>
                      <IconButton
                        size="small"
                        disabled={activeMatch <= 0}
                        onClick={() => setActiveMatch((a) => Math.max(0, a - 1))}
                        aria-label="previous match"
                      >
                        <KeyboardArrowUpIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        disabled={activeMatch >= matches.length - 1}
                        onClick={() => setActiveMatch((a) => Math.min(matches.length - 1, a + 1))}
                        aria-label="next match"
                      >
                        <KeyboardArrowDownIcon fontSize="small" />
                      </IconButton>
                    </>
                  )}
                </Stack>
                <Paper
                  ref={scrollRef}
                  variant="outlined"
                  sx={{
                    p: 2,
                    maxHeight: 380,
                    overflowY: 'auto',
                    bgcolor: theme.palette.mode === 'dark' ? 'rgba(0, 0, 0, 0.2)' : 'rgba(0, 0, 0, 0.02)',
                    borderRadius: 2,
                  }}
                >
                  {search.trim() && matches.length > 0 ? (
                    renderHighlighted()
                  ) : search.trim() ? (
                    <Box component="pre" sx={{ m: 0, fontFamily: 'monospace', fontSize: '0.85rem', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {text}
                    </Box>
                  ) : (
                    <DocumentContent text={text} filename={filename} />
                  )}
                  {search.trim() && matches.length === 0 && (
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                      No matches for &ldquo;{search.trim()}&rdquo; in the shown content.
                    </Typography>
                  )}
                </Paper>
              </Box>
            ) : active === 'reports' ? (
              <Box>
                {docReports.length === 0 ? (
                  <Paper sx={{ p: 3, textAlign: 'center', borderRadius: 2, border: '1px dashed', borderColor: 'divider' }}>
                    <Typography variant="body2" color="text.secondary">
                      No audit reports generated for this document yet. Use the Review action in Document Review to create one.
                    </Typography>
                  </Paper>
                ) : (
                  <Stack spacing={1.5}>
                    {docReports.map((r) => (
                      <Paper key={r.id} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={1}>
                          <Box>
                            <Typography variant="body2" fontWeight={600}>
                              {r.template_name || 'Standard Audit'}
                            </Typography>
                            <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                              <RiskChip level={r.risk_level} />
                              <Chip
                                size="small"
                                label={`${r.findings_count ?? (r.findings ? r.findings.length : 0)} findings`}
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.7rem', fontWeight: 500 }}
                              />
                              <Chip
                                size="small"
                                label={r.status || 'draft'}
                                variant="outlined"
                                sx={{ height: 20, fontSize: '0.7rem', textTransform: 'capitalize' }}
                              />
                            </Stack>
                          </Box>
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<VisibilityIcon />}
                            onClick={() => onOpenReport?.(r)}
                            sx={{ textTransform: 'none' }}
                          >
                            View Report
                          </Button>
                        </Stack>
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Box>
            ) : (
              <Box>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  Linked Scenarios ({detail.linked?.scenarios?.length || 0})
                </Typography>
                {(!detail.linked?.scenarios || detail.linked.scenarios.length === 0) ? (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    No scenarios currently reference this document.
                  </Typography>
                ) : (
                  <Stack spacing={1} sx={{ mb: 2 }}>
                    {detail.linked.scenarios.map((s, idx) => (
                      <Paper key={idx} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <Typography variant="body2" fontWeight={600}>
                          {s.scenario_title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Version: {s.version} · Scenario ID: {s.scenario_id}
                        </Typography>
                      </Paper>
                    ))}
                  </Stack>
                )}

                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  Linked Simulations ({detail.linked?.simulations?.length || 0})
                </Typography>
                {(!detail.linked?.simulations || detail.linked.simulations.length === 0) ? (
                  <Typography variant="body2" color="text.secondary">
                    No simulations currently reference this document.
                  </Typography>
                ) : (
                  <Stack spacing={1}>
                    {detail.linked.simulations.map((sim, idx) => (
                      <Paper key={idx} variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <Typography variant="body2">
                          Simulation {sim.id.slice(0, 8)}... — <b>{sim.status}</b> ({sim.phase})
                        </Typography>
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Box>
            )}
          </DialogContent>

          <DialogActions sx={{ px: 3, pb: 2, justifyContent: 'space-between' }}>
            {onDelete ? (
              <Button
                color="error"
                variant="outlined"
                startIcon={<DeleteOutlineIcon />}
                onClick={() => onDelete(detail)}
                sx={{ borderRadius: 2, textTransform: 'none' }}
              >
                Delete Document
              </Button>
            ) : (
              <Box />
            )}
            <Button onClick={onClose} variant="outlined" size="small" sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}>
              Close
            </Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
}