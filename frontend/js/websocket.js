// Reconnecting WebSocket client

class WSClient {
    constructor(url) {
        this.url = `ws://${window.location.host}${url}`;
        this.handlers = {};
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.socket = null;
    }

    connect() {
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            this.reconnectDelay = 1000;
            if (this.handlers['connected']) this.handlers['connected']();
        };

        this.socket.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (this.handlers[msg.type]) {
                    this.handlers[msg.type](msg.data || msg);
                }
            } catch (e) {
                console.error('WS parse error:', e);
            }
        };

        this.socket.onclose = () => {
            if (this.handlers['disconnected']) this.handlers['disconnected']();
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        };

        this.socket.onerror = () => {
            this.socket.close();
        };
    }

    on(type, handler) {
        this.handlers[type] = handler;
    }

    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        }
    }
}
