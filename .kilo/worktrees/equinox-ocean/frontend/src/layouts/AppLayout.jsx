import {
  AppBar,
  Avatar,
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BarChartIcon from '@mui/icons-material/BarChart';
import Brightness4Icon from '@mui/icons-material/Brightness4';
import Brightness7Icon from '@mui/icons-material/Brightness7';
import FactCheckIcon from '@mui/icons-material/FactCheck';
import GavelIcon from '@mui/icons-material/Gavel';
import GroupsIcon from '@mui/icons-material/Groups';
import LogoutIcon from '@mui/icons-material/Logout';
import SettingsIcon from '@mui/icons-material/Settings';
import SpaceDashboardIcon from '@mui/icons-material/SpaceDashboard';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import MenuIcon from '@mui/icons-material/Menu';
import MenuOpenIcon from '@mui/icons-material/MenuOpen';
import { useAuthStore } from '../auth/store';
import { useThemeMode } from '../theme/ThemeModeContext';

const NAV = [
  { label: 'Dashboard', path: '/', icon: SpaceDashboardIcon },
  { label: 'Ask AI', path: '/hub', icon: AutoAwesomeIcon },
  { label: 'Document Review', path: '/review', icon: FactCheckIcon },
  { label: 'Simulations', path: '/simulations', icon: GroupsIcon },
  { label: 'Analytics', path: '/analytics', icon: BarChartIcon },
  { label: 'Settings', path: '/settings', icon: SettingsIcon },
];

const PAGE_TITLES = Object.fromEntries(NAV.map(({ label, path }) => [path, label]));

const EXPANDED_DRAWER_WIDTH = 250;
const COLLAPSED_DRAWER_WIDTH = 72;

function initialsOf(name = '') {
  return name
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('') || 'U';
}

export default function AppLayout() {
  const theme = useTheme();
  const { pathname } = useLocation();
  const pageTitle = PAGE_TITLES[pathname];
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const logout = useAuthStore((s) => s.logout);
  const { toggle, mode } = useThemeMode();
  const isDark = theme.palette.mode === 'dark';
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    if (token && !user) {
      fetchMe().catch(() => {});
    }
  }, [token, user, fetchMe]);

  const drawerWidth = collapsed ? COLLAPSED_DRAWER_WIDTH : EXPANDED_DRAWER_WIDTH;

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <a href="#main-content" className="skip-link" aria-label="Skip to main content">
        Skip to main content
      </a>

      <Drawer
        variant="permanent"
        role="navigation"
        aria-label="Main navigation"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          transition: 'width 0.2s ease-in-out',
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: 'border-box',
            border: 'none',
            borderRight: '1px solid',
            borderColor: 'divider',
            backgroundColor: isDark ? '#0d1322' : '#fbfcfe',
            transition: 'width 0.2s ease-in-out',
            overflowX: 'hidden',
          },
        }}
      >
        {/* Brand */}
        <Stack
          direction="row"
          spacing={collapsed ? 0 : 1.5}
          alignItems="center"
          justifyContent={collapsed ? 'center' : 'flex-start'}
          sx={{ px: collapsed ? 1.5 : 2.5, py: 2.25 }}
        >
          <Tooltip title={collapsed ? 'Expand Navigation' : 'Collapse Navigation'}>
            <IconButton
              onClick={() => setCollapsed(!collapsed)}
              size="small"
              sx={{ p: 0 }}
              aria-label={collapsed ? 'Expand Navigation' : 'Collapse Navigation'}
            >
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  flexShrink: 0,
                  borderRadius: 2.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  background: isDark
                    ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
                    : 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  boxShadow: isDark ? '0 4px 14px rgba(99,102,241,0.45)' : '0 6px 16px rgba(79,70,229,0.35)',
                  cursor: 'pointer',
                  transition: 'transform 0.15s ease',
                  '&:hover': { transform: 'scale(1.05)' },
                }}
              >
                <GavelIcon sx={{ fontSize: 22 }} />
              </Box>
            </IconButton>
          </Tooltip>
          {!collapsed && (
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle1" fontWeight={800} sx={{ lineHeight: 1.1 }} noWrap>
                JurisLab
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.68rem', letterSpacing: '0.04em' }} noWrap display="block">
                LEGAL INTELLIGENCE
              </Typography>
            </Box>
          )}
        </Stack>

        <Divider sx={{ mx: 2, mb: 1.5 }} />

        {!collapsed && (
          <Typography
            variant="caption"
            color="text.disabled"
            sx={{ px: 3, mb: 0.75, display: 'block', fontWeight: 700, letterSpacing: '0.08em', fontSize: '0.66rem' }}
          >
            WORKSPACE
          </Typography>
        )}

        <List sx={{ px: collapsed ? 0.5 : 1 }}>
          {NAV.map(({ label, path, icon: Icon }) => {
            const selected = pathname === path;
            return (
              <Tooltip key={path} title={label} placement="right" disableHoverListener={!collapsed}>
                <ListItemButton
                  component={Link}
                  to={path}
                  selected={selected}
                  aria-label={label}
                  aria-current={selected ? 'page' : undefined}
                  sx={{
                    position: 'relative',
                    mx: collapsed ? 0.5 : 1.5,
                    my: 0.5,
                    px: collapsed ? 1 : 1.5,
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    color: selected ? 'primary.main' : 'text.secondary',
                    fontWeight: selected ? 700 : 600,
                    borderRadius: 2,
                    backgroundColor: selected
                      ? isDark
                        ? 'rgba(129,140,248,0.14)'
                        : 'rgba(79,70,229,0.08)'
                      : 'transparent',
                    '&:hover': {
                      backgroundColor: isDark ? 'rgba(148,163,184,0.08)' : 'rgba(15,23,42,0.05)',
                      color: 'text.primary',
                    },
                    '&::before': {
                      content: '""',
                      position: 'absolute',
                      left: 0,
                      top: '20%',
                      bottom: '20%',
                      width: 3,
                      borderRadius: 3,
                      bgcolor: selected ? 'primary.main' : 'transparent',
                    },
                  }}
                >
                  <ListItemIcon
                    sx={{
                      color: 'inherit',
                      minWidth: collapsed ? 'unset' : 36,
                      justifyContent: 'center',
                      '& svg': { fontSize: 21 },
                      opacity: selected ? 1 : 0.75,
                    }}
                  >
                    <Icon />
                  </ListItemIcon>
                  <ListItemText
                    sx={{
                      display: collapsed ? 'none' : 'block',
                    }}
                    primaryTypographyProps={{ fontSize: '0.9rem', fontWeight: 'inherit' }}
                    primary={label}
                  />
                </ListItemButton>
              </Tooltip>
            );
          })}
        </List>

        <Box sx={{ flexGrow: 1 }} />

        {/* Signed-in user card */}
        <Box sx={{ p: collapsed ? 1 : 2 }}>
          {collapsed ? (
            <Tooltip
              title={`${user?.full_name || user?.email?.split('@')[0] || 'User'} (${(user?.platform_role || 'member').toUpperCase()})`}
              placement="right"
            >
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
                <Avatar
                  sx={{
                    width: 34,
                    height: 34,
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    color: '#fff',
                    background: isDark
                      ? 'linear-gradient(135deg, #0ea5e9, #6366f1)'
                      : 'linear-gradient(135deg, #0284c7, #4f46e5)',
                  }}
                >
                  {initialsOf(user?.full_name || user?.email)}
                </Avatar>
              </Box>
            </Tooltip>
          ) : (
            <Box
              sx={{
                p: 1.25,
                borderRadius: 2.5,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: isDark ? 'rgba(148,163,184,0.05)' : 'rgba(15,23,42,0.03)',
              }}
            >
              <Stack direction="row" spacing={1.25} alignItems="center">
                <Avatar
                  sx={{
                    width: 34,
                    height: 34,
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    color: '#fff',
                    background: isDark
                      ? 'linear-gradient(135deg, #0ea5e9, #6366f1)'
                      : 'linear-gradient(135deg, #0284c7, #4f46e5)',
                  }}
                >
                  {initialsOf(user?.full_name || user?.email)}
                </Avatar>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography variant="body2" fontWeight={650} noWrap>
                    {user?.full_name || user?.email?.split('@')[0] || 'Guest'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" noWrap display="block">
                    {(user?.platform_role || 'member').toUpperCase()}
                  </Typography>
                </Box>
              </Stack>
            </Box>
          )}
        </Box>
      </Drawer>

      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <AppBar
          position="fixed"
          role="banner"
          elevation={0}
          sx={{
            width: `calc(100% - ${drawerWidth}px)`,
            ml: `${drawerWidth}px`,
            transition: 'width 0.2s ease-in-out, margin-left 0.2s ease-in-out',
            backgroundColor: isDark ? 'rgba(10,15,30,0.72)' : 'rgba(246,247,251,0.82)',
            backdropFilter: 'blur(14px)',
            borderBottom: '1px solid',
            borderColor: 'divider',
            color: 'text.primary',
          }}
        >
          <Toolbar sx={{ minHeight: 50, px: { xs: 2, md: 3 } }}>
            <Tooltip title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
              <IconButton
                onClick={() => setCollapsed(!collapsed)}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                size="small"
                sx={{ mr: 1.5, color: 'text.secondary', border: '1px solid', borderColor: 'divider' }}
              >
                {collapsed ? <MenuIcon fontSize="small" /> : <MenuOpenIcon fontSize="small" />}
              </IconButton>
            </Tooltip>

            {pageTitle && (
              <Box sx={{ flexGrow: 1 }}>
                <Typography variant="subtitle1" fontWeight={750} sx={{ lineHeight: 1.2 }}>
                  {pageTitle}
                </Typography>
              </Box>
            )}

            {Boolean(user?.email) && (
              <Chip
                label={user.email}
                size="small"
                variant="outlined"
                sx={{
                  mr: 1,
                  display: { xs: 'none', md: 'inline-flex' },
                  fontWeight: 550,
                  borderRadius: '999px',
                  color: 'text.secondary',
                }}
                aria-label={`Logged in as ${user.email}`}
              />
            )}

            <Tooltip title={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
              <IconButton
                onClick={toggle}
                aria-label={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
                sx={{ color: 'text.secondary', mr: 0.5, border: '1px solid', borderColor: 'divider' }}
                size="small"
              >
                {mode === 'dark' ? <Brightness7Icon /> : <Brightness4Icon />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Log out">
              <IconButton
                onClick={logout}
                aria-label="Log out"
                sx={{ color: 'text.secondary', border: '1px solid', borderColor: 'divider' }}
                size="small"
              >
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>

        <Box component="main" id="main-content" tabIndex={-1} sx={{ flexGrow: 1, px: { xs: 2, md: 3 }, py: 2, mt: 6.5 }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}