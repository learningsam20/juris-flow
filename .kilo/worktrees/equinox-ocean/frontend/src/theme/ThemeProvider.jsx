import { useMemo, useState } from 'react';
import { alpha, createTheme, ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeModeContext } from './ThemeModeContext';

const LIGHT = {
  primary: { main: '#4f46e5', light: '#818cf8', dark: '#3730a3', contrastText: '#ffffff' },
  secondary: { main: '#0f766e', light: '#14b8a6', dark: '#115e59', contrastText: '#ffffff' },
  success: { main: '#16a34a', light: '#4ade80', dark: '#15803d' },
  warning: { main: '#d97706', light: '#fbbf24', dark: '#b45309' },
  error: { main: '#dc2626', light: '#f87171', dark: '#b91c1c' },
  info: { main: '#0284c7', light: '#38bdf8', dark: '#0369a1' },
  background: { default: '#f6f7fb', paper: '#ffffff' },
  divider: 'rgba(15, 23, 42, 0.08)',
  text: { primary: '#0f172a', secondary: '#51607a', disabled: 'rgba(15, 23, 42, 0.38)' },
};

const DARK = {
  primary: { main: '#818cf8', light: '#a5b4fc', dark: '#6366f1', contrastText: '#0b1020' },
  secondary: { main: '#2dd4bf', light: '#5eead4', dark: '#14b8a6', contrastText: '#0b1020' },
  success: { main: '#4ade80', light: '#86efac', dark: '#22c55e' },
  warning: { main: '#fbbf24', light: '#fde68a', dark: '#f59e0b' },
  error: { main: '#f87171', light: '#fca5a5', dark: '#ef4444' },
  info: { main: '#38bdf8', light: '#7dd3fc', dark: '#0ea5e9' },
  background: { default: '#0a0f1e', paper: '#121a2d' },
  divider: 'rgba(148, 163, 184, 0.14)',
  text: { primary: '#e6ebf5', secondary: '#9aa7bd', disabled: 'rgba(148, 163, 184, 0.45)' },
};

function buildTheme(mode) {
  const palette = mode === 'dark' ? DARK : LIGHT;
  const isDark = mode === 'dark';

  return createTheme({
    palette: { mode, ...palette },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: '"Inter", "Inter Tight", "Roboto", "Helvetica", "Arial", sans-serif',
      h1: { letterSpacing: '-0.03em', fontWeight: 800 },
      h2: { letterSpacing: '-0.02em', fontWeight: 750 },
      h3: { letterSpacing: '-0.02em', fontWeight: 720 },
      h4: { letterSpacing: '-0.02em', fontWeight: 700 },
      h5: { letterSpacing: '-0.01em', fontWeight: 650 },
      h6: { letterSpacing: '-0.01em', fontWeight: 600 },
      subtitle1: { fontWeight: 600, letterSpacing: '-0.01em' },
      button: { fontWeight: 650, letterSpacing: '0em' },
    },
    shadows: [
      'none',
      '0 1px 2px rgba(15,23,42,0.05)',
      '0 1px 3px rgba(15,23,42,0.07), 0 1px 2px rgba(15,23,42,0.04)',
      '0 4px 6px -2px rgba(15,23,42,0.06), 0 2px 4px -2px rgba(15,23,42,0.04)',
      '0 6px 12px -4px rgba(15,23,42,0.08), 0 2px 6px -2px rgba(15,23,42,0.04)',
      '0 8px 18px -6px rgba(15,23,42,0.1), 0 3px 8px -3px rgba(15,23,42,0.05)',
      '0 10px 24px -8px rgba(15,23,42,0.12), 0 4px 10px -4px rgba(15,23,42,0.06)',
      '0 12px 28px -10px rgba(15,23,42,0.14), 0 5px 12px -5px rgba(15,23,42,0.07)',
      '0 14px 32px -12px rgba(15,23,42,0.16), 0 6px 14px -6px rgba(15,23,42,0.08)',
      '0 16px 36px -14px rgba(15,23,42,0.18), 0 7px 16px -7px rgba(15,23,42,0.09)',
      '0 18px 40px -16px rgba(15,23,42,0.2), 0 8px 18px -8px rgba(15,23,42,0.1)',
      ...Array(14).fill('none'),
    ],
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: palette.background.default,
            transition: 'background-color 0.25s ease',
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: 10,
            fontWeight: 650,
            transition: 'background-color 0.15s ease, transform 0.15s ease',
          },
          contained: {
            boxShadow: isDark
              ? '0 1px 2px rgba(0,0,0,0.3)'
              : `0 1px 2px ${alpha(palette.primary.main, 0.2)}`,
          },
          containedPrimary: {
            '&:hover': {
              transform: 'translateY(-1px)',
              boxShadow: isDark
                ? '0 4px 12px rgba(0,0,0,0.35)'
                : `0 4px 16px ${alpha(palette.primary.main, 0.25)}`,
            },
          },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: { borderRadius: 10 },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: 10,
            margin: '2px 10px',
            padding: '9px 12px',
          },
        },
      },
      MuiListItemIcon: {
        styleOverrides: {
          root: { minWidth: 36 },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 550 },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { borderRadius: 99 },
          bar: { borderRadius: 99 },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: { textTransform: 'none', fontWeight: 650 },
        },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: { height: 3, borderRadius: '3px 3px 0 0' },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: 12 },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { borderRadius: 8, fontSize: '0.78rem', fontWeight: 500 },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          head: { fontWeight: 700 },
        },
      },
      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: 16,
            boxShadow: isDark
              ? '0 24px 64px -16px rgba(0,0,0,0.6)'
              : '0 24px 64px -16px rgba(15,23,42,0.2)',
          },
        },
      },
    },
  });
}

function getSystemMode() {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export default function ThemeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    try {
      return localStorage.getItem('jurislab-theme') || getSystemMode();
    } catch {
      return getSystemMode();
    }
  });

  const toggle = () => {
    setMode((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      try {
        localStorage.setItem('jurislab-theme', next);
      } catch {
        // ignore
      }
      return next;
    });
  };

  const theme = useMemo(() => buildTheme(mode), [mode]);

  return (
    <ThemeModeContext.Provider value={{ toggle, mode }}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeModeContext.Provider>
  );
}