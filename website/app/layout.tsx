import type { ReactNode } from 'react';
import { CockpitProvider } from '@/components/Cockpit';
import { TOKEN } from '@/lib/server/guard.mjs';
import './globals.css';

export const dynamic = 'force-dynamic';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <title>Automatable Cockpit</title>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet" />
      </head>
      <body>
        <CockpitProvider token={TOKEN}>{children}</CockpitProvider>
      </body>
    </html>
  );
}
