'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, BookOpen } from 'lucide-react';
import { Source } from '@/types';

interface SourcesProps {
  sources?: Source[];
}

export function Sources({ sources }: SourcesProps) {
  const [expanded, setExpanded] = useState(false);

  // undefined: the answer is still streaming, so show nothing yet.
  if (!sources) return null;

  // An empty list means the answer used no section Bowen holds; say so.
  if (sources.length === 0) {
    return (
      <div className="mt-3 pt-3 border-t border-slate-200">
        <p className="text-xs text-slate-500">
          No sections from the Acts Bowen holds were used in this answer.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 pt-3 border-t border-slate-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 transition-colors"
      >
        <BookOpen className="w-4 h-4" />
        <span>{expanded ? 'Hide' : 'Show'} {sources.length} source{sources.length !== 1 ? 's' : ''}</span>
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          {sources.map((source, index) => (
            <a
              key={index}
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block p-3 bg-slate-50 rounded-lg hover:bg-slate-100 transition-colors group"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm text-slate-900 truncate">
                    {source.act_title}
                  </p>
                  {source.section_number && (
                    <p className="text-xs text-slate-600 mt-0.5">
                      Section {source.section_number}
                      {source.section_heading && ` - ${source.section_heading}`}
                    </p>
                  )}
                  {source.excerpt && (
                    <p className="text-xs text-slate-500 mt-2 line-clamp-2">
                      {source.excerpt}
                    </p>
                  )}
                </div>
                <ExternalLink className="w-4 h-4 text-slate-400 group-hover:text-blue-500 flex-shrink-0 mt-0.5" />
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
