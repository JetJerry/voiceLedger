import React from 'react';
import { ActivityLogItem } from '../../types/websocket';
import { formatTimestamp } from '../../services/websocketParser';
import { Radio, Zap, AlertTriangle, Info, Terminal } from 'lucide-react';

interface ActivityFeedProps {
  logs: ActivityLogItem[];
}

export const ActivityFeed: React.FC<ActivityFeedProps> = ({ logs }) => {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs flex flex-col h-full">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-blue-600" />
          <span>WebSocket Event Stream</span>
        </h3>
        <span className="text-2xs font-mono text-slate-400">
          {logs.length} logged
        </span>
      </div>

      <div className="mt-3 flex-1 overflow-y-auto max-h-[320px] space-y-2 pr-1">
        {logs.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
            <Radio className="w-5 h-5 mx-auto mb-2 text-slate-300 animate-pulse" />
            <span>Listening for real-time WebSocket frames...</span>
          </div>
        ) : (
          logs.map((log) => {
            let icon = <Info className="w-3.5 h-3.5 text-slate-400" />;
            let borderColor = 'border-slate-100 bg-slate-50/50';

            if (log.type === 'payment') {
              icon = <Zap className="w-3.5 h-3.5 text-emerald-600 fill-emerald-600" />;
              borderColor = 'border-emerald-200 bg-emerald-50/40';
            } else if (log.level === 'warning' || log.level === 'error') {
              icon = <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />;
              borderColor = 'border-amber-200 bg-amber-50/40';
            } else if (log.type === 'connection') {
              icon = <Radio className="w-3.5 h-3.5 text-blue-600" />;
              borderColor = 'border-blue-100 bg-blue-50/40';
            }

            return (
              <div
                key={log.id}
                className={`p-2.5 rounded-xl border text-xs transition-all ${borderColor}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {icon}
                    <span className="font-semibold text-slate-800 tracking-tight">
                      {log.title}
                    </span>
                  </div>
                  <span className="text-2xs font-mono text-slate-400 shrink-0">
                    {formatTimestamp(log.timestamp)}
                  </span>
                </div>
                <p className="text-2xs text-slate-500 mt-1 font-mono break-all pl-5">
                  {log.detail}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
