'use client';

import { useState, useEffect } from 'react';
import { RummageKiwi } from './RummageKiwi';
import Image from 'next/image';

const LOADING_PHRASES = [
  'Searching legislation...',
  'Rummaging through statutes...',
  'Consulting the archives...',
  'Cross-referencing sections...',
  'Parsing provisions...',
  'Sifting through schedules...',
  'Deciphering legalese...',
  'Checking the fine print...',
  'Flipping through Acts...',
  'Untangling subsections...',
  'Perusing parliamentary intent...',
  'Reviewing the record...',
];

export function TypingIndicator() {
  const [phraseIndex, setPhraseIndex] = useState(() =>
    Math.floor(Math.random() * LOADING_PHRASES.length)
  );

  useEffect(() => {
    const interval = setInterval(() => {
      setPhraseIndex((prev) => {
        let next;
        do {
          next = Math.floor(Math.random() * LOADING_PHRASES.length);
        } while (next === prev);
        return next;
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex justify-start">
      <div className="bg-white border border-slate-200 rounded-2xl rounded-bl-sm p-4">
        <div className="flex items-center gap-2 mb-2">
          <Image src="/logo-mark.png" alt="" width={24} height={24} className="w-6 h-6" />
          <span className="bowen-brand text-xs text-slate-500">Bowen</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 text-primary flex-shrink-0">
            <RummageKiwi className="w-full h-full" />
          </div>
          <span className="text-sm text-slate-500 transition-opacity duration-300">
            {LOADING_PHRASES[phraseIndex]}
          </span>
        </div>
      </div>
    </div>
  );
}
