// Initialize FullCalendar when page loads
document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');

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
            fetch(`/api/plugins/vendor-notification/maintenance/?${params}`)
                .then(response => response.json())
                .then(data => {
                    // Transform NetBox API response to FullCalendar event format
                    const events = data.results.map(event => ({
                        id: event.id,
                        title: `${event.name} - ${event.provider.display} (${event.impact_count} Impacted)`,
                        start: event.start,
                        end: event.end,
                        backgroundColor: `var(--tblr-${event.status_color})`,  // Use Tabler CSS variables
                        borderColor: `var(--tblr-${event.status_color})`,
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

        // Click handler - opens modal instead of navigating
        eventClick: function(info) {
            info.jsEvent.preventDefault(); // Don't follow URL
            showEventModal(info.event);
        },

        // Display multi-day events properly
        displayEventTime: true,
        displayEventEnd: true
    });

    calendar.render();
});

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
        `/plugins/vendor-notification/maintenance/${event.extendedProps.eventId}/`;

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

// Add event listeners for modal close buttons and backdrop
document.addEventListener('DOMContentLoaded', function() {
    // Close button handlers
    document.querySelectorAll('[data-bs-dismiss="modal"]').forEach(function(btn) {
        btn.addEventListener('click', closeEventModal);
    });
});

// Close modal when clicking backdrop
document.addEventListener('click', function(e) {
    if (e.target && e.target.id === 'eventModalBackdrop') {
        closeEventModal();
    }
});
