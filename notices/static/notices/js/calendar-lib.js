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
    const DAY_MS = 24 * 3600 * 1000;
    const LONG_THRESHOLD_MS = DAY_MS;

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

    const overlaps = (a, b) => a.startCol <= b.endCol && b.startCol <= a.endCol;

    // Packs one week row into lanes of one event height. A band is one lane tall
    // unless a short event sits on it in this row; then it is two: its top lane
    // is a slot holding that short, its bottom lane holds the label and is never
    // given to anything else. Input order breaks ties. Each placement gives the
    // event's top lane and its height in lanes.
    function layoutRow(segs) {
        // Start with every band that a short overlaps as 2x, then shrink the ones
        // whose slot stayed empty and pack again. Bands only shrink, so this
        // ends, and once it does every 2x band holds a short.
        let tall = new Set(
            segs.filter((band) => band.long && segs.some((seg) => !seg.long && overlaps(band, seg))).map((b) => b.id)
        );
        for (;;) {
            const { placements, laneCount, hosts } = packRow(segs, tall);
            if (hosts.size === tall.size) return { placements, laneCount };
            tall = hosts;
        }
    }

    // One packing pass with the given set of 2x bands. Bands go first, each in
    // the lowest lanes free on all its columns; then each short takes the lowest
    // lane that is free or a band's slot on all its columns. Returns the bands
    // whose slot a short took.
    function packRow(segs, tall) {
        const cells = new Map(); // "lane:col" -> 'band' | 'slot' | 'short'
        const fill = (seg, lane, kind) => {
            for (let col = seg.startCol; col <= seg.endCol; col++) cells.set(`${lane}:${col}`, kind);
        };
        const fits = (seg, lane, allowed) => {
            for (let col = seg.startCol; col <= seg.endCol; col++) {
                if (!allowed.includes(cells.get(`${lane}:${col}`))) return false;
            }
            return true;
        };
        const placed = new Map();
        const slots = []; // [lane, band] for each 2x band
        const hosts = new Set();
        let laneCount = 0;

        for (const band of segs.filter((seg) => seg.long)) {
            const lanes = tall.has(band.id) ? 2 : 1;
            let lane = 0;
            while (!fits(band, lane, [undefined]) || (lanes === 2 && !fits(band, lane + 1, [undefined]))) lane++;
            if (lanes === 2) {
                fill(band, lane, 'slot');
                fill(band, lane + 1, 'band');
                slots.push([lane, band]);
            } else {
                fill(band, lane, 'band');
            }
            placed.set(band.id, { lane, lanes });
            laneCount = Math.max(laneCount, lane + lanes);
        }

        for (const seg of segs.filter((seg) => !seg.long)) {
            let lane = 0;
            while (!fits(seg, lane, [undefined, 'slot'])) lane++;
            fill(seg, lane, 'short');
            for (const [slotLane, band] of slots) {
                if (slotLane === lane && overlaps(band, seg)) hosts.add(band.id);
            }
            placed.set(seg.id, { lane, lanes: 1 });
            laneCount = Math.max(laneCount, lane + 1);
        }

        const placements = segs.map((seg) => ({ id: seg.id, ...placed.get(seg.id) }));
        return { placements, laneCount, hosts };
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

    // A positive number of hours up to maxHours, or null.
    function parseHours(value, maxHours) {
        if (value === null || value === undefined || String(value).trim() === '') return null;
        const hours = Number(value);
        return Number.isFinite(hours) && hours > 0 && hours <= maxHours ? hours : null;
    }

    return { LONG_THRESHOLD_MS, isLong, segmentForRow, segmentsForRow, layoutRow, parseHours };
});
