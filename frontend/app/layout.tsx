import type { Metadata } from 'next';
import 'maplibre-gl/dist/maplibre-gl.css';
import './globals.css';

export const metadata: Metadata = {
  title: 'CURBOPS - Urban operations intelligence',
  description: 'Agentic AI dispatch control tower • Madrid Open Data × human-in-the-loop operations',
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
