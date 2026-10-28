// Initialize FullCalendar when page loads.
//
// FullCalendar provides the grid, toolbar, navigation and data loading. Events are
// loaded with display 'none' and drawn by renderEventLayer() instead, because the
// long-maintenance bands need a layout FullCalendar's own row stacking cannot do:
// short events sit in a band's top half while its label half stays visible.
document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');
    const scheduleRender = () => requestAnimationFrame(() => renderEventLayer(calendar));

    const calendar = new FullCalendar.Calendar(calendarEl, {
        // Basic settings
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,dayGridWeek'
        },

        // Height configuration - use contentHeight to prevent excessive height
        contentHeight: 800,

        // Event data source - use function to properly handle FullCalendar v6 API
        events: function(fetchInfo, successCallback, failureCallback) {
            // Build query parameters for NetBox API
            const params = new URLSearchParams({
                // Use NetBox's built-in operators for date range filtering
                end__gte: fetchInfo.startStr.split('T')[0],    // Events ending on or after range start
                start__lte: fetchInfo.endStr.split('T')[0],    // Events starting on or before range end
                limit: 0  // No pagination, get all events in range
            });

            // Fetch events from NetBox API
            fetch(`/api/plugins/notices/maintenance/?${params}`)
                .then(response => response.json())
                .then(data => {
                    // Transform NetBox API response to FullCalendar event format
                    const events = data.results.map(event => ({
                        id: event.id,
                        title: `${event.name} - ${event.provider.display} (${event.impact_count} Impacted)`,
                        start: event.start,
                        end: event.end,
                        display: 'none',  // drawn by renderEventLayer()
                        extendedProps: {
                            status: event.status,
                            statusColor: event.status_color,
                            provider: event.provider.display,
                            summary: event.summary,
                            comments: event.comments,
                            eventId: event.id
                        }
                    }));
                    successCallback(events);
                })
                .catch(error => {
                    console.error('Error fetching maintenance events:', error);
                    failureCallback(error);
                });
        },

        eventsSet: scheduleRender,
        datesSet: scheduleRender,
    });

    calendar.render();

    // Positions are fractions of the row width, but heights and tops are measured;
    // redraw when the calendar's width changes (window resize, sidebar toggle).
    let lastWidth = calendarEl.offsetWidth;
    new ResizeObserver(() => {
        if (calendarEl.offsetWidth !== lastWidth) {
            lastWidth = calendarEl.offsetWidth;
            scheduleRender();
        }
    }).observe(calendarEl);
});

const SHORT_GUTTER_PX = 2;
const SHORT_INSET_PX = 5;  // band edge (3px) + gutter

// Draw every event of the current day-grid view as an absolutely positioned layer,
// one per week row, using the lane layout from calendar-lib.js.
function renderEventLayer(calendar) {
    const lib = window.NoticesCalendar;
    const calendarEl = calendar.el;
    const body = calendarEl.querySelector('.fc-daygrid-body');
    if (!body) {
        return;
    }
    const lanePx = parseFloat(getComputedStyle(calendarEl).getPropertyValue('--notices-lane')) || 22;

    body.querySelectorAll('.notices-layer').forEach(el => el.remove());
    body.style.position = 'relative';

    const events = calendar.getEvents()
        .filter(event => event.start && event.end)
        .sort((a, b) => (a.start - b.start) || ((b.end - b.start) - (a.end - a.start)) || (a.id - b.id));

    // Pass 1: lay out each row and reserve its height, so rows below settle first.
    const rows = [];
    body.querySelectorAll('tr').forEach(tr => {
        const cells = tr.querySelectorAll('td.fc-daygrid-day');
        if (!cells.length) {
            return;
        }
        const [y, m, d] = cells[0].dataset.date.split('-').map(Number);
        const rowStart = new Date(y, m - 1, d);
        const segs = [];
        for (const event of events) {
            const seg = lib.segmentForRow(event.start, event.end, rowStart, cells.length);
            if (seg) {
                segs.push({ ...seg, id: event.id, long: lib.isLong(event.start, event.end), event });
            }
        }
        const layout = lib.layoutRow(segs);
        cells.forEach(cell => {
            cell.querySelector('.fc-daygrid-day-events').style.minHeight = `${layout.laneCount * lanePx}px`;
        });
        rows.push({ cells, segs, layout });
    });

    // Pass 2: measure where each row's event area starts and draw into it.
    const bodyTop = body.getBoundingClientRect().top;
    for (const { cells, segs, layout } of rows) {
        const eventsTop = cells[0].querySelector('.fc-daygrid-day-events').getBoundingClientRect().top;
        const layer = document.createElement('div');
        layer.className = 'notices-layer';
        layer.style.top = `${eventsTop - bodyTop}px`;

        const laneById = new Map(layout.placements.map(p => [p.id, p.lane]));
        const bandStarts = new Set(
            segs.filter(seg => seg.long && seg.startsHere).map(seg => `${laneById.get(seg.id)}:${seg.startCol}`)
        );
        for (const seg of segs) {
            const lane = laneById.get(seg.id);
            const left = (seg.startCol / cells.length) * 100;
            const width = ((seg.endCol - seg.startCol + 1) / cells.length) * 100;
            let el;
            if (seg.long) {
                el = buildBand(seg);
                el.style.left = `${left}%`;
                el.style.width = `${width}%`;
            } else {
                // Gutters inside the columns; wider on the left when the short sits
                // in a band's slot on the band's first day, to keep its edge visible.
                const inset = bandStarts.has(`${lane}:${seg.startCol}`) ? SHORT_INSET_PX : SHORT_GUTTER_PX;
                el = buildShort(seg);
                el.style.left = `calc(${left}% + ${inset}px)`;
                el.style.width = `calc(${width}% - ${inset + SHORT_GUTTER_PX}px)`;
            }
            el.style.top = `${lane * lanePx}px`;
            layer.appendChild(el);
        }
        body.appendChild(layer);
    }
}

