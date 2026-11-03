import { wsUrl } from "./config.js";

const BASE_DELAY_MS = 500;
const MAX_DELAY_MS = 15000;
const SILENCE_LIMIT_MS = 12000;

export function backoffDelay(attempt, random = Math.random) {
  const ceiling = Math.min(MAX_DELAY_MS, BASE_DELAY_MS * 2 ** attempt);
  return Math.round(ceiling / 2 + random() * (ceiling / 2));
}

export class LiveStream {
  constructor(onState) {
    this.onState = onState;
    this.listeners = new Set();
    this.filter = {};
    this.socket = null;
    this.attempt = 0;
    this.retryTimer = null;
    this.silenceTimer = null;
    this.closed = false;
    this.connect();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  setFilter(filter) {
    this.filter = filter;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(filter));
    }
  }

  watchSilence() {
    clearTimeout(this.silenceTimer);
    this.silenceTimer = setTimeout(() => {
      if (this.socket) {
        this.socket.close();
      }
    }, SILENCE_LIMIT_MS);
  }

  connect() {
    if (this.closed) {
      return;
    }
    const socket = new WebSocket(wsUrl("/ws/telemetry"));
    this.socket = socket;
    socket.onopen = () => {
      this.attempt = 0;
      this.onState("open");
      socket.send(JSON.stringify(this.filter));
      this.watchSilence();
    };
    socket.onmessage = (event) => {
      this.watchSilence();
      const message = JSON.parse(event.data);
      this.listeners.forEach((listener) => listener(message));
    };
    socket.onclose = () => {
      clearTimeout(this.silenceTimer);
      if (this.socket !== socket) {
        return;
      }
      this.onState("closed");
      clearTimeout(this.retryTimer);
      this.retryTimer = setTimeout(() => this.connect(), backoffDelay(this.attempt));
      this.attempt += 1;
    };
  }

  close() {
    this.closed = true;
    clearTimeout(this.retryTimer);
    clearTimeout(this.silenceTimer);
    if (this.socket) {
      this.socket.close();
    }
  }
}
