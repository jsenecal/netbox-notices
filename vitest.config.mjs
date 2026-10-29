import { defineConfig } from 'vitest/config';

// Day columns and DST cases in the calendar tests depend on the local time zone;
// pin one with DST so the results do not depend on the machine running them.
process.env.TZ = 'America/Toronto';

export default defineConfig({
    test: {
        include: ['tests/js/**/*.test.js'],
    },
});
