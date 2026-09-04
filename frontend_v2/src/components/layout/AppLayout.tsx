import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { DemoStepBar } from './DemoStepBar';

export const AppLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Navbar />
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <DemoStepBar />
        <Outlet />
      </main>
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-400">
        VoiceLedger v2.0 • Real-Time Financial Notification Platform • Zero Financial Mutation
      </footer>
    </div>
  );
};
