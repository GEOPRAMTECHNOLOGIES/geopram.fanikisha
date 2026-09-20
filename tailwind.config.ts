import type { Config } from "tailwindcss";
export default { content:["./app/**/*.{ts,tsx}"], theme:{extend:{fontFamily:{sans:["Segoe UI","system-ui","sans-serif"]}}}, plugins:[] } satisfies Config;

/* Admin-role integration review: included in complete deployment build. */
