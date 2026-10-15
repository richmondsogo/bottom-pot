const queryForm = document.querySelector('#queryForm');
const processingScreen = document.querySelector('#processingScreen');
const deliveryScreen = document.querySelector('#deliveryScreen');
const errorScreen = document.querySelector('#errorScreen');
const liveConsole = document.querySelector('#liveConsole');
const resultsBody = document.querySelector('#resultsBody');
const extractionSummary = document.querySelector('#extractionSummary');
const metrics = document.querySelector('#metrics');
const emptyState = document.querySelector('#emptyState');
const downloadButton = document.querySelector('#downloadBtn');
const downloadJsonButton = document.querySelector('#downloadJsonBtn');
const abortButton = document.querySelector('#cancelBtn');
const tableSearch = document.querySelector('#tableSearch');
const providerFilter = document.querySelector('#providerFilter');
const remoteFilter = document.querySelector('#remoteFilter');
const employmentFilter = document.querySelector('#employmentFilter');
const clearFiltersButton = document.querySelector('#clearFiltersBtn');
const filterSummary = document.querySelector('#filterSummary');
let activeRequest = null;
let currentResults = [];
let expandedJobId = null;

/** Format backend-normalized fields; only snippet records receive a last-resort label parse. */
function normalizeJob(job) {
    if (job.data_source !== 'snippet') {
        return {
            ...job,
            displayTitle: job.title || 'Untitled role',
            displayLocation: job.location || 'Unknown',
            displaySalary: formatSalary(job.salary),
            displayEmployment: formatJobType(job.employment_type),
            displayLocationType: formatWorkModel(job.work_model),
            displayPostedDate: formatPostedDate(job.posted_at),
        };
    }
    const rawTitle = job.title || 'Untitled role';
    const labels = ['Location', 'Employment Type', 'Job Type', 'Location Type'];
    const labelPattern = new RegExp(`(?:${labels.join('|')})\\s*[.:]\\s*`, 'gi');
    const matches = [...rawTitle.matchAll(labelPattern)];
    const details = {};

    matches.forEach((match, index) => {
        const lowerLabel = match[0].toLowerCase();
        const label = lowerLabel.startsWith('employment') || lowerLabel.startsWith('job type') ? 'employmentType' : lowerLabel.startsWith('location type') ? 'locationType' : 'location';
        const nextStart = matches[index + 1]?.index ?? rawTitle.length;
        details[label] = rawTitle.slice(match.index + match[0].length, nextStart).replace(/\.{3,}$/, '').trim();
    });

    const title = matches.length ? rawTitle.slice(0, matches[0].index).replace(/[.\s]+$/, '').trim() : rawTitle;
    const location = job.location || details.location || 'Unknown';
    const rawWorkModel = job.work_model || details.locationType || '';
    const workModelText = `${rawWorkModel} ${location} ${rawTitle}`.toLowerCase();
    const workModel = job.is_remote === true || /remote|work from home/.test(workModelText) ? 'Remote' : /hybrid/.test(workModelText) ? 'Hybrid' : job.is_remote === false || /in.?person|on.?site|onsite|office/.test(workModelText) ? 'In-person' : 'Unknown';
    const rawJobType = job.employment_type || details.employmentType || '';
    const jobTypeText = rawJobType.toLowerCase().replace(/[- ]/g, '_');
    const jobType = /intern/.test(jobTypeText) ? 'Internship' : /part/.test(jobTypeText) ? 'Part time' : /contract/.test(jobTypeText) ? 'Contract' : /full/.test(jobTypeText) ? 'Full time' : 'Unknown';
    const postedDate = formatPostedDate(job.posted_at);
    return { ...job, displayTitle: title || rawTitle, displayLocation: location, displaySalary: formatSalary(job.salary), displayEmployment: jobType, displayLocationType: workModel, displayPostedDate: postedDate };
}

function formatJobType(value) {
    return ({ full_time: 'Full time', part_time: 'Part time', internship: 'Internship', contract: 'Contract' })[value] || 'Unknown';
}

function formatWorkModel(value) {
    return ({ remote: 'Remote', hybrid: 'Hybrid', in_person: 'In-person' })[value] || 'Unknown';
}

function formatPostedDate(value) {
    if (!value) return 'Date unavailable';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? 'Date unavailable' : date.toISOString().slice(0, 10);
}

function formatSalary(salary) {
    if (!salary) return 'Not listed';
    if (typeof salary === 'string') return salary.trim() || 'Not listed';
    const currency = salary.currency ? `${salary.currency} ` : '';
    const period = salary.period ? ` / ${salary.period}` : '';
    if (salary.minimum != null && salary.maximum != null) {
        return `${currency}${Number(salary.minimum).toLocaleString()}-${Number(salary.maximum).toLocaleString()}${period}`;
    }
    if (salary.minimum != null) return `${currency}${Number(salary.minimum).toLocaleString()}+${period}`;
    if (salary.maximum != null) return `Up to ${currency}${Number(salary.maximum).toLocaleString()}${period}`;
    return 'Not listed';
}

