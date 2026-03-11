// Market Terminal - Main Application

class MarketTerminal {
    constructor() {
        this.ws = new WSClient('/ws');
        this.feed = new FeedRenderer('feed');
        this.filters = new FilterManager();
        this.headlines = [];
        this.autoScroll = true;
    }

    init() {
        // Setup filters
        this.filters.init();
        this.filters.onChange(() => this.applyFilters());

        // Track scroll position to manage auto-scroll
        const feedContainer = document.getElementById('feed-container');
        if (feedContainer) {
            feedContainer.addEventListener('scroll', () => {
                const { scrollTop } = feedContainer;
                // If user scrolled down, disable auto-scroll; if near top, re-enable
                this.autoScroll = scrollTop < 50;
            });
        }

        // Setup WebSocket
        this.ws.on('connected', () => {
            document.getElementById('connection-status').className = 'status-dot connected';
            document.getElementById('status-text').textContent = 'Connected';
        });

        this.ws.on('disconnected', () => {
            document.getElementById('connection-status').className = 'status-dot disconnected';
            document.getElementById('status-text').textContent = 'Reconnecting...';
        });

        this.ws.on('new_headline', (data) => this.onNewHeadline(data));
        this.ws.on('analysis_update', (data) => this.onAnalysisUpdate(data));
        this.ws.on('stats_update', (data) => this.onStatsUpdate(data));

        this.ws.connect();

        // Load initial data
        this.loadInitialData();

        // Start clock
        this.updateClock();
        setInterval(() => this.updateClock(), 1000);

        // Refresh stats every 15s
        setInterval(() => this.loadStats(), 15000);

        // Periodic full data refresh every 60s to pick up analysis results
        // that may have been missed by WebSocket
        setInterval(() => this.refreshData(), 60000);
    }

    async loadInitialData() {
        try {
            const response = await fetch('/api/headlines?limit=300');
            const data = await response.json();
            this.headlines = data;
            this.feed.renderAll(data);
            this.loadStats();
        } catch (e) {
            console.error('Failed to load initial data:', e);
        }
    }

    async refreshData() {
        // Silently refresh to pick up analysis updates
        try {
            const response = await fetch('/api/headlines?limit=300');
            const data = await response.json();
            this.headlines = data;
            // Only re-render if filters are active or we're at the top
            if (this.autoScroll) {
                const filtered = this.headlines.filter(h => this.filters.matches(h));
                this.feed.renderAll(filtered);
            }
        } catch (e) {
            // silent
        }
    }

    async loadStats() {
        try {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            this.onStatsUpdate(stats);
        } catch (e) {
            // ignore
        }
    }

    onNewHeadline(data) {
        this.headlines.unshift(data);
        if (this.headlines.length > 1000) this.headlines.pop();

        if (this.filters.matches(data)) {
            this.feed.prepend(data);
        }
    }

    onAnalysisUpdate(data) {
        const headlineId = data.headline_id;
        const analysis = data.data || data;

        // Update in-memory data
        const idx = this.headlines.findIndex(h => h.id === headlineId);
        if (idx !== -1) {
            Object.assign(this.headlines[idx], analysis);
            this.headlines[idx].is_analyzed = true;
        }

        // Update the DOM card
        this.feed.updateCard(headlineId, analysis);
    }

    onStatsUpdate(stats) {
        const el = document.getElementById('stats-text');
        if (el) {
            el.textContent = `Headlines today: ${stats.total || 0} | Analyzed: ${stats.analyzed || 0}`;
        }
    }

    applyFilters() {
        const filtered = this.headlines.filter(h => this.filters.matches(h));
        this.feed.renderAll(filtered);
    }

    updateClock() {
        const el = document.getElementById('clock');
        if (el) {
            const now = new Date();
            el.textContent = now.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
                timeZoneName: 'short',
            });
        }
    }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
    const terminal = new MarketTerminal();
    terminal.init();
});
