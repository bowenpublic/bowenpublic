import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'Bowen Public – Ask about New Zealand law',
    template: '%s – Bowen Public',
  },
  description: 'Chatbot legal information tool for New Zealand legislation. Get instant answers with citations to official sources.',
  keywords: ['New Zealand law', 'legal information', 'NZ legislation', 'legal assistant'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="48x48" />
        <link rel="icon" href="/icon-32.png" type="image/png" sizes="32x32" />
        <link rel="icon" href="/icon-192.png" type="image/png" sizes="192x192" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href="https://use.typekit.net/czn0xnx.css" />
      </head>
      <body className="antialiased">{children}</body>
    </html>
  );
}
