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
  FormControl,
  InputLabel,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import ArticleIcon from '@mui/icons-material/Article';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DescriptionIcon from '@mui/icons-material/Description';
import DriveFolderUploadIcon from '@mui/icons-material/DriveFolderUpload';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutlined';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import RefreshIcon from '@mui/icons-material/Refresh';
import ScheduleIcon from '@mui/icons-material/Schedule';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import { useRef, useState } from 'react';
import { api } from '../api/client';
import { DOC_TYPES, DOMAINS, JURISDICTIONS } from './documentMeta';

function formatSize(bytes) {
  if (bytes === undefined || bytes === null || isNaN(bytes)) return '';
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
}

function formatTime(ms) {
  if (ms === undefined || ms === null) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function getFileIcon(filename = '') {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.pdf')) {
    return <PictureAsPdfIcon color="error" fontSize="small" />;
  }
  if (lower.endsWith('.docx') || lower.endsWith('.doc')) {
    return <ArticleIcon color="primary" fontSize="small" />;
  }
  return <DescriptionIcon color="action" fontSize="small" />;
}

function humanizeError(err) {
  if (err.status === 413) {
    return 'File exceeds the 25 MB size limit.';
  }
  if (err.status === 415) {
    return 'Unsupported file type — use PDF, DOCX, DOC, TXT, or Markdown.';
  }
  const reason = err.message && err.message !== 'Request failed' ? err.message : null;
  if (reason) {
    return `Upload failed: ${reason}`;
  }
  return `Upload failed (HTTP ${err.status || 'unknown'}). Check the file and try again.`;
}

function makeJob(file, idx) {
  return {
    key: `${idx}-${file.webkitRelativePath || file.name}`,
    filename: file.webkitRelativePath || file.name,
    name: file.name,
    size: file.size,
    sizeLabel: formatSize(file.size),
    state: 'queued',
    error: '',
    elapsed: null,
    doc: null,
  };
}

const STATUS_META = {
  uploading: { icon: <CircularProgress size={14} />, label: 'Uploading', color: 'default' },
  indexed: { icon: <CheckCircleIcon fontSize="small" color="success" />, label: 'Indexed', color: 'success' },
  conflict: { icon: <WarningAmberIcon fontSize="small" color="warning" />, label: 'Already exists', color: 'warning' },
  skipped: { icon: <SkipNextIcon fontSize="small" color="disabled" />, label: 'Skipped', color: 'default' },
  error: { icon: <ErrorOutlineIcon fontSize="small" color="error" />, label: 'Failed', color: 'error' },
};

const QUEUED_META = { icon: <ScheduleIcon fontSize="small" color="disabled" />, label: 'Queued', color: 'default' };

function ResultChip({ state }) {
  const meta = STATUS_META[state] || QUEUED_META;
  return (
    <Chip
      size="small"
      icon={meta.icon}
      label={meta.label}
      color={meta.color === 'default' ? 'default' : meta.color}
      variant="outlined"
      sx={{ fontWeight: 600 }}
    />
  );
}

function FileRow({ job }) {
  return (
    <Box
      sx={{
        py: 1,
        px: 1.5,
        borderRadius: 2,
        border: '1px solid',
        borderColor: job.state === 'error' ? 'error.light' : 'divider',
        bgcolor: (theme) =>
          theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.02)',
      }}
    >
      <Stack
        direction="row"
        spacing={1.5}
        sx={{
          justifyContent: "space-between",
          alignItems: "center"
        }}>
        <Stack
          direction="row"
          spacing={1}
          sx={{
            alignItems: "center",
            minWidth: 0
          }}>
          {getFileIcon(job.filename)}
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" noWrap sx={{
              fontWeight: 600
            }}>
              {job.filename}
            </Typography>
            <Stack
              direction="row"
              spacing={1}
              sx={{
                alignItems: "center",
                flexWrap: "wrap"
              }}>
              {job.sizeLabel && (
                <Typography variant="caption" sx={{
                  color: "text.secondary"
                }}>
                  {job.sizeLabel}
                </Typography>
              )}
              {job.elapsed !== null && (
                <Typography
                  variant="caption"
                  sx={{
                    color: "text.secondary",
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 0.4
                  }}>
                  <AccessTimeIcon sx={{ fontSize: 12 }} />
                  {formatTime(job.elapsed)}
                </Typography>
              )}
              {job.doc?.status && (
                <Typography variant="caption" color="primary">
                  {job.doc.status}
                </Typography>
              )}
            </Stack>
          </Box>
        </Stack>
        <ResultChip state={job.state} />
      </Stack>
      {job.error && (
        <Alert severity="error" icon={false} sx={{ mt: 0.75, py: 0, borderRadius: 1.5 }}>
          <Typography variant="caption">{job.error}</Typography>
        </Alert>
      )}
    </Box>
  );
}

