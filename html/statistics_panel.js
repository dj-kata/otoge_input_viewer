(function () {
    const configurations = {
        release: { max: 100 },
        density: { max: 50 }
    };

    function bandColor(kind, value) {
        if (kind === 'release') {
            if (value <= 40) return '#4ddf8b';
            if (value <= 60) return '#e6d94f';
            if (value <= 80) return '#ffad42';
            return '#ff5b64';
        }
        if (value <= 20) return '#4ddf8b';
        if (value <= 30) return '#cddd4d';
        if (value < 40) return '#ffad42';
        return '#ff5b64';
    }

    function panelMarkup() {
        const row = (kind, unit) => `
            <div class="statistics-row statistics-${kind}">
                <span class="statistics-meter" data-statistics-meter="${kind}" aria-hidden="true"></span>
                <span class="statistics-value" data-statistics-value="${kind}">--</span>
                <span class="statistics-unit">${unit}</span>
            </div>`;
        return `
            <div class="statistics-left">
                ${row('release', 'ms')}
                ${row('density', 'n/s')}
            </div>
            <div class="statistics-notes">
                <span class="statistics-notes-value" data-statistics-value="notes">0</span>
            </div>`;
    }

    function initializePanel(panel) {
        panel.innerHTML = panelMarkup();
        panel.querySelectorAll('[data-statistics-meter]').forEach(meter => {
            for (let index = 0; index < 20; index += 1) {
                const segment = document.createElement('span');
                segment.className = 'statistics-segment';
                meter.appendChild(segment);
            }
        });
        fitNotesValue(panel.querySelector('[data-statistics-value="notes"]'));
    }

    function fitNotesValue(element) {
        if (!element) return;
        const container = element.parentElement;
        const maximumSize = Math.min(72, container.clientHeight * 0.82);
        const availableWidth = Math.max(1, container.clientWidth - 8);
        element.style.fontSize = `${maximumSize}px`;
        const measurement = element.cloneNode(true);
        measurement.style.position = 'fixed';
        measurement.style.visibility = 'hidden';
        measurement.style.width = 'max-content';
        measurement.style.maxWidth = 'none';
        measurement.style.overflow = 'visible';
        document.body.appendChild(measurement);
        const textWidth = measurement.getBoundingClientRect().width;
        measurement.remove();
        if (textWidth > availableWidth) {
            const fittedSize = maximumSize * availableWidth / textWidth * 0.98;
            element.style.fontSize = `${Math.max(24, fittedSize)}px`;
        }
    }

    function updateMeter(kind, rawValue) {
        const value = Number(rawValue);
        if (!Number.isFinite(value)) return;
        const configuration = configurations[kind];
        const activeCount = value > 0
            ? Math.min(20, Math.ceil(value / configuration.max * 20))
            : 0;
        document.querySelectorAll(`[data-statistics-meter="${kind}"]`).forEach(meter => {
            Array.from(meter.children).forEach((segment, index) => {
                if (index < activeCount) {
                    const segmentValue = (index + 1) * configuration.max / 20;
                    const color = bandColor(kind, segmentValue);
                    segment.style.backgroundColor = color;
                    segment.style.boxShadow = `0 0 2px ${color}66`;
                } else {
                    segment.style.backgroundColor = 'rgba(110, 125, 154, 0.14)';
                    segment.style.boxShadow = 'none';
                }
            });
        });
        const color = bandColor(kind, value);
        document.querySelectorAll(`[data-statistics-value="${kind}"]`).forEach(element => {
            element.style.color = color;
        });
    }

    window.updateStatisticsPanel = function (kind, rawValue) {
        if (window.statisticsPreviewMode) return;
        const text = String(rawValue);
        document.querySelectorAll(`[data-statistics-value="${kind}"]`).forEach(element => {
            element.textContent = text;
            if (kind === 'notes') fitNotesValue(element);
        });
        if (configurations[kind]) updateMeter(kind, rawValue);
    };

    function initializeKeyPreview() {
        const style = getComputedStyle(document.documentElement);
        const thresholdLow = Number(style.getPropertyValue('--threshold-release-low'));
        const thresholdHigh = Number(style.getPropertyValue('--threshold-release-high'));
        const values = [58, 72, 91, 63, 78, 86, 61, 55, 69, 84, 47, 76, 93, 64];

        values.forEach((value, index) => {
            const button = document.getElementById(`btn${index + 1}`);
            if (!button) return;

            let band = 'low';
            if (value > thresholdHigh) {
                band = 'high';
            } else if (value > thresholdLow) {
                band = 'mid';
            }
            button.textContent = value;
            button.style.setProperty(
                'outline', style.getPropertyValue(`--outline-release-${band}`).trim()
            );
            button.style.setProperty(
                'color', style.getPropertyValue(`--color-release-eachkey-${band}`).trim()
            );
        });
    }

    function initialize() {
        document.querySelectorAll('[data-statistics-panel]').forEach(initializePanel);
        const parameters = new URLSearchParams(window.location.search);
        const mode = parameters.get('stats-view');
        document.documentElement.classList.toggle('stats-view-graph', mode === 'graph');
        if (parameters.get('preview') === '1') {
            document.documentElement.classList.add('statistics-preview');
            document.querySelectorAll('warning').forEach(element => {
                element.textContent = '';
            });
            window.updateStatisticsPanel(
                'release', parameters.get('preview-release') || 57.3
            );
            window.updateStatisticsPanel(
                'density', parameters.get('preview-density') || 24.8
            );
            window.updateStatisticsPanel(
                'notes', parameters.get('preview-notes') || 1234567
            );
            initializeKeyPreview();
            window.statisticsPreviewMode = true;
        }
    }

    initialize();
    window.addEventListener('resize', () => {
        document.querySelectorAll('[data-statistics-value="notes"]').forEach(fitNotesValue);
    });
}());
