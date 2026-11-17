import type { Metadata } from 'next';
import '@/app/globals.css';

export const metadata: Metadata = {
  title: 'Relay | CCS-KU BFC',
  description: 'Shared gear, loan documents, return reports, photos, and manuals',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
