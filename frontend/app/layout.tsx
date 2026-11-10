import type { Metadata } from 'next';
import 'maplibre-gl/dist/maplibre-gl.css';
import './globals.css';
import './workspace.css';

export const metadata: Metadata = {
  title: 'CurbOps AI · Madrid fleet operations',
  description: 'Investigate Madrid road notices, compare street routes and review dispatch decisions for a simulated delivery fleet.',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
