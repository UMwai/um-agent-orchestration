import React, { useEffect, useRef, useState } from 'react';

export default function App() {
  const [status, setStatus] = useState('disconnected');
  const logRef = useRef([]);
  const [, force] = useState(0);

  useEffect(() => {
    // Basic dashboard WebSocket to verify proxy works
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    ws.onopen = () => {
      setStatus('connected');
      ws.send('hello-from-vite-ui');
    };
    ws.onmessage = (e) => {
      logRef.current.push(`WS message: ${e.data}`);
      force((x) => x + 1);
    };
    ws.onclose = () => setStatus('disconnected');
    ws.onerror = () => setStatus('error');
    return () => ws.close();
  }, []);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 24 }}>
      <h1>Agent UM-7 Dashboard (Vite)</h1>
      <p style={{ color: '#64748b' }}>
        This is a precompiled React app scaffold. The legacy dashboard.html remains available
        as a fallback until the full UI is migrated.
      </p>

      <div style={{ marginTop: 16 }}>
        <strong>WebSocket:</strong> {status}
      </div>
      <div style={{ marginTop: 12, background: '#0f172a', color: '#e2e8f0', padding: 12, borderRadius: 6 }}>
        <div style={{ marginBottom: 8, color: '#94a3b8' }}>Messages</div>
        <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
{logRef.current.join('\n')}
        </pre>
      </div>
    </div>
  );
}

