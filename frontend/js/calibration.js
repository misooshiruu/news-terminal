// Calibration Page — fetches data from /api/calibration/* and renders tables

class CalibrationView {
    constructor() {
        this.summaryEl = document.getElementById('summary-stats');
        this.impactEl = document.getElementById('impact-table');
        this.sentimentEl = document.getElementById('sentiment-table');
    }

    async init() {
        await Promise.all([
            this.loadSummary(),
            this.loadImpactData(),
            this.loadSentimentData(),
        ]);
    }

    async loadSummary() {
        try {
            const resp = await fetch('/api/calibration/summary');
            const data = await resp.json();
            this.renderSummary(data);
        } catch (e) {
            this.summaryEl.innerHTML = '<div class="empty-state">Failed to load summary</div>';
        }
    }

    async loadImpactData() {
        try {
            const resp = await fetch('/api/calibration/by-impact');
            const data = await resp.json();
            this.renderImpactTable(data);
        } catch (e) {
            this.impactEl.innerHTML = '<div class="empty-state">Failed to load data</div>';
        }
    }

    async loadSentimentData() {
        try {
            const resp = await fetch('/api/calibration/by-sentiment');
            const data = await resp.json();
            this.renderSentimentTable(data);
        } catch (e) {
            this.sentimentEl.innerHTML = '<div class="empty-state">Failed to load data</div>';
        }
    }

    renderSummary(data) {
        const total = data.total_tracked || 0;
        const complete = data.total_complete || 0;

        if (total === 0) {
            this.summaryEl.innerHTML = `
                <div class="empty-state">
                    No move tracking data yet. Data will accumulate as headlines are analyzed
                    during market hours. Each headline needs ~1 hour to complete all checkpoints.
                </div>`;
            return;
        }

        const earliest = data.earliest ? new Date(data.earliest).toLocaleDateString() : 'N/A';
        const latest = data.latest ? new Date(data.latest).toLocaleDateString() : 'N/A';

        this.summaryEl.innerHTML = `
            <div class="cal-stat">
                <div class="label">Headlines Tracked</div>
                <div class="value">${total}</div>
            </div>
            <div class="cal-stat">
                <div class="label">Complete (all checkpoints)</div>
                <div class="value">${complete}</div>
            </div>
            <div class="cal-stat">
                <div class="label">Date Range</div>
                <div class="value" style="font-size:14px">${earliest} - ${latest}</div>
            </div>`;
    }

    renderImpactTable(data) {
        if (!data || data.length === 0) {
            this.impactEl.innerHTML = '<div class="empty-state">No completed move data yet. Check back after headlines have been tracked for 1+ hours.</div>';
            return;
        }

        let html = `
            <table class="cal-table">
                <thead>
                    <tr>
                        <th>Impact Score</th>
                        <th>Sample Size</th>
                        <th>Avg SPY Move T+5m</th>
                        <th>Avg SPY Move T+15m</th>
                        <th>Avg SPY Move T+1h</th>
                        <th>Avg VIX Move T+1h</th>
                    </tr>
                </thead>
                <tbody>`;

        for (const row of data) {
            html += `
                <tr>
                    <td><span class="impact-badge impact-${row.impact_score}">${row.impact_score}</span></td>
                    <td>${row.sample_count}</td>
                    <td>${this.fmtPct(row.avg_spy_move_t5_pct)}</td>
                    <td>${this.fmtPct(row.avg_spy_move_t15_pct)}</td>
                    <td>${this.fmtPct(row.avg_spy_move_t60_pct)}</td>
                    <td>${row.avg_vix_move_t60 != null ? row.avg_vix_move_t60.toFixed(2) : '-'}</td>
                </tr>`;
        }

        html += '</tbody></table>';
        this.impactEl.innerHTML = html;
    }

    renderSentimentTable(data) {
        if (!data || data.length === 0) {
            this.sentimentEl.innerHTML = '<div class="empty-state">No completed sentiment data yet.</div>';
            return;
        }

        let html = `
            <table class="cal-table">
                <thead>
                    <tr>
                        <th>Sentiment</th>
                        <th>Sample Size</th>
                        <th>Correct Direction</th>
                        <th>Accuracy</th>
                        <th>Avg SPY Return T+1h</th>
                    </tr>
                </thead>
                <tbody>`;

        for (const row of data) {
            const accuracy = row.sample_count > 0
                ? ((row.correct_direction / row.sample_count) * 100).toFixed(1)
                : 0;
            const accClass = accuracy >= 60 ? 'accuracy-good' : accuracy >= 45 ? 'accuracy-ok' : 'accuracy-bad';
            const sentClass = row.sentiment === 'bullish' ? 'accuracy-good' : row.sentiment === 'bearish' ? 'accuracy-bad' : 'accuracy-ok';

            html += `
                <tr>
                    <td><span class="${sentClass}" style="text-transform:uppercase; font-weight:600; font-size:11px">${row.sentiment}</span></td>
                    <td>${row.sample_count}</td>
                    <td>${row.correct_direction || 0} / ${row.sample_count}</td>
                    <td><span class="${accClass}">${accuracy}%</span></td>
                    <td>${this.fmtPct(row.avg_spy_return_pct, true)}</td>
                </tr>`;
        }

        html += '</tbody></table>';
        this.sentimentEl.innerHTML = html;
    }

    fmtPct(val, signed = false) {
        if (val == null) return '-';
        const prefix = signed && val >= 0 ? '+' : '';
        return `${prefix}${val.toFixed(4)}%`;
    }
}

// Boot
document.addEventListener('DOMContentLoaded', () => {
    const view = new CalibrationView();
    view.init();
});
