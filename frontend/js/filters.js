// Filter management

class FilterManager {
    constructor() {
        this.activeCategories = new Set();
        this.activeSources = new Set();
        this.minImpact = 0;
        this.tickerSearch = '';
        this.onChangeCallback = null;

        this.categories = [
            'Energy', 'Bonds', 'Equities', 'FX', 'Commodities', 'Crypto',
            'Geopolitics', 'Trade', 'Monetary Policy', 'Fiscal Policy',
            'Regulation', 'Earnings', 'M&A', 'Tech', 'Politics', 'Labor',
        ];

        this.sourceTypes = [
            { key: 'rss', label: 'RSS Feeds' },
            { key: 'api', label: 'API' },
            { key: 'twitter', label: 'Twitter' },
        ];
    }

    init() {
        this.renderCategoryFilters();
        this.renderSourceFilters();
        this.renderImpactFilters();
        this.setupTickerSearch();
    }

    onChange(callback) {
        this.onChangeCallback = callback;
    }

    renderCategoryFilters() {
        const container = document.getElementById('category-filters');
        if (!container) return;

        // All toggle
        const allLabel = document.createElement('label');
        const allCheck = document.createElement('input');
        allCheck.type = 'checkbox';
        allCheck.checked = true;
        allCheck.addEventListener('change', () => {
            if (allCheck.checked) {
                this.activeCategories.clear();
                container.querySelectorAll('input[data-category]').forEach(cb => cb.checked = false);
            }
            this._emitChange();
        });
        allLabel.appendChild(allCheck);
        allLabel.appendChild(document.createTextNode(' All'));
        container.appendChild(allLabel);

        this.categories.forEach(cat => {
            const label = document.createElement('label');
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.dataset.category = cat;
            cb.addEventListener('change', () => {
                if (cb.checked) {
                    this.activeCategories.add(cat);
                    container.querySelector('input:not([data-category])').checked = false;
                } else {
                    this.activeCategories.delete(cat);
                    if (this.activeCategories.size === 0) {
                        container.querySelector('input:not([data-category])').checked = true;
                    }
                }
                this._emitChange();
            });
            label.appendChild(cb);
            label.appendChild(document.createTextNode(` ${cat}`));
            container.appendChild(label);
        });
    }

    renderSourceFilters() {
        const container = document.getElementById('source-filters');
        if (!container) return;

        this.sourceTypes.forEach(src => {
            const label = document.createElement('label');
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = true;
            cb.dataset.source = src.key;
            cb.addEventListener('change', () => {
                if (cb.checked) {
                    this.activeSources.delete(src.key);
                } else {
                    this.activeSources.add(src.key);
                }
                this._emitChange();
            });
            label.appendChild(cb);
            label.appendChild(document.createTextNode(` ${src.label}`));
            container.appendChild(label);
        });
    }

    renderImpactFilters() {
        const container = document.getElementById('impact-filters');
        if (!container) return;

        for (let i = 1; i <= 5; i++) {
            const btn = document.createElement('button');
            btn.className = 'impact-btn';
            btn.textContent = i;
            btn.dataset.impact = i;
            btn.addEventListener('click', () => {
                if (this.minImpact === i) {
                    this.minImpact = 0;
                    btn.classList.remove('active');
                } else {
                    container.querySelectorAll('.impact-btn').forEach(b => b.classList.remove('active'));
                    this.minImpact = i;
                    btn.classList.add('active');
                }
                this._emitChange();
            });
            container.appendChild(btn);
        }
    }

    setupTickerSearch() {
        const input = document.getElementById('ticker-search');
        if (!input) return;

        let debounceTimer;
        input.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                this.tickerSearch = input.value.trim().toUpperCase();
                this._emitChange();
            }, 300);
        });
    }

    matches(headline) {
        // Category filter
        if (this.activeCategories.size > 0) {
            const hCats = headline.categories || [];
            if (!hCats.some(c => this.activeCategories.has(c))) return false;
        }

        // Source filter (exclusion-based)
        if (this.activeSources.size > 0) {
            if (this.activeSources.has(headline.source_category)) return false;
        }

        // Impact filter
        if (this.minImpact > 0) {
            if (!headline.impact_score || headline.impact_score < this.minImpact) return false;
        }

        // Ticker search
        if (this.tickerSearch) {
            const tickers = headline.tickers || [];
            const title = (headline.title || '').toUpperCase();
            const searchTerms = this.tickerSearch.split(',').map(t => t.trim()).filter(Boolean);
            if (!searchTerms.some(term => tickers.includes(term) || title.includes(term))) {
                return false;
            }
        }

        return true;
    }

    _emitChange() {
        if (this.onChangeCallback) this.onChangeCallback();
    }
}
