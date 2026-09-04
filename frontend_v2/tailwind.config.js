/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#EFF6FF',
          100: '#DBEAFE',
          500: '#3B82F6',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
          900: '#1E3A8A',
        },
        surface: {
          canvas: '#F8FAFC', // Slate 50
          card: '#FFFFFF',
          cardSubtle: '#F1F5F9', // Slate 100
          border: '#E2E8F0', // Slate 200
          borderStrong: '#CBD5E1', // Slate 300
        },
        financial: {
          captured: '#059669', // Emerald 600
          capturedBg: '#ECFDF5', // Emerald 50
          failed: '#DC2626', // Red 600
          failedBg: '#FEF2F2', // Red 50
          pending: '#D97706', // Amber 600
          pendingBg: '#FFFBEB', // Amber 50
          soundbox: '#4F46E5', // Indigo 600
        },
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(15, 23, 42, 0.06), 0 1px 2px -1px rgba(15, 23, 42, 0.04)',
        'card-hover': '0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.06)',
      },
    },
  },
  plugins: [],
};