function buildEventElement(seg, className) {
    const event = seg.event;
    const el = document.createElement('a');
    el.className = className;
    el.href = `/plugins/notices/maintenance/${event.extendedProps.eventId}/`;
    el.title = `${event.title}\n${event.start.toLocaleString()} - ${event.end.toLocaleString()}`;
    el.style.setProperty('--notices-c', `var(--tblr-${event.extendedProps.statusColor})`);
    el.addEventListener('click', e => {
        e.preventDefault();
        showEventModal(event);
    });
    return el;
}

function buildBand(seg) {
    let className = 'notices-band';
    if (seg.startsHere) className += ' notices-band--start';
    if (seg.endsHere) className += ' notices-band--end';
    const el = buildEventElement(seg, className);
    const label = document.createElement('span');
    label.className = 'notices-band-label';
    label.textContent = seg.event.title;
    el.appendChild(label);
    return el;
}

function buildShort(seg) {
    const el = buildEventElement(seg, 'fc-event fc-h-event fc-daygrid-event fc-daygrid-block-event notices-short');
    const event = seg.event;
    const time = event.start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    el.textContent = seg.startsHere ? `${time} ${event.title}` : event.title;
    return el;
}

// Show event details in modal
function showEventModal(event) {
    // Populate modal fields
    document.getElementById('eventModalTitle').textContent = event.title;
    document.getElementById('eventModalProvider').textContent = event.extendedProps.provider;
    document.getElementById('eventModalSummary').textContent = event.extendedProps.summary;

    // Format dates
    document.getElementById('eventModalStart').textContent =
        new Date(event.start).toLocaleString();
    document.getElementById('eventModalEnd').textContent =
        new Date(event.end).toLocaleString();

    // Status badge with color from backend (using NetBox/Bootstrap 5.2 text-bg class)
    const statusBadge = document.getElementById('eventModalStatus');
    statusBadge.textContent = event.extendedProps.status;
    statusBadge.className = `badge text-bg-${event.extendedProps.statusColor}`;

    // Comments (optional field)
    const commentsRow = document.getElementById('eventModalCommentsRow');
    if (event.extendedProps.comments) {
        document.getElementById('eventModalComments').textContent = event.extendedProps.comments;
        commentsRow.style.display = 'flex';
    } else {
        commentsRow.style.display = 'none';
    }

    // Link to full detail page (UI, not API)
    document.getElementById('eventModalViewLink').href =
        `/plugins/notices/maintenance/${event.extendedProps.eventId}/`;

    // Show modal manually (Bootstrap 5 compatible)
    const modalEl = document.getElementById('eventModal');
    modalEl.classList.add('show');
    modalEl.style.display = 'block';
    document.body.classList.add('modal-open');

    // Create backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop fade show';
    backdrop.id = 'eventModalBackdrop';
    document.body.appendChild(backdrop);
}

