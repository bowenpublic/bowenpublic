'use client';

import Link from 'next/link';
import { ArrowLeft, Shield } from 'lucide-react';

export default function DataPolicyPage() {
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

        <div className="flex items-center gap-3 mb-2">
          <Shield className="w-8 h-8 text-slate-700" />
          <h1 className="text-3xl font-semibold text-slate-900">
            Data Policy
          </h1>
        </div>
        <p className="text-slate-500 mb-8">
          How Bowen handles your data
        </p>

        <div className="prose prose-slate max-w-none">
          <section className="mb-10">
            <h2>Our Commitment</h2>
            <p>
              Bowen is a free public service designed to make New Zealand legal information
              more accessible. We are committed to protecting your privacy and being transparent
              about how we handle data.
            </p>
          </section>

          <section className="mb-10">
            <h2>What We Collect</h2>
            <p>
              When you use Bowen, we collect:
            </p>
            <ul>
              <li>Your queries and the responses Bowen provides</li>
              <li>Basic session information to improve the service</li>
            </ul>
            <p>
              We do not collect personal identifying information. We do not require you to
              create an account or provide your name, email, or any other personal details.
            </p>
          </section>

          <section className="mb-10">
            <h2>How We Use Your Data</h2>
            <p>
              All queries and responses are <strong>anonymised</strong> and are used solely to:
            </p>
            <ul>
              <li>Monitor that Bowen is providing accurate and helpful information</li>
              <li>Identify areas where Bowen can be improved</li>
              <li>Ensure the service remains reliable and available</li>
            </ul>
          </section>

          <section className="mb-10">
            <h2>What We Will Never Do</h2>
            <p>
              Your data will <strong>never be sold</strong>. We will never:
            </p>
            <ul>
              <li>Sell your queries or any data to third parties</li>
              <li>Use your data for advertising or marketing purposes</li>
      
            </ul>
            <p>
              All data is held internally and used exclusively to ensure Bowen continues
              to provide a quality free public service.
            </p>
          </section>

          <section className="mb-10">
            <h2>Data Retention</h2>
            <p>
              We retain anonymised query logs to help us understand how Bowen is being used
              and to improve the service over time. These logs do not contain any information
              that could identify you personally.
            </p>
          </section>



          <section className="mb-10">
            <h2>Questions</h2>
            <p>
              If you have any questions about this data policy or how Bowen handles your
              information, please get in touch with us.<br /><br />info@bowenpublic.com
            </p>
          </section>

          <section className="border-t border-slate-200 pt-8">
            <p className="text-sm text-slate-500">
              This policy may be updated from time to time. Bowen is committed to maintaining
              the trust of our users and will always prioritise your privacy.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
