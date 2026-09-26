import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../auth/store';

export default function Protected({ children }) {
  const token = useAuthStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;
  return children;
}