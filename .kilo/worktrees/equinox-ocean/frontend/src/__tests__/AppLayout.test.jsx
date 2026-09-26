import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('jurislab-theme', 'light');
});
import ThemeProvider from '../theme/ThemeProvider';
import AppLayout from '../layouts/AppLayout';

function renderAppLayout() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/']}>
        <AppLayout />
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe('AppLayout', () => {
  it('renders a skip link to the main content anchor', () => {
    renderAppLayout();
    const skipLink = screen.getByRole('link', { name: /skip to main content/i });
    expect(skipLink).toHaveAttribute('href', '#main-content');
    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main-content');
  });

  it('has an accessible navigation that is keyboard reachable', () => {
    renderAppLayout();
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    const links = within(nav).getAllByRole('link');
    expect(links.length).toBeGreaterThan(0);
    const themeToggle = screen.getByRole('button', {
      name: /switch to (light|dark) mode/i,
    });
    themeToggle.focus();
    expect(themeToggle).toHaveFocus();
  });

  it('provides a dark/light mode toggle with an accessible label', () => {
    renderAppLayout();
    const toggle = screen.getByRole('button', {
      name: /switch to (light|dark) mode/i,
    });
    const current = toggle.getAttribute('aria-label');
    const other = current === 'Switch to light mode'
      ? 'Switch to dark mode'
      : 'Switch to light mode';
    fireEvent.click(toggle);
    expect(screen.getByRole('button', { name: other })).toBeInTheDocument();
  });
});
