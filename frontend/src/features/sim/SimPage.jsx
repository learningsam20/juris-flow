import {
  Alert,
  Autocomplete,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  Grid,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  Step,
  StepLabel,
  Stepper,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AddIcon from '@mui/icons-material/Add';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BalanceIcon from '@mui/icons-material/Balance';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutlined';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutlined';
import EditIcon from '@mui/icons-material/Edit';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import GavelIcon from '@mui/icons-material/Gavel';
import HeadphonesIcon from '@mui/icons-material/Headphones';
import HistoryIcon from '@mui/icons-material/History';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PsychologyIcon from '@mui/icons-material/Psychology';
import RefreshIcon from '@mui/icons-material/Refresh';
import ShieldIcon from '@mui/icons-material/Shield';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import StorageIcon from '@mui/icons-material/Storage';
import TokenIcon from '@mui/icons-material/Token';
import TuneIcon from '@mui/icons-material/Tune';
import VolumeUpIcon from '@mui/icons-material/VolumeUp';
import DownloadIcon from '@mui/icons-material/Download';
import CloseIcon from '@mui/icons-material/Close';
import ArticleIcon from '@mui/icons-material/Article';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import FilterListIcon from '@mui/icons-material/FilterList';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import EventIcon from '@mui/icons-material/Event';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import FlashOnIcon from '@mui/icons-material/FlashOn';
import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../../api/client';
import { JURISDICTIONS } from '../../components/documentMeta';
import { EmptyState } from '../../components/ui';

const SIM_PHASES = ['opening', 'arguments', 'judge_questions', 'outcome'];
const PHASE_LABELS = {
  opening: 'Opening Statements',
  arguments: 'Adversarial Arguments',
  judge_questions: 'Judicial Inquiry',
  outcome: 'Judicial Ruling & Case Study',
};

const EXHAUSTIVE_SEQUENCE = [
  {
    id: 'openings',
    label: 'Opening Statements',
    phase: 'opening',
    targetId: 'section-openings',
    icon: <ShieldIcon sx={{ fontSize: 18 }} />,
    description: 'Initial positions, party claims & statutory grounds',
  },
  {
    id: 'arguments',
    label: 'Adversarial Arguments',
    phase: 'arguments',
    targetId: 'section-arguments',
    icon: <BalanceIcon sx={{ fontSize: 18 }} />,
    description: 'Multi-turn legal rebuttals & cross-examinations',
  },
  {
    id: 'inquiry',
    label: 'Judicial Inquiry',
    phase: 'judge_questions',
    targetId: 'section-inquiry',
    icon: <PsychologyIcon sx={{ fontSize: 18 }} />,
    description: 'Bench interrogation, evidentiary questions & standards',
  },
  {
    id: 'verdict',
    label: 'Judicial Ruling & Verdict',
    phase: 'outcome',
    targetId: 'section-verdict',
    icon: <GavelIcon sx={{ fontSize: 18 }} />,
    description: 'Final bench ruling, party award & determination',
  },
  {
    id: 'audio',
    label: 'Courtroom Audio Broadcast',
    phase: 'completed',
    targetId: 'section-audio',
    icon: <HeadphonesIcon sx={{ fontSize: 18 }} />,
    description: 'Dual neural voice podcasts: Overview & Live Hearing',
  },
  {
    id: 'casestudy',
    label: 'Post-Trial Case Study',
    phase: 'completed',
    targetId: 'section-case-study',
    icon: <MenuBookIcon sx={{ fontSize: 18 }} />,
    description: 'Exhaustive doctrinal analysis & statutory precedents',
  },
];

const AGENT_CONFIGS = {
  judge: {
    name: 'Presiding Judge / Arbitrator',
    icon: <GavelIcon fontSize="small" />,
    color: '#8b5cf6',
    bgColor: 'rgba(139, 92, 246, 0.12)',
    borderColor: 'rgba(139, 92, 246, 0.35)',
    avatarBg: '#7c3aed',
  },
  plaintiff: {
    name: 'Plaintiff Counsel',
    icon: <ShieldIcon fontSize="small" />,
    color: '#3b82f6',
    bgColor: 'rgba(59, 130, 246, 0.12)',
    borderColor: 'rgba(59, 130, 246, 0.35)',
    avatarBg: '#2563eb',
  },
  defendant: {
    name: 'Defense Counsel',
    icon: <BalanceIcon fontSize="small" />,
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.12)',
    borderColor: 'rgba(245, 158, 11, 0.35)',
    avatarBg: '#d97706',
  },
  informer: {
    name: 'Legal Aid & Procedure Informer',
    icon: <LightbulbOutlinedIcon fontSize="small" />,
    color: '#14b8a6',
    bgColor: 'rgba(20, 184, 166, 0.12)',
    borderColor: 'rgba(20, 184, 166, 0.35)',
    avatarBg: '#0d9488',
  },
  witness: {
    name: 'Expert / Fact Witness',
    icon: <MenuBookIcon fontSize="small" />,
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.35)',
    avatarBg: '#059669',
  },
  orchestrator: {
    name: 'Simulation Orchestrator',
    icon: <SmartToyIcon fontSize="small" />,
    color: '#6366f1',
    bgColor: 'rgba(99, 102, 241, 0.12)',
    borderColor: 'rgba(99, 102, 241, 0.35)',
    avatarBg: '#4f46e5',
  },
  narrator: {
    name: 'Judicial Narrator',
    icon: <HeadphonesIcon fontSize="small" />,
    color: '#8b5cf6',
    bgColor: 'rgba(139, 92, 246, 0.12)',
    borderColor: 'rgba(139, 92, 246, 0.35)',
    avatarBg: '#7c3aed',
  },
  multi_voice: {
    name: 'Multi-Voice Dialogue (Plaintiff, Defendant, Judge)',
    icon: <HeadphonesIcon fontSize="small" />,
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.12)',
    borderColor: 'rgba(6, 182, 212, 0.35)',
    avatarBg: '#0891b2',
  },
};

const ALL_AGENT_KEYS = ['plaintiff', 'defendant', 'judge', 'informer', 'witness'];

