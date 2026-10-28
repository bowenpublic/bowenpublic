import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Te Tiriti o Waitangi',
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
