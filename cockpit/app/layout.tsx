import type { ReactNode } from 'react';
import { CockpitProvider } from '@/components/Cockpit';
import { TOKEN } from '@/lib/server/guard.mjs';
import './globals.css';

export const dynamic = 'force-dynamic';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Geist+Mono:wght@400;600&display=swap" rel="stylesheet" />
        <title>Upwork Cockpit</title>
      </head>
      <body>
        <CockpitProvider token={TOKEN}>{children}</CockpitProvider>
      </body>
    </html>
  );
}