export default function DocumentUploader({ onUploaded }) {
  const theme = useTheme();
  const fileRef = useRef(null);
  const folderRef = useRef(null);

  const [mode, setMode] = useState('file');
  const [selectedFile, setSelectedFile] = useState(null);
  const [folderFiles, setFolderFiles] = useState([]);
  const [title, setTitle] = useState('');
  const [docCategory, setDocCategory] = useState('knowledge_artefact');
  const [docType, setDocType] = useState('contract');
  const [jurisdiction, setJurisdiction] = useState('');
  const [domain, setDomain] = useState('');
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [alertInfo, setAlertInfo] = useState({ show: false, message: '', severity: 'info' });
  const [conflictPrompt, setConflictPrompt] = useState(null);
  // { files: File[], names: string[], uploaded: number, failed: number }

  const isReady = mode === 'file' ? Boolean(selectedFile) : folderFiles.length > 0;

  function clearPicker() {
    if (mode !== 'file') return;
    setSelectedFile(null);
    if (fileRef.current) fileRef.current.value = '';
    setTitle('');
  }

  async function runJobs(files, { overwrite = false, title: docTitle = '', jobIndices = null } = {}) {
    if (!files.length) {
      setAlertInfo({ show: true, message: 'Please select a document file or folder first.', severity: 'warning' });
      return null;
    }
    setBusy(true);
    setAlertInfo({ show: false, message: '', severity: 'info' });

    const resetting = !jobIndices;
    // Keep a local snapshot so progress updates don't race React state.
    let snapshot = resetting
      ? files.map((f, idx) => makeJob(f, idx))
      : null;

    if (resetting) {
      setSummary(null);
      setJobs(snapshot);
    }

    const patchJob = (index, patch) => {
      if (snapshot) {
        snapshot = snapshot.map((job, i) => (i === index ? { ...job, ...patch } : job));
        setJobs(snapshot);
        return;
      }
      setJobs((prev) => prev.map((job, i) => (i === index ? { ...job, ...patch } : job)));
    };

    const startedAt = performance.now();
    const totals = { uploaded: 0, conflict: 0, failed: 0, skipped: 0 };
    const conflictFiles = [];
    const conflictIndices = [];

    for (let i = 0; i < files.length; i += 1) {
      const file = files[i];
      const targetIndex = jobIndices ? jobIndices[i] : i;
      patchJob(targetIndex, { state: 'uploading', error: '' });
      const t0 = performance.now();
      try {
        const form = new FormData();
        form.append('file', file, file.webkitRelativePath || file.name);
        if (docTitle) form.append('title', docTitle);
        form.append('doc_category', docCategory);
        form.append('doc_type', docType);
        if (jurisdiction) form.append('jurisdiction', jurisdiction);
        if (domain) form.append('domain', domain);
        if (overwrite) form.append('overwrite', 'true');

        const doc = await api('/documents/upload', { method: 'POST', form });
        totals.uploaded += 1;
        patchJob(targetIndex, { state: 'indexed', elapsed: performance.now() - t0, doc, error: '' });
      } catch (err) {
        if (err.status === 409 && !overwrite) {
          totals.conflict += 1;
          conflictFiles.push(file);
          conflictIndices.push(targetIndex);
          patchJob(targetIndex, {
            state: 'conflict',
            elapsed: performance.now() - t0,
            error: 'Already exists in your library.',
          });
        } else {
          totals.failed += 1;
          patchJob(targetIndex, {
            state: 'error',
            elapsed: performance.now() - t0,
            error: humanizeError(err),
          });
        }
      }
    }

    setBusy(false);
    setSummary({ totals, elapsed: performance.now() - startedAt });
    if (totals.uploaded > 0) onUploaded?.();
    return { totals, conflictFiles, conflictIndices, elapsed: performance.now() - startedAt };
  }

  async function handleUpload() {
    if (!isReady) {
      setAlertInfo({ show: true, message: 'Please select a document file or folder first.', severity: 'warning' });
      return;
    }

    const files = mode === 'folder' ? folderFiles : selectedFile ? [selectedFile] : [];
    const docTitle = mode === 'file' ? title.trim() : '';
    const result = await runJobs(files, { overwrite: false, title: docTitle });
    if (!result) return;

    if (result.totals.conflict > 0) {
      setConflictPrompt({
        files: result.conflictFiles,
        indices: result.conflictIndices,
        names: result.conflictFiles.map((f) => f.webkitRelativePath || f.name),
        uploaded: result.totals.uploaded,
        failed: result.totals.failed,
      });
      return;
    }

    if (result.totals.uploaded > 0 && result.totals.failed === 0) {
      clearPicker();
    }
  }

  async function resolveConflicts(action) {
    const prompt = conflictPrompt;
    if (!prompt) return;
    setConflictPrompt(null);

    if (action === 'replace') {
      const docTitle = mode === 'file' ? title.trim() : '';
      const priorUploaded = prompt.uploaded;
      const priorFailed = prompt.failed;
      const result = await runJobs(prompt.files, {
        overwrite: true,
        title: docTitle,
        jobIndices: prompt.indices,
      });
      if (result) {
        setSummary({
          elapsed: result.elapsed,
          totals: {
            uploaded: priorUploaded + result.totals.uploaded,
            conflict: 0,
            failed: priorFailed + result.totals.failed,
            skipped: 0,
          },
        });
        if (priorUploaded + result.totals.uploaded > 0 && priorFailed + result.totals.failed === 0) {
          clearPicker();
        }
      }
      return;
    }

    // Skip existing — keep newly ingested docs; leave library copies untouched.
    setJobs((prev) =>
      prev.map((job, idx) =>
        prompt.indices.includes(idx)
          ? {
              ...job,
              state: 'skipped',
              error: 'Skipped — kept the existing library copy.',
            }
          : job,
      ),
    );
    setSummary((prev) => ({
      elapsed: prev?.elapsed || 0,
      totals: {
        uploaded: prompt.uploaded,
        conflict: 0,
        failed: prompt.failed,
        skipped: prompt.files.length,
      },
    }));
    setAlertInfo({
      show: true,
      severity: prompt.uploaded > 0 ? 'success' : 'info',
      message:
        prompt.uploaded > 0
          ? `Skipped ${prompt.files.length} existing document${prompt.files.length === 1 ? '' : 's'}. ${prompt.uploaded} new document${prompt.uploaded === 1 ? '' : 's'} ingested.`
          : `Skipped ${prompt.files.length} existing document${prompt.files.length === 1 ? '' : 's'}. Nothing new was ingested.`,
    });
    if (prompt.uploaded > 0) clearPicker();
  }

  function clearJobs() {
    setJobs([]);
    setSummary(null);
    setConflictPrompt(null);
  }

  const done = jobs.filter((j) => j.state !== 'queued' && j.state !== 'uploading').length;
  const percent = jobs.length ? Math.round((done / jobs.length) * 100) : 0;
  const pickButtons = (
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
      <Button
        variant={mode === 'file' ? 'contained' : 'outlined'}
        startIcon={<InsertDriveFileIcon />}
        onClick={() => {
          setMode('file');
          clearJobs();
          setSelectedFile(null);
          setFolderFiles([]);
        }}
        sx={{ textTransform: 'none', borderRadius: 2 }}
      >
        Single File
      </Button>
      <Button
        variant={mode === 'folder' ? 'contained' : 'outlined'}
        startIcon={<DriveFolderUploadIcon />}
        onClick={() => {
          setMode('folder');
          clearJobs();
          setSelectedFile(null);
        }}
        sx={{ textTransform: 'none', borderRadius: 2 }}
      >
        Entire Folder
      </Button>

      {mode === 'file' ? (
        <Button
          variant="outlined"
          color="secondary"
          startIcon={<CloudUploadIcon />}
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          sx={{ textTransform: 'none', borderRadius: 2, flexGrow: { xs: 1, sm: 0 } }}
        >
          Choose File
        </Button>
      ) : (
        <Button
          variant="outlined"
          color="secondary"
          startIcon={<DriveFolderUploadIcon />}
          onClick={() => folderRef.current?.click()}
          disabled={busy}
          sx={{ textTransform: 'none', borderRadius: 2, flexGrow: { xs: 1, sm: 0 } }}
        >
          Choose Folder
        </Button>
      )}
    </Stack>
  );

  return (
    <Box>
      <input
        type="file"
        ref={fileRef}
        accept=".pdf,.docx,.doc,.txt,.md,.markdown"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) {
            setSelectedFile(f);
            clearJobs();
          }
        }}
      />
      <input
        type="file"
        ref={folderRef}
        webkitdirectory=""
        multiple
        style={{ display: 'none' }}
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          if (files.length) {
            setFolderFiles(files);
            clearJobs();
          }
        }}
      />

      {pickButtons}

      {mode === 'file' ? (
        <Box
          sx={{
            border: '1px dashed',
            borderColor: selectedFile ? 'primary.main' : 'divider',
            borderRadius: 2,
            p: 2,
            textAlign: 'center',
            bgcolor: 'background.paper',
            cursor: 'pointer',
            '&:hover': { borderColor: 'primary.main' },
          }}
          onClick={() => fileRef.current?.click()}
        >
          <CloudUploadIcon color="primary" sx={{ fontSize: 36, mb: 0.5 }} />
          <Typography variant="body2" sx={{
            fontWeight: 600
          }}>
            {selectedFile ? selectedFile.name : 'Click or browse to choose a file'}
          </Typography>
          <Typography variant="caption" sx={{
            color: "text.secondary"
          }}>
            {selectedFile
              ? `${formatSize(selectedFile.size)} · ${selectedFile.type || 'document'}`
              : 'PDF, DOCX, TXT, MD — max 25MB per file'}
          </Typography>
        </Box>
      ) : (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ mb: 2 }}>
          <Box
            sx={{
              flex: 1,
              border: '1px dashed',
              borderColor: folderFiles.length ? 'primary.main' : 'divider',
              borderRadius: 2,
              p: 2,
              textAlign: 'center',
              bgcolor: 'background.paper',
              cursor: 'pointer',
              '&:hover': { borderColor: 'primary.main' },
            }}
            onClick={() => folderRef.current?.click()}
          >
            <DriveFolderUploadIcon color="primary" sx={{ fontSize: 32, mb: 0.5 }} />
            <Typography variant="body2" sx={{
              fontWeight: 600
            }}>
              {folderFiles.length > 0 ? `${folderFiles.length} file${folderFiles.length === 1 ? '' : 's'} selected` : 'Click or browse to choose a folder'}
            </Typography>
            <Typography variant="caption" sx={{
              color: "text.secondary"
            }}>
              Every document inside the folder is uploaded and indexed one by one, with progress shown per file.
            </Typography>
          </Box>
          {folderFiles.length > 0 && (
            <Paper
              variant="outlined"
              sx={{
                flex: 1,
                p: 1.5,
                borderRadius: 2,
                maxHeight: 130,
                overflowY: 'auto',
                bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.25)' : 'rgba(0,0,0,0.02)',
              }}
            >
              {folderFiles.slice(0, 12).map((f) => (
                <Typography key={f.webkitRelativePath || f.name} variant="caption" noWrap sx={{
                  display: "block"
                }}>
                  {f.webkitRelativePath || f.name}
                </Typography>
              ))}
              {folderFiles.length > 12 && (
                <Typography variant="caption" sx={{
                  color: "text.secondary"
                }}>
                  + {folderFiles.length - 12} more
                </Typography>
              )}
            </Paper>
          )}
        </Stack>
      )}

      <Stack spacing={1.5} sx={{ mt: 2.25 }}>
        {/* Row 1: Category & Title */}
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
          <FormControl size="small" sx={{ minWidth: { xs: '100%', md: 280 } }}>
            <InputLabel>Document Category</InputLabel>
            <Select
              value={docCategory}
              label="Document Category"
              onChange={(e) => setDocCategory(e.target.value)}
              MenuProps={{ slotProps: { paper: { sx: { minWidth: 280 } } } }}
            >
              <MenuItem value="knowledge_artefact">
                <Box>
                  <Typography variant="body2" sx={{
                    fontWeight: 650
                  }}>Knowledge Artefact</Typography>
                  <Typography variant="caption" sx={{
                    color: "text.secondary"
                  }}>Grounding precedent for simulations & RAG</Typography>
                </Box>
              </MenuItem>
              <MenuItem value="contract_review">
                <Box>
                  <Typography variant="body2" sx={{
                    fontWeight: 650
                  }}>Contract Review</Typography>
                  <Typography variant="caption" sx={{
                    color: "text.secondary"
                  }}>Commercial contract for risk auditing</Typography>
                </Box>
              </MenuItem>
            </Select>
          </FormControl>

          {mode === 'file' && (
            <TextField
              label="Document title (optional)"
              fullWidth
              size="small"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Master Services Agreement 2026"
            />
          )}
        </Stack>

        {/* Row 2: Type, Jurisdiction, Domain */}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
          <FormControl fullWidth size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Type</InputLabel>
            <Select
              value={docType}
              label="Type"
              onChange={(e) => setDocType(e.target.value)}
              MenuProps={{ slotProps: { paper: { sx: { minWidth: 200, maxHeight: 320 } } } }}
            >
              {DOC_TYPES.map((t) => (
                <MenuItem key={t} value={t} sx={{ textTransform: 'capitalize' }}>{t}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Jurisdiction</InputLabel>
            <Select
              value={jurisdiction}
              label="Jurisdiction"
              onChange={(e) => setJurisdiction(e.target.value)}
              MenuProps={{ slotProps: { paper: { sx: { minWidth: 220, maxHeight: 320 } } } }}
            >
              <MenuItem value="">None / Global</MenuItem>
              {JURISDICTIONS.map((j) => (
                <MenuItem key={j} value={j}>{j}</MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth size="small" sx={{ minWidth: 180 }}>
            <InputLabel>Domain</InputLabel>
            <Select
              value={domain}
              label="Domain"
              onChange={(e) => setDomain(e.target.value)}
              MenuProps={{ slotProps: { paper: { sx: { minWidth: 220, maxHeight: 320 } } } }}
            >
              <MenuItem value="">None / General</MenuItem>
              {DOMAINS.map((d) => (
                <MenuItem key={d} value={d} sx={{ textTransform: 'capitalize' }}>
                  {d.replace(/_/g, ' ')}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>
      </Stack>

      <Stack
        direction="row"
        spacing={2}
        sx={{
          justifyContent: "flex-end",
          alignItems: "center",
          mt: 2
        }}>
        {!isReady && (
          <Typography variant="caption" sx={{
            color: "text.secondary"
          }}>
            Nothing selected yet
          </Typography>
        )}
        <Button
          variant="contained"
          disabled={!isReady || busy}
          startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <CloudUploadIcon />}
          onClick={() => handleUpload()}
          sx={{ textTransform: 'none', borderRadius: 2, minWidth: 180 }}
        >
          {busy ? 'Uploading & Indexing...' : mode === 'folder' ? 'Upload Folder' : 'Upload & Index'}
        </Button>
      </Stack>

      {alertInfo.show && (
        <Alert
          severity={alertInfo.severity}
          onClose={() => setAlertInfo({ ...alertInfo, show: false })}
          sx={{ mt: 2, borderRadius: 2 }}
        >
          {alertInfo.message}
        </Alert>
      )}

      <Dialog
        open={Boolean(conflictPrompt)}
        onClose={() => resolveConflicts('skip')}
        maxWidth="sm"
        fullWidth
        slotProps={{ paper: { sx: { borderRadius: 3 } } }}
      >
        <DialogTitle sx={{ fontWeight: 700, pb: 1 }}>
          {conflictPrompt?.files.length === 1
            ? 'Document already exists'
            : `${conflictPrompt?.files.length || 0} documents already exist`}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            {conflictPrompt?.uploaded > 0
              ? `${conflictPrompt.uploaded} new document${conflictPrompt.uploaded === 1 ? '' : 's'} already ingested. What should we do with the duplicates?`
              : 'Choose whether to replace the existing library copies, or skip them and keep only newly ingested documents.'}
          </Typography>
          <Paper variant="outlined" sx={{ borderRadius: 2, maxHeight: 220, overflow: 'auto' }}>
            <List dense disablePadding>
              {(conflictPrompt?.names || []).slice(0, 12).map((name) => (
                <ListItem key={name} divider>
                  <ListItemIcon sx={{ minWidth: 36 }}>{getFileIcon(name)}</ListItemIcon>
                  <ListItemText
                    primary={name}
                    slotProps={{ primary: { noWrap: true, fontSize: '0.875rem' } }}
                  />
                </ListItem>
              ))}
              {(conflictPrompt?.names?.length || 0) > 12 && (
                <ListItem>
                  <ListItemText
                    primary={`…and ${conflictPrompt.names.length - 12} more`}
                    slotProps={{ primary: { color: 'text.secondary', fontSize: '0.8rem' } }}
                  />
                </ListItem>
              )}
            </List>
          </Paper>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5, gap: 1, flexWrap: 'wrap' }}>
          <Button
            onClick={() => resolveConflicts('skip')}
            startIcon={<SkipNextIcon />}
            sx={{ textTransform: 'none' }}
            disabled={busy}
          >
            {conflictPrompt?.uploaded > 0
              ? 'Skip duplicates — keep new only'
              : 'Skip — don’t ingest'}
          </Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() => resolveConflicts('replace')}
            startIcon={<RefreshIcon />}
            sx={{ textTransform: 'none' }}
            disabled={busy}
          >
            Replace existing
          </Button>
        </DialogActions>
      </Dialog>

      {jobs.length > 0 && (
        <Paper variant="outlined" sx={{ mt: 2, p: 1.5, borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.02)' }}>
          <Stack
            direction="row"
            sx={{
              justifyContent: "space-between",
              alignItems: "center",
              mb: 1
            }}>
            <Typography variant="subtitle2" sx={{
              fontWeight: 700
            }}>
              {busy ? 'Uploading documents…' : `${jobs.length} file${jobs.length === 1 ? '' : 's'} processed`}
            </Typography>
            <Tooltip title="Clear results">
              <Button size="small" onClick={clearJobs} disabled={busy} sx={{ textTransform: 'none' }}>
                Clear
              </Button>
            </Tooltip>
          </Stack>

          {busy && (
            <Box sx={{ mb: 1 }}>
              <LinearProgress variant="determinate" value={percent} sx={{ height: 6, borderRadius: 2, mb: 0.5 }} />
              <Typography variant="caption" sx={{
                color: "text.secondary"
              }}>
                {done} of {jobs.length} files processed
              </Typography>
            </Box>
          )}

          {summary && (
            <Alert
              severity={
                summary.totals.failed > 0
                  ? 'error'
                  : summary.totals.conflict > 0
                    ? 'warning'
                    : 'success'
              }
              icon={false}
              sx={{ mb: 1, borderRadius: 2 }}
            >
              <Typography variant="body2" sx={{
                fontWeight: 600
              }}>
                Finished in {formatTime(summary.elapsed)} — {summary.totals.uploaded} uploaded
                {summary.totals.skipped ? `, ${summary.totals.skipped} skipped` : ''}
                {summary.totals.conflict ? `, ${summary.totals.conflict} already existed` : ''}
                {summary.totals.failed ? `, ${summary.totals.failed} failed` : ''}.
              </Typography>
            </Alert>
          )}

          <Stack divider={<Box sx={{ height: 1, bgcolor: 'divider' }} />} spacing={1}>
            {jobs.map((job) => (
              <FileRow key={job.key} job={job} />
            ))}
          </Stack>
        </Paper>
      )}
    </Box>
  );
}