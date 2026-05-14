import type { Config } from 'tailwindcss';

export default {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        ink: '#0f172a',
        mist: '#e2e8f0',
        sea: '#0f766e',
        coral: '#ea580c',
        sand: '#f8fafc',
      },
    },
  },
  plugins: [],
} satisfies Config;

