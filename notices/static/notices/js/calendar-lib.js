// Pure helpers for the maintenance calendar: no DOM access, so they can be unit
// tested under Node (tests/js/). Exposed as window.NoticesCalendar in the browser.
(function (root, factory) {
    if (typeof module === 'object' && module.exports) {
        module.exports = factory();
    } else {
        root.NoticesCalendar = factory();
    }
})(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    // Maintenances longer than this are drawn as bands. Fixed on purpose: it is
    // independent of the "hide longer than" threshold.
    const LONG_THRESHOLD_MS = 24 * 3600 * 1000;
    const DAY_MS = 24 * 3600 * 1000;
    // Same cap as the server's MAX_DURATION_FILTER_HOURS (notices/constants.py).
    const MAX_HOURS = 100000;

    function isLong(start, end) {
        return end - start > LONG_THRESHOLD_MS;
    }

    function localMidnight(date) {
        return new Date(date.getFullYear(), date.getMonth(), date.getDate());
    }

    // Rounding absorbs the 23h and 25h days around DST changes.
    function dayIndex(date, rowStart) {
        return Math.round((localMidnight(date) - rowStart) / DAY_MS);
    }

    // Columns are local calendar days. The end is exclusive, so an event ending at
    // exactly local midnight stops on the previous day; a zero-length event still
    // occupies its start day.
    function segmentForRow(start, end, rowStart, nDays) {
        const first = dayIndex(start, rowStart);
        let last = dayIndex(end, rowStart);
        if (end > start && end.getTime() === localMidnight(end).getTime()) {
            last -= 1;
        }
        if (last < 0 || first > nDays - 1) {
            return null;
        }
        return {
            startCol: Math.max(first, 0),
            endCol: Math.min(last, nDays - 1),
            startsHere: first >= 0,
            endsHere: last <= nDays - 1,
        };
    }

    // Packs one week row into lanes of one event height. A band takes two lanes:
    // its top lane is a slot one short event may sit in, its bottom lane holds the
    // label and is never given to anything else. Input order breaks ties.
    function layoutRow(segs) {
        const bandRows = []; // bandRows[k] = list of [startCol, endCol] already placed
        const labelBlocked = new Set(); // "lane:col"
        const shortTaken = new Set(); // "lane:col"
        const laneOf = new Map();
        let maxLane = -1;

        const overlaps = (a, b) => a.startCol <= b[1] && b[0] <= a.endCol;

        for (const seg of segs) {
            if (!seg.long) continue;
            let k = 0;
            while (bandRows[k] && bandRows[k].some((span) => overlaps(seg, span))) k++;
            (bandRows[k] = bandRows[k] || []).push([seg.startCol, seg.endCol]);
            for (let col = seg.startCol; col <= seg.endCol; col++) labelBlocked.add(`${2 * k + 1}:${col}`);
            laneOf.set(seg.id, 2 * k);
            maxLane = Math.max(maxLane, 2 * k + 1);
        }

        for (const seg of segs) {
            if (seg.long) continue;
            const free = (lane) => {
                for (let col = seg.startCol; col <= seg.endCol; col++) {
                    const key = `${lane}:${col}`;
                    if (labelBlocked.has(key) || shortTaken.has(key)) return false;
                }
                return true;
            };
            let lane = 0;
            while (!free(lane)) lane++;
            for (let col = seg.startCol; col <= seg.endCol; col++) shortTaken.add(`${lane}:${col}`);
            laneOf.set(seg.id, lane);
            maxLane = Math.max(maxLane, lane);
        }

        return {
            placements: segs.map((seg) => ({ id: seg.id, lane: laneOf.get(seg.id) })),
            laneCount: maxLane + 1,
        };
    }

    // Segments of FullCalendar events ({id, start, end}) that touch one row, with
    // the long flag. FullCalendar reports a zero-length event's end as null; such
    // an event is treated as ending when it starts.
    function segmentsForRow(events, rowStart, nDays) {
        const segs = [];
        for (const event of events) {
            const end = event.end || event.start;
            const seg = segmentForRow(event.start, end, rowStart, nDays);
            if (seg) {
                segs.push({ ...seg, id: event.id, long: isLong(event.start, end), event });
            }
        }
        return segs;
    }

    // A positive number of hours up to MAX_HOURS, or null.
    function parseHours(value) {
        if (value === null || value === undefined || String(value).trim() === '') return null;
        const hours = Number(value);
        return Number.isFinite(hours) && hours > 0 && hours <= MAX_HOURS ? hours : null;
    }

    return { LONG_THRESHOLD_MS, MAX_HOURS, isLong, segmentForRow, segmentsForRow, layoutRow, parseHours };
});
