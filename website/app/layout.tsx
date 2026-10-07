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
      </head>
      <body>
        <CockpitProvider token={TOKEN}>{children}</CockpitProvider>
      </body>
    </html>
  );
}