// Close modal function
function closeEventModal() {
    const modalEl = document.getElementById('eventModal');
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
    document.body.classList.remove('modal-open');

    // Remove backdrop
    const backdrop = document.getElementById('eventModalBackdrop');
    if (backdrop) {
        backdrop.remove();
    }
}

// Close subscribe modal function
function closeSubscribeModal() {
    const modalEl = document.getElementById('icalSubscribeModal');
    modalEl.classList.remove('show');
    modalEl.style.display = 'none';
    document.body.classList.remove('modal-open');

    // Remove backdrop
    const backdrop = document.getElementById('icalSubscribeModalBackdrop');
    if (backdrop) {
        backdrop.remove();
    }
}

// Add event listeners for modal close buttons and backdrop
document.addEventListener('DOMContentLoaded', function() {
    // Close button handlers - detect which modal and call appropriate close function
    document.querySelectorAll('[data-bs-dismiss="modal"]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            // Find which modal this button belongs to
            const modal = btn.closest('.modal');
            if (modal && modal.id === 'eventModal') {
                closeEventModal();
            } else if (modal && modal.id === 'icalSubscribeModal') {
                closeSubscribeModal();
            }
        });
    });
});

// Close modal when clicking backdrop
document.addEventListener('click', function(e) {
    if (e.target && e.target.id === 'eventModalBackdrop') {
        closeEventModal();
    } else if (e.target && e.target.id === 'icalSubscribeModalBackdrop') {
        closeSubscribeModal();
    }
});

// iCal Subscribe and Download button handlers
document.addEventListener('DOMContentLoaded', function() {
    // Subscribe button - shows modal with subscription URL
    const subscribeBtn = document.getElementById('icalSubscribeBtn');
    if (subscribeBtn) {
        subscribeBtn.addEventListener('click', function() {
            // Generate the iCal feed URL with token placeholder
            const baseUrl = window.location.origin;
            const icalPath = '/plugins/notices/ical/maintenances.ics';
            const tokenPlaceholder = window.ICAL_TOKEN_PLACEHOLDER || 'changeme';
            const subscribeUrl = `${baseUrl}${icalPath}?token=${tokenPlaceholder}`;

            // Populate the modal input field
            document.getElementById('icalSubscribeUrl').value = subscribeUrl;

            // Show the subscribe modal manually
            const modalEl = document.getElementById('icalSubscribeModal');
            modalEl.classList.add('show');
            modalEl.style.display = 'block';
            document.body.classList.add('modal-open');

            // Create backdrop
            const backdrop = document.createElement('div');
            backdrop.className = 'modal-backdrop fade show';
            backdrop.id = 'icalSubscribeModalBackdrop';
            document.body.appendChild(backdrop);
        });
    }

    // Copy URL button in subscribe modal
    const copyBtn = document.getElementById('copyUrlBtn');
    if (copyBtn) {
        copyBtn.addEventListener('click', function() {
            const urlInput = document.getElementById('icalSubscribeUrl');
            const url = urlInput.value;

            // Copy to clipboard using modern API
            navigator.clipboard.writeText(url).then(function() {
                // Visual feedback - change button text temporarily
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="mdi mdi-check"></i> Copied!';
                copyBtn.classList.remove('btn-outline-secondary');
                copyBtn.classList.add('btn-success');

                // Reset after 2 seconds
                setTimeout(function() {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.classList.remove('btn-success');
                    copyBtn.classList.add('btn-outline-secondary');
                }, 2000);
            }).catch(function(err) {
                console.error('Failed to copy URL:', err);
                // Fallback - select the text
                urlInput.select();
            });
        });
    }

    // Download button - triggers one-time download
    const downloadBtn = document.getElementById('icalDownloadBtn');
    if (downloadBtn) {
        downloadBtn.addEventListener('click', function() {
            // Generate download URL with download=true parameter
            const icalPath = '/plugins/notices/ical/maintenances.ics';
            const downloadUrl = `${icalPath}?download=true`;

            // Navigate to download URL (will use session auth)
            window.location.href = downloadUrl;
        });
    }
});
