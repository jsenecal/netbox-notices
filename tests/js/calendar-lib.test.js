// Unit tests for notices/static/notices/js/calendar-lib.js.
// Run with: npm test  (vitest.config.mjs pins TZ=America/Toronto)
import { expect, test } from 'vitest';

import calendarLib from '../../notices/static/notices/js/calendar-lib.js';

const { LONG_THRESHOLD_MS, isLong, segmentForRow, layoutRow, parseHours, segmentsForRow } = calendarLib;

// Local-time date; month is 1-based here to keep the cases readable.
function d(y, m, day, h = 0, min = 0) {
    return new Date(y, m - 1, day, h, min);
}

test('LONG_THRESHOLD_MS is 24 hours', () => {
    expect(LONG_THRESHOLD_MS).toBe(24 * 3600 * 1000);
});

test('isLong is strict at 24h', () => {
    expect(isLong(d(2026, 10, 5), d(2026, 10, 6))).toBe(false);
    expect(isLong(d(2026, 10, 5), d(2026, 10, 6, 0, 1))).toBe(true);
});

test('segmentForRow: end at local midnight does not touch the next day', () => {
    // Row starts Mon 2026-10-05; event Tue 09:00 -> Thu 00:00 covers Tue and Wed.
    expect(segmentForRow(d(2026, 10, 6, 9), d(2026, 10, 8), d(2026, 10, 5), 7)).toEqual({
        startCol: 1,
        endCol: 2,
        startsHere: true,
        endsHere: true,
    });
});

test('segmentForRow: zero-length event occupies its start day', () => {
    expect(segmentForRow(d(2026, 10, 6, 9), d(2026, 10, 6, 9), d(2026, 10, 5), 7)).toEqual({
        startCol: 1,
        endCol: 1,
        startsHere: true,
        endsHere: true,
    });
});

test('segmentForRow: event continuing into the next row has no end here', () => {
    const start = d(2026, 10, 8, 9);
    const end = d(2026, 10, 14, 18);
    expect(segmentForRow(start, end, d(2026, 10, 5), 7)).toEqual({
        startCol: 3,
        endCol: 6,
        startsHere: true,
        endsHere: false,
    });
    expect(segmentForRow(start, end, d(2026, 10, 12), 7)).toEqual({
        startCol: 0,
        endCol: 2,
        startsHere: false,
        endsHere: true,
    });
});

test('segmentForRow: events outside the row are null', () => {
    // Ends exactly at the row's first midnight: last day is the day before.
    expect(segmentForRow(d(2026, 10, 3, 10), d(2026, 10, 5), d(2026, 10, 5), 7)).toBe(null);
    // Starts after the row's last day.
    expect(segmentForRow(d(2026, 10, 12, 1), d(2026, 10, 12, 3), d(2026, 10, 5), 7)).toBe(null);
});

test('segmentForRow: DST changes map days to the right columns', () => {
    // Spring forward on Sun 2026-03-08 (America/Toronto): a 23h day inside the row.
    expect(segmentForRow(d(2026, 3, 9, 1), d(2026, 3, 9, 3), d(2026, 3, 2), 14).startCol).toBe(7);
    // Fall back on Sun 2026-11-01: a 25h day inside the row.
    expect(segmentForRow(d(2026, 11, 2, 1), d(2026, 11, 2, 3), d(2026, 10, 26), 14).startCol).toBe(7);
});

test('layoutRow: empty row', () => {
    expect(layoutRow([])).toEqual({ placements: [], laneCount: 0 });
});

test('layoutRow: one band plus three shorts on its first day', () => {
    const result = layoutRow([
        { id: 'B', startCol: 1, endCol: 4, long: true },
        { id: 'S1', startCol: 1, endCol: 1, long: false },
        { id: 'S2', startCol: 1, endCol: 1, long: false },
        { id: 'S3', startCol: 1, endCol: 1, long: false },
    ]);
    // S1 takes the band's slot, so the band is 2x; lane 1 is its label; S2 and S3 go below.
    expect(result).toEqual({
        placements: [
            { id: 'B', lane: 0, lanes: 2 },
            { id: 'S1', lane: 0, lanes: 1 },
            { id: 'S2', lane: 2, lanes: 1 },
            { id: 'S3', lane: 3, lanes: 1 },
        ],
        laneCount: 4,
    });
});

test('layoutRow: three stacked bands fill their slots', () => {
    const result = layoutRow([
        { id: 'B1', startCol: 1, endCol: 5, long: true },
        { id: 'B2', startCol: 2, endCol: 4, long: true },
        { id: 'B3', startCol: 2, endCol: 5, long: true },
        { id: 'S1', startCol: 3, endCol: 3, long: false },
        { id: 'S2', startCol: 3, endCol: 3, long: false },
        { id: 'S3', startCol: 3, endCol: 3, long: false },
    ]);
    expect(result).toEqual({
        placements: [
            { id: 'B1', lane: 0, lanes: 2 },
            { id: 'B2', lane: 2, lanes: 2 },
            { id: 'B3', lane: 4, lanes: 2 },
            { id: 'S1', lane: 0, lanes: 1 },
            { id: 'S2', lane: 2, lanes: 1 },
            { id: 'S3', lane: 4, lanes: 1 },
        ],
        laneCount: 6,
    });
});

