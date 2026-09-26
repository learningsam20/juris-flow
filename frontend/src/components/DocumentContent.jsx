import { Box } from '@mui/material';
import ReactMarkdown from 'react-markdown';

const MARKDOWN_EXT = /\.(md|markdown)$/i;

export default function DocumentContent({ text, filename, sx }) {
  if (text && MARKDOWN_EXT.test(filename || '')) {
    return (
      <Box
        sx={{
          '& h1, & h2, & h3, & h4': { fontWeight: 700, mt: 2, mb: 1 },
          '& p': { my: 1, lineHeight: 1.7 },
          '& ul, & ol': { pl: 3, my: 1 },
          '& blockquote': {
            pl: 2,
            ml: 0,
            borderLeft: '4px solid',
            borderColor: 'primary.main',
            color: 'text.secondary',
          },
          fontSize: '0.92rem',
          ...sx,
        }}
      >
        <ReactMarkdown>{text}</ReactMarkdown>
      </Box>
    );
  }
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
        ...sx,
      }}
    >
      {text || 'No text extracted.'}
    </Box>
  );
}