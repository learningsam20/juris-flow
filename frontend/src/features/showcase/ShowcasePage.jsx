import { Box, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { Link as RouterLink } from 'react-router-dom';

const DECK_SRC = '/showcase/index.html';

export default function ShowcasePage() {
  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: (t) => t.zIndex.modal + 1,
        display: 'flex',
        flexDirection: 'column',
        bgcolor: '#f4f1eb',
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        sx={{
          px: 1.5,
          py: 0.75,
          borderBottom: '1px solid',
          borderColor: 'divider',
          bgcolor: 'rgba(255,255,255,0.92)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <Tooltip title="Back to app">
          <IconButton component={RouterLink} to="/" size="small" aria-label="Back to dashboard">
            <ArrowBackIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        <Typography variant="subtitle2" sx={{ flex: 1, fontWeight: 600 }}>
          JurisFlow · Showcase
        </Typography>
        <Tooltip title="Open deck in new tab">
          <IconButton
            size="small"
            href={DECK_SRC}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open showcase in new tab"
          >
            <OpenInNewIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Stack>
      <Box
        component="iframe"
        title="JurisFlow presentation"
        src={DECK_SRC}
        sx={{ flex: 1, width: '100%', border: 0, bgcolor: '#f4f1eb' }}
      />
    </Box>
  );
}
