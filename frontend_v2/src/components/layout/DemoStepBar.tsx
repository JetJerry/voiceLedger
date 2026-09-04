import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, Speaker, Cpu, ChevronRight, Play } from 'lucide-react';

export const DemoStepBar: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  const steps = [
    {
      id: 1,
      path: '/',
      label: 'Live Operations',
      sublabel: 'Real-time /ws/merchant stream',
      icon: Activity,
      color: 'emerald',
    },
    {
      id: 2,
      path: '/devices',
      label: 'Soundbox Simulator',
      sublabel: 'Hardware /ws/device audio & ACK',
      icon: Speaker,
      color: 'indigo',
    },
    {
      id: 3,
      path: '/architecture',
      label: 'System Architecture',
      sublabel: 'Transactional outbox & invariants',
      icon: Cpu,
      color: 'amber',
    },
  ];

  const currentStepIndex = steps.findIndex((s) => s.path === location.pathname);
  const activeStep = currentStepIndex !== -1 ? steps[currentStepIndex] : steps[0];

  const handleNextStep = () => {
    if (currentStepIndex < steps.length - 1) {
      navigate(steps[currentStepIndex + 1].path);
    } else {
      navigate(steps[0].path);
    }
  };

  return (
    <aside aria-label="Demo flow walkthrough" className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs mb-6 flex flex-col md:flex-row md:items-center justify-between gap-3">
      {/* Left: Step Stepper */}
      <div className="flex items-center gap-2 overflow-x-auto">
        <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-100 text-slate-600 text-3xs font-bold uppercase tracking-wider shrink-0">
          <Play className="w-2.5 h-2.5 text-blue-600 fill-blue-600" />
          Demo Flow
        </span>

        <div className="flex items-center gap-1.5 min-w-max">
          {steps.map((step, idx) => {
            const Icon = step.icon;
            const isCurrent = step.path === location.pathname;

            return (
              <React.Fragment key={step.id}>
                <button
                  type="button"
                  onClick={() => navigate(step.path)}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    isCurrent
                      ? 'bg-blue-50 text-blue-700 border border-blue-200 shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                  }`}
                >
                  <span
                    className={`w-4 h-4 rounded-full flex items-center justify-center text-3xs font-bold ${
                      isCurrent ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {step.id}
                  </span>
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="hidden sm:inline">{step.label}</span>
                </button>

                {idx < steps.length - 1 && (
                  <ChevronRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Right: Quick Stage Advancement */}
      <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
        <span className="text-2xs text-slate-500 font-medium">
          Current: <strong className="text-slate-800">{activeStep.label}</strong>
        </span>

        <button
          type="button"
          onClick={handleNextStep}
          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium transition-colors"
          title="Jump to the next stage of the presentation"
        >
          <span>Next Step</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </aside>
  );
};
