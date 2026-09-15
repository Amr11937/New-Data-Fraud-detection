import { useCallback, useEffect, useState } from 'react';
import { fmsWs } from '@/services/websocket';
import type { WsEvent } from '@/types';

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [recentAlerts, setRecentAlerts] = useState<WsEvent[]>([]);

  useEffect(() => {
    fmsWs.connect();

    const unsubscribe = fmsWs.subscribe((event) => {
      setIsConnected(fmsWs.isConnected);
      if (event.type === 'fraud_event') {
        setRecentAlerts((prev) => [event, ...prev].slice(0, 50));
      }
      if (event.type === 'connected') {
        setIsConnected(true);
      }
    });

    const intervalId = setInterval(() => setIsConnected(fmsWs.isConnected), 5000);

    return () => {
      unsubscribe();
      clearInterval(intervalId);
    };
  }, []);

  const clearAlerts = useCallback(() => setRecentAlerts([]), []);

  return { isConnected, recentAlerts, clearAlerts };
}
