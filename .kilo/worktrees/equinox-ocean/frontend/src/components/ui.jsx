import {
  Box,
  Card,
  CardActionArea,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Typography,
  useTheme,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

/**
 * Shared page hero. Gives every page a consistent eyebrow chip, title,
 * subtitle, and action cluster rendered on a soft gradient banner.
 */
export function PageHeader({ icon, eyebrow, title, subtitle, actions, children, sx }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  return (
    <Paper
      elevation={0}
      sx={{
        p: { xs: 2.5, md: 3 },
        mb: 3,
        borderRadius: 3,
        background: isDark
          ? 'linear-gradient(135deg, rgba(23,32,58,0.95) 0%, rgba(49,46,129,0.55) 100%)'
          : 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 55%, #dbeafe 100%)',
        border: '1px solid',
        borderColor: isDark ? 'rgba(129,140,248,0.35)' : 'rgba(79,70,229,0.2)',
        boxShadow: isDark ? '0 8px 32px -16px rgba(0,0,0,0.6)' : '0 8px 28px -18px rgba(79,70,229,0.4)',
        ...sx,
      }}
    >
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', sm: 'center' }}
        spacing={2}
      >
        <Box sx={{ minWidth: 0 }}>
          {eyebrow && (
            <Chip
              size="small"
              icon={icon}
              label={eyebrow}
              color="primary"
              variant={isDark ? 'filled' : 'outlined'}
              sx={{ mb: 1.25, fontWeight: 700, fontSize: '0.72rem', height: 26 }}
            />
          )}
          <Typography
            variant="h4"
            fontWeight={800}
            sx={{ letterSpacing: '-0.03em', lineHeight: 1.15, wordBreak: 'break-word' }}
          >
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, maxWidth: 720 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
        {actions && (
          <Stack
            direction="row"
            spacing={1}
            flexWrap="wrap"
            justifyContent={{ xs: 'flex-start', sm: 'flex-end' }}
            sx={{ flexShrink: 0 }}
          >
            {actions}
          </Stack>
        )}
      </Stack>
      {children}
    </Paper>
  );
}

/**
 * Standard content card with an optional icon + title header row.
 * Consistent borders, radius, and padding across every page.
 */
export function SectionCard({ icon, title, action, children, sx, contentSx }) {
  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 3,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        display: 'flex',
        flexDirection: 'column',
        ...sx,
      }}
    >
      {(icon || title || action) && (
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ px: 2.5, pt: 2.25 }}
        >
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0 }}>
            {icon}
            <Typography component="div" variant="h6" fontWeight={650} sx={{ letterSpacing: '-0.01em' }}>
              {title}
            </Typography>
          </Stack>
          {action}
        </Stack>
      )}
      <Box sx={{ px: 2.5, pt: 2, pb: 2.5, flexGrow: 1, ...contentSx }}>{children}</Box>
    </Card>
  );
}

/**
 * Clickable KPI metric tile used on the dashboard and analytics.
 * `ariaLabel` gives the whole tile a stable accessible name.
 */
export function StatTile({
  label,
  value,
  icon,
  color,
  sub,
  footer,
  onClick,
  loading,
  ariaLabel,
}) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Card
      elevation={0}
      sx={{
        borderRadius: 3,
        border: '1px solid',
        borderColor: 'divider',
        backgroundColor: 'background.paper',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
        '&:hover': onClick
          ? {
              transform: 'translateY(-3px)',
              borderColor: 'primary.main',
              boxShadow: isDark
                ? '0 12px 28px -12px rgba(0,0,0,0.6)'
                : '0 12px 28px -14px rgba(79,70,229,0.35)',
            }
          : {},
      }}
    >
      <CardActionArea onClick={onClick} aria-label={ariaLabel || label} disabled={!onClick} sx={{ '&:disabled': { pointerEvents: 'none' } }}>
        <Stack sx={{ p: 2.5 }}>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Box sx={{ minWidth: 0, pr: 1.5 }}>
              <Typography
                variant="caption"
                color="text.secondary"
                fontWeight={700}
                textTransform="uppercase"
                letterSpacing="0.6px"
                sx={{ fontSize: '0.7rem', display: 'block', mb: 0.5 }}
              >
                {label}
              </Typography>
              <Typography variant="h3" fontWeight={800} sx={{ color, lineHeight: 1.15 }}>
                {loading ? <CircularProgress size={30} /> : value}
              </Typography>
            </Box>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color,
                flexShrink: 0,
                mt: 0.25,
                '& svg': { fontSize: 28 },
              }}
            >
              {icon}
            </Box>
          </Stack>

          {sub && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {sub}
            </Typography>
          )}

          {footer && (
            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 1.5, color }}>
              <Typography variant="caption" fontWeight={700}>
                {footer}
              </Typography>
              <ArrowForwardIcon sx={{ fontSize: 13 }} />
            </Stack>
          )}
        </Stack>
      </CardActionArea>
    </Card>
  );
}

/** Small status dot/badge used in telemetry rows. */
export function StatusChip({ active, label, activeColor = 'success', inactiveColor = 'default' }) {
  return (
    <Chip
      size="small"
      label={label}
      color={active ? activeColor : inactiveColor}
      sx={{ height: 24, fontSize: '0.75rem', fontWeight: 600 }}
    />
  );
}

/**
 * Empty-state block used consistently across lists and tables.
 */
export function EmptyState({ icon, title, body, action }) {
  return (
    <Box
      sx={{
        p: 4,
        textAlign: 'center',
        borderRadius: 3,
        border: '1px dashed',
        borderColor: 'divider',
        bgcolor: (t) => (t.palette.mode === 'dark' ? 'rgba(148,163,184,0.04)' : 'rgba(79,70,229,0.02)'),
      }}
    >
      {icon && <Box sx={{ color: 'text.disabled', mb: 1 }}>{icon}</Box>}
      <Typography variant="subtitle1" fontWeight={700}>
        {title}
      </Typography>
      {body && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 500, mx: 'auto', mt: 0.5 }}>
          {body}
        </Typography>
      )}
      {action && <Box sx={{ mt: 2 }}>{action}</Box>}
    </Box>
  );
}