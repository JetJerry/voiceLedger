import React from 'react';
import { RefreshCw, Radio } from 'lucide-react';
import { useMerchantEvents } from '../../hooks/useMerchantEvents';

export const ConnectionBadge: React.FC = () => {
  const { status, reconnectAttempts, lastHeartbeat, reconnect } = useMerchantEvents();

  let dotColor = 'bg-slate-400';
  let badgeBorder = 'border-slate-200';
  let badgeBg = 'bg-white';
  let statusText = 'WebSocket Offline';

  if (status === 'CONNECTED') {
    dotColor = 'bg-emerald-500 animate-pulse';
    badgeBorder = 'border-emerald-200';
    badgeBg = 'bg-emerald-50/50';
    statusText = 'WebSocket Feed: Connected';
  } else if (status === 'CONNECTING') {
    dotColor = 'bg-amber-400 animate-ping';
    badgeBorder = 'border-amber-200';
    badgeBg = 'bg-amber-50/50';
    statusText = 'WebSocket: Connecting...';
  } else if (status === 'RECONNECTING') {
    dotColor = 'bg-amber-500 animate-pulse';
    badgeBorder = 'border-amber-200';
    badgeBg = 'bg-amber-50/50';
    statusText = `WebSocket: Reconnecting (Attempt ${reconnectAttempts})...`;
  }

  return (
    <div className={`inline-flex items-center gap-2.5 px-3 py-1.5 rounded-full border text-xs shadow-2xs ${badgeBg} ${badgeBorder}`}>
      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${dotColor}`} />
        <Radio className="w-3.5 h-3.5 text-slate-500" />
      </div>

      <span className="font-semibold text-slate-800 tracking-tight">{statusText}</span>

      {lastHeartbeat && status === 'CONNECTED' && (
        <span className="hidden sm:inline text-2xs text-slate-400 border-l border-slate-200 pl-2">
          Keep-alive active
        </span>
      )}

      {(status === 'DISCONNECTED' || status === 'RECONNECTING') && (
        <button
          onClick={reconnect}
          className="ml-1 inline-flex items-center gap-1 px-2 py-0.5 text-2xs font-semibold rounded bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 transition-colors shadow-2xs"
          title="Manually retry WebSocket connection"
        >
          <RefreshCw className="w-2.5 h-2.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
