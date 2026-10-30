import { wsUrl } from "./config.js";

export class LiveStream {
  constructor(onState) {
    this.onState = onState;
    this.listeners = new Set();
    this.filter = {};
    this.socket = null;
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

  connect() {
    this.socket = new WebSocket(wsUrl("/ws/telemetry"));
    this.socket.onopen = () => {
      this.onState("open");
      this.socket.send(JSON.stringify(this.filter));
    };
    this.socket.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.listeners.forEach((listener) => listener(message));
    };
    this.socket.onclose = () => {
      this.onState("closed");
      setTimeout(() => this.connect(), 1000);
    };
  }
}
