/**
 * WebSocket client for real-time fraud alerts. Connects to the merged
 * backend's /api/ws endpoint (app/routers/ws.py). Ported from
 * Broadband FMS's services/websocket.ts -- the reconnect logic doesn't
 * depend on what's on the other end.
 */
import type { WsEvent } from '@/types';

type MessageHandler = (event: WsEvent) => void;

class FmsWebSocket {
  private ws: WebSocket | null = null;
  private handlers: Set<MessageHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1000;
  private maxDelay = 30_000;
  private shouldReconnect = true;

  connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;
    const url = `${protocol}://${host}/api/ws`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[WS] Connected to fraud alert stream');
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (event) => {
      try {
        const parsed: WsEvent = JSON.parse(event.data);
        this.handlers.forEach((h) => h(parsed));
      } catch {
        // ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      console.log('[WS] Connection closed');
      if (this.shouldReconnect) this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.warn('[WS] Error:', err);
      this.ws?.close();
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
  }

  subscribe(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const fmsWs = new FmsWebSocket();
