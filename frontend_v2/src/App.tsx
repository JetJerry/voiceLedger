import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Authentication Route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Merchant Application Routes */}
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route
              path="/devices"
              element={
                <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-xs text-center text-slate-500">
                  <h2 className="text-lg font-bold text-slate-800">Soundbox Hardware Management</h2>
                  <p className="text-xs text-slate-500 mt-2">
                    Coming in Batch 4: Registered Soundbox fleet telemetry & Virtual Soundbox Hardware Simulator.
                  </p>
                </div>
              }
            />
            <Route
              path="/architecture"
              element={
                <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-xs text-center text-slate-500">
                  <h2 className="text-lg font-bold text-slate-800">System Architecture & Invariants</h2>
                  <p className="text-xs text-slate-500 mt-2">
                    Coming in Batch 5: Interactive transactional outbox and zero-financial-mutation pipeline.
                  </p>
                </div>
              }
            />
          </Route>

          {/* Catch-all redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