export default function SimPage() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  // Navigation tab: 0 = Scenarios, 1 = Simulations
  const [tab, setTab] = useState(0);

  const [pageLoading, setPageLoading] = useState(true);

  // Data lists
  const [scenarios, setScenarios] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [documents, setDocuments] = useState([]);

  // Selected filters in Simulations tab
  const [selectedScenarioFilter, setSelectedScenarioFilter] = useState('');
  const [selectedSimId, setSelectedSimId] = useState(null);
  const [historySearch, setHistorySearch] = useState('');
  const [historyWinnerFilter, setHistoryWinnerFilter] = useState('all');

  // Active loaded simulation & playback
  const [sim, setSim] = useState(null);
  const [caseStudy, setCaseStudy] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [audioAssets, setAudioAssets] = useState([]);
  const [isSynthesizingAudio, setIsSynthesizingAudio] = useState(false);
  const [audioMsg, setAudioMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [currentTurnCount, setCurrentTurnCount] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [msg, setMsg] = useState('');
  const [msgSeverity, setMsgSeverity] = useState('info');

  // Human in the Loop (inject / steer)
  const [factInput, setFactInput] = useState('');
  const [steerInput, setSteerInput] = useState('');
  const [isInjecting, setIsInjecting] = useState(false);
  const [isSteering, setIsSteering] = useState(false);

  // Thinking toggles
  const [expandedThinking, setExpandedThinking] = useState({});

  // Scenario Config Modal (Create & Edit)
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [editingScenarioId, setEditingScenarioId] = useState(null);
  const [scenarioToDelete, setScenarioToDelete] = useState(null);

  // Enhanced Scenario Configuration Fields
  const [configTitle, setConfigTitle] = useState('');
  const [configFacts, setConfigFacts] = useState('');
  const [configJurisdiction, setConfigJurisdiction] = useState('Pennsylvania');
  const [configDomain, setConfigDomain] = useState('commercial');
  const [configJudgeEffort, setConfigJudgeEffort] = useState('medium');
  const [configTurnLimit, setConfigTurnLimit] = useState(8);
  const [configProofStandard, setConfigProofStandard] = useState('preponderance');
  const [configActiveAgents, setConfigActiveAgents] = useState(['plaintiff', 'defendant', 'judge', 'informer', 'witness']);
  const [configFocusAreas, setConfigFocusAreas] = useState('');
  const [configLinkedDocs, setConfigLinkedDocs] = useState([]);
  const [configIncidentDate, setConfigIncidentDate] = useState('');
  const [configProceedingsDate, setConfigProceedingsDate] = useState('');
  const [configScenarioFile, setConfigScenarioFile] = useState(null);
  const scenarioFileInputRef = useRef(null);

  const transcriptBottomRef = useRef(null);
  const selectedSimIdRef = useRef(selectedSimId);
  selectedSimIdRef.current = selectedSimId;

  const loadAll = useCallback(async () => {
    try {
      const [scRes, simRes, docRes] = await Promise.all([
        api('/scenarios').catch(() => ({ scenarios: [] })),
        api('/simulations').catch(() => ({ simulations: [] })),
        api('/documents').catch(() => ({ documents: [] })),
      ]);
      const scList = Array.isArray(scRes?.scenarios)
        ? scRes.scenarios
        : Array.isArray(scRes)
        ? scRes
        : [];
      const simList = Array.isArray(simRes?.simulations)
        ? simRes.simulations
        : Array.isArray(simRes)
        ? simRes
        : [];
      const docList = Array.isArray(docRes?.documents)
        ? docRes.documents
        : Array.isArray(docRes)
        ? docRes
        : [];
      setScenarios(scList);
      setExecutions(simList);
      setDocuments(docList);

      // Check if there is an active running simulation in localStorage, or saved selected simulation
      const activeStorageId = localStorage.getItem('jurisflow_active_sim_id');
      const savedSelectedId = localStorage.getItem('jurisflow_selected_sim_id');
      const targetSimId =
        activeStorageId ||
        (simList.some((s) => s.id === savedSelectedId) ? savedSelectedId : simList[0]?.id);

      if (activeStorageId) {
        setSelectedSimId(activeStorageId);
        setBusy(true);
        loadExecutionDetail(activeStorageId);
      } else if (targetSimId) {
        loadExecutionDetail(targetSimId);
      }
    } catch (err) {
      setMsg(`Unable to load data: ${err.message}`);
      setMsgSeverity('error');
    } finally {
      setPageLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Polling loop: ensures tribunal continues running when user switches pages/tabs
  useEffect(() => {
    let timer = null;
    const activeId = localStorage.getItem('jurisflow_active_sim_id') || (busy ? selectedSimId : null);
    const isOngoing = Boolean(
      activeId ||
      (sim && ['running', 'pending', 'opening', 'arguments', 'judge_questions'].includes(sim.status))
    );

    if (isOngoing) {
      const targetSimId = activeId || sim?.id;
      if (targetSimId) {
        timer = setInterval(async () => {
          try {
            const detail = await api(`/simulations/${targetSimId}`);
            setSim(detail);
            if (detail.turns?.length) {
              setCurrentTurnCount(detail.turns.length);
            }
            if (detail.status === 'completed' || detail.status === 'failed') {
              localStorage.removeItem('jurisflow_active_sim_id');
              localStorage.removeItem('jurisflow_sim_start_time');
              setBusy(false);
              clearInterval(timer);

              if (detail.status === 'completed') {
                if (detail.case_study) {
                  setCaseStudy(detail.case_study);
                } else {
                  let attempts = 0;
                  const fetchCS = async () => {
                    try {
                      const cs = await api(`/simulations/${detail.id}/case_study`);
                      if (cs) setCaseStudy(cs);
                    } catch {
                      attempts++;
                      if (attempts < 4) {
                        setTimeout(fetchCS, 2000);
                      }
                    }
                  };
                  fetchCS();
                }
                try {
                  const auds = await api(`/simulations/${detail.id}/audio`);
                  setAudioAssets(Array.isArray(auds) ? auds : []);
                } catch {
                  /* no audio */
                }
                setMsg(`Simulation completed. Verdict: ${(detail.verdict?.winner || 'draw').toUpperCase()}`);
                setMsgSeverity('success');
              } else {
                setMsg(`Simulation finished with status: ${detail.status}`);
                setMsgSeverity('warning');
              }

              // Refresh executions list
              api('/simulations').then((res) => {
                const list = res?.simulations ?? (Array.isArray(res) ? res : []);
                setExecutions(list);
              }).catch(() => {});
            }
          } catch {
            /* ignore transient errors during polling */
          }
        }, 1500);
      }
    }

    return () => {
      if (timer) clearInterval(timer);
    };
  }, [busy, selectedSimId, sim?.status, sim?.id]);

  // Track elapsed seconds while simulation is active
  useEffect(() => {
    let timer = null;
    if (busy) {
      const startTimeStr = localStorage.getItem('jurisflow_sim_start_time');
      const startMs = startTimeStr ? parseInt(startTimeStr, 10) : Date.now();
      setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));

      timer = setInterval(() => {
        setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
      }, 1000);
    } else {
      setElapsedSeconds(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [busy]);

  useEffect(() => {
    if (transcriptBottomRef.current) {
      transcriptBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [sim?.turns?.length]);

  // Artifact cache state: case study + role-play markdown files for this run
  useEffect(() => {
    const id = sim?.id;
    if (!id) {
      setArtifacts(null);
      return undefined;
    }
    let cancelled = false;
    api(`/simulations/${id}/artifacts`)
      .then((res) => {
        if (!cancelled) setArtifacts(res || null);
      })
      .catch(() => {
        if (!cancelled) setArtifacts(null);
      });
    return () => {
      cancelled = true;
    };
  }, [sim?.id, sim?.status]);

  async function loadExecutionDetail(simId) {
    if (!simId) return;
    setSelectedSimId(simId);
    try {
      localStorage.setItem('jurisflow_selected_sim_id', simId);
    } catch {
      /* ignore */
    }
    try {
      const detail = await api(`/simulations/${simId}`);
      setSim(detail);
      if (detail.case_study) {
        setCaseStudy(detail.case_study);
      } else {
        try {
          const cs = await api(`/simulations/${simId}/case_study`);
          if (cs) setCaseStudy(cs);
          else setCaseStudy(null);
        } catch {
          setCaseStudy(null);
        }
      }
      try {
        const auds = await api(`/simulations/${simId}/audio`);
        setAudioAssets(Array.isArray(auds) ? auds : []);
      } catch {
        setAudioAssets([]);
      }
    } catch (err) {
      setMsg(`Failed to load simulation execution: ${err.message}`);
      setMsgSeverity('error');
    }
  }

  // Navigate from a scenario card directly to its simulation history grid
  function viewScenarioHistory(sc) {
    setSelectedScenarioFilter(sc.id);
    setTab(1); // Switch to Execution History grid tab
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Open an execution in the dedicated full-width Simulation Details tab
  const handleSelectExecution = (simId) => {
    loadExecutionDetail(simId);
    setTab(2); // Switch to Simulation Details tab
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Smooth scroll jump to target anchor section with sticky offset compensation
  const handleJumpToSection = (targetId) => {
    let el = document.getElementById(targetId);

    // Intelligent fallbacks if explicit anchor tag is not directly in DOM
    if (!el) {
      if (targetId === 'section-openings') {
        el = document.getElementById('section-transcript');
      } else if (targetId === 'section-arguments') {
        // Look for turn with arguments ID or 3rd turn (rebuttals)
        el = document.getElementById('section-arguments') ||
             document.querySelector('#section-transcript [id="section-arguments"]') ||
             document.querySelectorAll('#section-transcript .MuiCard-root')[2];
      } else if (targetId === 'section-inquiry') {
        // Look for inquiry turn or judge inquiry cards
        el = document.getElementById('section-inquiry') ||
             document.querySelector('#section-transcript [id="section-inquiry"]');
        if (!el) {
          const cards = document.querySelectorAll('#section-transcript .MuiCard-root');
          for (const card of cards) {
            if (card.textContent.includes('Judge') || card.textContent.includes('Inquiry')) {
              el = card;
              break;
            }
          }
        }
      } else if (targetId === 'section-verdict') {
        el = document.getElementById('section-verdict') ||
             document.getElementById('section-verdict-turn') ||
             document.getElementById('section-case-study-divider');
      }
    }

    if (el) {
      const topOffset = 130; // Compensate for sticky AppBar (56px) + sticky Quick Jump bar (60px) + margin
      const elPos = el.getBoundingClientRect().top + window.pageYOffset;
      window.scrollTo({
        top: Math.max(0, elPos - topOffset),
        behavior: 'smooth',
      });
    } else {
      if (targetId === 'section-verdict' && sim?.status !== 'completed') {
        setMsg('Judicial verdict is still pending tribunal deliberation.');
        setMsgSeverity('info');
      } else {
        const transcript = document.getElementById('section-transcript');
        if (transcript) {
          const elPos = transcript.getBoundingClientRect().top + window.pageYOffset;
          window.scrollTo({ top: Math.max(0, elPos - 130), behavior: 'smooth' });
        }
      }
    }
  };

  // Open Scenario Config Modal for Create
  function openCreateModal() {
    setEditingScenarioId(null);
    setConfigTitle('');
    setConfigFacts('');
    setConfigScenarioFile(null);
    if (scenarioFileInputRef.current) scenarioFileInputRef.current.value = '';
    setConfigJurisdiction('Pennsylvania');
    setConfigDomain('commercial');
    setConfigIncidentDate('');
    setConfigProceedingsDate(new Date().toISOString().split('T')[0]);
    setConfigJudgeEffort('medium');
    setConfigTurnLimit(8);
    setConfigProofStandard('preponderance');
    setConfigActiveAgents(['plaintiff', 'defendant', 'judge', 'informer', 'witness']);
    setConfigFocusAreas('Material Breach, Damages');
    setConfigLinkedDocs([]);
    setConfigModalOpen(true);
  }

  // Open Scenario Config Modal for Edit
  function openEditModal(sc) {
    setEditingScenarioId(sc.id);
    setConfigTitle(sc.title || '');
    setConfigFacts(sc.fact_pattern || sc.description || '');
    setConfigScenarioFile(null);
    if (scenarioFileInputRef.current) scenarioFileInputRef.current.value = '';
    setConfigJurisdiction(sc.jurisdiction || 'Pennsylvania');
    setConfigDomain(sc.domain || 'commercial');
    const p = sc.parameters || (sc.current_version && sc.current_version.parameters) || {};
    setConfigIncidentDate(sc.incident_date || p.incident_date || '');
    setConfigProceedingsDate(sc.proceedings_date || p.proceedings_date || '');
    setConfigJudgeEffort(p.judge_effort || 'medium');
    setConfigTurnLimit(p.turn_limit || 8);
    setConfigProofStandard(p.standard_of_proof || 'preponderance');
    setConfigActiveAgents(p.active_agents || ['plaintiff', 'defendant', 'judge', 'informer', 'witness']);
    setConfigFocusAreas((sc.focus_areas || p.focus_areas || []).join(', '));
    setConfigLinkedDocs(sc.document_ids || p.document_ids || []);
    setConfigModalOpen(true);
  }

  // Save Scenario (Create or Edit)
  async function handleSaveScenario(e) {
    e.preventDefault();
    const cleanTitle = configTitle.trim();
    if (!cleanTitle) {
      setMsg('Scenario title is required.');
      setMsgSeverity('warning');
      return;
    }

    const focusList = configFocusAreas
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    const parameters = {
      judge_effort: configJudgeEffort,
      turn_limit: configTurnLimit,
      standard_of_proof: configProofStandard,
      active_agents: configActiveAgents,
      focus_areas: focusList,
      document_ids: configLinkedDocs,
      incident_date: configIncidentDate || null,
      proceedings_date: configProceedingsDate || null,
    };

    setBusy(true);
    try {
      if (editingScenarioId) {
        await api(`/scenarios/${editingScenarioId}`, {
          method: 'PUT',
          body: {
            title: cleanTitle,
            fact_pattern: configFacts,
            jurisdiction: configJurisdiction,
            domain: configDomain,
            parameters,
            incident_date: configIncidentDate || null,
            proceedings_date: configProceedingsDate || null,
            document_ids: configLinkedDocs,
          },
        });
        setMsg(`Scenario "${cleanTitle}" updated successfully.`);
      } else if (configScenarioFile) {
        const form = new FormData();
        form.append('file', configScenarioFile);
        form.append('title', cleanTitle);
        form.append('fact_pattern', configFacts || '');
        form.append('jurisdiction', configJurisdiction || '');
        form.append('domain', configDomain || '');
        if (configIncidentDate) form.append('incident_date', configIncidentDate);
        if (configProceedingsDate) form.append('proceedings_date', configProceedingsDate);
        form.append('parameters', JSON.stringify(parameters));
        if (configLinkedDocs && configLinkedDocs.length) {
          form.append('document_ids', JSON.stringify(configLinkedDocs));
        }
        await api('/scenarios/upload', {
          method: 'POST',
          form,
        });
        setMsg(`Scenario "${cleanTitle}" created with indexed dispute dossier.`);
      } else {
        await api('/scenarios', {
          method: 'POST',
          body: {
            title: cleanTitle,
            fact_pattern: configFacts,
            jurisdiction: configJurisdiction,
            domain: configDomain,
            parameters,
            incident_date: configIncidentDate || null,
            proceedings_date: configProceedingsDate || null,
            document_ids: configLinkedDocs,
          },
        });
        setMsg(`Scenario "${cleanTitle}" created successfully.`);
      }
      setMsgSeverity('success');
      setConfigModalOpen(false);
      await loadAll();
    } catch (err) {
      setMsg(`Failed to save scenario: ${err.message}`);
      setMsgSeverity('error');
    } finally {
      setBusy(false);
    }
  }

  // Delete Scenario
  async function handleDeleteScenario(id) {
    setBusy(true);
    try {
      await api(`/scenarios/${id}`, { method: 'DELETE' });
      setScenarioToDelete(null);
      setMsg('Scenario deleted successfully.');
      setMsgSeverity('success');
      if (sim && sim.scenario_id === id) {
        setSim(null);
        setCaseStudy(null);
      }
      await loadAll();
    } catch (err) {
      setMsg(`Failed to delete scenario: ${err.message}`);
      setMsgSeverity('error');
    } finally {
      setBusy(false);
    }
  }

  // Execute / Run Simulation from Scenario in background
  async function runScenarioSimulation(sc) {
    setBusy(true);
    setMsg(`Tribunal session launched for "${sc.title}". Agents are actively deliberating...`);
    setMsgSeverity('info');
    setCaseStudy(null);
    setAudioAssets([]);
    setCurrentTurnCount(0);
    setTab(2); // Switch to Simulation Details tab immediately to observe
    setSelectedScenarioFilter(sc.id);

    const p = sc.parameters || {};
    const effort = p.judge_effort || 'medium';
    const rounds = p.turn_limit || 8;
    const agents = p.active_agents || ALL_AGENT_KEYS;

    try {
      localStorage.setItem('jurisflow_sim_start_time', Date.now().toString());
      const s = await api('/simulations', {
        method: 'POST',
        body: {
          scenario_id: sc.id,
          active_agents: agents,
          judge_effort: effort,
          judge_max_rounds: rounds,
          async_run: true,
        },
      });
      localStorage.setItem('jurisflow_active_sim_id', s.id);
      setSim(s);
      setSelectedSimId(s.id);

      // Refresh executions list immediately so pending run is visible in history
      api('/simulations').then((simRes) => {
        const list = simRes?.simulations ?? (Array.isArray(simRes) ? simRes : []);
        setExecutions(list);
      }).catch(() => {});
    } catch (err) {
      localStorage.removeItem('jurisflow_active_sim_id');
      localStorage.removeItem('jurisflow_sim_start_time');
      setBusy(false);
      setMsg(`Simulation failed to initialize: ${err.message}`);
      setMsgSeverity('error');
    }
  }

  // Generate Audio Narration for Completed Simulation
  async function handleGenerateAudio(simId) {
    if (!simId) return;
    setIsSynthesizingAudio(true);
    setAudioMsg({ text: 'Synthesizing high-fidelity judicial voice narration & per-role audio clips in background...', severity: 'info' });
    try {
      setMsg('Synthesizing high-fidelity judicial voice narration & audio clips in background...');
      setMsgSeverity('info');
      await api(`/simulations/${simId}/audio`, { method: 'POST' });

      // Poll until audio assets are ready
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        try {
          const auds = await api(`/simulations/${simId}/audio`);
          if (Array.isArray(auds) && auds.length > 0) {
            setAudioAssets(auds);
            setAudioMsg({ text: `Synthesis complete: ${auds.length} high-fidelity audio tracks generated and ready for playback.`, severity: 'success' });
            setMsg('Audio narration synthesis completed and available for playback.');
            setMsgSeverity('success');
            setIsSynthesizingAudio(false);
            clearInterval(interval);
          } else if (attempts >= 15) {
            setIsSynthesizingAudio(false);
            setAudioMsg({ text: 'Audio generation is running in background. Files will appear once synthesis finishes.', severity: 'warning' });
            clearInterval(interval);
          }
        } catch (pollErr) {
          if (attempts >= 15) {
            setIsSynthesizingAudio(false);
            setAudioMsg({ text: `Audio status check: ${pollErr.message}`, severity: 'warning' });
            clearInterval(interval);
          }
        }
      }, 2000);
    } catch (err) {
      setIsSynthesizingAudio(false);
      const errMsg = err.message || 'Server error';
      setAudioMsg({ text: `Audio synthesis error: ${errMsg}`, severity: 'error' });
      setMsg(`Audio synthesis notice: ${errMsg}`);
      setMsgSeverity('error');
    }
  }

  // Copy Disk Storage Path
  function handleCopyDiskPath(simObj) {
    const sId = typeof simObj === 'object' && simObj ? simObj.id : simObj;
    const diskPath = (typeof simObj === 'object' && simObj?.disk_path)
      ? simObj.disk_path
      : `backend/data/simulations/${sId}/`;
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(diskPath);
    }
    setMsg(`Disk archive path copied to clipboard: ${diskPath}`);
    setMsgSeverity('success');
  }

  // Export Raw Transcript JSON
  function handleExportJson(simulation) {
    if (!simulation) return;
    const blob = new Blob([JSON.stringify(simulation, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `simulation_${simulation.id.slice(0, 8)}_transcript.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Download a cached markdown artifact (case study or role-play transcript)
  async function handleDownloadArtifact(key) {
    if (!sim?.id) return;
    try {
      setMsg('Preparing markdown artifact…');
      setMsgSeverity('info');
      const res = await api(`/simulations/${sim.id}/artifacts/${key}`);
      const blob = new Blob([res?.markdown || ''], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = res?.filename || `${key}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setMsg(`Downloaded ${res?.filename || `${key}.md`}`);
      setMsgSeverity('success');
      const refreshed = await api(`/simulations/${sim.id}/artifacts`).catch(() => null);
      if (refreshed) setArtifacts(refreshed);
    } catch (err) {
      setMsg(`Artifact download failed: ${err.message}`);
      setMsgSeverity('error');
    }
  }

  // Human-in-the-loop: inject fact
  async function handleInjectFact(e) {
    e.preventDefault();
    if (!factInput.trim() || !sim) return;
    setIsInjecting(true);
    try {
      await api(`/simulations/${sim.id}/fact`, {
        method: 'POST',
        body: { fact: factInput.trim() },
      });
      setFactInput('');
      setMsg('Authoritative fact injected into simulation context.');
      setMsgSeverity('success');
      await loadExecutionDetail(sim.id);
    } catch (err) {
      setMsg(`Failed to inject fact: ${err.message}`);
      setMsgSeverity('error');
    } finally {
      setIsInjecting(false);
    }
  }

  // Human-in-the-loop: steer controversy focus
  async function handleSteerFocus(e) {
    e.preventDefault();
    if (!steerInput.trim() || !sim) return;
    setIsSteering(true);
    try {
      await api(`/simulations/${sim.id}/steer`, {
        method: 'POST',
        body: { focus: steerInput.trim() },
      });
      setSteerInput('');
      setMsg('Procedural steering focus applied.');
      setMsgSeverity('success');
      await loadExecutionDetail(sim.id);
    } catch (err) {
      setMsg(`Failed to steer focus: ${err.message}`);
      setMsgSeverity('error');
    } finally {
      setIsSteering(false);
    }
  }

  const toggleThinking = (idx) => {
    setExpandedThinking((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  const getPhaseStepIndex = (phase) => {
    const idx = SIM_PHASES.indexOf(phase);
    return idx >= 0 ? idx : 0;
  };

  // Safe and robust filtering based on selected scenario
  const safeExecutions = Array.isArray(executions) ? executions : [];
  const selectedScenarioObj = scenarios.find((s) => s.id === selectedScenarioFilter);
  const filteredExecutions = safeExecutions.filter((e) => {
    if (!selectedScenarioFilter) return true;
    return (
      e.scenario_id === selectedScenarioFilter ||
      (selectedScenarioObj && e.scenario_title === selectedScenarioObj.title)
    );
  });

  const displayedExecutions = filteredExecutions.filter((e) => {
    if (historyWinnerFilter !== 'all') {
      const w = (e.winner || e.verdict?.winner || '').toLowerCase();
      if (historyWinnerFilter === 'plaintiff' && w !== 'plaintiff') return false;
      if (historyWinnerFilter === 'defendant' && w !== 'defendant' && w !== 'defense') return false;
      if (historyWinnerFilter === 'draw' && w !== 'draw' && w !== 'tie' && w !== 'settlement') return false;
    }
    if (historySearch.trim()) {
      const q = historySearch.toLowerCase();
      const matchTitle = (e.scenario_title || '').toLowerCase().includes(q);
      const matchId = (e.id || '').toLowerCase().includes(q);
      const matchWinner = (e.winner || e.verdict?.winner || '').toLowerCase().includes(q);
      const matchRationale = (e.rationale || e.verdict?.rationale || '').toLowerCase().includes(q);
      if (!matchTitle && !matchId && !matchWinner && !matchRationale) return false;
    }
    return true;
  });

  // Historical performance metrics for remaining time estimation
  const completedRuns = safeExecutions.filter((e) => e.status === 'completed' && e.duration_seconds > 0);
  const avgDurationSec = completedRuns.length > 0
    ? Math.round(completedRuns.reduce((acc, r) => acc + r.duration_seconds, 0) / completedRuns.length)
    : 22;
  const estimatedRemainingSec = Math.max(0, avgDurationSec - elapsedSeconds);

  if (pageLoading) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 2 }}>
        <CircularProgress size={42} thickness={4} />
        <Typography
          variant="body2"
          sx={{
            color: "text.secondary",
            fontWeight: 650
          }}>
          Loading simulation environments and audio archives…
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
          aria-label="Simulation workspace key tabs"
        >
          <Tab
            label={`Scenarios (${scenarios.length})`}
            icon={<GavelIcon />}
            iconPosition="start"
            sx={{ textTransform: 'none', fontWeight: 650, fontSize: '0.9rem' }}
          />
          <Tab
            label={`Execution History (${safeExecutions.length})`}
            icon={<HistoryIcon />}
            iconPosition="start"
            sx={{ textTransform: 'none', fontWeight: 650, fontSize: '0.9rem' }}
          />
          <Tab
            label={sim ? (sim.scenario_title ? (sim.scenario_title.length > 24 ? `Trial: ${sim.scenario_title.slice(0, 22)}…` : `Trial: ${sim.scenario_title}`) : `Trial #${sim.id.slice(0, 8)}`) : 'Trial Details'}
            icon={<SmartToyIcon />}
            iconPosition="start"
            sx={{ textTransform: 'none', fontWeight: 650, fontSize: '0.9rem', whiteSpace: 'nowrap' }}
          />
        </Tabs>

        {busy && (
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
              Tribunal Streaming Turn {currentTurnCount}...
            </Typography>
          </Stack>
        )}
      </Paper>

      {/* TAB 0: SCENARIOS WORKSPACE */}
      {tab === 0 && (
        <Box>
          {/* Action Row */}
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
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 750,
                color: "text.secondary"
              }}>
              Contested Legal Controversy Scenarios ({scenarios.length})
            </Typography>

            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={openCreateModal}
              sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
            >
              Create New Scenario
            </Button>
          </Paper>

          {scenarios.length === 0 ? (
            <EmptyState
              icon={<GavelIcon sx={{ fontSize: 44 }} />}
              title="No controversy scenarios created yet"
              body="Create your first scenario to configure fact patterns, participating agents, and judicial rigor."
              action={
                <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateModal} sx={{ mt: 1 }}>
                  Create Scenario
                </Button>
              }
            />
          ) : (
            <Grid container spacing={2.5}>
              {scenarios.map((sc) => {
                const scExecs = executions.filter((e) => e.scenario_id === sc.id);
                const latestExec = scExecs[0];
                const p = sc.parameters || {};

                return (
                  <Grid key={sc.id} size={{xs: 12, sm: 6, lg: 4}}>
                    <Card
                      elevation={0}
                      sx={{
                        borderRadius: 3,
                        border: '1px solid',
                        borderColor: 'divider',
                        height: '100%',
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
                      <CardContent sx={{ p: 2.5, flexGrow: 1 }}>
                        <Stack
                          direction="row"
                          sx={{
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            mb: 1
                          }}>
                          <Box sx={{ minWidth: 0, flexGrow: 1, pr: 1 }}>
                            <Typography variant="subtitle1" noWrap title={sc.title} sx={{
                              fontWeight: 750
                            }}>
                              {sc.title}
                            </Typography>
                            <Stack direction="row" spacing={0.5} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                              <Chip size="small" label={sc.jurisdiction || 'Global'} color="primary" variant="outlined" sx={{ fontSize: '0.7rem' }} />
                              <Chip size="small" label={sc.domain || 'commercial'} variant="outlined" sx={{ fontSize: '0.7rem' }} />
                              {(sc.incident_date || p.incident_date) && (
                                <Chip
                                  size="small"
                                  icon={<EventIcon sx={{ fontSize: '13px !important' }} />}
                                  label={`Incident: ${sc.incident_date || p.incident_date}`}
                                  variant="outlined"
                                  sx={{ fontSize: '0.7rem' }}
                                />
                              )}
                              {(sc.proceedings_date || p.proceedings_date) && (
                                <Chip
                                  size="small"
                                  icon={<CalendarMonthIcon sx={{ fontSize: '13px !important' }} />}
                                  label={`Proceedings: ${sc.proceedings_date || p.proceedings_date}`}
                                  variant="outlined"
                                  color="secondary"
                                  sx={{ fontSize: '0.7rem' }}
                                />
                              )}
                              {(p.dossier || sc.current_version?.parameters?.dossier) && (
                                <Chip
                                  size="small"
                                  icon={<ArticleIcon sx={{ fontSize: '13px !important' }} />}
                                  label={`Dossier: ${(p.dossier || sc.current_version?.parameters?.dossier)?.filename || 'attachment'}`}
                                  color="info"
                                  variant="outlined"
                                  sx={{ fontSize: '0.7rem', fontWeight: 650 }}
                                />
                              )}
                            </Stack>
                          </Box>

                          <Stack direction="row" spacing={0.5}>
                            <Tooltip title="Configure & Edit Scenario">
                              <IconButton size="small" onClick={() => openEditModal(sc)} aria-label={`edit scenario ${sc.title}`}>
                                <TuneIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete Scenario">
                              <IconButton size="small" color="error" onClick={() => setScenarioToDelete(sc)} aria-label={`delete scenario ${sc.title}`}>
                                <DeleteOutlineIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        </Stack>

                        {/* Fact Pattern Snippet */}
                        {sc.fact_pattern && (
                          <Typography
                            variant="body2"
                            sx={{
                              color: "text.secondary",
                              my: 1.5,
                              lineHeight: 1.5,
                              display: '-webkit-box',
                              WebkitLineClamp: 3,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              fontSize: '0.84rem'
                            }}>
                            {sc.fact_pattern}
                          </Typography>
                        )}

                        {/* Config Summary Badges */}
                        <Paper
                          elevation={0}
                          sx={{
                            p: 1.25,
                            mt: 1.5,
                            borderRadius: 2,
                            bgcolor: isDark ? 'rgba(148,163,184,0.05)' : 'rgba(15,23,42,0.02)',
                            border: '1px solid',
                            borderColor: 'divider',
                          }}
                        >
                          <Stack
                            direction="row"
                            sx={{
                              flexWrap: "wrap",
                              gap: 0.75
                            }}>
                            <Chip
                              size="small"
                              label={`Rigor: ${p.judge_effort || 'medium'}`}
                              sx={{ fontSize: '0.68rem', textTransform: 'capitalize' }}
                            />
                            <Chip
                              size="small"
                              label={`${(p.active_agents || ALL_AGENT_KEYS).length} Agents`}
                              sx={{ fontSize: '0.68rem' }}
                            />
                          </Stack>
                        </Paper>

                        {/* Execution History Summary */}
                        <Box sx={{ mt: 1.5 }}>
                          {scExecs.length > 0 ? (
                            <Stack direction="row" spacing={1} sx={{
                              alignItems: "center"
                            }}>
                              <HistoryIcon fontSize="small" color="action" />
                              <Typography variant="caption" sx={{
                                color: "text.secondary"
                              }}>
                                <b>{scExecs.length} run{scExecs.length > 1 ? 's' : ''}</b> executed
                                {latestExec?.winner && ` · Latest: ${latestExec.winner.toUpperCase()}`}
                              </Typography>
                            </Stack>
                          ) : (
                            <Typography
                              variant="caption"
                              sx={{
                                color: "text.disabled",
                                fontStyle: 'italic'
                              }}>
                              No simulation executions recorded yet.
                            </Typography>
                          )}
                        </Box>
                      </CardContent>

                      <Divider />

                      <Box sx={{ p: 1.5, px: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Stack direction="row" spacing={1}>
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<HistoryIcon fontSize="small" />}
                            onClick={() => viewScenarioHistory(sc)}
                            sx={{ textTransform: 'none', fontWeight: 600, borderRadius: 1.5, fontSize: '0.78rem' }}
                          >
                            History ({scExecs.length})
                          </Button>
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<EditIcon fontSize="small" />}
                            onClick={() => openEditModal(sc)}
                            sx={{ textTransform: 'none', fontWeight: 600, borderRadius: 1.5, fontSize: '0.78rem' }}
                          >
                            Edit
                          </Button>
                        </Stack>

                        <Button
                          size="small"
                          variant="contained"
                          disabled={busy}
                          startIcon={<PlayArrowIcon fontSize="small" />}
                          onClick={() => runScenarioSimulation(sc)}
                          sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 1.5, fontSize: '0.78rem' }}
                        >
                          Run Simulation
                        </Button>
                      </Box>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          )}
        </Box>
      )}

      {/* TAB 1: EXECUTION HISTORY (FULL-WIDTH RESPONSIVE GRID) */}
      {tab === 1 && (
        <Box>
          {/* Top Control Bar: Filters, Search, and Summary Stats */}
          <Paper
            elevation={0}
            variant="outlined"
            sx={{
              p: 2,
              mb: 2.5,
              borderRadius: 3,
              bgcolor: 'background.paper',
            }}
          >
            <Grid container spacing={2} sx={{
              alignItems: "center"
            }}>
              {/* Scenario Filter Dropdown */}
              <Grid size={{xs: 12, sm: 6, md: 3.5}}>
                <FormControl size="small" fullWidth>
                  <InputLabel id="history-scenario-select-label">Filter by Scenario</InputLabel>
                  <Select
                    labelId="history-scenario-select-label"
                    label="Filter by Scenario"
                    value={selectedScenarioFilter}
                    onChange={(e) => setSelectedScenarioFilter(e.target.value)}
                    MenuProps={{ slotProps: { paper: { sx: { minWidth: 320, maxHeight: 360 } } } }}
                  >
                    <MenuItem value="">All Scenarios ({safeExecutions.length} runs)</MenuItem>
                    {scenarios.map((s) => {
                      const count = safeExecutions.filter(
                        (x) => x.scenario_id === s.id || x.scenario_title === s.title
                      ).length;
                      return (
                        <MenuItem key={s.id} value={s.id}>
                          {s.title} ({count})
                        </MenuItem>
                      );
                    })}
                  </Select>
                </FormControl>
              </Grid>

              {/* Keyword Search Field */}
              <Grid size={{xs: 12, sm: 6, md: 3.5}}>
                <TextField
                  size="small"
                  fullWidth
                  placeholder="Search runs by title, ID, verdict..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                  sx={{
                    '& .MuiOutlinedInput-root': { borderRadius: 2 },
                  }}
                />
              </Grid>

              {/* Winner Filter Chips */}
              <Grid size={{xs: 12, md: 5}}>
                <Stack
                  direction="row"
                  spacing={0.75}
                  sx={{
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: 0.5
                  }}>
                  <FilterListIcon fontSize="small" sx={{ color: 'text.secondary', mr: 0.5 }} />
                  <Chip
                    label={`All (${filteredExecutions.length})`}
                    size="small"
                    clickable
                    color={historyWinnerFilter === 'all' ? 'primary' : 'default'}
                    variant={historyWinnerFilter === 'all' ? 'filled' : 'outlined'}
                    onClick={() => setHistoryWinnerFilter('all')}
                    sx={{ fontWeight: 650, height: 22, fontSize: '0.7rem' }}
                  />
                  <Chip
                    icon={<ShieldIcon sx={{ fontSize: '13px !important' }} />}
                    label={`Plaintiff (${filteredExecutions.filter((e) => (e.winner || e.verdict?.winner) === 'plaintiff').length})`}
                    size="small"
                    clickable
                    color={historyWinnerFilter === 'plaintiff' ? 'info' : 'default'}
                    variant={historyWinnerFilter === 'plaintiff' ? 'filled' : 'outlined'}
                    onClick={() => setHistoryWinnerFilter('plaintiff')}
                    sx={{ fontWeight: 650, height: 22, fontSize: '0.7rem' }}
                  />
                  <Chip
                    icon={<BalanceIcon sx={{ fontSize: '13px !important' }} />}
                    label={`Defense (${filteredExecutions.filter((e) => ['defendant', 'defense'].includes(e.winner || e.verdict?.winner)).length})`}
                    size="small"
                    clickable
                    color={historyWinnerFilter === 'defendant' ? 'warning' : 'default'}
                    variant={historyWinnerFilter === 'defendant' ? 'filled' : 'outlined'}
                    onClick={() => setHistoryWinnerFilter('defendant')}
                    sx={{ fontWeight: 650, height: 22, fontSize: '0.7rem' }}
                  />
                  <Chip
                    label={`Draw (${filteredExecutions.filter((e) => ['draw', 'tie', 'settlement'].includes(e.winner || e.verdict?.winner)).length})`}
                    size="small"
                    clickable
                    color={historyWinnerFilter === 'draw' ? 'secondary' : 'default'}
                    variant={historyWinnerFilter === 'draw' ? 'filled' : 'outlined'}
                    onClick={() => setHistoryWinnerFilter('draw')}
                    sx={{ fontWeight: 650, height: 22, fontSize: '0.7rem' }}
                  />
                </Stack>
              </Grid>
            </Grid>
          </Paper>

          {/* Execution History Grid */}
          {displayedExecutions.length === 0 ? (
            <EmptyState
              icon={<HistoryIcon sx={{ fontSize: 44 }} />}
              title="No execution runs found"
              body={
                historySearch || selectedScenarioFilter || historyWinnerFilter !== 'all'
                  ? 'Try clearing or modifying your filter criteria above.'
                  : 'Launch a simulation from the Scenarios tab to see its recorded run here.'
              }
              action={
                <Button
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={() => setTab(0)}
                  sx={{ mt: 1, textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
                >
                  Go to Scenarios & Launch Run
                </Button>
              }
            />
          ) : (
            <Grid container spacing={2.5}>
              {displayedExecutions.map((exec) => {
                const isSelected = sim && sim.id === exec.id;
                const winner = exec.winner || exec.verdict?.winner;
                const winnerLower = (winner || '').toLowerCase();
                const isPlaintiff = winnerLower === 'plaintiff';
                const isDefense = winnerLower === 'defendant' || winnerLower === 'defense';

                let winnerColor = '#64748b';
                let winnerBg = 'rgba(100, 116, 139, 0.1)';
                let WinnerIcon = GavelIcon;
                if (isPlaintiff) {
                  winnerColor = '#2563eb';
                  winnerBg = 'rgba(37, 99, 235, 0.1)';
                  WinnerIcon = ShieldIcon;
                } else if (isDefense) {
                  winnerColor = '#d97706';
                  winnerBg = 'rgba(217, 119, 6, 0.1)';
                  WinnerIcon = BalanceIcon;
                }

                const createdDate = exec.created_at ? new Date(exec.created_at).toLocaleString() : '';
                const durationStr = exec.duration_seconds ? `${exec.duration_seconds}s` : 'N/A';
                const rationale = exec.rationale || exec.verdict?.rationale || '';

                return (
                  <Grid key={exec.id} size={{xs: 12, sm: 6, md: 4}}>
                    <Card
                      elevation={0}
                      onClick={() => handleSelectExecution(exec.id)}
                      sx={{
                        p: 2.5,
                        borderRadius: 3,
                        height: '100%',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'space-between',
                        cursor: 'pointer',
                        border: '1px solid',
                        borderColor: isSelected
                          ? 'primary.main'
                          : isDark
                          ? 'rgba(255,255,255,0.08)'
                          : 'rgba(0,0,0,0.08)',
                        bgcolor: isSelected
                          ? isDark
                            ? 'rgba(99,102,241,0.08)'
                            : 'rgba(99,102,241,0.04)'
                          : 'background.paper',
                        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                        '&:hover': {
                          transform: 'translateY(-3px)',
                          boxShadow: isDark
                            ? '0 12px 28px rgba(0,0,0,0.4)'
                            : '0 12px 28px rgba(99,102,241,0.12)',
                          borderColor: 'primary.main',
                        },
                      }}
                    >
                      <Box>
                        {/* Top Header: Scenario Title and Status */}
                        <Stack
                          direction="row"
                          sx={{
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            gap: 1,
                            mb: 1
                          }}>
                          <Typography
                            variant="subtitle1"
                            sx={{
                              fontWeight: 800,
                              lineHeight: 1.3,
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden'
                            }}>
                            {exec.scenario_title || `Simulation ${exec.id.slice(0, 8)}`}
                          </Typography>
                          <Chip
                            label={exec.status}
                            size="small"
                            color={exec.status === 'completed' ? 'success' : exec.status === 'failed' ? 'error' : 'primary'}
                            sx={{ textTransform: 'capitalize', fontWeight: 700, fontSize: '0.68rem', height: 22 }}
                          />
                        </Stack>

                        {/* Run ID, Proceedings & Incident Date */}
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            display: "block",
                            mb: 1,
                            fontSize: '0.72rem'
                          }}>
                          ID: {exec.id.slice(0, 8)} · Proceedings: <b>{exec.proceedings_date || createdDate || 'Recent'}</b>
                          {exec.incident_date && ` · Incident: ${exec.incident_date}`}
                        </Typography>

                        {/* Winner Badge */}
                        {winner && (
                          <Paper
                            elevation={0}
                            sx={{
                              px: 1.5,
                              py: 0.75,
                              mb: 1.5,
                              borderRadius: 2,
                              bgcolor: winnerBg,
                              border: `1px solid ${winnerColor}40`,
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1,
                            }}
                          >
                            <WinnerIcon sx={{ fontSize: 16, color: winnerColor }} />
                            <Typography
                              variant="caption"
                              sx={{
                                fontWeight: 800,
                                color: winnerColor
                              }}>
                              WINNER: {winner.toUpperCase()}
                            </Typography>
                          </Paper>
                        )}

                        {/* Rationale Snippet */}
                        {rationale && (
                          <Typography
                            variant="body2"
                            sx={{
                              color: "text.secondary",
                              fontSize: '0.8rem',
                              lineHeight: 1.5,
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              fontStyle: 'italic',
                              mb: 1.5
                            }}>
                            &quot;{rationale}&quot;
                          </Typography>
                        )}
                      </Box>

                      {/* Footer: Metrics & Action */}
                      <Box sx={{ pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                        <Stack
                          direction="row"
                          spacing={1}
                          sx={{
                            alignItems: "center",
                            flexWrap: "wrap",
                            mb: 1.5,
                            fontSize: '0.72rem',
                            color: 'text.secondary'
                          }}>
                          <Box component="span" sx={{ fontWeight: 650 }}>{exec.turns_count || exec.current_turn || 0} turns</Box>
                          <Box component="span" sx={{ color: 'text.disabled' }}>·</Box>
                          <Box component="span" sx={{ fontWeight: 650 }}>{durationStr}</Box>
                          {exec.total_tokens ? (
                            <>
                              <Box component="span" sx={{ color: 'text.disabled' }}>·</Box>
                              <Box component="span" sx={{ fontWeight: 650 }}>{exec.total_tokens.toLocaleString()} tok</Box>
                            </>
                          ) : null}
                          {exec.grounded_turns_count !== undefined && exec.turns_count ? (
                            <>
                              <Box component="span" sx={{ color: 'text.disabled' }}>·</Box>
                              <Box
                                component="span"
                                sx={{
                                  fontWeight: 700,
                                  color: exec.is_fully_grounded ? 'success.main' : (exec.grounded_turns_count === 0 ? 'warning.main' : 'info.main'),
                                }}
                              >
                                {exec.is_fully_grounded
                                  ? '100% Grounded'
                                  : `${exec.grounded_turns_count}/${exec.turns_count} Grounded`}
                              </Box>
                            </>
                          ) : null}
                        </Stack>

                        <Button
                          fullWidth
                          size="small"
                          variant="outlined"
                          endIcon={<ArrowForwardIcon fontSize="small" />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSelectExecution(exec.id);
                          }}
                          sx={{
                            textTransform: 'none',
                            fontWeight: 700,
                            borderRadius: 2,
                            fontSize: '0.78rem',
                          }}
                        >
                          View Full Simulation & Analysis
                        </Button>
                      </Box>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          )}
        </Box>
      )}

      {/* TAB 2: DEDICATED FULL-WIDTH SIMULATION DETAILS & CASE STUDY */}
      {tab === 2 && (
        <Box id="section-top">
          {sim ? (
            <Stack spacing={2.5}>
                {/* Simulation Stage Header & Telemetry Bar */}
                <Paper
                  elevation={0}
                  variant="outlined"
                  sx={{
                    p: 2.25,
                    borderRadius: 3,
                    bgcolor: 'background.paper',
                    border: '1px solid',
                    borderColor: 'divider',
                  }}
                >
                  {/* Top Breadcrumb Navigation */}
                  <Stack
                    direction="row"
                    sx={{
                      justifyContent: "space-between",
                      alignItems: "center",
                      mb: 1.25
                    }}>
                    <Button
                      size="small"
                      startIcon={<ArrowBackIcon fontSize="small" />}
                      onClick={() => setTab(1)}
                      sx={{
                        textTransform: 'none',
                        fontWeight: 650,
                        color: 'text.secondary',
                        p: 0,
                        minWidth: 'auto',
                        fontSize: '0.82rem',
                        '&:hover': { color: 'primary.main', bgcolor: 'transparent' },
                      }}
                    >
                      Back to History Grid
                    </Button>
                    <Stack direction="row" spacing={1} sx={{
                      alignItems: "center"
                    }}>
                      {scenarios.some((s) => s.id === sim.scenario_id || s.title === sim.scenario_title) && (
                        <Tooltip title="Edit Linked Scenario Configuration">
                          <IconButton
                            size="small"
                            onClick={() => {
                              const matched = scenarios.find((s) => s.id === sim.scenario_id || s.title === sim.scenario_title);
                              if (matched) openEditModal(matched);
                            }}
                            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                            aria-label="Edit scenario"
                          >
                            <EditIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Stack>
                  </Stack>

                  {/* Main Title & Executive Telemetry Strip */}
                  <Stack
                    direction="row"
                    sx={{
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: 2
                    }}>
                    <Box sx={{ minWidth: 260, flex: 1 }}>
                      <Stack
                        direction="row"
                        spacing={1.25}
                        sx={{
                          alignItems: "center",
                          mb: 0.75
                        }}>
                        <Typography
                          variant="h5"
                          sx={{
                            fontWeight: 800,
                            letterSpacing: '-0.01em',
                            lineHeight: 1.2
                          }}>
                          {sim.scenario_title || `Simulation ${sim.id.slice(0, 8)}`}
                        </Typography>
                        <Chip
                          label={sim.status}
                          size="small"
                          color={sim.status === 'completed' ? 'success' : sim.status === 'failed' ? 'error' : 'primary'}
                          sx={{ textTransform: 'capitalize', fontWeight: 700, borderRadius: 1.5, height: 24, fontSize: '0.75rem' }}
                        />
                      </Stack>

                      {/* Clean Metadata Pills */}
                      <Stack
                        direction="row"
                        spacing={1}
                        sx={{
                          alignItems: "center",
                          flexWrap: "wrap",
                          gap: 0.75
                        }}>
                        <Tooltip title={`Full Run ID: ${sim.id}`}>
                          <Chip
                            size="small"
                            label={`#${sim.id.slice(0, 8)}`}
                            variant="outlined"
                            sx={{ fontFamily: 'monospace', fontWeight: 650, fontSize: '0.72rem', height: 22 }}
                          />
                        </Tooltip>
                        {sim.scenario_jurisdiction && (
                          <Chip size="small" label={sim.scenario_jurisdiction} variant="outlined" sx={{ fontSize: '0.72rem', height: 22 }} />
                        )}
                        {(sim.incident_date || sim.scenario_parameters?.incident_date) && (
                          <Chip
                            size="small"
                            icon={<EventIcon sx={{ fontSize: '13px !important' }} />}
                            label={`Incident: ${sim.incident_date || sim.scenario_parameters?.incident_date}`}
                            variant="outlined"
                            sx={{ fontSize: '0.72rem', height: 22 }}
                          />
                        )}
                        {(sim.proceedings_date || sim.scenario_parameters?.proceedings_date || (sim.created_at ? new Date(sim.created_at).toISOString().split('T')[0] : null)) && (
                          <Chip
                            size="small"
                            icon={<CalendarMonthIcon sx={{ fontSize: '13px !important' }} />}
                            label={`Proceedings: ${sim.proceedings_date || sim.scenario_parameters?.proceedings_date || new Date(sim.created_at).toISOString().split('T')[0]}`}
                            color="primary"
                            variant="outlined"
                            sx={{ fontSize: '0.72rem', height: 22 }}
                          />
                        )}
                        {(() => {
                          const turnsList = sim.turns || [];
                          if (!turnsList.length) return null;
                          const groundedCount = turnsList.filter(
                            (t) => (t.citations && t.citations.length > 0) || t.is_grounded || (t.payload && t.payload.is_grounded)
                          ).length;
                          const total = turnsList.length;
                          const ungroundedCount = total - groundedCount;
                          if (ungroundedCount === 0) {
                            return (
                              <Chip
                                size="small"
                                icon={<VerifiedUserIcon sx={{ fontSize: '13px !important' }} />}
                                label="Fully Grounded"
                                color="success"
                                variant="outlined"
                                sx={{ fontSize: '0.72rem', fontWeight: 650, height: 22 }}
                              />
                            );
                          }
                          return (
                            <Tooltip title={`${groundedCount} turns grounded with local knowledge, ${ungroundedCount} turns using general reasoning.`}>
                              <Chip
                                size="small"
                                icon={<VerifiedUserIcon sx={{ fontSize: '13px !important' }} />}
                                label={`${groundedCount}/${total} Grounded`}
                                variant="outlined"
                                sx={{ fontSize: '0.72rem', fontWeight: 600, height: 22, color: 'text.secondary' }}
                              />
                            </Tooltip>
                          );
                        })()}
                      </Stack>
                    </Box>

                    {/* Unified Sleek Telemetry Capsule */}
                    <Paper
                      elevation={0}
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        borderRadius: 2.5,
                        p: 1,
                        px: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        bgcolor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                        gap: 2,
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <AccessTimeIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                        <Box>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "text.secondary",
                              fontSize: '0.64rem',
                              fontWeight: 650,
                              display: 'block',
                              lineHeight: 1
                            }}>
                            DURATION
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight: 750,
                              lineHeight: 1.25
                            }}>
                            {sim.duration_seconds ? `${sim.duration_seconds}s` : `${elapsedSeconds}s`}
                          </Typography>
                        </Box>
                      </Box>

                      <Divider orientation="vertical" flexItem sx={{ my: 0.25 }} />

                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TokenIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                        <Box>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "text.secondary",
                              fontSize: '0.64rem',
                              fontWeight: 650,
                              display: 'block',
                              lineHeight: 1
                            }}>
                            TOKENS
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight: 750,
                              lineHeight: 1.25
                            }}>
                            {sim.total_tokens ? sim.total_tokens.toLocaleString() : 'Estimating'}
                          </Typography>
                        </Box>
                      </Box>

                      <Divider orientation="vertical" flexItem sx={{ my: 0.25 }} />

                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <AutoAwesomeIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                        <Box>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "text.secondary",
                              fontSize: '0.64rem',
                              fontWeight: 650,
                              display: 'block',
                              lineHeight: 1
                            }}>
                            TURNS
                          </Typography>
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight: 750,
                              lineHeight: 1.25
                            }}>
                            {sim.turns?.length || sim.current_turn || 0} / {sim.turn_limit || 8}
                          </Typography>
                        </Box>
                      </Box>
                    </Paper>
                  </Stack>
                </Paper>

                {/* Unified Sticky Tribunal Proceeding Stepper Bar */}
                <Paper
                  elevation={2}
                  sx={{
                    position: 'sticky',
                    top: 56,
                    zIndex: 110,
                    p: 0.75,
                    px: 1.5,
                    borderRadius: 2.5,
                    bgcolor: isDark ? 'rgba(15, 23, 42, 0.94)' : 'rgba(255, 255, 255, 0.96)',
                    backdropFilter: 'blur(14px)',
                    border: '1px solid',
                    borderColor: 'divider',
                    boxShadow: isDark ? '0 4px 20px rgba(0,0,0,0.4)' : '0 4px 16px rgba(0,0,0,0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 1,
                    overflowX: 'auto',
                  }}
                >
                  <Stack
                    direction="row"
                    spacing={0.75}
                    sx={{
                      alignItems: "center",
                      minWidth: 'max-content'
                    }}>
                    <Typography
                      variant="caption"
                      sx={{
                        fontWeight: 800,
                        color: "text.secondary",
                        mr: 0.75,
                        textTransform: 'uppercase',
                        letterSpacing: 0.8,
                        fontSize: '0.68rem',
                        display: { xs: 'none', sm: 'inline-block' }
                      }}>
                      Phases:
                    </Typography>

                    {EXHAUSTIVE_SEQUENCE.map((step, sIdx) => {
                      const isCompleted = sim.status === 'completed' || sIdx <= getPhaseStepIndex(sim.phase);
                      const isCurrent = !['completed', 'failed'].includes(sim.status) && sIdx === getPhaseStepIndex(sim.phase);

                      return (
                        <Button
                          key={step.id}
                          size="small"
                          onClick={() => handleJumpToSection(step.targetId)}
                          startIcon={
                            <Box
                              sx={{
                                width: 20,
                                height: 20,
                                borderRadius: '50%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '0.68rem',
                                fontWeight: 800,
                                bgcolor: isCurrent ? 'primary.main' : isCompleted ? (isDark ? 'rgba(99,102,241,0.25)' : 'rgba(99,102,241,0.12)') : 'action.disabledBackground',
                                color: isCurrent ? '#fff' : isCompleted ? 'primary.main' : 'text.disabled',
                              }}
                            >
                              {sIdx + 1}
                            </Box>
                          }
                          sx={{
                            textTransform: 'none',
                            fontWeight: isCurrent ? 750 : isCompleted ? 650 : 500,
                            fontSize: '0.78rem',
                            py: 0.5,
                            px: 1.25,
                            borderRadius: 2,
                            whiteSpace: 'nowrap',
                            color: isCurrent ? 'primary.main' : isCompleted ? 'text.primary' : 'text.secondary',
                            bgcolor: isCurrent
                              ? isDark ? 'rgba(99,102,241,0.18)' : 'rgba(99,102,241,0.08)'
                              : 'transparent',
                            border: '1px solid',
                            borderColor: isCurrent ? 'primary.main' : 'transparent',
                            '&:hover': {
                              bgcolor: isDark ? 'rgba(99,102,241,0.12)' : 'rgba(99,102,241,0.06)',
                            },
                          }}
                        >
                          {step.label}
                        </Button>
                      );
                    })}
                  </Stack>

                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<KeyboardArrowUpIcon sx={{ fontSize: '15px !important' }} />}
                    onClick={() => handleJumpToSection('section-top')}
                    sx={{
                      textTransform: 'none',
                      fontSize: '0.72rem',
                      fontWeight: 650,
                      borderRadius: 2,
                      py: 0.35,
                      px: 1.2,
                      flexShrink: 0,
                    }}
                  >
                    Top
                  </Button>
                </Paper>

                {/* Sleek Progress Indicator with Historical Runtime Estimation */}
                {(busy || ['running', 'pending', 'opening', 'arguments', 'judge_questions'].includes(sim.status)) && (
                  <Paper
                    elevation={0}
                    sx={{
                      p: 2.5,
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor: 'primary.main',
                      background: isDark
                        ? 'linear-gradient(135deg, rgba(99,102,241,0.14) 0%, rgba(168,85,247,0.08) 100%)'
                        : 'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(168,85,247,0.04) 100%)',
                    }}
                  >
                    <Stack spacing={1.5}>
                      <Stack
                        direction="row"
                        sx={{
                          justifyContent: "space-between",
                          alignItems: "center",
                          flexWrap: "wrap",
                          gap: 1
                        }}>
                        <Stack direction="row" spacing={1.5} sx={{
                          alignItems: "center"
                        }}>
                          <CircularProgress size={20} thickness={5} />
                          <Box>
                            <Typography variant="subtitle2" color="primary" sx={{
                              fontWeight: 800
                            }}>
                              Tribunal Deliberation Active — Turn {sim.turns?.length || currentTurnCount || 1} of {sim.turn_limit || 8}
                            </Typography>
                            <Typography variant="caption" sx={{
                              color: "text.secondary"
                            }}>
                              Phase: <b>{PHASE_LABELS[sim.phase] || sim.phase || 'Opening Statements'}</b>
                            </Typography>
                          </Box>
                        </Stack>

                        <Stack direction="row" spacing={1} sx={{
                          alignItems: "center"
                        }}>
                          <Chip
                            icon={<AccessTimeIcon sx={{ fontSize: '14px !important' }} />}
                            size="small"
                            label={`${elapsedSeconds}s elapsed`}
                            variant="outlined"
                            sx={{ fontWeight: 650, fontSize: '0.72rem' }}
                          />
                          <Chip
                            size="small"
                            color="primary"
                            label={`~${estimatedRemainingSec}s remaining (historic avg ~${avgDurationSec}s)`}
                            sx={{ fontWeight: 700, fontSize: '0.72rem' }}
                          />
                        </Stack>
                      </Stack>

                      <LinearProgress
                        variant="determinate"
                        value={Math.min(95, Math.max(10, (((sim.turns?.length || currentTurnCount || 1) / (sim.turn_limit || 8)) * 100)))}
                        sx={{
                          height: 8,
                          borderRadius: 4,
                          bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
                          '& .MuiLinearProgress-bar': {
                            borderRadius: 4,
                            background: 'linear-gradient(90deg, #6366f1 0%, #a855f7 50%, #3b82f6 100%)',
                          },
                        }}
                      />

                      <Stack
                        direction="row"
                        sx={{
                          justifyContent: "space-between",
                          alignItems: "center"
                        }}>
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            display: 'flex',
                            alignItems: 'center',
                            gap: 0.5
                          }}>
                          <span>⚡</span> Background execution active — you can switch tabs or navigate across the application without losing progress.
                        </Typography>
                        <Typography variant="caption" color="primary" sx={{
                          fontWeight: 700
                        }}>
                          {Math.round(Math.min(95, Math.max(10, (((sim.turns?.length || currentTurnCount || 1) / (sim.turn_limit || 8)) * 100))))}% Complete
                        </Typography>
                      </Stack>
                    </Stack>
                  </Paper>
                )}

                {/* Final Verdict Banner */}
                {sim.status === 'completed' && sim.verdict && sim.verdict.winner && (
                  <Paper
                    id="section-verdict"
                    elevation={0}
                    sx={{
                      p: 2.5,
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor:
                        sim.verdict.winner === 'draw'
                          ? 'divider'
                          : sim.verdict.winner === 'plaintiff'
                          ? 'success.main'
                          : 'warning.main',
                      bgcolor: isDark
                        ? sim.verdict.winner === 'draw'
                          ? 'rgba(255,255,255,0.02)'
                          : 'rgba(76,175,80,0.08)'
                        : sim.verdict.winner === 'draw'
                        ? 'rgba(0,0,0,0.01)'
                        : 'rgba(232,245,233,0.6)',
                    }}
                  >
                    <Stack direction="row" spacing={1.5} sx={{
                      alignItems: "flex-start"
                    }}>
                      <GavelIcon sx={{ color: sim.verdict.winner === 'draw' ? 'text.secondary' : 'success.main', mt: 0.5 }} />
                      <Box sx={{ minWidth: 0, flex: 1 }}>
                        <Typography variant="subtitle1" sx={{
                          fontWeight: 800
                        }}>
                          Judicial Verdict — Winner: {(sim.verdict.winner || '').toUpperCase()}
                        </Typography>
                        {sim.verdict.rationale && (
                          <Typography
                            variant="body2"
                            sx={{
                              color: "text.secondary",
                              mt: 0.5,
                              lineHeight: 1.6
                            }}>
                            {sim.verdict.rationale}
                          </Typography>
                        )}
                      </Box>
                    </Stack>
                  </Paper>
                )}

                {/* Human-in-the-Loop Controls (Inject Facts / Steer) */}
                {(sim.status === 'paused' || sim.status === 'human_input' || busy) && (
                  <Paper
                    elevation={0}
                    variant="outlined"
                    sx={{
                      p: 2,
                      borderRadius: 2.5,
                      bgcolor: isDark ? 'rgba(99,102,241,0.05)' : 'rgba(79,70,229,0.03)',
                      border: '1px solid',
                      borderColor: 'primary.light',
                    }}
                  >
                    <Typography
                      variant="subtitle2"
                      color="primary"
                      sx={{
                        fontWeight: 750,
                        mb: 1.5
                      }}>
                      Human-in-the-Loop Intervention
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid size={{xs: 12, sm: 6}}>
                        <form onSubmit={handleInjectFact}>
                          <Stack direction="row" spacing={1}>
                            <TextField
                              size="small"
                              fullWidth
                              placeholder="Inject authoritative evidentiary fact..."
                              value={factInput}
                              onChange={(e) => setFactInput(e.target.value)}
                              disabled={isInjecting}
                            />
                            <Button
                              type="submit"
                              size="small"
                              variant="outlined"
                              disabled={isInjecting || !factInput.trim()}
                              sx={{ textTransform: 'none', flexShrink: 0 }}
                            >
                              Inject
                            </Button>
                          </Stack>
                        </form>
                      </Grid>
                      <Grid size={{xs: 12, sm: 6}}>
                        <form onSubmit={handleSteerFocus}>
                          <Stack direction="row" spacing={1}>
                            <TextField
                              size="small"
                              fullWidth
                              placeholder="Steer focus (e.g. examine clause 4.2)..."
                              value={steerInput}
                              onChange={(e) => setSteerInput(e.target.value)}
                              disabled={isSteering}
                            />
                            <Button
                              type="submit"
                              size="small"
                              variant="outlined"
                              disabled={isSteering || !steerInput.trim()}
                              sx={{ textTransform: 'none', flexShrink: 0 }}
                            >
                              Steer
                            </Button>
                          </Stack>
                        </form>
                      </Grid>
                    </Grid>
                  </Paper>
                )}

                {/* Interactive Transcript */}
                <Stack spacing={2} id="section-transcript">
                  {(() => {
                    let markedOpening = false;
                    let markedArguments = false;
                    let markedInquiry = false;
                    let markedVerdict = false;

                    const turnsList = sim.turns || [];
                    const totalTurns = turnsList.length;

                    return turnsList.map((t, idx) => {
                      let turnAnchorId = undefined;
                      const phase = (t.phase || '').toLowerCase();
                      const role = (t.agent_role || '').toLowerCase();
                      const isJudge = role === 'judge';

                      if ((phase === 'opening' || idx === 0) && !markedOpening) {
                        turnAnchorId = 'section-openings';
                        markedOpening = true;
                      } else if ((phase === 'arguments' || (idx >= 2 && ['plaintiff', 'defendant'].includes(role))) && !markedArguments) {
                        turnAnchorId = 'section-arguments';
                        markedArguments = true;
                      } else if ((phase === 'judge_questions' || phase === 'inquiry' || (isJudge && idx < totalTurns - 1)) && !markedInquiry) {
                        turnAnchorId = 'section-inquiry';
                        markedInquiry = true;
                      } else if ((isJudge && (t.payload?.winner || idx === totalTurns - 1)) && !markedVerdict) {
                        turnAnchorId = 'section-verdict-turn';
                        markedVerdict = true;
                      }

                      const agentKey = (t.agent_role || 'orchestrator').toLowerCase();
                      const config = AGENT_CONFIGS[agentKey] || AGENT_CONFIGS.orchestrator;
                      const thinking = t.thinking || (t.payload && t.payload.thinking) || '';
                      const action = t.action || (t.payload && t.payload.action) || '';
                      const knowledgeCitations = t.knowledge_citations || t.citations || (t.payload && (t.payload.knowledge_citations || t.payload.citations)) || [];
                      const scenarioCitations = t.scenario_citations || (t.payload && t.payload.scenario_citations) || [];
                      const isThinkingOpen = Boolean(expandedThinking[idx]);
                      const isGrounded = Boolean(
                        (knowledgeCitations && knowledgeCitations.length > 0) ||
                        t.is_grounded ||
                        (t.payload && t.payload.is_grounded)
                      );

                      return (
                        <Card
                          id={turnAnchorId}
                          key={t.id || idx}
                          elevation={0}
                          sx={{
                            borderRadius: 3,
                            border: '1px solid',
                            borderColor: config.borderColor,
                            overflow: 'hidden',
                            bgcolor: 'background.paper',
                          }}
                        >
                          {/* Agent Header Banner */}
                          <Box
                            sx={{
                              px: 2.5,
                              py: 1.25,
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              backgroundColor: config.bgColor,
                              borderBottom: '1px solid',
                              borderColor: config.borderColor,
                            }}
                          >
                            <Stack direction="row" spacing={1.5} sx={{
                              alignItems: "center"
                            }}>
                              <Avatar
                                sx={{
                                  bgcolor: config.avatarBg,
                                  width: 32,
                                  height: 32,
                                  color: '#fff',
                                }}
                              >
                                {config.icon}
                              </Avatar>
                              <Box>
                                <Typography
                                  variant="subtitle2"
                                  sx={{
                                    fontWeight: 800,
                                    color: isDark ? '#fff' : '#1e293b'
                                  }}>
                                  {config.name}
                                </Typography>
                                <Typography variant="caption" sx={{
                                  color: "text.secondary"
                                }}>
                                  Turn {t.turn_number ?? idx + 1} · Phase: <b>{PHASE_LABELS[t.phase] || t.phase}</b>
                                </Typography>
                              </Box>
                            </Stack>

                            <Stack
                              direction="row"
                              spacing={1}
                              sx={{
                                alignItems: "center",
                                flexWrap: "wrap"
                              }}>
                              {scenarioCitations.length > 0 && (
                                <Tooltip title={`Referenced ${scenarioCitations.length} dispute evidence excerpt${scenarioCitations.length > 1 ? 's' : ''} from uploaded case dossier`}>
                                  <Chip
                                    size="small"
                                    icon={<ArticleIcon sx={{ fontSize: '13px !important' }} />}
                                    label="Dossier"
                                    color="info"
                                    variant="outlined"
                                    sx={{
                                      fontWeight: 650,
                                      fontSize: '0.72rem',
                                      height: 22,
                                    }}
                                  />
                                </Tooltip>
                              )}

                              {isGrounded ? (
                                <Tooltip title={`Grounded with local knowledge (${knowledgeCitations.length} cited source${knowledgeCitations.length > 1 ? 's' : ''})`}>
                                  <Chip
                                    size="small"
                                    icon={<VerifiedUserIcon sx={{ fontSize: '13px !important' }} />}
                                    label="Grounded"
                                    color="success"
                                    variant="outlined"
                                    sx={{
                                      fontWeight: 650,
                                      fontSize: '0.72rem',
                                      height: 22,
                                    }}
                                  />
                                </Tooltip>
                              ) : (
                                <Tooltip title="This turn was generated using prompt facts and general legal reasoning.">
                                  <Chip
                                    size="small"
                                    label="General Reasoning"
                                    variant="outlined"
                                    sx={{
                                      fontWeight: 600,
                                      fontSize: '0.72rem',
                                      height: 22,
                                      color: 'text.secondary',
                                      borderColor: 'divider',
                                    }}
                                  />
                                </Tooltip>
                              )}
                            </Stack>
                          </Box>

                          <CardContent sx={{ p: 2.5 }}>
                            {/* Strategic Action / Intent Callout */}
                            {action && (
                              <Box
                                sx={{
                                  mb: 2,
                                  p: 1.25,
                                  px: 1.75,
                                  borderRadius: 2,
                                  bgcolor: isDark ? 'rgba(99, 102, 241, 0.08)' : 'rgba(99, 102, 241, 0.04)',
                                  border: '1px solid',
                                  borderColor: isDark ? 'rgba(99, 102, 241, 0.2)' : 'rgba(99, 102, 241, 0.12)',
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  gap: 1.25,
                                }}
                              >
                                <FlashOnIcon sx={{ fontSize: 18, color: 'primary.main', mt: 0.2, flexShrink: 0 }} />
                                <Box>
                                  <Typography
                                    variant="caption"
                                    sx={{
                                      fontWeight: 750,
                                      color: "primary.main",
                                      textTransform: "uppercase",
                                      letterSpacing: 0.5,
                                      display: 'block',
                                      fontSize: '0.68rem',
                                      mb: 0.25
                                    }}>
                                    Counsel Strategic Intent
                                  </Typography>
                                  <Typography variant="body2" sx={{ fontSize: '0.85rem', color: 'text.primary', lineHeight: 1.45 }}>
                                    {action}
                                  </Typography>
                                </Box>
                              </Box>
                            )}
                            {/* Strategic Deliberation & Thinking */}
                            {thinking && (
                              <Box sx={{ mb: 2 }}>
                                <Paper
                                  variant="outlined"
                                  onClick={() => toggleThinking(idx)}
                                  sx={{
                                    p: 1,
                                    px: 1.5,
                                    borderRadius: 2,
                                    cursor: 'pointer',
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center',
                                    backgroundColor: isDark ? 'rgba(139, 92, 246, 0.06)' : 'rgba(139, 92, 246, 0.04)',
                                    borderColor: 'rgba(139, 92, 246, 0.25)',
                                  }}
                                >
                                  <Stack direction="row" spacing={1} sx={{
                                    alignItems: "center"
                                  }}>
                                    <PsychologyIcon fontSize="small" sx={{ color: '#8b5cf6' }} />
                                    <Typography
                                      variant="caption"
                                      sx={{
                                        fontWeight: 700,
                                        color: '#8b5cf6'
                                      }}>
                                      Agent Deliberation & Reasoning
                                    </Typography>
                                  </Stack>
                                  <IconButton size="small" sx={{ color: '#8b5cf6' }}>
                                    {isThinkingOpen ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                                  </IconButton>
                                </Paper>

                                <Collapse in={isThinkingOpen}>
                                  <Box
                                    sx={{
                                      mt: 1,
                                      p: 1.5,
                                      borderRadius: 2,
                                      backgroundColor: isDark ? 'rgba(0,0,0,0.25)' : '#f8fafc',
                                      borderLeft: '3px solid #8b5cf6',
                                    }}
                                  >
                                    <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary', lineHeight: 1.6 }}>
                                      &quot;{thinking}&quot;
                                    </Typography>
                                  </Box>
                                </Collapse>
                              </Box>
                            )}

                            {/* Spoken Text */}
                            <Box sx={{ fontSize: '0.92rem', lineHeight: 1.65 }}>
                              <ReactMarkdown>{t.text || t.content || '_No statement provided._'}</ReactMarkdown>
                            </Box>

                            {/* Citations & Local Knowledge Grounding */}
                            {isGrounded && knowledgeCitations.length > 0 ? (
                              <Box sx={{ mt: 2, pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                                <Stack
                                  direction="row"
                                  spacing={0.75}
                                  sx={{
                                    alignItems: "center",
                                    mb: 1
                                  }}>
                                  <VerifiedUserIcon sx={{ fontSize: 16, color: '#10b981' }} />
                                  <Typography
                                    variant="caption"
                                    sx={{
                                      fontWeight: 800,
                                      color: isDark ? '#34d399' : '#059669'
                                    }}>
                                    Grounded with Local Knowledge ({knowledgeCitations.length} cited source{knowledgeCitations.length > 1 ? 's' : ''}):
                                  </Typography>
                                </Stack>
                                <Stack
                                  direction="row"
                                  spacing={0.75}
                                  useFlexGap
                                  sx={{
                                    flexWrap: "wrap",
                                    gap: 0.75
                                  }}>
                                  {knowledgeCitations.map((c, cIdx) => (
                                    <Tooltip
                                      key={cIdx}
                                      title={c.excerpt ? `"${c.excerpt}"` : 'Local knowledge citation'}
                                      arrow
                                    >
                                      <Chip
                                        size="small"
                                        variant="outlined"
                                        icon={<MenuBookIcon fontSize="small" sx={{ color: '#10b981 !important' }} />}
                                        label={c.legal_provision || (c.document_id ? `Doc: ${c.document_id}` : `Source ${cIdx + 1}`)}
                                        sx={{
                                          fontSize: '0.72rem',
                                          fontWeight: 600,
                                          borderColor: isDark ? 'rgba(16, 185, 129, 0.35)' : 'rgba(16, 185, 129, 0.25)',
                                          bgcolor: isDark ? 'rgba(16, 185, 129, 0.05)' : 'rgba(16, 185, 129, 0.03)',
                                        }}
                                      />
                                    </Tooltip>
                                  ))}
                                </Stack>
                              </Box>
                            ) : (
                              <Paper
                                variant="outlined"
                                sx={{
                                  mt: 2,
                                  p: 1.5,
                                  borderRadius: 2,
                                  display: 'flex',
                                  alignItems: 'flex-start',
                                  gap: 1.25,
                                  bgcolor: isDark ? 'rgba(245, 158, 11, 0.08)' : 'rgba(254, 243, 199, 0.65)',
                                  borderColor: isDark ? 'rgba(245, 158, 11, 0.35)' : '#f59e0b',
                                }}
                              >
                                <WarningAmberIcon sx={{ fontSize: 19, color: '#f59e0b', mt: 0.2, flexShrink: 0 }} />
                                <Box>
                                  <Typography
                                    variant="caption"
                                    sx={{
                                      fontWeight: 800,
                                      color: isDark ? '#fbbf24' : '#b45309',
                                      display: 'block'
                                    }}>
                                    Response Not Grounded with Local Knowledge
                                  </Typography>
                                  <Typography variant="caption" sx={{ color: isDark ? 'rgba(255,255,255,0.7)' : '#78350f', display: 'block', mt: 0.2, lineHeight: 1.45, fontSize: '0.73rem' }}>
                                    This statement was generated without supporting citations from your organization’s local knowledge base. The AI agent relied on general LLM reasoning and baseline scenario facts.
                                  </Typography>
                                </Box>
                              </Paper>
                            )}
                          </CardContent>
                        </Card>
                      );
                    });
                  })()}
                  <div ref={transcriptBottomRef} />
                </Stack>

                {/* VISUAL SEPARATION: TRIAL PROCEEDINGS -> POST-TRIAL JURISPRUDENCE */}
                <Paper
                  id="section-case-study-divider"
                  elevation={0}
                  sx={{
                    my: 3.5,
                    p: 3,
                    borderRadius: 3.5,
                    border: '2px solid',
                    borderColor: isDark ? 'rgba(99, 102, 241, 0.45)' : 'rgba(99, 102, 241, 0.3)',
                    background: isDark
                      ? 'linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%)'
                      : 'linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%)',
                    boxShadow: isDark ? '0 8px 32px rgba(0,0,0,0.4)' : '0 8px 24px rgba(99,102,241,0.08)',
                  }}
                >
                  <Stack
                    direction="row"
                    sx={{
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: 2
                    }}>
                    <Stack direction="row" spacing={2} sx={{
                      alignItems: "center"
                    }}>
                      <Avatar
                        sx={{
                          bgcolor: 'primary.main',
                          width: 44,
                          height: 44,
                          boxShadow: '0 4px 12px rgba(99,102,241,0.35)',
                        }}
                      >
                        <MenuBookIcon sx={{ color: '#fff' }} />
                      </Avatar>
                      <Box>
                        <Typography variant="overline" sx={{ letterSpacing: 1.5, fontWeight: 800, color: 'primary.main', display: 'block', lineHeight: 1.2 }}>
                          POST-TRIAL JURISPRUDENCE & SYNTHESIS
                        </Typography>
                        <Typography variant="h6" sx={{
                          fontWeight: 850
                        }}>
                          Independent Judicial Case Study & Analysis
                        </Typography>
                        <Typography variant="caption" sx={{
                          color: "text.secondary"
                        }}>
                          Formal doctrinal review, statutory interpretations, and legal risk takeaways generated post-deliberation.
                        </Typography>
                      </Box>
                    </Stack>

                    {/* Bidirectional Jump Hyperlinks */}
                    <Stack direction="row" spacing={1} sx={{
                      flexWrap: "wrap"
                    }}>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<KeyboardArrowUpIcon sx={{ fontSize: '16px !important' }} />}
                        onClick={() => handleJumpToSection('section-transcript')}
                        sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2, fontSize: '0.74rem' }}
                      >
                        ↑ Live Trial Transcript
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={<GavelIcon sx={{ fontSize: '14px !important' }} />}
                        onClick={() => handleJumpToSection('section-verdict')}
                        sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2, fontSize: '0.74rem' }}
                      >
                        ↑ Final Verdict
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        color="secondary"
                        startIcon={<HeadphonesIcon sx={{ fontSize: '14px !important' }} />}
                        onClick={() => handleJumpToSection('section-audio')}
                        sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2, fontSize: '0.74rem' }}
                      >
                        ↓ Audio Broadcast
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        onClick={() => handleJumpToSection('section-case-study')}
                        sx={{ textTransform: 'none', fontWeight: 700, borderRadius: 2, fontSize: '0.74rem' }}
                      >
                        ↓ Read Case Study
                      </Button>
                    </Stack>
                  </Stack>
                </Paper>

                {/* Audio Narration & Voice Synthesizer Section */}
                {sim.status === 'completed' && (
                  <Paper
                    id="section-audio"
                    elevation={0}
                    variant="outlined"
                    sx={{
                      p: 2.5,
                      borderRadius: 3,
                      bgcolor: 'background.paper',
                      border: '1px solid',
                      borderColor: isDark ? 'rgba(139, 92, 246, 0.3)' : 'rgba(139, 92, 246, 0.2)',
                    }}
                  >
                    <Stack
                      direction="row"
                      sx={{
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: 1.5,
                        mb: 1.5
                      }}>
                      <Stack direction="row" spacing={1.5} sx={{
                        alignItems: "center"
                      }}>
                        <Avatar sx={{ bgcolor: '#8b5cf6', width: 36, height: 36 }}>
                          <HeadphonesIcon fontSize="small" sx={{ color: '#fff' }} />
                        </Avatar>
                        <Box>
                          <Typography variant="subtitle1" sx={{
                            fontWeight: 800
                          }}>
                            Voice Narration & Audio Synthesis
                          </Typography>
                          <Typography variant="caption" sx={{
                            color: "text.secondary"
                          }}>
                            Multi-actor neural voice synthesis rendered directly from verified argument transcripts.
                          </Typography>
                        </Box>
                      </Stack>

                      <Button
                        size="small"
                        variant={audioAssets.length > 0 ? 'outlined' : 'contained'}
                        color="secondary"
                        disabled={isSynthesizingAudio}
                        startIcon={isSynthesizingAudio ? <CircularProgress size={16} color="inherit" /> : <VolumeUpIcon />}
                        onClick={() => handleGenerateAudio(sim.id)}
                        sx={{
                          textTransform: 'none',
                          fontWeight: 650,
                          borderRadius: 2,
                          background:
                            !audioAssets.length && !isSynthesizingAudio
                              ? 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)'
                              : undefined,
                        }}
                      >
                        {isSynthesizingAudio
                          ? 'Synthesizing Voices...'
                          : audioAssets.length > 0
                          ? 'Regenerate Audio Clips'
                          : 'Synthesize Audio Narration'}
                      </Button>
                    </Stack>

                    {/* Synthesizing Progress Feedback */}
                    {isSynthesizingAudio && (
                      <Box sx={{ mt: 2, mb: 1.5 }}>
                        <LinearProgress color="secondary" sx={{ borderRadius: 1, height: 6 }} />
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            display: 'block',
                            mt: 0.75
                          }}>
                          Synthesizing distinct neural voices per agent role (Judge, Plaintiff, Defendant, Informer, Narrator) in background...
                        </Typography>
                      </Box>
                    )}

                    {/* Status Feedback Notice */}
                    {audioMsg && !isSynthesizingAudio && (
                      <Alert
                        severity={audioMsg.severity}
                        onClose={() => setAudioMsg(null)}
                        sx={{ mt: 1.5, mb: 1.5, py: 0.5, borderRadius: 2 }}
                      >
                        {audioMsg.text}
                      </Alert>
                    )}

                    {audioAssets.length > 0 ? (
                      <Stack spacing={2} sx={{ mt: 2 }}>
                        {audioAssets.map((asset, aIdx) => {
                          const isOverview = asset.kind === 'learning' || asset.kind === 'overview' || asset.agent_role === 'narrator';
                          const cardColor = isOverview ? '#8b5cf6' : '#06b6d4';
                          const title =
                            asset.title ||
                            (isOverview
                              ? '1. Case Overview & Executive Summary'
                              : '2. Live Courtroom Hearing & Oral Argument (Multi-Voice)');
                          const description =
                            asset.description ||
                            (isOverview
                              ? 'Comprehensive, end-to-end spoken analysis of dispute record, legal claims, judicial reasoning, and principles.'
                              : 'Immersive live tribunal proceeding featuring courtroom opening announcements, rhetorical advocate arguments, and commanding bench rulings.');
                          const audioSrc = asset.url || asset.audio_url;

                          return (
                            <Paper
                              key={asset.id || aIdx}
                              elevation={0}
                              sx={{
                                p: 2,
                                borderRadius: 2.5,
                                bgcolor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.015)',
                                border: '1px solid',
                                borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
                                transition: 'all 0.15s ease',
                                '&:hover': {
                                  borderColor: cardColor,
                                  bgcolor: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)',
                                },
                              }}
                            >
                              <Stack
                                direction="row"
                                sx={{
                                  justifyContent: "space-between",
                                  alignItems: "flex-start",
                                  flexWrap: "wrap",
                                  gap: 1.5,
                                  mb: 1.5
                                }}>
                                <Box sx={{ flex: 1, minWidth: 260 }}>
                                  <Stack
                                    direction="row"
                                    spacing={1}
                                    sx={{
                                      alignItems: "center",
                                      mb: 0.75
                                    }}>
                                    <Chip
                                      size="small"
                                      label={isOverview ? 'AUDIO 1 · OVERVIEW' : 'AUDIO 2 · LIVE COURT HEARING'}
                                      sx={{
                                        fontWeight: 800,
                                        fontSize: '0.68rem',
                                        bgcolor: `${cardColor}20`,
                                        color: cardColor,
                                        border: `1px solid ${cardColor}40`,
                                        height: 22,
                                      }}
                                    />
                                    {!isOverview && (
                                      <Stack direction="row" spacing={0.5}>
                                        <Chip
                                          size="small"
                                          label="Plaintiff"
                                          sx={{
                                            height: 20,
                                            fontSize: '0.62rem',
                                            fontWeight: 700,
                                            bgcolor: 'rgba(59,130,246,0.15)',
                                            color: '#3b82f6',
                                          }}
                                        />
                                        <Chip
                                          size="small"
                                          label="Defense"
                                          sx={{
                                            height: 20,
                                            fontSize: '0.62rem',
                                            fontWeight: 700,
                                            bgcolor: 'rgba(245,158,11,0.15)',
                                            color: '#f59e0b',
                                          }}
                                        />
                                        <Chip
                                          size="small"
                                          label="Judge"
                                          sx={{
                                            height: 20,
                                            fontSize: '0.62rem',
                                            fontWeight: 700,
                                            bgcolor: 'rgba(139,92,246,0.15)',
                                            color: '#8b5cf6',
                                          }}
                                        />
                                        <Chip
                                          size="small"
                                          label="Dramatized Courtroom"
                                          variant="outlined"
                                          sx={{
                                            height: 20,
                                            fontSize: '0.62rem',
                                            fontWeight: 700,
                                            borderColor: 'rgba(6,182,212,0.4)',
                                            color: '#06b6d4',
                                          }}
                                        />
                                      </Stack>
                                    )}
                                  </Stack>

                                  <Typography
                                    variant="subtitle2"
                                    sx={{
                                      fontWeight: 800,
                                      fontSize: '0.95rem'
                                    }}>
                                    {title}
                                  </Typography>
                                  <Typography
                                    variant="caption"
                                    sx={{
                                      color: "text.secondary",
                                      display: 'block',
                                      mt: 0.25
                                    }}>
                                    {description}
                                  </Typography>
                                </Box>

                                <Typography
                                  variant="caption"
                                  sx={{
                                    color: "text.secondary",
                                    fontWeight: 600,
                                    pt: 0.5
                                  }}>
                                  {asset.duration_ms ? `${(asset.duration_ms / 1000).toFixed(1)}s · ` : ''}
                                  {asset.size_bytes ? `${Math.round(asset.size_bytes / 1024)} KB` : ''}
                                </Typography>
                              </Stack>

                              {audioSrc ? (
                                <Stack
                                  direction="row"
                                  spacing={1.5}
                                  sx={{
                                    alignItems: "center",
                                    mt: 1
                                  }}>
                                  <Box sx={{ flex: 1, '& audio': { width: '100%', height: 36, borderRadius: 2 } }}>
                                    {/* eslint-disable-next-line jsx-a11y/media-has-caption -- generated narration MP3, no separate caption track */}
                                    <audio controls src={audioSrc} style={{ width: '100%' }} />
                                  </Box>
                                  <Tooltip title="Download MP3">
                                    <IconButton
                                      size="small"
                                      component="a"
                                      href={audioSrc}
                                      download={asset.file_name || `audio-${aIdx + 1}.mp3`}
                                      sx={{ border: '1px solid', borderColor: 'divider', height: 36, width: 36, borderRadius: 2 }}
                                      aria-label="Download MP3"
                                    >
                                      <DownloadIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </Stack>
                              ) : (
                                <Chip size="small" label={asset.status || 'Processing'} color="warning" variant="outlined" />
                              )}
                            </Paper>
                          );
                        })}
                      </Stack>
                    ) : (
                      <Typography
                        variant="caption"
                        sx={{
                          color: "text.secondary",
                          display: 'block',
                          mt: 1,
                          fontStyle: 'italic'
                        }}>
                        Audio clips have not yet been synthesized for this run. Click &quot;Synthesize Audio Narration&quot; above to generate audio files.
                      </Typography>
                    )}
                  </Paper>
                )}

                {/* Pedagogical Judicial Case Study Analysis */}
                {caseStudy && (
                  <Paper
                    id="section-case-study"
                    elevation={0}
                    sx={{
                      p: 3,
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor: 'success.main',
                      backgroundColor: isDark ? 'rgba(16, 185, 129, 0.04)' : '#f0fdf4',
                    }}
                  >
                    <Stack
                      direction="row"
                      spacing={1.5}
                      sx={{
                        alignItems: "center",
                        mb: 1.5
                      }}>
                      <CheckCircleOutlineIcon color="success" sx={{ fontSize: 26 }} />
                      <Typography
                        variant="h6"
                        sx={{
                          fontWeight: 800,
                          color: "success.main"
                        }}>
                        Judicial Case Study & Analysis
                      </Typography>
                    </Stack>
                    <Divider sx={{ mb: 2 }} />
                    <Box sx={{ '& p': { lineHeight: 1.7 }, '& blockquote': { borderLeft: '3px solid #10b981', pl: 2 } }}>
                      <ReactMarkdown>{caseStudy.markdown || caseStudy.summary || ''}</ReactMarkdown>
                    </Box>
                  </Paper>
                )}

                {/* Disk Archival & Telemetry Artifacts Section */}
                {sim.status === 'completed' && (
                  <Paper
                    elevation={0}
                    variant="outlined"
                    sx={{
                      p: 2.5,
                      borderRadius: 3,
                      bgcolor: isDark ? 'rgba(148,163,184,0.03)' : 'rgba(15,23,42,0.02)',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Stack
                      direction="row"
                      sx={{
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: 1.5
                      }}>
                      <Stack direction="row" spacing={1.5} sx={{
                        alignItems: "center"
                      }}>
                        <Avatar sx={{ bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)', width: 34, height: 34 }}>
                          <StorageIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                        </Avatar>
                        <Box>
                          <Typography variant="subtitle2" sx={{
                            fontWeight: 800
                          }}>
                            Disk Storage & Data Archive
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{
                              color: "text.secondary",
                              fontFamily: 'monospace',
                              wordBreak: 'break-all'
                            }}>
                            {sim.disk_path || `backend/data/simulations/${sim.id}/`}
                          </Typography>
                        </Box>
                      </Stack>

                      <Stack direction="row" spacing={1}>
                        <Tooltip title="Copy Disk Storage Path">
                          <IconButton
                            size="small"
                            onClick={() => handleCopyDiskPath(sim)}
                            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                            aria-label="Copy disk path"
                          >
                            <ContentCopyIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Export Transcript JSON">
                          <IconButton
                            size="small"
                            onClick={() => handleExportJson(sim)}
                            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                            aria-label="Export transcript JSON"
                          >
                            <DownloadIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Stack>
                    </Stack>

                    <Divider sx={{ my: 1.5 }} />

                    <Box>
                      <Typography
                        variant="caption"
                        sx={{
                          fontWeight: 800,
                          display: 'block',
                          mb: 1
                        }}>
                        Downloadable artifacts
                      </Typography>
                      <Stack
                        direction="row"
                        spacing={1}
                        useFlexGap
                        sx={{
                          flexWrap: "wrap",
                          gap: 1
                        }}>
                        {(artifacts?.artifacts || []).map((artifact) => (
                          <Button
                            key={artifact.key}
                            size="small"
                            variant="outlined"
                            startIcon={<ArticleIcon sx={{ fontSize: '16px !important' }} />}
                            disabled={!artifact.available}
                            onClick={() => handleDownloadArtifact(artifact.key)}
                            sx={{ borderRadius: 2, textTransform: 'none', fontWeight: 650 }}
                          >
                            {artifact.title} (.md)
                          </Button>
                        ))}
                        {(artifacts?.artifacts || []).length === 0 && (
                          <Typography variant="caption" sx={{
                            color: "text.secondary"
                          }}>
                            Artifacts appear once the simulation has at least one turn.
                          </Typography>
                        )}
                      </Stack>
                      {(artifacts?.artifacts || []).length > 0 && (
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            display: 'block',
                            mt: 1
                          }}>
                          {artifacts.artifacts
                            .map(
                              (a) =>
                                `${a.title}: ${
                                  a.cached
                                    ? 'cached on disk'
                                    : a.available
                                      ? 'generated on first download'
                                      : sim.status === 'completed'
                                        ? 'not available'
                                        : 'available after completion'
                                }`
                            )
                            .join('  ·  ')}
                        </Typography>
                      )}
                    </Box>

                    <Divider sx={{ my: 1.5 }} />

                    <Typography variant="caption" sx={{
                      color: "text.secondary"
                    }}>
                      Full execution data including all turns, model deliberation timestamps, and citations are permanently archived to disk in <code>transcript.json</code>, <code>case_study.md</code> and <code>role_play.md</code>.
                    </Typography>
                  </Paper>
                )}
              </Stack>
            ) : selectedScenarioObj ? (
              /* Scenario Ready for Simulation Panel (No execution loaded yet) */
              <Paper
                id="section-dossier"
                elevation={0}
                variant="outlined"
                sx={{
                  p: 3,
                  borderRadius: 3,
                  bgcolor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Stack spacing={2.5}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 1.5 }}>
                    <Box>
                      <Typography variant="h6" sx={{
                        fontWeight: 800
                      }}>
                        {selectedScenarioObj.title}
                      </Typography>
                      <Stack direction="row" spacing={0.75} sx={{ mt: 0.75 }}>
                        <Chip size="small" label={selectedScenarioObj.jurisdiction || 'Global'} color="primary" variant="outlined" />
                        <Chip size="small" label={selectedScenarioObj.domain || 'commercial'} variant="outlined" />
                      </Stack>
                    </Box>

                    <Stack direction="row" spacing={1} sx={{
                      alignItems: "center"
                    }}>
                      <Tooltip title="Edit Scenario Configuration">
                        <IconButton
                          size="small"
                          onClick={() => openEditModal(selectedScenarioObj)}
                          sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                          aria-label="Edit scenario"
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Button
                        size="small"
                        variant="contained"
                        startIcon={<PlayArrowIcon />}
                        disabled={busy}
                        onClick={() => runScenarioSimulation(selectedScenarioObj)}
                        sx={{ textTransform: 'none', fontWeight: 700, borderRadius: 2 }}
                      >
                        Run Simulation Now
                      </Button>
                    </Stack>
                  </Box>

                  <Divider />

                  <Box>
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        display: "block",
                        mb: 0.75
                      }}>
                      Fact Pattern & Controversy Background
                    </Typography>
                    <Typography variant="body2" sx={{ lineHeight: 1.7, color: 'text.primary' }}>
                      {selectedScenarioObj.fact_pattern || selectedScenarioObj.description || 'No fact pattern details recorded.'}
                    </Typography>
                  </Box>

                  <Paper
                    elevation={0}
                    sx={{
                      p: 2,
                      borderRadius: 2.5,
                      bgcolor: isDark ? 'rgba(148,163,184,0.05)' : 'rgba(15,23,42,0.02)',
                      border: '1px solid',
                      borderColor: 'divider',
                    }}
                  >
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        display: "block",
                        mb: 1
                      }}>
                      Configured Simulation Parameters
                    </Typography>
                    <Stack
                      direction="row"
                      sx={{
                        flexWrap: "wrap",
                        gap: 1
                      }}>
                      <Chip size="small" label={`Judge Rigor: ${(selectedScenarioObj.parameters || {}).judge_effort || 'medium'}`} />
                      <Chip size="small" label={`Turn Limit: ${(selectedScenarioObj.parameters || {}).turn_limit || 8} turns`} />
                      <Chip size="small" label={`Standard of Proof: ${(selectedScenarioObj.parameters || {}).standard_of_proof || 'preponderance'}`} />
                      <Chip size="small" label={`${((selectedScenarioObj.parameters || {}).active_agents || ALL_AGENT_KEYS).length} Active Autonomous Agents`} />
                    </Stack>
                  </Paper>
                </Stack>
              </Paper>
          ) : (
            <EmptyState
              icon={<SmartToyIcon sx={{ fontSize: 48 }} />}
              title="No simulation selected"
              body="Select an execution run from the history catalog or launch a new trial from the Scenarios tab."
              action={
                <Stack direction="row" spacing={1.5} sx={{ mt: 1 }}>
                  <Button
                    variant="contained"
                    startIcon={<HistoryIcon />}
                    onClick={() => setTab(1)}
                    sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
                  >
                    Browse Execution History
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<PlayArrowIcon />}
                    onClick={() => setTab(0)}
                    sx={{ textTransform: 'none', fontWeight: 650, borderRadius: 2 }}
                  >
                    Go to Scenarios
                  </Button>
                </Stack>
              }
            />
          )}
        </Box>
      )}

      {/* ENHANCED SCENARIO CONFIGURATION MODAL (Create & Edit) */}
      <Dialog
        open={configModalOpen}
        onClose={() => setConfigModalOpen(false)}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: { sx: { borderRadius: 3, p: 1 } }
        }}
      >
        <DialogTitle sx={{ fontWeight: 800, p: 2 }}>
          <Stack
            direction="row"
            sx={{
              justifyContent: "space-between",
              alignItems: "center"
            }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TuneIcon color="primary" />
              <Typography variant="h6" sx={{
                fontWeight: 800
              }}>
                {editingScenarioId ? 'Edit Scenario & Configuration' : 'Create New Controversy Scenario'}
              </Typography>
            </Box>
            <IconButton onClick={() => setConfigModalOpen(false)} size="small" aria-label="Close dialog">
              <CloseIcon />
            </IconButton>
          </Stack>
        </DialogTitle>
        <form onSubmit={handleSaveScenario}>
          <DialogContent dividers sx={{ p: 3 }}>
            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                fontWeight: 700,
                textTransform: "uppercase",
                display: "block",
                mb: 1
              }}>
              Basic Controversy Details
            </Typography>

            <TextField
              label="Scenario Title"
              fullWidth
              size="small"
              margin="dense"
              value={configTitle}
              onChange={(e) => setConfigTitle(e.target.value)}
              placeholder="e.g. Acme Corp Breach of Indemnity & Software License"
              required
            />

            <TextField
              label="Fact Pattern & Controversy Background"
              fullWidth
              multiline
              minRows={3}
              maxRows={6}
              size="small"
              margin="dense"
              value={configFacts}
              onChange={(e) => setConfigFacts(e.target.value)}
              placeholder="Detail the factual narrative, underlying agreements, specific breaches, and parties involved..."
            />

            {/* Upload Scenario Dispute Dossier (PDF / Text / DOCX) */}
            <Box
              sx={{
                mt: 1.5,
                mb: 1.5,
                p: 1.5,
                borderRadius: 2,
                border: '1px dashed',
                borderColor: configScenarioFile ? 'primary.main' : 'divider',
                bgcolor: (theme) =>
                  theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
              }}
            >
              <input
                type="file"
                ref={scenarioFileInputRef}
                accept=".pdf,.txt,.docx,.doc,.md"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    setConfigScenarioFile(file);
                  }
                }}
              />
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1}
                sx={{
                  justifyContent: "space-between",
                  alignItems: { xs: 'flex-start', sm: 'center' }
                }}>
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 750,
                      display: "block",
                      color: "text.primary"
                    }}>
                    Scenario Dispute Dossier (PDF / TXT / DOCX)
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      fontSize: '0.72rem'
                    }}>
                    Upload full dispute documentation. Chunked & indexed into a dedicated scenario vector index for simulation RAG.
                  </Typography>
                </Box>
                {configScenarioFile ? (
                  <Chip
                    size="small"
                    color="primary"
                    icon={<ArticleIcon fontSize="small" />}
                    label={`${configScenarioFile.name} (${Math.round(configScenarioFile.size / 1024)} KB)`}
                    onDelete={() => {
                      setConfigScenarioFile(null);
                      if (scenarioFileInputRef.current) scenarioFileInputRef.current.value = '';
                    }}
                  />
                ) : (
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<CloudUploadIcon fontSize="small" />}
                    onClick={() => scenarioFileInputRef.current?.click()}
                    sx={{ textTransform: 'none', borderRadius: 1.5, whiteSpace: 'nowrap' }}
                  >
                    Attach Dossier File
                  </Button>
                )}
              </Stack>
            </Box>

            <Grid container spacing={2} sx={{ mt: 0.5, mb: 1 }}>
              <Grid size={{xs: 12, sm: 6}}>
                <Autocomplete
                  options={JURISDICTIONS}
                  freeSolo
                  disableClearable={false}
                  value={configJurisdiction}
                  onInputChange={(_e, val) => setConfigJurisdiction(val ?? '')}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Jurisdiction"
                      size="small"
                      fullWidth
                      helperText="Pick a jurisdiction or type your own"
                    />
                  )}
                />
              </Grid>
              <Grid size={{xs: 12, sm: 6}}>
                <TextField
                  label="Domain"
                  size="small"
                  fullWidth
                  value={configDomain}
                  onChange={(e) => setConfigDomain(e.target.value)}
                />
              </Grid>
              <Grid size={{xs: 12, sm: 6}}>
                <TextField
                  label="Date of Incident"
                  type="date"
                  size="small"
                  fullWidth
                  helperText="Date of breach, injury, tort, or operative event"
                  value={configIncidentDate}
                  onChange={(e) => setConfigIncidentDate(e.target.value)}
                  slotProps={{
                    inputLabel: { shrink: true }
                  }}
                />
              </Grid>
              <Grid size={{xs: 12, sm: 6}}>
                <TextField
                  label="Date of Proceedings"
                  type="date"
                  size="small"
                  fullWidth
                  helperText="Date trial / tribunal convened"
                  value={configProceedingsDate}
                  onChange={(e) => setConfigProceedingsDate(e.target.value)}
                  slotProps={{
                    inputLabel: { shrink: true }
                  }}
                />
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />

            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                fontWeight: 700,
                textTransform: "uppercase",
                display: "block",
                mb: 1
              }}>
              Enhanced Simulation Parameters & Agent Rigor
            </Typography>

            <Grid container spacing={2} sx={{ mb: 2 }}>
              <Grid size={{xs: 12, sm: 4}}>
                <FormControl fullWidth size="small">
                  <InputLabel>Judge Rigor / Effort</InputLabel>
                  <Select
                    value={configJudgeEffort}
                    label="Judge Rigor / Effort"
                    onChange={(e) => setConfigJudgeEffort(e.target.value)}
                    MenuProps={{ slotProps: { paper: { sx: { minWidth: 260, maxHeight: 320 } } } }}
                  >
                    <MenuItem value="low">Low (Expedited Ruling)</MenuItem>
                    <MenuItem value="medium">Medium (Standard Scrutiny)</MenuItem>
                    <MenuItem value="high">High (Exhaustive Evidence Analysis)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid size={{xs: 12, sm: 4}}>
                <FormControl fullWidth size="small">
                  <InputLabel>Simulation Rounds (Depth)</InputLabel>
                  <Select
                    value={configTurnLimit}
                    label="Simulation Rounds (Depth)"
                    onChange={(e) => setConfigTurnLimit(Number(e.target.value))}
                    MenuProps={{ slotProps: { paper: { sx: { minWidth: 240, maxHeight: 320 } } } }}
                  >
                    <MenuItem value={6}>6 Turns (Fast)</MenuItem>
                    <MenuItem value={8}>8 Turns (Standard)</MenuItem>
                    <MenuItem value={12}>12 Turns (Comprehensive)</MenuItem>
                    <MenuItem value={16}>16 Turns (Deep Inquiry)</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid size={{xs: 12, sm: 4}}>
                <FormControl fullWidth size="small">
                  <InputLabel>Standard of Proof</InputLabel>
                  <Select
                    value={configProofStandard}
                    label="Standard of Proof"
                    onChange={(e) => setConfigProofStandard(e.target.value)}
                    MenuProps={{ slotProps: { paper: { sx: { minWidth: 260, maxHeight: 320 } } } }}
                  >
                    <MenuItem value="preponderance">Preponderance of Evidence</MenuItem>
                    <MenuItem value="clear_and_convincing">Clear & Convincing</MenuItem>
                    <MenuItem value="beyond_reasonable_doubt">Beyond a Reasonable Doubt</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>

            {/* Participating Agents Checkbox Strip */}
            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                fontWeight: 650,
                display: "block",
                mb: 0.5
              }}>
              Active Autonomous Agents:
            </Typography>
            <Stack
              direction="row"
              spacing={1}
              sx={{
                flexWrap: "wrap",
                mb: 2
              }}>
              {ALL_AGENT_KEYS.map((role) => {
                const isSelected = configActiveAgents.includes(role);
                const isCore = role === 'judge' || role === 'plaintiff' || role === 'defendant';
                return (
                  <Chip
                    key={role}
                    label={AGENT_CONFIGS[role]?.name || role}
                    color={isSelected ? 'primary' : 'default'}
                    variant={isSelected ? 'filled' : 'outlined'}
                    onClick={() => {
                      if (isCore) return; // Core agents required
                      setConfigActiveAgents((prev) =>
                        prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
                      );
                    }}
                    sx={{ textTransform: 'capitalize', fontWeight: 650, cursor: isCore ? 'default' : 'pointer' }}
                  />
                );
              })}
            </Stack>

            {/* Key Controversy Focus Areas */}
            <TextField
              label="Evidentiary Focus Areas (Comma-separated)"
              fullWidth
              size="small"
              value={configFocusAreas}
              onChange={(e) => setConfigFocusAreas(e.target.value)}
              placeholder="e.g. Material Breach, Mitigation of Damages, Causation"
              sx={{ mb: 2 }}
            />

            {/* Linked Documents from Repository */}
            {documents.length > 0 && (
              <FormControl fullWidth size="small">
                <InputLabel>Link Precedent Documents from Repository</InputLabel>
                <Select
                  multiple
                  value={configLinkedDocs}
                  onChange={(e) => setConfigLinkedDocs(e.target.value)}
                  label="Link Precedent Documents from Repository"
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.map((val) => {
                        const d = documents.find((doc) => doc.id === val);
                        return <Chip key={val} size="small" label={d?.title || d?.filename || val} />;
                      })}
                    </Box>
                  )}
                >
                  {documents.map((d) => (
                    <MenuItem key={d.id} value={d.id}>
                      <Checkbox checked={configLinkedDocs.indexOf(d.id) > -1} />
                      {d.title || d.filename} ({d.jurisdiction || 'Global'})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setConfigModalOpen(false)} variant="outlined" size="small" sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              disabled={busy || !configTitle.trim()}
              sx={{ textTransform: 'none', fontWeight: 700, borderRadius: 2, px: 2.5 }}
            >
              {busy ? <CircularProgress size={18} color="inherit" /> : editingScenarioId ? 'Save Changes' : 'Create Scenario'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* CONFIRM DELETE SCENARIO DIALOG */}
      <Dialog open={Boolean(scenarioToDelete)} onClose={() => setScenarioToDelete(null)}>
        <DialogTitle sx={{ p: 2 }}>
          <Stack
            direction="row"
            sx={{
              justifyContent: "space-between",
              alignItems: "center"
            }}>
            <Typography variant="h6" sx={{
              fontWeight: 750
            }}>Confirm Scenario Deletion</Typography>
            <IconButton onClick={() => setScenarioToDelete(null)} size="small" aria-label="Close dialog">
              <CloseIcon />
            </IconButton>
          </Stack>
        </DialogTitle>
        <DialogContent sx={{ p: 2.5 }}>
          <Typography variant="body2">
            Are you sure you want to delete <b>{scenarioToDelete?.title}</b>? All version history and past simulations will be unlinked.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setScenarioToDelete(null)} variant="outlined" size="small" sx={{ borderRadius: 2, textTransform: 'none', px: 2.5, fontWeight: 650 }}>
            Cancel
          </Button>
          <Button
            onClick={() => handleDeleteScenario(scenarioToDelete?.id)}
            color="error"
            variant="contained"
            disabled={busy}
            sx={{ textTransform: 'none', borderRadius: 2, px: 2.5, fontWeight: 650 }}
          >
            {busy ? 'Deleting…' : 'Delete Scenario'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}