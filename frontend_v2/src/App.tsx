import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { SoundboxProvider } from './context/SoundboxContext';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { DevicesPage } from './pages/DevicesPage';
import { ArchitecturePage } from './pages/ArchitecturePage';
import { PaymentsPage } from './pages/PaymentsPage';
import { StorePage } from './pages/StorePage';
import { SalesPage } from './pages/SalesPage';
import { VoiceTalkbackPage } from './pages/VoiceTalkbackPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <WebSocketProvider>
        <SoundboxProvider>
          <BrowserRouter>
            <Routes>
              {/* Public Authentication Routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Protected Merchant Application Routes */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<DashboardPage />} />
                <Route path="/payments" element={<PaymentsPage />} />
                <Route path="/store" element={<StorePage />} />
                <Route path="/sales" element={<SalesPage />} />
                <Route path="/talkback" element={<VoiceTalkbackPage />} />
                <Route path="/devices" element={<DevicesPage />} />
                <Route path="/architecture" element={<ArchitecturePage />} />
              </Route>

              {/* Catch-all redirect */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </SoundboxProvider>
      </WebSocketProvider>
    </AuthProvider>
  );
};

export default App;
