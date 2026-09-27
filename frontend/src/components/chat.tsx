'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, BookOpen } from 'lucide-react';
import { ManatIcon } from './ManatIcon';
import { KiwiIcon } from './KiwiIcon';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { DisclaimerFooter } from './DisclaimerFooter';
import { TypingIndicator } from './TypingIndicator';
import { getActs } from '@/lib/api';
import { Act } from '@/types';

// Fallback legislation coverage (used if API fails)
const FALLBACK_LEGISLATION = [
  { title: 'Residential Tenancies Act 1986', short_name: 'RTA', topics: ['tenancy', 'bonds', 'housing'] },
  { title: 'Employment Relations Act 2000', short_name: 'ERA', topics: ['employment', 'dismissal', 'leave'] },
  { title: 'Companies Act 1993', short_name: 'CA', topics: ['directors', 'shareholders', 'incorporation'] },
  { title: 'Consumer Guarantees Act 1993', short_name: 'CGA', topics: ['refunds', 'repairs', 'guarantees'] },
  { title: 'Property Law Act 2007', short_name: 'PLA', topics: ['property', 'mortgages', 'leases'] },
  { title: 'Fair Trading Act 1986', short_name: 'FTA', topics: ['consumer protection', 'misleading conduct'] },
  { title: 'Privacy Act 2020', short_name: 'PA', topics: ['personal information', 'data breaches'] },
  { title: 'Building Act 2004', short_name: 'BA', topics: ['consents', 'code compliance'] },
  { title: 'Contract and Commercial Law Act 2017', short_name: 'CCLA', topics: ['contracts', 'sale of goods'] },
  { title: 'Resource Management Act 1991', short_name: 'RMA', topics: ['environment', 'resource consents'] },
  { title: 'Crimes Act 1961', short_name: 'CA1961', topics: ['criminal offences', 'sentencing'] },
  { title: 'Health and Safety at Work Act 2015', short_name: 'HSWA', topics: ['workplace safety', 'PCBU duties'] },
  { title: 'Human Rights Act 1993', short_name: 'HRA', topics: ['discrimination', 'equality'] },
  { title: 'Income Tax Act 2007', short_name: 'ITA', topics: ['tax', 'deductions', 'income'] },
  { title: 'Land Transport Act 1998', short_name: 'LTA', topics: ['driving', 'licences', 'traffic'] },
  { title: 'Immigration Act 2009', short_name: 'IA', topics: ['visas', 'residence', 'deportation'] },
  { title: 'Trusts Act 2019', short_name: 'TA', topics: ['trusts', 'trustees', 'beneficiaries'] },
  { title: 'Insolvency Act 2006', short_name: 'INSA', topics: ['bankruptcy', 'liquidation'] },
  { title: 'Copyright Act 1994', short_name: 'CRA', topics: ['copyright', 'intellectual property'] },
  { title: 'Credit Contracts and Consumer Finance Act 2003', short_name: 'CCCFA', topics: ['loans', 'credit', 'interest'] },
  { title: 'Official Information Act 1982', short_name: 'OIA', topics: ['government', 'requests', 'disclosure'] },
  { title: 'Family Violence Act 2018', short_name: 'FVA', topics: ['protection orders', 'domestic violence'] },
  { title: 'Accident Compensation Act 2001', short_name: 'ACA', topics: ['ACC', 'injury', 'compensation'] },
  { title: 'Financial Markets Conduct Act 2013', short_name: 'FMCA', topics: ['securities', 'investment', 'disclosure'] },
  { title: 'Harmful Digital Communications Act 2015', short_name: 'HDCA', topics: ['cyberbullying', 'online harassment'] },
  { title: 'Unit Titles Act 2010', short_name: 'UTA', topics: ['body corporate', 'apartments'] },
  { title: 'Local Government Act 2002', short_name: 'LGA', topics: ['councils', 'rates', 'bylaws'] },
  { title: 'Family Court Act 1980', short_name: 'FCA', topics: ['family court', 'jurisdiction'] },
  { title: 'Coroners Act 2006', short_name: 'CORA', topics: ['inquests', 'death inquiries'] },
  { title: 'Sale of Goods Act 1908', short_name: 'SOGA', topics: ['sale', 'goods', 'contracts'] },
  { title: 'Constitution Act 1986', short_name: 'CONST', topics: ['parliament', 'sovereignty', 'executive'] },
  { title: 'Electoral Act 1993', short_name: 'ELEC', topics: ['voting', 'elections', 'parliament'] },
  { title: 'Citizenship Act 1977', short_name: 'CITZ', topics: ['citizenship', 'naturalisation'] },
  { title: 'Anti-Money Laundering and Countering Financing of Terrorism Act 2009', short_name: 'AML', topics: ['money laundering', 'terrorism financing', 'reporting'] },
  { title: 'Trade Marks Act 2002', short_name: 'TMA', topics: ['trade marks', 'registration', 'infringement'] },
  { title: 'Patents Act 2013', short_name: 'PATA', topics: ['patents', 'inventions', 'intellectual property'] },
  { title: 'Climate Change Response Act 2002', short_name: 'CCRA', topics: ['emissions', 'carbon', 'climate'] },
  { title: 'Conservation Act 1987', short_name: 'CONS', topics: ['conservation', 'DOC', 'protected areas'] },
  { title: 'Public Service Act 2020', short_name: 'PSA', topics: ['public service', 'government agencies'] },
  { title: 'Fire and Emergency New Zealand Act 2017', short_name: 'FENZ', topics: ['fire', 'emergency', 'rescue'] },
  { title: 'Public Finance Act 1989', short_name: 'PFA', topics: ['budget', 'appropriation', 'crown'] },
  { title: 'District Courts Act 1947', short_name: 'DCA', topics: ['district court', 'jurisdiction'] },
  { title: 'Biosecurity Act 1993', short_name: 'BSA', topics: ['biosecurity', 'pest', 'quarantine'] },
  { title: 'Fisheries Act 1996', short_name: 'FA', topics: ['fishing', 'quota', 'marine'] },
  { title: 'Hazardous Substances and New Organisms Act 1996', short_name: 'HSNO', topics: ['hazardous', 'chemicals', 'GMO'] },
  { title: 'Freedom Camping Act 2011', short_name: 'FCAM', topics: ['camping', 'vehicles', 'local authority'] },
  { title: 'Health Act 1956', short_name: 'HA', topics: ['public health', 'sanitation', 'disease'] },
  { title: 'Medicines Act 1981', short_name: 'MA', topics: ['medicine', 'pharmacy', 'prescription'] },
  { title: 'Smokefree Environments and Regulated Products Act 1990', short_name: 'SEA', topics: ['smoking', 'tobacco', 'vaping'] },
  { title: 'Civil Defence Emergency Management Act 2002', short_name: 'CDEM', topics: ['civil defence', 'emergency', 'disaster response'] },
  { title: 'Health Practitioners Competence Assurance Act 2003', short_name: 'HPCA', topics: ['health practitioners', 'registration', 'competence'] },
  { title: 'Heritage New Zealand Pouhere Taonga Act 2014', short_name: 'HNZPT', topics: ['heritage', 'historic places', 'archaeology'] },
  { title: 'Local Electoral Act 2001', short_name: 'LEA', topics: ['local elections', 'voting', 'councils'] },
  { title: 'Local Government Act 1974', short_name: 'LGA1974', topics: ['local government', 'roads', 'public works'] },
  { title: 'Local Government (Auckland Council) Act 2009', short_name: 'LGACA', topics: ['Auckland', 'council', 'local government'] },
  { title: 'Local Government Official Information and Meetings Act 1987', short_name: 'LGOIMA', topics: ['official information', 'meetings', 'councils'] },
  { title: 'Local Government (Rating) Act 2002', short_name: 'LGRA', topics: ['rates', 'rating', 'property tax'] },
  { title: 'Maori Fisheries Act 2004', short_name: 'MFA', topics: ['Maori fisheries', 'Te Ohu Kaimoana', 'iwi'] },
  { title: 'Marine and Coastal Area (Takutai Moana) Act 2011', short_name: 'MCAA', topics: ['marine area', 'coastal', 'customary rights'] },
  { title: 'Nga Wai o Maniapoto (Waipa River) Act 2012', short_name: 'NWMWR', topics: ['Waipa River', 'Maniapoto', 'treaty settlement'] },
  { title: 'Ngai Tahu Claims Settlement Act 1998', short_name: 'NTCS', topics: ['Ngai Tahu', 'treaty settlement', 'South Island'] },
  { title: 'Ngati Tuwharetoa, Raukawa, and Te Arawa River Iwi Waikato River Act 2010', short_name: 'NTRTA', topics: ['Waikato River', 'river iwi', 'treaty settlement'] },
  { title: 'Oranga Tamariki Act 1989', short_name: 'OTA', topics: ['child protection', 'youth justice', 'welfare'] },
  { title: 'Privacy Act 1993', short_name: 'PA1993', topics: ['privacy', 'personal information', 'data protection'] },
  { title: 'Rates Rebate Act 1973', short_name: 'RRA', topics: ['rates rebate', 'low income', 'relief'] },
  { title: 'Rating Valuations Act 1998', short_name: 'RVA', topics: ['valuations', 'property', 'rating'] },
  { title: 'Reserves Act 1977', short_name: 'RA', topics: ['reserves', 'recreation', 'conservation'] },
  { title: 'Te Awa Tupua (Whanganui River Claims Settlement) Act 2017', short_name: 'TAT', topics: ['Whanganui River', 'legal personhood', 'treaty settlement'] },
  { title: 'Te Ture mo Te Reo Maori 2016 (Maori Language Act)', short_name: 'TRMA', topics: ['Te Reo Maori', 'language', 'revitalisation'] },
  { title: 'Te Runanga o Ngai Tahu Act 1996', short_name: 'TRNT', topics: ['Ngai Tahu', 'governance', 'iwi'] },
  { title: 'Te Ture Whenua Maori Act 1993 (Maori Land Act)', short_name: 'TTWM', topics: ['Maori land', 'land court', 'succession'] },
  { title: 'Te Urewera Act 2014', short_name: 'TUA', topics: ['Te Urewera', 'Tuhoe', 'treaty settlement'] },
  { title: 'Treaty of Waitangi Act 1975', short_name: 'TOWA', topics: ['Treaty of Waitangi', 'Waitangi Tribunal', 'claims'] },
  { title: 'Treaty of Waitangi (Fisheries Claims) Settlement Act 1992', short_name: 'TOWFS', topics: ['fisheries settlement', 'Sealord', 'Treaty'] },
  { title: 'Waikato Raupatu Claims Settlement Act 1995', short_name: 'WRCS', topics: ['Waikato-Tainui', 'raupatu', 'treaty settlement'] },
  { title: 'Waikato-Tainui Raupatu Claims (Waikato River) Settlement Act 2010', short_name: 'WTWR', topics: ['Waikato River', 'Waikato-Tainui', 'river settlement'] },
  { title: 'Sentencing Act 2002', short_name: 'SA', topics: ['sentencing', 'imprisonment', 'community sentences'] },
  { title: 'Criminal Procedure Act 2011', short_name: 'CPA', topics: ['criminal procedure', 'trials', 'charges'] },
  { title: 'Evidence Act 2006', short_name: 'EVA', topics: ['evidence', 'admissibility', 'witnesses'] },
  { title: 'Bail Act 2000', short_name: 'BAIL', topics: ['bail', 'remand', 'conditions'] },
  { title: 'Care of Children Act 2004', short_name: 'COCA', topics: ['children', 'guardianship', 'parenting orders'] },
  { title: 'Property (Relationships) Act 1976', short_name: 'PRA', topics: ['relationship property', 'separation', 'division'] },
  { title: 'Limitation Act 2010', short_name: 'LA', topics: ['limitation periods', 'time bars', 'claims'] },
  { title: 'Lawyers and Conveyancers Act 2006', short_name: 'LCA', topics: ['legal profession', 'conduct', 'discipline'] },
  { title: 'Search and Surveillance Act 2012', short_name: 'SSA', topics: ['search warrants', 'surveillance', 'police powers'] },
  { title: 'Protection of Personal and Property Rights Act 1988', short_name: 'PPPR', topics: ['enduring powers of attorney', 'welfare guardians', 'capacity'] },
];

