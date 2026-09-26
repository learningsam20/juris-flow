import { Route, Routes } from 'react-router-dom';
import ThemeProvider from './theme/ThemeProvider';
import Protected from './components/Protected';
import LoginPage from './features/dashboard/LoginPage';
import Dashboard from './features/dashboard/Dashboard';
import Layout from './layouts/AppLayout';
import HubPage from './features/hub/HubPage';
import ReviewPage from './features/review/ReviewPage';
import SimPage from './features/sim/SimPage';
import RunDetailPage from './features/sim/RunDetailPage';
import AnalyticsPage from './features/analytics/AnalyticsPage';
import InsightsPage from './features/insights/InsightsPage';
import SettingsPage from './features/settings/SettingsPage';
import ShowcasePage from './features/showcase/ShowcasePage';

export default function App() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/showcase"
          element={
            <Protected>
              <ShowcasePage />
            </Protected>
          }
        />
        <Route
          path="/"
          element={
            <Protected>
              <Layout />
            </Protected>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="hub" element={<HubPage />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="simulations" element={<SimPage />} />
          <Route path="simulations/:simulationId" element={<RunDetailPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="insights" element={<InsightsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </ThemeProvider>
  );
}
