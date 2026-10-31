import { AlertTriangle } from 'lucide-react';
import Link from 'next/link';

/** Bowen Public's pages on Facebook and LinkedIn, as inline SVG icons. */
const SOCIAL_LINKS: { name: string; url: string; path: string }[] = [
  {
    name: 'Facebook',
    url: 'https://www.facebook.com/profile.php?id=61596094557259',
    path: 'M24 12.07C24 5.41 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.04V9.41c0-3.02 1.8-4.7 4.54-4.7 1.31 0 2.68.24 2.68.24v2.97h-1.5c-1.5 0-1.96.93-1.96 1.89v2.26h3.32l-.53 3.5h-2.8V24C19.62 23.1 24 18.1 24 12.07',
  },
  {
    name: 'LinkedIn',
    url: 'https://www.linkedin.com/company/bowenpublic/',
    path: 'M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.13 1.45-2.13 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zm1.78 13.02H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z',
  },
];

function SocialLinks() {
  return (
    <span className="inline-flex items-center gap-3">
      {SOCIAL_LINKS.map(({ name, url, path }) => (
        <a
          key={name}
          href={url}
          aria-label={`Bowen Public on ${name}`}
          title={name}
          target="_blank"
          rel="noopener"
          className="inline-flex text-[#5d78c5] hover:text-[#4a63a8]"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" width={18} height={18} fill="currentColor">
            <path d={path} />
          </svg>
        </a>
      ))}
    </span>
  );
}

export function DisclaimerFooter() {
  return (
    <div className="flex flex-col items-center gap-1 text-xs text-slate-500 py-2">
      <div className="flex items-center gap-2">

        <span>
          <span className="bowen-brand">Bowen</span> is an ai model, NOT legal advice. Consult a qualified NZ lawyer for legal decisions.
        </span>
      </div>
      <div className="flex gap-3">
        <Link
          href="/data-policy"
          className="text-slate-400 hover:text-slate-600 underline underline-offset-2"
        >
          Data Policy
        </Link>
        <Link
          href="/te-tiriti"
          className="text-slate-400 hover:text-slate-600 underline underline-offset-2"
        >
          Bowen's approach to The Treaty / Te Tiriti
        </Link>
        <Link
          href="/about"
          className="text-slate-400 hover:text-slate-600 underline underline-offset-2"
        >
          About
        </Link>
        <SocialLinks />
      </div>
    </div>
  );
}
