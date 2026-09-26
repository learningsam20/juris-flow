import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ClearIcon from '@mui/icons-material/Clear';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SearchIcon from '@mui/icons-material/Search';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { api } from '../../api/client';
import { DOMAINS, JURISDICTIONS } from '../../components/documentMeta';
import InspectDocumentDialog from '../../components/InspectDocumentDialog';
import { EmptyState } from '../../components/ui';

const ASK_PLACEHOLDER = 'Ask anything about your documents…';
const DEFAULT_TOP_K = 3;
const TOP_K_OPTIONS = [3, 5, 8, 12];

const typewriter = (fullText, onTick) => {
  if (fullText.length <= 220) {
    onTick(fullText);
    return () => {};
  }
  let index = 0;
  const CHUNK = 64;
  const timer = setInterval(() => {
    index += CHUNK;
    onTick(fullText.slice(0, index));
    if (index >= fullText.length) {
      onTick(fullText);
      clearInterval(timer);
    }
  }, 22);
  return () => clearInterval(timer);
};

function SourceSnippet({ text }) {
  const [expand, setExpand] = useState(false);
  const clamped = expand || text.length <= 480;
  const shown = clamped ? text : `${text.slice(0, 480)}…`;
  return (
    <Box>
      <Box
        sx={{
          p: 1.5,
          my: 1.5,
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
          borderLeft: '3px solid',
          borderLeftColor: 'primary.main',
          bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(148,163,184,0.06)' : 'rgba(79,70,229,0.03)'),
          fontFamily: 'monospace',
          fontSize: '0.83rem',
          lineHeight: 1.6,
          color: 'text.primary',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {shown}
      </Box>
      {!clamped && (
        <Button size="small" onClick={() => setExpand(true)} sx={{ textTransform: 'none', mt: -0.5 }}>
          Show full section
        </Button>
      )}
    </Box>
  );
}

function stripMarkdownProps(props) {
  const rest = { ...props };
  void rest.node;
  void rest.inline;
  void rest.className;
  delete rest.node;
  delete rest.inline;
  delete rest.className;
  return rest;
}

const markdownComponents = {
  p: (props) => <Box component="p" sx={{ margin: '0.4em 0' }} {...stripMarkdownProps(props)} />,
  ul: (props) => <Box component="ul" sx={{ margin: '0.4em 0', paddingLeft: '1.6em' }} {...stripMarkdownProps(props)} />,
  ol: (props) => <Box component="ol" sx={{ margin: '0.4em 0', paddingLeft: '1.6em' }} {...stripMarkdownProps(props)} />,
  li: (props) => <Box component="li" sx={{ margin: '0.2em 0' }} {...stripMarkdownProps(props)} />,
  h1: (props) => <Box component="h1" sx={{ fontSize: '1.2rem', margin: '0.6em 0 0.3em' }} {...stripMarkdownProps(props)} />,
  h2: (props) => <Box component="h2" sx={{ fontSize: '1.1rem', margin: '0.6em 0 0.3em' }} {...stripMarkdownProps(props)} />,
  h3: (props) => <Box component="h3" sx={{ fontSize: '1rem', margin: '0.5em 0 0.3em' }} {...stripMarkdownProps(props)} />,
  blockquote: (props) => (
    <Box
      component="blockquote"
      sx={{ margin: '0.5em 0', padding: '0.25em 0.9em', borderRadius: 1, borderLeft: '3px solid', borderColor: 'primary.main', bgcolor: 'action.hover' }}
      {...stripMarkdownProps(props)}
    />
  ),
  code: (props) => (
    <Box component="code" sx={{ backgroundColor: 'rgba(128,128,128,0.12)', borderRadius: 4, padding: '0.1em 0.3em', fontSize: '0.85em' }} {...stripMarkdownProps(props)} />
  ),
};

function CitationBadge({ index }) {
  return (
    <Box
      sx={{
        width: 30,
        height: 30,
        flexShrink: 0,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 700,
        fontSize: '0.85rem',
        color: 'primary.contrastText',
        background: (t) => `linear-gradient(135deg, ${t.palette.primary.main}, ${t.palette.primary.dark})`,
        boxShadow: '0 4px 10px -4px rgba(79,70,229,0.5)',
      }}
    >
      {index}
    </Box>
  );
}

export default function HubPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const [q, setQ] = useState('');
  const [jurisdiction, setJurisdiction] = useState('');
  const [domain, setDomain] = useState('');
  const [topK, setTopK] = useState(DEFAULT_TOP_K);
  const [phase, setPhase] = useState('idle'); // idle | retrieving | answering | done
  const [progress, setProgress] = useState('');
  const [answer, setAnswer] = useState('');
  const [typedAnswer, setTypedAnswer] = useState('');
  const [sources, setSources] = useState([]);
  const [discovered, setDiscovered] = useState([]);
  const [askError, setAskError] = useState('');
  const [toastMsg, setToastMsg] = useState('');
  const [inspect, setInspect] = useState(null);
  const askToken = useRef(0);
  const discoveredRef = useRef([]);

  useEffect(() => {
    if (phase !== 'done' || !answer) {
      setTypedAnswer('');
      return undefined;
    }
    let dispose;
    const timer = setTimeout(() => {
      dispose = typewriter(answer, setTypedAnswer);
    }, 60);
    return () => {
      clearTimeout(timer);
      dispose?.();
    };
  }, [phase, answer]);

  const busy = phase === 'retrieving' || phase === 'answering';

  async function discoverSources(query) {
    const token = askToken.current;
    try {
      const search = await api('/knowledge/search', {
        method: 'POST',
        body: { query, jurisdiction: jurisdiction || undefined, domain: domain || undefined, limit: topK },
      });
      if (token !== askToken.current) return;
      const results = (search.results || []).map((r, i) => ({
        index: i + 1,
        document_id: r.id,
        title: r.title || r.filename,
        filename: r.filename,
        snippet: r.text || '',
        score: r.score,
      }));
      discoveredRef.current = results;
      setDiscovered(results);
      const n = results.length;
      setProgress(n > 0 ? `Found ${n} relevant source${n === 1 ? '' : 's'} — generating your answer…` : 'No exact matches — searching more broadly…');
    } catch {
      if (token === askToken.current) setProgress('Generating your answer…');
    }
  }

  async function handleAsk(e) {
    if (e) e.preventDefault();
    const query = q.trim();
    if (!query) {
      setAskError('Type a question first.');
      return;
    }
    const token = ++askToken.current;
    setAskError('');
    setAnswer('');
    setTypedAnswer('');
    setSources([]);
    setDiscovered([]);
    discoveredRef.current = [];
    setPhase('retrieving');
    setProgress('Searching your indexed documents…');
    discoverSources(query);
    setPhase('answering');
    setProgress('Generating your answer from the cited sources…');
    try {
      const res = await api('/knowledge/ask', {
        method: 'POST',
        body: {
          query,
          jurisdiction: jurisdiction || undefined,
          domain: domain || undefined,
          top_k: topK,
        },
      });
      if (token !== askToken.current) return;
      setAnswer(res.answer || '');
      setSources(res.sources && res.sources.length ? res.sources : discoveredRef.current);
      setPhase('done');
    } catch (err) {
      if (token !== askToken.current) return;
      setAskError(`Could not generate an answer: ${err.message}`);
      setPhase('idle');
    }
  }

  function handleNewQuestion() {
    setQ('');
    setAnswer('');
    setTypedAnswer('');
    setSources([]);
    setDiscovered([]);
    discoveredRef.current = [];
    setAskError('');
    setPhase('idle');
  }

  function openInspect(source) {
    setInspect({ docId: source.document_id, docHint: source.title, filenameHint: source.filename });
  }

  function copyAnswer() {
    if (!answer) return;
    navigator.clipboard.writeText(answer);
    setToastMsg('Answer copied to clipboard');
  }

  const hasActiveFilters = Boolean(jurisdiction || domain);
  const emptyLibrary = phase === 'done' && sources.length === 0;

  return (
    <Box sx={{ maxWidth: 1060, mx: 'auto' }}>
      {askError && (
        <Alert severity="error" onClose={() => setAskError('')} sx={{ mb: 2, borderRadius: 2 }}>
          {askError}
        </Alert>
      )}

      {/* Ask panel */}
      <Paper
        elevation={0}
        sx={{
          p: { xs: 2, md: 2.5 },
          mb: 2.5,
          borderRadius: 3,
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: 'background.paper',
          boxShadow: '0 10px 30px -24px rgba(79,70,229,0.45)',
        }}
      >
        <form onSubmit={handleAsk}>
          <TextField
            fullWidth
            multiline
            minRows={1}
            maxRows={6}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!busy) handleAsk();
              }
            }}
            placeholder={ASK_PLACEHOLDER}
            disabled={busy}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <AutoAwesomeIcon color="primary" sx={{ fontSize: 20 }} />
                  </InputAdornment>
                ),
                endAdornment: q ? (
                  <InputAdornment position="end">
                    <IconButton size="small" onClick={() => setQ('')} edge="end" aria-label="clear question">
                      <ClearIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ) : null,
                sx: {
                  borderRadius: 2.5,
                  bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(148,163,184,0.05)' : 'rgba(15,23,42,0.02)'),
                  py: 0.5,
                  '& .MuiInputBase-input': {
                    fontSize: '1rem',
                    lineHeight: 1.45,
                  },
                },
              }
            }}
          />

          <Box
            sx={{
              display: 'flex',
              flexDirection: { xs: 'column', md: 'row' },
              alignItems: { xs: 'stretch', md: 'center' },
              justifyContent: 'space-between',
              gap: 1.5,
              mt: 2,
              pt: 2,
              borderTop: '1px solid',
              borderColor: 'divider',
            }}
          >
            {/* Filter controls */}
            <Box
              sx={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: 1.5,
                flex: 1,
              }}
            >
              {/* Jurisdiction */}
              <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 220, md: 240 }, flex: { sm: 1 } }}>
                <Select
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  displayEmpty
                  disabled={busy}
                  MenuProps={{ slotProps: { paper: { sx: { minWidth: 260, maxHeight: 340 } } } }}
                  sx={{
                    borderRadius: 2,
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)'),
                    '& .MuiSelect-select': {
                      py: 1,
                      display: 'flex',
                      alignItems: 'center',
                    },
                  }}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                      <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.82rem', fontWeight: 500, flexShrink: 0 }}>
                        Jurisdiction:
                      </Typography>
                      <Typography variant="body2" sx={{ color: 'text.primary', fontSize: '0.85rem', fontWeight: 650 }} noWrap>
                        {selected || 'All'}
                      </Typography>
                    </Box>
                  )}
                >
                  <MenuItem value="">All Jurisdictions</MenuItem>
                  {JURISDICTIONS.map((j) => (
                    <MenuItem key={j} value={j}>{j}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Domain */}
              <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 220, md: 240 }, flex: { sm: 1 } }}>
                <Select
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  displayEmpty
                  disabled={busy}
                  MenuProps={{ slotProps: { paper: { sx: { minWidth: 260, maxHeight: 340 } } } }}
                  sx={{
                    borderRadius: 2,
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)'),
                    '& .MuiSelect-select': {
                      py: 1,
                      display: 'flex',
                      alignItems: 'center',
                    },
                  }}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
                      <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.82rem', fontWeight: 500, flexShrink: 0 }}>
                        Domain:
                      </Typography>
                      <Typography variant="body2" sx={{ color: 'text.primary', fontSize: '0.85rem', fontWeight: 650 }} noWrap>
                        {selected
                          ? selected.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                          : 'All'}
                      </Typography>
                    </Box>
                  )}
                >
                  <MenuItem value="">All Domains</MenuItem>
                  {DOMAINS.map((d) => (
                    <MenuItem key={d} value={d}>
                      {d.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Top Sources */}
              <FormControl size="small" sx={{ minWidth: { xs: '100%', sm: 140 } }}>
                <Select
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  disabled={busy}
                  sx={{
                    borderRadius: 2,
                    bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)'),
                    '& .MuiSelect-select': {
                      py: 1,
                      display: 'flex',
                      alignItems: 'center',
                    },
                  }}
                  renderValue={(val) => (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                      <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.82rem', fontWeight: 500 }}>
                        Sources:
                      </Typography>
                      <Typography variant="body2" sx={{ color: 'text.primary', fontSize: '0.85rem', fontWeight: 600 }}>
                        {val}
                      </Typography>
                    </Box>
                  )}
                >
                  {TOP_K_OPTIONS.map((val) => (
                    <MenuItem key={val} value={val}>{val} Sources</MenuItem>
                  ))}
                </Select>
              </FormControl>

              {hasActiveFilters && (
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => {
                    setJurisdiction('');
                    setDomain('');
                  }}
                  disabled={busy}
                  sx={{
                    textTransform: 'none',
                    borderRadius: 2,
                    height: 40,
                    px: 1.5,
                    whiteSpace: 'nowrap',
                  }}
                >
                  Clear Filters
                </Button>
              )}
            </Box>

            {/* Action button */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: { xs: 'stretch', md: 'flex-end' } }}>
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={busy}
                startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <AutoAwesomeIcon />}
                sx={{
                  textTransform: 'none',
                  minWidth: { xs: '100%', md: 150 },
                  px: 3,
                  py: 1.1,
                  borderRadius: 2.5,
                  fontWeight: 600,
                  boxShadow: '0 4px 14px 0 rgba(79,70,229,0.39)',
                }}
              >
                {busy ? 'Working…' : 'Ask AI'}
              </Button>
            </Box>
          </Box>

          <Typography
            variant="caption"
            sx={{
              color: "text.secondary",
              display: 'block',
              mt: 1,
              pl: 0.5
            }}>
            Press <b>Enter</b> to ask · <b>Shift + Enter</b> for a new line
          </Typography>
        </form>
      </Paper>

      {busy && (
        <Paper elevation={0} sx={{ p: 2.5, mb: 2.5, borderRadius: 3, textAlign: 'center', bgcolor: 'transparent' }}>
          <LinearProgress sx={{ borderRadius: 2, height: 6, mb: 1.5 }} />
          <Stack
            direction="row"
            spacing={1.5}
            sx={{
              justifyContent: "center",
              alignItems: "center"
            }}>
            <SearchIcon color="disabled" fontSize="small" />
            <Typography variant="body2" sx={{
              color: "text.secondary"
            }}>
              {progress}
            </Typography>
          </Stack>
        </Paper>
      )}

      {busy && discovered.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Stack
            direction="row"
            spacing={1}
            sx={{
              alignItems: "center",
              mb: 1
            }}>
            <SearchIcon color="primary" fontSize="small" />
            <Typography variant="subtitle2" sx={{
              fontWeight: 700
            }}>
              Sources discovered ({discovered.length})
            </Typography>
            <CircularProgress size={13} sx={{ ml: 'auto' }} />
          </Stack>
          <Stack spacing={1}>
            {discovered.map((s) => (
              <Paper
                key={`discovered-${s.index}`}
                elevation={0}
                sx={{
                  p: 1.75,
                  borderRadius: 2.5,
                  border: '1px dashed',
                  borderColor: 'divider',
                  transition: 'border-color 0.15s ease',
                  '&:hover': { borderColor: 'primary.main' },
                }}
              >
                <Stack direction="row" spacing={1.5} sx={{
                  alignItems: "center"
                }}>
                  <CitationBadge index={s.index} />
                  <Typography
                    variant="body2"
                    noWrap
                    sx={{
                      fontWeight: 650,
                      minWidth: 0,
                      flex: 1
                    }}>
                    {s.title}
                  </Typography>
                  <Chip
                    size="small"
                    label={`${Math.round(s.score * 100)}% match`}
                    color="primary"
                    variant="outlined"
                    sx={{ height: 18, fontSize: '0.65rem', fontWeight: 650 }}
                  />
                </Stack>
                {s.snippet && <SourceSnippet text={s.snippet} />}
              </Paper>
            ))}
          </Stack>
        </Box>
      )}

      {phase === 'done' && (
        <Box sx={{ mb: 4 }}>
          {/* Answer */}
          <Paper
            elevation={0}
            sx={{
              p: { xs: 2, md: 3 },
              mb: 3,
              borderRadius: 3,
              border: '1px solid',
              borderColor: 'divider',
              bgcolor: isDark ? 'rgba(99,102,241,0.06)' : 'rgba(79,70,229,0.03)',
            }}
          >
            <Stack
              direction="row"
              sx={{
                justifyContent: "space-between",
                alignItems: "center",
                mb: 1.5,
                flexWrap: 'wrap',
                gap: 1
              }}>
              <Stack direction="row" spacing={1} sx={{
                alignItems: "center"
              }}>
                <CheckCircleIcon color="success" fontSize="small" />
                <Typography variant="subtitle2" sx={{
                  fontWeight: 700
                }}>
                  Answer
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1}>
                {answer && (
                  <Button size="small" startIcon={<ContentCopyIcon fontSize="small" />} onClick={copyAnswer} sx={{ textTransform: 'none' }}>
                    Copy Answer
                  </Button>
                )}
                <Button size="small" variant="text" onClick={handleNewQuestion} sx={{ textTransform: 'none' }}>
                  New Question
                </Button>
              </Stack>
            </Stack>
            <Box sx={{ color: 'text.primary', fontSize: '0.95rem', lineHeight: 1.75 }}>
              {typedAnswer ? (
                <ReactMarkdown components={markdownComponents}>{typedAnswer}</ReactMarkdown>
              ) : (
                <Typography variant="body2" sx={{
                  color: "text.secondary"
                }}>
                  …
                </Typography>
              )}
            </Box>
          </Paper>

          {sources.length > 0 && (
            <Box>
              <Stack
                direction="row"
                sx={{
                  justifyContent: "space-between",
                  alignItems: "center",
                  mb: 1.25
                }}>
                <Typography variant="h6" sx={{
                  fontWeight: 700
                }}>
                  Cited Sources ({sources.length})
                </Typography>
                <Typography variant="caption" sx={{
                  color: "text.secondary"
                }}>
                  Answer generated from {sources.length} cited passage{sources.length === 1 ? '' : 's'}
                </Typography>
              </Stack>
              <Stack spacing={1.5}>
                {sources.map((s) => (
                  <Paper
                    key={s.index}
                    elevation={0}
                    sx={{
                      p: { xs: 1.75, md: 2 },
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor: 'divider',
                      transition: 'transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease',
                      '&:hover': { borderColor: 'primary.main', transform: 'translateY(-1px)', boxShadow: theme.shadows[3] },
                    }}
                  >
                    <Stack
                      direction="row"
                      spacing={1}
                      sx={{
                        justifyContent: "space-between",
                        alignItems: "flex-start"
                      }}>
                      <Stack
                        direction="row"
                        spacing={1.5}
                        sx={{
                          alignItems: "flex-start",
                          minWidth: 0
                        }}>
                        <CitationBadge index={s.index} />
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="subtitle2" noWrap sx={{
                            fontWeight: 700
                          }}>
                            {s.title}
                          </Typography>
                          <Stack
                            direction="row"
                            spacing={1}
                            sx={{
                              flexWrap: "wrap",
                              alignItems: "center",
                              mt: 0.25
                            }}>
                            {s.filename && (
                              <Typography variant="caption" noWrap sx={{
                                color: "text.secondary"
                              }}>
                                {s.filename}
                              </Typography>
                            )}
                            {s.score !== undefined && s.score > 0 && (
                              <Chip size="small" label={`${Math.round(s.score * 100)}% match`} color="primary" variant="outlined" sx={{ height: 20, fontSize: '0.7rem', fontWeight: 600 }} />
                            )}
                          </Stack>
                        </Box>
                      </Stack>
                      <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0 }}>
                        {s.snippet && (
                          <Button
                            size="small"
                            startIcon={<ContentCopyIcon fontSize="small" />}
                            onClick={() => {
                              navigator.clipboard.writeText(s.snippet);
                              setToastMsg('Cited section copied to clipboard');
                            }}
                            sx={{ textTransform: 'none', display: { xs: 'none', sm: 'inline-flex' } }}
                          >
                            Copy Section
                          </Button>
                        )}
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<VisibilityIcon fontSize="small" />}
                          onClick={() => openInspect(s)}
                          sx={{ textTransform: 'none' }}
                        >
                          Inspect
                        </Button>
                      </Stack>
                    </Stack>
                    {s.snippet && <SourceSnippet text={s.snippet} />}
                  </Paper>
                ))}
              </Stack>
            </Box>
          )}

          {emptyLibrary && (
            <EmptyState
              icon={<SearchIcon sx={{ fontSize: 44, color: 'primary.main' }} />}
              title="No relevant content found"
              body={
                <span>
                  I could not find any matching passages in the current library. Upload contracts and other{' '}
                  documents via <b>Document Review</b>, then ask again.
                </span>
              }
              action={
                <Button variant="contained" component={Link} to="/review" sx={{ textTransform: 'none' }}>
                  Go to Document Review
                </Button>
              }
            />
          )}
        </Box>
      )}

      <InspectDocumentDialog
        open={Boolean(inspect)}
        docId={inspect?.docId}
        docHint={inspect?.docHint}
        filenameHint={inspect?.filenameHint}
        onClose={() => setInspect(null)}
        toast={setToastMsg}
      />

      <Snackbar
        open={Boolean(toastMsg)}
        autoHideDuration={3000}
        onClose={() => setToastMsg('')}
        message={toastMsg}
      />
    </Box>
  );
}