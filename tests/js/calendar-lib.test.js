// Unit tests for notices/static/notices/js/calendar-lib.js.
// Run with: make test-js  (TZ=America/Toronto node --test tests/js/)
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
    LONG_THRESHOLD_MS,
    isLong,
    segmentForRow,
    layoutRow,
    parseHours,
} = require(path.join(__dirname, '..', '..', 'notices', 'static', 'notices', 'js', 'calendar-lib.js'));

// Local-time date; month is 1-based here to keep the cases readable.
function d(y, m, day, h = 0, min = 0) {
    return new Date(y, m - 1, day, h, min);
}

test('LONG_THRESHOLD_MS is 24 hours', () => {
    assert.equal(LONG_THRESHOLD_MS, 24 * 3600 * 1000);
});

test('isLong is strict at 24h', () => {
    assert.equal(isLong(d(2026, 10, 5), d(2026, 10, 6)), false);
    assert.equal(isLong(d(2026, 10, 5), d(2026, 10, 6, 0, 1)), true);
});

test('segmentForRow: end at local midnight does not touch the next day', () => {
    // Row starts Mon 2026-10-05; event Tue 09:00 -> Thu 00:00 covers Tue and Wed.
    assert.deepEqual(segmentForRow(d(2026, 10, 6, 9), d(2026, 10, 8), d(2026, 10, 5), 7), {
        startCol: 1,
        endCol: 2,
        startsHere: true,
        endsHere: true,
    });
});

test('segmentForRow: zero-length event occupies its start day', () => {
    assert.deepEqual(segmentForRow(d(2026, 10, 6, 9), d(2026, 10, 6, 9), d(2026, 10, 5), 7), {
        startCol: 1,
        endCol: 1,
        startsHere: true,
        endsHere: true,
    });
});

test('segmentForRow: event continuing into the next row has no end here', () => {
    const start = d(2026, 10, 8, 9);
    const end = d(2026, 10, 14, 18);
    assert.deepEqual(segmentForRow(start, end, d(2026, 10, 5), 7), {
        startCol: 3,
        endCol: 6,
        startsHere: true,
        endsHere: false,
    });
    assert.deepEqual(segmentForRow(start, end, d(2026, 10, 12), 7), {
        startCol: 0,
        endCol: 2,
        startsHere: false,
        endsHere: true,
    });
});

test('segmentForRow: events outside the row are null', () => {
    // Ends exactly at the row's first midnight: last day is the day before.
    assert.equal(segmentForRow(d(2026, 10, 3, 10), d(2026, 10, 5), d(2026, 10, 5), 7), null);
    // Starts after the row's last day.
    assert.equal(segmentForRow(d(2026, 10, 12, 1), d(2026, 10, 12, 3), d(2026, 10, 5), 7), null);
});

test('segmentForRow: DST changes map days to the right columns', () => {
    // Spring forward on Sun 2026-03-08 (America/Toronto): a 23h day inside the row.
    assert.equal(segmentForRow(d(2026, 3, 9, 1), d(2026, 3, 9, 3), d(2026, 3, 2), 14).startCol, 7);
    // Fall back on Sun 2026-11-01: a 25h day inside the row.
    assert.equal(segmentForRow(d(2026, 11, 2, 1), d(2026, 11, 2, 3), d(2026, 10, 26), 14).startCol, 7);
});

test('layoutRow: empty row', () => {
    assert.deepEqual(layoutRow([]), { placements: [], laneCount: 0 });
});

test('layoutRow: one band plus three shorts on its first day', () => {
    const result = layoutRow([
        { id: 'B', startCol: 1, endCol: 4, long: true },
        { id: 'S1', startCol: 1, endCol: 1, long: false },
        { id: 'S2', startCol: 1, endCol: 1, long: false },
        { id: 'S3', startCol: 1, endCol: 1, long: false },
    ]);
    // S1 takes the band's slot; lane 1 is the band's label; S2 and S3 go below.
    assert.deepEqual(result, {
        placements: [
            { id: 'B', lane: 0 },
            { id: 'S1', lane: 0 },
            { id: 'S2', lane: 2 },
            { id: 'S3', lane: 3 },
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
    assert.deepEqual(result, {
        placements: [
            { id: 'B1', lane: 0 },
            { id: 'B2', lane: 2 },
            { id: 'B3', lane: 4 },
            { id: 'S1', lane: 0 },
            { id: 'S2', lane: 2 },
            { id: 'S3', lane: 4 },
        ],
        laneCount: 6,
    });
});

test('layoutRow: bands that do not overlap share a row', () => {
    const result = layoutRow([
        { id: 'B1', startCol: 0, endCol: 1, long: true },
        { id: 'B2', startCol: 3, endCol: 5, long: true },
    ]);
    assert.deepEqual(result, {
        placements: [
            { id: 'B1', lane: 0 },
            { id: 'B2', lane: 0 },
        ],
        laneCount: 2,
    });
});

test('layoutRow: a short spanning two columns needs a lane free in both', () => {
    const result = layoutRow([
        { id: 'B', startCol: 2, endCol: 4, long: true },
        { id: 'A', startCol: 1, endCol: 1, long: false },
        { id: 'C', startCol: 1, endCol: 2, long: false },
    ]);
    // C: lane 0 is taken by A on col 1, lane 1 is B's label on col 2.
    assert.deepEqual(result, {
        placements: [
            { id: 'B', lane: 0 },
            { id: 'A', lane: 0 },
            { id: 'C', lane: 2 },
        ],
        laneCount: 3,
    });
});

test('parseHours accepts positive numbers only', () => {
    assert.equal(parseHours('24'), 24);
    assert.equal(parseHours('1.5'), 1.5);
    for (const value of ['abc', '-5', '0', '', '  ', 'Infinity', null, undefined]) {
        assert.equal(parseHours(value), null, `parseHours(${JSON.stringify(value)})`);
    }
});
