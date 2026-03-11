// Feed rendering

class FeedRenderer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.maxCards = 500;
    }

    renderAll(headlines) {
        this.container.innerHTML = '';
        headlines.forEach(h => this.append(h));
    }

    prepend(headline) {
        const card = this.createCard(headline);
        if (this.container.firstChild) {
            this.container.insertBefore(card, this.container.firstChild);
        } else {
            this.container.appendChild(card);
        }
        // Trim old cards
        while (this.container.children.length > this.maxCards) {
            this.container.removeChild(this.container.lastChild);
        }
    }

    append(headline) {
        const card = this.createCard(headline);
        card.style.animation = 'none';
        this.container.appendChild(card);
    }

    updateCard(headlineId, analysis) {
        const card = document.querySelector(`[data-id="${headlineId}"]`);
        if (!card) return;

        // Update sentiment border
        card.classList.remove('bullish', 'bearish', 'neutral-analyzed');
        if (analysis.sentiment) {
            card.classList.add(analysis.sentiment === 'neutral' ? 'neutral-analyzed' : analysis.sentiment);
        }

        // Update meta line
        const meta = card.querySelector('.headline-meta');
        if (analysis.sentiment) {
            let sentBadge = card.querySelector('.headline-sentiment');
            if (!sentBadge) {
                sentBadge = document.createElement('span');
                sentBadge.className = 'headline-sentiment';
                meta.appendChild(sentBadge);
            }
            sentBadge.className = `headline-sentiment ${analysis.sentiment}`;
            sentBadge.textContent = analysis.sentiment.toUpperCase();
        }

        if (analysis.impact_score) {
            let impactBadge = card.querySelector('.impact-badge');
            if (!impactBadge) {
                impactBadge = document.createElement('span');
                impactBadge.className = 'impact-badge';
                meta.appendChild(impactBadge);
            }
            impactBadge.className = `impact-badge impact-${analysis.impact_score}`;
            impactBadge.textContent = analysis.impact_score;
        }

        // Update tags
        const tagsContainer = card.querySelector('.headline-tags');
        if (tagsContainer) {
            tagsContainer.innerHTML = '';
            if (analysis.tickers) {
                analysis.tickers.forEach(t => {
                    const tag = document.createElement('span');
                    tag.className = 'tag ticker';
                    tag.textContent = t;
                    tagsContainer.appendChild(tag);
                });
            }
            if (analysis.categories) {
                analysis.categories.forEach(c => {
                    const tag = document.createElement('span');
                    tag.className = 'tag category';
                    tag.textContent = c;
                    tagsContainer.appendChild(tag);
                });
            }
        }

        // Update summary
        if (analysis.summary) {
            let summaryEl = card.querySelector('.headline-summary');
            if (!summaryEl) {
                summaryEl = document.createElement('div');
                summaryEl.className = 'headline-summary';
                card.appendChild(summaryEl);
            }
            summaryEl.textContent = analysis.summary;
        }
    }

    createCard(h) {
        const card = document.createElement('div');
        card.className = 'headline-card';
        card.dataset.id = h.id;
        card.dataset.categories = JSON.stringify(h.categories || []);
        card.dataset.tickers = JSON.stringify(h.tickers || []);
        card.dataset.sourceCategory = h.source_category || '';
        card.dataset.sentiment = h.sentiment || '';
        card.dataset.impact = h.impact_score || 0;

        // Sentiment border
        if (h.sentiment === 'bullish') card.classList.add('bullish');
        else if (h.sentiment === 'bearish') card.classList.add('bearish');
        else if (h.is_analyzed) card.classList.add('neutral-analyzed');

        // Meta line
        const meta = document.createElement('div');
        meta.className = 'headline-meta';

        const time = document.createElement('span');
        time.className = 'headline-time';
        time.textContent = this.formatTime(h.ingested_at || h.published_at);
        meta.appendChild(time);

        const sep1 = document.createElement('span');
        sep1.textContent = '|';
        meta.appendChild(sep1);

        const source = document.createElement('span');
        source.className = 'headline-source';
        source.textContent = this.formatSource(h.source);
        meta.appendChild(source);

        if (h.sentiment) {
            const sep2 = document.createElement('span');
            sep2.textContent = '|';
            meta.appendChild(sep2);

            const sent = document.createElement('span');
            sent.className = `headline-sentiment ${h.sentiment}`;
            sent.textContent = h.sentiment.toUpperCase();
            meta.appendChild(sent);
        }

        if (h.impact_score) {
            const impact = document.createElement('span');
            impact.className = `impact-badge impact-${h.impact_score}`;
            impact.textContent = h.impact_score;
            meta.appendChild(impact);
        }

        card.appendChild(meta);

        // Title
        const title = document.createElement('div');
        title.className = 'headline-title';
        if (h.url) {
            const link = document.createElement('a');
            link.href = h.url;
            link.target = '_blank';
            link.rel = 'noopener';
            link.textContent = h.title;
            title.appendChild(link);
        } else {
            title.textContent = h.title;
        }
        card.appendChild(title);

        // Tags
        const tags = document.createElement('div');
        tags.className = 'headline-tags';
        if (h.tickers && h.tickers.length > 0) {
            h.tickers.forEach(t => {
                const tag = document.createElement('span');
                tag.className = 'tag ticker';
                tag.textContent = t;
                tags.appendChild(tag);
            });
        }
        if (h.categories && h.categories.length > 0) {
            h.categories.forEach(c => {
                const tag = document.createElement('span');
                tag.className = 'tag category';
                tag.textContent = c;
                tags.appendChild(tag);
            });
        }
        card.appendChild(tags);

        // Analysis summary
        if (h.analysis_summary) {
            const summary = document.createElement('div');
            summary.className = 'headline-summary';
            summary.textContent = h.analysis_summary;
            card.appendChild(summary);
        }

        return card;
    }

    formatTime(isoString) {
        if (!isoString) return '--:--';
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
        });
    }

    formatSource(source) {
        if (!source) return 'Unknown';
        // Clean up source names
        return source
            .replace(/_/g, ' ')
            .replace(/^twitter /, '@')
            .replace(/^rss /, '')
            .split(' ')
            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
            .join(' ');
    }
}