function normalizedResults() {
    return currentResults.map(normalizeJob);
}

function filteredResults() {
    const searchTerm = tableSearch.value.trim().toLowerCase();
    return normalizedResults().filter((job) => {
        const searchable = [job.displayTitle, job.company, job.displayLocation, job.displaySalary, job.displayEmployment, job.displayLocationType, job.displayPostedDate, job.provider].join(' ').toLowerCase();
        const matchesSearch = !searchTerm || searchable.includes(searchTerm);
        const matchesProvider = !providerFilter.value || job.provider === providerFilter.value;
        const matchesRemote = !remoteFilter.value || (remoteFilter.value === 'remote' ? job.displayLocationType.toLowerCase().includes('remote') : !job.displayLocationType.toLowerCase().includes('remote'));
        const matchesEmployment = !employmentFilter.value || job.displayEmployment === employmentFilter.value;
        return matchesSearch && matchesProvider && matchesRemote && matchesEmployment;
    });
}

function populateFilterOptions() {
    const providers = [...new Set(normalizedResults().map((job) => job.provider).filter(Boolean))].sort();
    const employmentTypes = [...new Set(normalizedResults().map((job) => job.displayEmployment).filter((value) => value && value !== 'Not specified'))].sort();
    providerFilter.replaceChildren(new Option('All providers', ''), ...providers.map((value) => new Option(value, value)));
    employmentFilter.replaceChildren(new Option('All types', ''), ...employmentTypes.map((value) => new Option(value, value)));
}

/** Convert a streamed JobListing into the columns used by the downloadable CSV. */
function csvValue(value) {
    const escaped = String(value ?? '').replaceAll('"', '""');
    return `"${escaped}"`;
}

function downloadCsv() {
    const header = ['Job title', 'Company', 'Location', 'Salary', 'Job type', 'Work model', 'Posted date', 'Provider', 'Apply URL'];
    const rows = filteredResults().map((job) => [job.displayTitle, job.company, job.displayLocation, job.displaySalary, job.displayEmployment, job.displayLocationType, job.displayPostedDate, job.provider, job.apply_url]);
    const csv = [header, ...rows].map((row) => row.map(csvValue).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${document.querySelector('#keywords').value.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'bottom-pot'}-results.csv`;
    link.click();
    URL.revokeObjectURL(url);
}

function downloadJson() {
    const json = JSON.stringify(filteredResults().map(({ displayTitle, displayLocation, displayEmployment, displayLocationType, displayPostedDate, ...job }) => job), null, 2);
    const url = URL.createObjectURL(new Blob([json], { type: 'application/json;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${document.querySelector('#keywords').value.toLowerCase().replace(/[^a-z0-9]+/g, '-') || 'bottom-pot'}-results.json`;
    link.click();
    URL.revokeObjectURL(url);
}

function renderResults() {
    resultsBody.replaceChildren();
    const visibleResults = filteredResults();
    emptyState.classList.toggle('hidden', visibleResults.length !== 0);
    filterSummary.textContent = currentResults.length === visibleResults.length ? `${currentResults.length} result${currentResults.length === 1 ? '' : 's'}` : `Showing ${visibleResults.length} of ${currentResults.length} results`;
    visibleResults.forEach((job) => {
        const row = document.createElement('tr');
        [job.displayTitle, job.company, job.displayLocation, job.displaySalary, job.displayEmployment, job.displayLocationType, job.displayPostedDate, job.provider].forEach((value) => {
            const cell = document.createElement('td');
            cell.textContent = value;
            row.appendChild(cell);
        });
        const actionCell = document.createElement('td');
        const detailsButton = document.createElement('button');
        detailsButton.className = 'text-button detail-toggle';
        detailsButton.type = 'button';
        detailsButton.textContent = expandedJobId === job.id ? 'Hide details' : 'Details';
        detailsButton.setAttribute('aria-expanded', expandedJobId === job.id ? 'true' : 'false');
        detailsButton.addEventListener('click', () => {
            expandedJobId = expandedJobId === job.id ? null : job.id;
            renderResults();
        });
        const link = document.createElement('a');
        link.href = job.apply_url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'Apply ->';
        actionCell.append(detailsButton, link);
        row.appendChild(actionCell);
        resultsBody.appendChild(row);
        if (expandedJobId === job.id) {
            resultsBody.appendChild(renderDetailRow(job));
        }
    });
}

function renderDetailRow(job) {
    const row = document.createElement('tr');
    row.className = 'detail-row';
    const cell = document.createElement('td');
    cell.colSpan = 9;
    const description = job.description || job.summary || 'No description was returned for this posting.';
    const requirements = job.requirements || 'Requirements unavailable.';
    cell.innerHTML = `
        <article class="job-detail" aria-label="${job.displayTitle} details">
            <div>
                <span>Role</span>
                <strong>${escapeHtml(job.displayTitle)}</strong>
            </div>
            <div>
                <span>Salary</span>
                <strong>${escapeHtml(job.displaySalary)}</strong>
            </div>
            <div>
                <span>Source</span>
                <strong>${escapeHtml(job.provider)} - ${escapeHtml(job.data_source)}</strong>
            </div>
            <p>${escapeHtml(description)}</p>
            <p>${escapeHtml(requirements)}</p>
            <a href="${escapeAttribute(job.source_url)}" target="_blank" rel="noopener">Open source posting</a>
        </article>
    `;
    row.appendChild(cell);
    return row;
}

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
}