test('layoutRow: bands with nothing on them are 1x and share a row when apart', () => {
    const result = layoutRow([
        { id: 'B1', startCol: 0, endCol: 1, long: true },
        { id: 'B2', startCol: 3, endCol: 5, long: true },
    ]);
    expect(result).toEqual({
        placements: [
            { id: 'B1', lane: 0, lanes: 1 },
            { id: 'B2', lane: 0, lanes: 1 },
        ],
        laneCount: 1,
    });
});

test('layoutRow: overlapping 1x bands stack one lane each', () => {
    const result = layoutRow([
        { id: 'B1', startCol: 0, endCol: 4, long: true },
        { id: 'B2', startCol: 2, endCol: 6, long: true },
        { id: 'S', startCol: 6, endCol: 6, long: false },
    ]);
    // S is on B2's last day, but B1 has ended there: S fits in lane 0 above B2,
    // so nothing sits on either band and both stay one lane.
    expect(result).toEqual({
        placements: [
            { id: 'B1', lane: 0, lanes: 1 },
            { id: 'B2', lane: 1, lanes: 1 },
            { id: 'S', lane: 0, lanes: 1 },
        ],
        laneCount: 2,
    });
});

test('layoutRow: only the stacked band a short sits on grows', () => {
    const result = layoutRow([
        { id: 'B1', startCol: 0, endCol: 4, long: true },
        { id: 'B2', startCol: 2, endCol: 6, long: true },
        { id: 'S1', startCol: 3, endCol: 3, long: false },
    ]);
    // S1 takes B1's slot; B2 below it has nothing on it and stays one lane.
    expect(result).toEqual({
        placements: [
            { id: 'B1', lane: 0, lanes: 2 },
            { id: 'B2', lane: 2, lanes: 1 },
            { id: 'S1', lane: 0, lanes: 1 },
        ],
        laneCount: 3,
    });
});

test('layoutRow: a short on another day leaves the band 1x', () => {
    const result = layoutRow([
        { id: 'B', startCol: 0, endCol: 2, long: true },
        { id: 'S', startCol: 4, endCol: 4, long: false },
    ]);
    expect(result).toEqual({
        placements: [
            { id: 'B', lane: 0, lanes: 1 },
            { id: 'S', lane: 0, lanes: 1 },
        ],
        laneCount: 1,
    });
});

test('layoutRow: a short spanning two columns needs a lane free in both', () => {
    const result = layoutRow([
        { id: 'B', startCol: 2, endCol: 4, long: true },
        { id: 'A', startCol: 1, endCol: 1, long: false },
        { id: 'C', startCol: 1, endCol: 2, long: false },
    ]);
    // C cannot use B's slot (A holds lane 0 on col 1), so nothing sits on B: B
    // is 1x, and C takes lane 1, free on both columns once B is one lane.
    expect(result).toEqual({
        placements: [
            { id: 'B', lane: 0, lanes: 1 },
            { id: 'A', lane: 0, lanes: 1 },
            { id: 'C', lane: 1, lanes: 1 },
        ],
        laneCount: 2,
    });
});

test('parseHours accepts positive numbers up to the given maximum', () => {
    expect(parseHours('24', 100)).toBe(24);
    expect(parseHours('1.5', 100)).toBe(1.5);
    expect(parseHours('100', 100)).toBe(100);
    for (const value of ['abc', '-5', '0', '', '  ', 'Infinity', '101', null, undefined]) {
        expect(parseHours(value, 100), `parseHours(${JSON.stringify(value)})`).toBe(null);
    }
});

test('segmentsForRow keeps zero-length events (FullCalendar reports end as null)', () => {
    const at = d(2026, 10, 6, 9);
    const segs = segmentsForRow([{ id: 1, start: at, end: null }], d(2026, 10, 5), 7);
    expect(segs.length).toBe(1);
    expect({ startCol: segs[0].startCol, endCol: segs[0].endCol, long: segs[0].long }).toEqual({ startCol: 1, endCol: 1, long: false });
});

test('segmentsForRow flags long events and skips events outside the row', () => {
    const events = [
        { id: 1, start: d(2026, 10, 6, 9), end: d(2026, 10, 9, 9) },
        { id: 2, start: d(2026, 10, 20, 1), end: d(2026, 10, 20, 2) },
    ];
    const segs = segmentsForRow(events, d(2026, 10, 5), 7);
    expect(segs.map(s => [s.id, s.long])).toEqual([[1, true]]);
    expect(segs[0].event).toBe(events[0]);
});
