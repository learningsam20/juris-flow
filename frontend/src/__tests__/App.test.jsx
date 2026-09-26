import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { useAuthStore } from '../auth/store';

vi.mock('../api/client', () => ({
  api: vi.fn().mockResolvedValue([]),
}));

function renderApp(route = '/login') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  );
}

describe('App', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.getState().logout();
  });

  it('renders the sign-in form at /login', async () => {
    renderApp('/login');
    expect(screen.getByText('Sign in')).toBeInTheDocument();
  });

  it('redirects an unauthenticated user from / to /login', () => {
    renderApp('/');
    expect(screen.getByText('Sign in')).toBeInTheDocument();
  });

  it('renders dashboard nav when authenticated', () => {
    useAuthStore.setState({ token: 'test-token' });
    renderApp('/');
    const nav = screen.getByRole('navigation', { name: /main navigation/i });
    expect(within(nav).getByText('Dashboard')).toBeInTheDocument();
    expect(within(nav).getByText('Ask AI')).toBeInTheDocument();
  });

  it('has a skip-link to main content when authenticated', () => {
    useAuthStore.setState({ token: 'test-token' });
    renderApp('/');
    const skipLink = screen.getByRole('link', { name: /skip to main content/i });
    expect(skipLink).toHaveAttribute('href', '#main-content');
  });
});