import { useEffect, useState } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  Paper,
  Stack,
  Tab,
  Tabs,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import AudiotrackIcon from '@mui/icons-material/Audiotrack';
import DownloadIcon from '@mui/icons-material/Download';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { api, streamJson } from '../../api/client';

const STATUS_LABEL = {
  pending: 'Pending',
  running: 'Running',
  opening: 'Opening statements',
  arguments: 'Arguments',
  judge_questions: 'Judicial questions',
  outcome: 'Outcome deliberation',
  completed: 'Completed',
  paused: 'Paused',
};

export default function RunDetailPage() {
  const { simulationId } = useParams();
  const isDark = useTheme().palette.mode === 'dark';

  const [sim, setSim] = useState(null);
  const [turns, setTurns] = useState([]);
  const [tab, setTab] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState('');
  const [loadError, setLoadError] = useState('');

  // Audio vertical (slice-2 reuse)
  const [audioAssets, setAudioAssets] = useState([]);
  const [audioError, setAudioError] = useState('');
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);

  const loadAudio = async (id) => {
    try {
      const assets = await api(`/simulations/${id}/audio`);
      setAudioAssets(assets ?? []);
    } catch (err) {
      setAudioError(err.message);
    }
  };

  useEffect(() => {
    if (!simulationId) return;
    let cancelled = false;
    (async () => {
      try {
        const s = await api(`/simulations/${simulationId}`);
        if (cancelled) return;
        setSim(s);
        setTurns(s.turns ?? []);
        loadAudio(simulationId);
      } catch (err) {
        if (!cancelled) setLoadError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [simulationId]);

  const advanceStream = async () => {
    if (!simulationId) return;
    setIsStreaming(true);
    setStreamError('');
    try {
      await streamJson(
        `/simulations/${simulationId}/advance/stream`,
        (name, data) => {
          if (name === '__data__' && data) {
            try {
              const cur = JSON.parse(data);
              setSim(cur);
              setTurns(cur.turns ?? []);
            } catch {
              /* partial frame — keep last good state */
            }
          }
        },
        { method: 'POST' },
      );
      loadAudio(simulationId);
    } catch (err) {
      setStreamError(err.message);
    } finally {
      setIsStreaming(false);
    }
  };

  const generateAudio = async () => {
    if (!simulationId) return;
    setIsGeneratingAudio(true);
    setAudioError('');
    try {
      await api(`/simulations/${simulationId}/audio`, { method: 'POST', body: {} });
      loadAudio(simulationId);
    } catch (err) {
      setAudioError(err.message);
    } finally {
      setIsGeneratingAudio(false);
    }
  };

  return (
    <Box>
      <Stack
        direction="row"
        spacing={1}
        sx={{
          alignItems: "center",
          mb: 2
        }}>
        <IconButton component={RouterLink} to="/simulations" size="small" aria-label="Back to runs">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h6" sx={{
          fontWeight: 700
        }}>
          Simulation Run
        </Typography>
      </Stack>

      {loadError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {loadError}
        </Alert>
      )}

      {sim && (
        <Card variant="outlined" sx={{ mb: 2, borderRadius: 3 }}>
          <CardContent>
            <Typography variant="h6">{sim.title || `Run ${sim.id}`}</Typography>
            <Stack
              direction="row"
              spacing={1.5}
              sx={{
                flexWrap: "wrap",
                mt: 1
              }}>
              <Chip
                size="small"
                label={STATUS_LABEL[sim.status] || sim.status}
                color={sim.status === 'completed' ? 'success' : 'primary'}
              />
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  alignSelf: 'center'
                }}>
                Phase: {sim.phase || '—'} · Turn {sim.current_turn ?? 0}
              </Typography>
            </Stack>
            {audioError && (
              <Alert severity="warning" sx={{ mt: 1.5 }}>
                {audioError}
              </Alert>
            )}
            <Stack direction="row" spacing={1.5} sx={{ mt: 2 }}>
              <Button
                size="small"
                variant="contained"
                onClick={advanceStream}
                disabled={isStreaming || sim.status === 'completed' || sim.status === 'paused'}
                startIcon={isStreaming ? <CircularProgress size={14} /> : <PlayArrowIcon />}
              >
                {isStreaming ? 'Streaming…' : 'Advance (stream)'}
              </Button>
              <Button
                size="small"
                variant="outlined"
                onClick={generateAudio}
                disabled={isGeneratingAudio}
                startIcon={isGeneratingAudio ? <CircularProgress size={14} /> : <AudiotrackIcon />}
              >
                {isGeneratingAudio ? 'Generating…' : 'Generate narration'}
              </Button>
            </Stack>
            {streamError && (
              <Alert severity="error" sx={{ mt: 1.5 }}>
                {streamError}
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      <Paper variant="outlined" sx={{ borderRadius: 3 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ px: 2, pt: 1 }}>
          <Tab label={`Transcript (${turns.length})`} />
          <Tab label={`Audio (${audioAssets.length})`} />
        </Tabs>

        {tab === 0 && (
          <Box sx={{ p: 2.5, maxHeight: 480, overflowY: 'auto' }}>
            {turns.length === 0 && (
              <Typography variant="body2" sx={{
                color: "text.secondary"
              }}>
                No turns yet. Click “Advance (stream)” to drive the tribunal turn-by-turn.
              </Typography>
            )}
            <Stack spacing={1.5}>
              {turns.map((t, i) => (
                <Box
                  key={t.id ?? i}
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    border: '1px solid',
                    borderColor: 'divider',
                    bgcolor: isDark ? 'rgba(124,58,237,0.06)' : '#faf5ff',
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 700,
                      color: "secondary.main"
                    }}>
                    {t.agent_role || 'narrator'} · Turn {t.turn_number ?? i + 1}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 0.5, whiteSpace: 'pre-wrap' }}>
                    {t.content}
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Box>
        )}

        {tab === 1 && (
          <Box sx={{ p: 2.5 }}>
            {audioAssets.length === 0 && (
              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  mb: 1.5
                }}>
                No narration yet. Generate it from the run card above, or advance the tribunal to completion first.
              </Typography>
            )}
            <Stack spacing={1.5}>
              {audioAssets.map((asset) => (
                <Box
                  key={asset.id}
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  <Typography variant="caption" sx={{
                    fontWeight: 700
                  }}>
                    {asset.kind === 'run'
                      ? 'Full case run'
                      : asset.kind === 'learning'
                        ? 'Learning narration'
                        : `${asset.agent_role || 'narrator'} · turn ${asset.turn_number}`}
                  </Typography>
                  {asset.duration_ms > 0 && (
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        display: "block"
                      }}>
                      {asset.duration_ms} ms · ≈{asset.estimated_tokens} tokens
                    </Typography>
                  )}
                  <Stack
                    direction="row"
                    spacing={1}
                    sx={{
                      alignItems: "center",
                      mt: 1
                    }}>
                    {asset.url ? (
                      <>
                        <audio controls preload="none" src={asset.url} style={{ maxWidth: 320, height: 32 }}>
                          <track kind="captions" />
                        </audio>
                        <IconButton
                          component="a"
                          href={asset.url}
                          download
                          size="small"
                          aria-label="Download audio"
                        >
                          <DownloadIcon fontSize="small" />
                        </IconButton>
                      </>
                    ) : (
                      <Typography variant="caption" sx={{
                        color: "text.secondary"
                      }}>
                        {asset.status === 'error' ? `Error: ${asset.error}` : 'Pending…'}
                      </Typography>
                    )}
                  </Stack>
                </Box>
              ))}
            </Stack>
          </Box>
        )}
      </Paper>
    </Box>
  );
}
