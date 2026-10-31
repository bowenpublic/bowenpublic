'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-slate-600 hover:text-slate-900 mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Bowen
        </Link>

        <h1 className="text-3xl font-semibold text-slate-900 mb-2">
          About{' '}
          <span className="bowen-brand">
            <span style={{color: '#5d78c5'}}>B</span>
            <span style={{color: '#ffce31'}}>o</span>
            <span style={{color: '#e25063'}}>w</span>
            <span style={{color: '#ffce31'}}>e</span>
            <span style={{color: '#e25063'}}>n</span>
          </span>
        </h1>
        <p className="text-slate-500 mb-10">
          A free public legal information tool for New Zealand legislation
        </p>

        <div className="prose prose-slate max-w-none">
          <section className="mb-10">
            <h2 className="font-bold">Contact</h2>
            <p>
              For all enquiries, reach out to{' '}
              <a href="mailto:info@bowenpublic.com" className="text-blue-600 hover:underline">
                info@bowenpublic.com
              </a>
            </p>
          </section>

          <section className="mb-10">
            <h2 className="font-bold">Charitable Trust</h2>
            <p>
              Bowen Public is operated by the Bowen Public Charitable Trust,
              a charitable trust board incorporated under the Charitable Trusts Act 1957
              (registration 70000608).
            </p>
            <p>
              The Trust is governed by an independent board.
              Its charitable purposes include advancing free access to legal
              information, research into the responsible application of AI for
              public benefit, and open-source publication of all software and
              research outputs.
            </p>
            <p>
              The Bowen Public service is free to use and its source code is
              publicly available. The Trust is committed to transparency in
              how the tool works and how it handles user data.
            </p>
            <p className="text-sm text-slate-500">
              Registration with Charities Services is in progress.
            </p>
          </section>

          <section className="border-t border-slate-200 pt-8">
            <p className="text-sm text-slate-500">
              Bowen is a free public legal information tool. It provides information, not legal advice.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