// Database stats - acts count derived from FALLBACK_LEGISLATION above
const DATABASE_STATS = {
  sections: 54890,
  chunks: 63167,
};

// Placeholder supporters - replace with actual donors
const SUPPORTERS = [
  { name: 'Russell McVeagh', tier: 'gold' },
  { name: 'Chapman Tripp', tier: 'gold' },
  { name: 'Bell Gully', tier: 'silver' },
  { name: 'Simpson Grierson', tier: 'silver' },
  { name: 'MinterEllisonRuddWatts', tier: 'silver' },
  { name: 'Buddle Findlay', tier: 'bronze' },
  { name: 'Duncan Cotterill', tier: 'bronze' },
  { name: 'Lane Neave', tier: 'bronze' },
];

export function Chat() {
  const { messages, isLoading, error, send, clearMessages } = useChat();
  const [acts, setActs] = useState<Array<{ title: string; short_name: string; topics: string[] }> | null>(null);
  const [showLegislation, setShowLegislation] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastAssistantRef = useRef<HTMLDivElement>(null);
  const wasLoadingRef = useRef(false);

  // Fetch acts from API on mount
  useEffect(() => {
    getActs()
      .then((fetchedActs) => {
        if (fetchedActs && fetchedActs.length > 0) {
          setActs(fetchedActs.map(act => ({
            title: act.title,
            short_name: act.short_name,
            topics: act.topics
          })));
        } else {
          setActs(FALLBACK_LEGISLATION);
        }
      })
      .catch((err) => {
        console.warn('Failed to fetch acts from API, using fallback:', err);
        setActs(FALLBACK_LEGISLATION);
      });
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Scroll to top of assistant answer when response completes
  useEffect(() => {
    if (wasLoadingRef.current && !isLoading && messages.length > 0) {
      // Loading just finished - scroll to top of the last assistant message
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant' && lastAssistantRef.current) {
        const headerHeight = 80; // Account for sticky header
        const elementTop = lastAssistantRef.current.getBoundingClientRect().top + window.scrollY;
        window.scrollTo({ top: elementTop - headerHeight, behavior: 'smooth' });
      }
    } else if (isLoading) {
      // While loading, scroll to bottom to show typing indicator
      scrollToBottom();
    }
    wasLoadingRef.current = isLoading;
  }, [messages, isLoading]);

  return (
    <div className="min-h-screen bg-white flex flex-col">

      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <div className="w-10 h-10 bg-white border border-slate-200 rounded-lg flex items-center justify-center shadow-md">
              <ManatIcon className="w-5 h-5 text-black" />
            </div>
            <div>
              <h1 className="bowen-brand text-xl tracking-wide">
                <span style={{color: '#5d78c5'}}>B</span>
                <span style={{color: '#ffce31'}}>o</span>
                <span style={{color: '#e25063'}}>w</span>
                <span style={{color: '#ffce31'}}>e</span>
                <span style={{color: '#e25063'}}>n</span>
              </h1>
              <p className="text-[10px] uppercase tracking-wider text-black">
                PUBLIC
              </p>
            </div>
          </Link>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-full">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-green-700 font-medium">Online</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
            <div className="flex items-center gap-3 mb-6">
            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center">
                <ManatIcon className="w-8 h-8 text-primary" />
              </div>
              <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center">
                <KiwiIcon className="w-8 h-8 text-primary" />
              </div>

            </div>
            <h2 className="text-3xl text-primary mb-3">
              Ask <span className="bowen-brand"><span style={{color: '#5d78c5'}}>B</span><span style={{color: '#ffce31'}}>o</span><span style={{color: '#e25063'}}>w</span><span style={{color: '#ffce31'}}>e</span><span style={{color: '#e25063'}}>n</span></span> about New Zealand Law
            </h2>
            <p className="text-slate-500 max-w-md mb-8">
              A public and free service for all New Zealanders.
            </p>

            {/* Database Stats */}
            <div className="w-full max-w-2xl mb-6">
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 text-center">
                  {acts ? (
                    <p className="text-2xl font-semibold text-slate-800">{acts.length}</p>
                  ) : (
                    <div className="h-8 w-12 mx-auto bg-slate-200 rounded animate-pulse" />
                  )}
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide">Acts</p>
                </div>
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 text-center">
                  <p className="text-2xl font-semibold text-slate-800">{DATABASE_STATS.sections.toLocaleString()}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide">Sections</p>
                </div>
                <div className="bg-slate-50 rounded-lg border border-slate-200 p-3 text-center">
                  <p className="text-2xl font-semibold text-slate-800">{DATABASE_STATS.chunks.toLocaleString()}</p>
                  <p className="text-[10px] text-slate-500 uppercase tracking-wide">Searchable Chunks</p>
                </div>
              </div>
            </div>

            {/* Legislation Coverage */}
            <div className="w-full max-w-2xl">
              <button
                onClick={() => setShowLegislation(!showLegislation)}
                className="mx-auto flex items-center gap-2 px-4 py-2 text-white/90 text-sm font-medium rounded-lg animate-gradient-shift"
                style={{ backgroundImage: 'linear-gradient(270deg, #3b82f6, #ec4899, #8b5cf6, #3b82f6)', backgroundSize: '300% 100%' }}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.582a.5.5 0 0 1 0 .963L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" fill="currentColor"/>
                  <path d="M20 3v4M22 5h-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
                Legislation Coverage
                <svg className={`w-3 h-3 transition-transform ${showLegislation ? 'rotate-180' : ''}`} viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              {showLegislation && (
                <div className="mt-3 bg-slate-50 rounded-xl border border-slate-200 p-3">
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                    {(acts ?? []).map((act) => (
                      <div key={act.short_name} className="text-left p-2 bg-white rounded-lg border border-slate-100">
                        <p className="text-xs font-medium text-slate-700 leading-tight">{act.title}</p>
                        <p className="text-[10px] text-slate-400 mt-0.5 truncate">{act.topics.join(', ')}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Donate Button */}
            <div className="w-full max-w-2xl mt-4 flex justify-center">
              <Link
                href="/donate"
                className="flex items-center gap-2 px-4 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-600 text-sm font-medium rounded-lg transition-colors"
              >
                <BookOpen className="w-4 h-4 text-pink-500" />
                Support Bowen Public
              </Link>
            </div>

            {/* Supporters Section */}

            {showLegislation && <div className="h-96" />}
          </div>
        ) : (
          <div className="space-y-6 pb-32">
            {messages.map((message, index) => {
              const isLastAssistant = message.role === 'assistant' && index === messages.length - 1;
              return (
                <div key={index} ref={isLastAssistant ? lastAssistantRef : undefined}>
                  <ChatMessage message={message} />
                </div>
              );
            })}
            {isLoading && !(messages.length > 0 && messages[messages.length - 1].role === 'assistant' && messages[messages.length - 1].content) && <TypingIndicator />}
            {error && (
              <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <p>{error}</p>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </main>

      {/* Input Area */}
      <div className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent pt-8 pb-4 px-4">
        <div className="max-w-3xl mx-auto">
          <ChatInput onSend={send} isLoading={isLoading} />
          <DisclaimerFooter />
        </div>
      </div>
    </div>
  );
}
