import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputLabel,
  LinearProgress,
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
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1.5}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
          {getFileIcon(job.filename)}
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" fontWeight={600} noWrap>
              {job.filename}
            </Typography>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              {job.sizeLabel && (
                <Typography variant="caption" color="text.secondary">
                  {job.sizeLabel}
                </Typography>
              )}
              {job.elapsed !== null && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.4 }}>
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

  const isReady = mode === 'file' ? Boolean(selectedFile) : folderFiles.length > 0;
  const conflictCount = jobs.filter((j) => j.state === 'conflict').length;

  function updateJob(index, patch) {
    setJobs((prev) => prev.map((job, i) => (i === index ? { ...job, ...patch } : job)));
  }

  async function runJobs(files, { overwrite = false, title: docTitle = '' } = {}) {
    if (!files.length) {
      setAlertInfo({ show: true, message: 'Please select a document file or folder first.', severity: 'warning' });
      return;
    }
    setBusy(true);
    setAlertInfo({ show: false, message: '', severity: 'info' });
    setSummary(null);
    const initial = files.map((f, idx) => makeJob(f, idx));
    setJobs(initial);

    const startedAt = performance.now();
    const totals = { uploaded: 0, conflict: 0, failed: 0 };

    for (let i = 0; i < files.length; i += 1) {
      const file = files[i];
      updateJob(i, { state: 'uploading', error: '' });
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
        updateJob(i, { state: 'indexed', elapsed: performance.now() - t0, doc });
      } catch (err) {
        if (err.status === 409) {
          totals.conflict += 1;
          updateJob(i, {
            state: 'conflict',
            elapsed: performance.now() - t0,
            error: 'This document already exists in your library. Choose "Replace conflicts" to re-index it.',
          });
        } else {
          totals.failed += 1;
          updateJob(i, { state: 'error', elapsed: performance.now() - t0, error: humanizeError(err) });
        }
      }
    }

    setBusy(false);
    setSummary({ totals, elapsed: performance.now() - startedAt });
    if (totals.uploaded > 0) onUploaded?.();
    return totals;
  }

  async function handleUpload(overwrite = false) {
    if (!isReady) {
      setAlertInfo({ show: true, message: 'Please select a document file or folder first.', severity: 'warning' });
      return;
    }

    const files = mode === 'folder' ? folderFiles : selectedFile ? [selectedFile] : [];
    const totals = await runJobs(files, {
      overwrite,
      title: mode === 'file' ? title.trim() : '',
    });

    // A clean single-file upload clears the picker so the next file is easy to add.
    if (mode === 'file' && !overwrite && totals.uploaded === 1 && totals.conflict === 0 && totals.failed === 0) {
      setSelectedFile(null);
      if (fileRef.current) fileRef.current.value = '';
      setTitle('');
    }
  }

  function replaceConflicts() {
    if (!conflictCount) return;
    if (mode === 'folder') {
      const files = folderFiles.filter((file, i) => jobs[i]?.state === 'conflict');
      runJobs(files, { overwrite: true });
    } else if (selectedFile) {
      runJobs([selectedFile], { overwrite: true });
    }
  }

  function clearJobs() {
    setJobs([]);
    setSummary(null);
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
          <Typography variant="body2" fontWeight={600}>
            {selectedFile ? selectedFile.name : 'Click or browse to choose a file'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
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
            <Typography variant="body2" fontWeight={600}>
              {folderFiles.length > 0 ? `${folderFiles.length} file${folderFiles.length === 1 ? '' : 's'} selected` : 'Click or browse to choose a folder'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
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
                <Typography key={f.webkitRelativePath || f.name} variant="caption" display="block" noWrap>
                  {f.webkitRelativePath || f.name}
                </Typography>
              ))}
              {folderFiles.length > 12 && (
                <Typography variant="caption" color="text.secondary">
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
              MenuProps={{ PaperProps: { sx: { minWidth: 280 } } }}
            >
              <MenuItem value="knowledge_artefact">
                <Box>
                  <Typography variant="body2" fontWeight={650}>Knowledge Artefact</Typography>
                  <Typography variant="caption" color="text.secondary">Grounding precedent for simulations & RAG</Typography>
                </Box>
              </MenuItem>
              <MenuItem value="contract_review">
                <Box>
                  <Typography variant="body2" fontWeight={650}>Contract Review</Typography>
                  <Typography variant="caption" color="text.secondary">Commercial contract for risk auditing</Typography>
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
              MenuProps={{ PaperProps: { sx: { minWidth: 200, maxHeight: 320 } } }}
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
              MenuProps={{ PaperProps: { sx: { minWidth: 220, maxHeight: 320 } } }}
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
              MenuProps={{ PaperProps: { sx: { minWidth: 220, maxHeight: 320 } } }}
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

      <Stack direction="row" justifyContent="flex-end" alignItems="center" spacing={2} sx={{ mt: 2 }}>
        {!isReady && (
          <Typography variant="caption" color="text.secondary">
            Nothing selected yet
          </Typography>
        )}
        <Button
          variant="contained"
          disabled={!isReady || busy}
          startIcon={busy ? <CircularProgress size={18} color="inherit" /> : <CloudUploadIcon />}
          onClick={() => handleUpload(false)}
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

      {conflictCount > 0 && (
        <Alert
          severity="warning"
          action={
            <Button size="small" color="inherit" startIcon={<RefreshIcon />} onClick={replaceConflicts} disabled={busy}>
              Replace {conflictCount}
            </Button>
          }
          icon={<WarningAmberIcon fontSize="small" />}
          sx={{ mt: 2, borderRadius: 2 }}
        >
          {conflictCount} existing document{conflictCount === 1 ? '' : 's'} will be replaced with fresh content and re-indexed.
        </Alert>
      )}

      {jobs.length > 0 && (
        <Paper variant="outlined" sx={{ mt: 2, p: 1.5, borderRadius: 2, bgcolor: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.2)' : 'rgba(0,0,0,0.02)' }}>
          <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
            <Typography variant="subtitle2" fontWeight={700}>
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
              <Typography variant="caption" color="text.secondary">
                {done} of {jobs.length} files processed
              </Typography>
            </Box>
          )}

          {summary && (
            <Alert
              severity={summary.totals.failed > 0 ? 'warning' : 'success'}
              icon={false}
              sx={{ mb: 1, borderRadius: 2 }}
            >
              <Typography variant="body2" fontWeight={600}>
                Finished in {formatTime(summary.elapsed)} — {summary.totals.uploaded} uploaded, {summary.totals.conflict} already existed, {summary.totals.failed} failed.
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