function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, '&#96;');
}

function renderMetrics(done) {
    const items = [['Results', done.total], ['Search time', `${done.search_time_ms} ms`], ['Providers', done.providers_searched.length], ['Serper queries', done.serper_queries_used]];
    metrics.replaceChildren(...items.map(([label, value]) => {
        const element = document.createElement('div');
        element.className = 'metric';
        const valueElement = document.createElement('strong');
        valueElement.textContent = value;
        const labelElement = document.createElement('span');
        labelElement.textContent = label;
        element.append(valueElement, labelElement);
        return element;
    }));
}

function showError(message) {
    processingScreen.classList.add('hidden');
    queryForm.classList.remove('hidden');
    errorScreen.classList.remove('hidden');
    document.querySelector('#errorMessage').textContent = message;
}

function resetView() {
    activeRequest?.abort();
    activeRequest = null;
    currentResults = [];
    expandedJobId = null;
    tableSearch.value = '';
    providerFilter.replaceChildren(new Option('All providers', ''));
    employmentFilter.replaceChildren(new Option('All types', ''));
    remoteFilter.value = '';
    filterSummary.textContent = '';
    queryForm.reset();
    queryForm.classList.remove('hidden');
    processingScreen.classList.add('hidden');
    deliveryScreen.classList.add('hidden');
    errorScreen.classList.add('hidden');
}

/** Read FastAPI's named SSE events from a fetch response without buffering the search. */
async function streamSearch(url) {
    const response = await fetch(url, { signal: activeRequest.signal, headers: { Accept: 'text/event-stream' } });
    if (!response.ok || !response.body) throw new Error(`The search service returned HTTP ${response.status}.`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let eventName = '';
    let eventData = '';
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim();
            if (line.startsWith('data:')) eventData += line.slice(5).trim();
            if (line === '' && eventName && eventData) {
                const payload = JSON.parse(eventData);
                if (eventName === 'results') {
                    currentResults.push(...payload.batch);
                    liveConsole.textContent = `Received ${currentResults.length} result${currentResults.length === 1 ? '' : 's'}...`;
                    populateFilterOptions();
                    renderResults();
                } else if (eventName === 'done') {
                    renderMetrics(payload);
                    extractionSummary.textContent = payload.cached ? 'Loaded from the recent search cache.' : 'Fresh results compiled from the selected ATS platforms.';
                } else if (eventName === 'error') throw new Error(payload.message);
                eventName = '';
                eventData = '';
            }
        }
    }
}

queryForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    currentResults = [];
    queryForm.classList.add('hidden');
    errorScreen.classList.add('hidden');
    deliveryScreen.classList.add('hidden');
    processingScreen.classList.remove('hidden');
    activeRequest = new AbortController();
    const params = new URLSearchParams({ q: document.querySelector('#keywords').value.trim(), days_back: document.querySelector('#postAge').value, include_nigerian: document.querySelector('#includeNigerian').checked });
    const location = document.querySelector('#location').value.trim();
    const workModel = document.querySelector('#workModel').value;
    if (location) params.set('location', location);
    if (workModel !== 'any') params.set('remote', workModel === 'remote');
    if (document.querySelector('#deepScrape').checked) params.set('deep_scrape', 'true');
    try {
        await streamSearch(`/search?${params}`);
        populateFilterOptions();
        processingScreen.classList.add('hidden');
        deliveryScreen.classList.remove('hidden');
        renderResults();
    } catch (error) {
        if (error.name !== 'AbortError') showError(error.message);
    } finally {
        activeRequest = null;
    }
});

abortButton.addEventListener('click', resetView);
document.querySelector('#resetBtn').addEventListener('click', resetView);
document.querySelector('#errorResetBtn').addEventListener('click', resetView);
downloadButton.addEventListener('click', downloadCsv);
downloadJsonButton.addEventListener('click', downloadJson);
[tableSearch, providerFilter, remoteFilter, employmentFilter].forEach((control) => control.addEventListener('input', renderResults));
clearFiltersButton.addEventListener('click', () => {
    tableSearch.value = '';
    providerFilter.value = '';
    remoteFilter.value = '';
    employmentFilter.value = '';
    renderResults();
});
