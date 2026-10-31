'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function TeTiritiPage() {
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
          <span className="bowen-brand">
            <span style={{color: '#5d78c5'}}>B</span>
            <span style={{color: '#ffce31'}}>o</span>
            <span style={{color: '#e25063'}}>w</span>
            <span style={{color: '#ffce31'}}>e</span>
            <span style={{color: '#e25063'}}>n</span>
          </span>'s Approach to Te Tiriti o Waitangi
        </h1>
        <p className="text-slate-500 mb-6">
          How Bowen handles Treaty of Waitangi matters in New Zealand law
        </p>

        {/* Navigation */}
        <nav className="flex flex-wrap gap-4 mb-12 text-sm">
          <a href="#te-tiriti" className="text-slate-600 hover:text-slate-900 underline underline-offset-2">
            Te Tiriti / The Treaty
          </a>
          <a href="#how-bowen-handles" className="text-slate-600 hover:text-slate-900 underline underline-offset-2">
            How Bowen Handles Treaty Queries
          </a>
          <a href="#essay" className="text-slate-600 hover:text-slate-900 underline underline-offset-2">
            From Possession to Ownership
          </a>
        </nav>

        <div className="prose prose-slate max-w-none">
          {/* Section 1: Te Tiriti / The Treaty */}
          <section id="te-tiriti" className="mb-12">
            <h2 className="font-bold">Te Tiriti o Waitangi</h2>
            <div className="prose prose-slate text-sm leading-relaxed">
              <p>
                Ko Wikitoria te Kuini o Ingarani i tana mahara atawai ki nga Rangatira me nga Hapu
                o Nu Tirani i tana hiahia hoki kia tohungia ki a ratou o ratou rangatiratanga me to
                ratou wenua, a kia mau tonu hoki te Rongo ki a ratou me te Atanoho hoki kua wakaaro
                ia he mea tika kia tukua mai tetahi Rangatira - hei kai wakarite ki nga Tangata maori
                o Nu Tirani - kia wakaaetia e nga Rangatira maori te Kawanatanga o te Kuini ki nga
                wahikatoa o te wenua nei me nga motu - na te mea hoki he tokomaha ke nga tangata o
                tona Iwi Kua noho ki tenei wenua, a e haere mai nei.
              </p>
              <p>
                Na ko te Kuini e hiahia ana kia wakaritea te Kawanatanga kia kaua ai nga kino e puta
                mai ki te tangata maori ki te Pakeha e noho ture kore ana.
              </p>
              <p>
                Na kua pai te Kuini kia tukua a hau a Wiremu Hopihona he Kapitana i te Roiara Nawi
                hei Kawana mo nga wahi katoa o Nu Tirani e tukua aianei amua atu ki te Kuini, e mea
                atu ana ia ki nga Rangatira o te wakaminenga o nga hapu o Nu Tirani me era Rangatira
                atu enei ture ka korerotia nei.
              </p>

              <h4 className="font-semibold mt-6">Ko te tuatahi</h4>
              <p>
                Ko nga Rangatira o te wakaminenga me nga Rangatira katoa hoki ki hai i uru ki taua
                wakaminenga ka tuku rawa atu ki te Kuini o Ingarani ake tonu atu - te Kawanatanga
                katoa o o ratou wenua.
              </p>

              <h4 className="font-semibold mt-6">Ko te tuarua</h4>
              <p>
                Ko te Kuini o Ingarani ka wakarite ka wakaae ki nga Rangatira ki nga hapu - ki nga
                tangata katoa o Nu Tirani te tino rangatiratanga o o ratou wenua o ratou kainga me
                o ratou taonga katoa. Otiia ko nga Rangatira o te wakaminenga me nga Rangatira katoa
                atu ka tuku ki te Kuini te hokonga o era wahi wenua e pai ai te tangata nona te
                wenua - ki te ritenga o te utu e wakaritea ai e ratou ko te kai hoko e meatia nei e
                te Kuini hei kai hoko mona.
              </p>

              <h4 className="font-semibold mt-6">Ko te tuatoru</h4>
              <p>
                Hei wakaritenga mai hoki tenei mo te wakaaetanga ki te Kawanatanga o te Kuini - Ka
                tiakina e te Kuini o Ingarani nga tangata maori katoa o Nu Tirani ka tukua ki a ratou
                nga tikanga katoa rite tahi ki ana mea ki nga tangata o Ingarani.
              </p>

              <p className="mt-6 italic">[signed] W. Hobson Consul & Lieutenant Governor</p>

              <p className="mt-6">
                Na ko matou ko nga Rangatira o te Wakaminenga o nga hapu o Nu Tirani ka huihui nei
                ki Waitangi ko matou hoki ko nga Rangatira o Nu Tirani ka kite nei i te ritenga o
                enei kupu. Ka tangohia ka wakaaetia katoatia e matou, koia ka tohungia ai o matou
                ingoa o matou tohu.
              </p>
              <p>
                Ka meatia tenei ki Waitangi i te ono o nga ra o Pepueri i te tau kotahi mano e waru
                rau e wa te kau o to tatou Ariki.
              </p>
              <p className="font-semibold">Ko nga Rangatira o te Wakaminenga</p>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="font-bold">The Treaty of Waitangi</h2>
            <div className="prose prose-slate text-sm leading-relaxed">
              <p>
                Her Majesty Victoria Queen of the United Kingdom of Great Britain and Ireland
                regarding with Her Royal Favor the Native Chiefs and Tribes of New Zealand and
                anxious to protect their just Rights and Property and to secure to them the
                enjoyment of Peace and Good Order has deemed it necessary in consequence of the
                great number of Her Majesty's Subjects who have already settled in New Zealand
                and the rapid extension of Emigration both from Europe and Australia which is
                still in progress to constitute and appoint a functionary properly authorized to
                treat with the Aborigines of New Zealand for the recognition of Her Majesty's
                sovereign authority over the whole or any part of those islands - Her Majesty
                therefore being desirous to establish a settled form of Civil Government with a
                view to avert the evil consequences which must result from the absence of the
                necessary Laws and Institutions alike to the native population and to Her subjects
                has been graciously pleased to empower and to authorize me William Hobson a Captain
                in Her Majesty's Royal Navy Consul and Lieutenant Governor of such parts of New
                Zealand as may be or hereafter shall be ceded to Her Majesty to invite the
                confederated and independent Chiefs of New Zealand to concur in the following
                Articles and Conditions.
              </p>

              <h4 className="font-semibold mt-6">Article the first</h4>
              <p>
                The Chiefs of the Confederation of the United Tribes of New Zealand and the
                separate and independent Chiefs who have not become members of the Confederation
                cede to Her Majesty the Queen of England absolutely and without reservation all
                the rights and powers of Sovereignty which the said Confederation or Individual
                Chiefs respectively exercise or possess, or may be supposed to exercise or to
                possess over their respective Territories as the sole sovereigns thereof.
              </p>

              <h4 className="font-semibold mt-6">Article the second</h4>
              <p>
                Her Majesty the Queen of England confirms and guarantees to the Chiefs and Tribes
                of New Zealand and to the respective families and individuals thereof the full
                exclusive and undisturbed possession of their Lands and Estates Forests Fisheries
                and other properties which they may collectively or individually possess so long
                as it is their wish and desire to retain the same in their possession; but the
                Chiefs of the United Tribes and the individual Chiefs, yield to Her Majesty the
                exclusive right of Preemption over such lands as the proprietors thereof may be
                disposed to alienate at such prices as may be agreed upon between the respective
                Proprietors and persons appointed by Her Majesty to treat with them in that behalf.
              </p>

              <h4 className="font-semibold mt-6">Article the third</h4>
              <p>
                In consideration thereof Her Majesty the Queen of England extends to the Natives
                of New Zealand Her royal protection and imparts to them all the Rights and
                Privileges of British Subjects.
              </p>

              <p className="mt-6 italic">[signed] W. Hobson Lieutenant Governor</p>

              <p className="mt-6">
                Now therefore We the Chiefs of the Confederation of the United Tribes of New
                Zealand being assembled in Congress at Victoria in Waitangi and We the Separate
                and Independent Chiefs of New Zealand claiming authority over the Tribes and
                Territories which are specified after our respective names, having been made
                fully to understand the Provisions of the foregoing Treaty, accept and enter
                into the same in the full spirit and meaning thereof in witness of which we
                have attached our signatures or marks at the places and the dates respectively
                specified.
              </p>
              <p>
                Done at Waitangi this Sixth day of February in the year of Our Lord one thousand
                eight hundred and forty.
              </p>
              <p className="font-semibold">The Chiefs of the Confederation</p>
            </div>
          </section>

          {/* Section 2: How Bowen Handles Treaty Queries */}
          <section id="how-bowen-handles" className="mb-12 border-t border-slate-200 pt-12">
            <h2 className="font-bold">How Bowen Handles Treaty Queries</h2>
            <p>
              Te Tiriti o Waitangi is foundational to New Zealand's legal system. It underpins our
              constitutional arrangements and increasingly permeates statute law across environmental,
              health, education, and governance domains. For a legal information tool like Bowen,
              handling Treaty matters requires particular care.
            </p>

            <h3>The Two Texts</h3>
            <p>
              Bowen recognises the material differences between the Māori and English texts of
              Te Tiriti. Article 2, for example, guarantees "tino rangatiratanga" in te reo Māori
              but "exclusive and undisturbed possession" in English—concepts that carry different
              weight and meaning.
            </p>

            <h3>Treaty Clauses in Legislation</h3>
            <p>
              Many modern NZ Acts contain Treaty clauses. Bowen's database includes legislation like:
            </p>
            <ul>
              <li>Treaty of Waitangi Act 1975</li>
              <li>Te Ture Whenua Maori Act 1993</li>
              <li>Resource Management Act 1991 (s8 — Treaty principles)</li>
              <li>Conservation Act 1987 (s4 — give effect to Treaty principles)</li>
              <li>Various Treaty settlement Acts</li>
            </ul>

            <h3>Historical Context</h3>
            <p>
              Bowen draws on curated scholarly references to provide historical context, including
              the evolution from <em>Wi Parata v Bishop of Wellington</em> (1877)—which dismissed
              the Treaty as "a simple nullity"—to the modern recognition of Treaty principles.
            </p>

            <h3>Ongoing Work</h3>
            <p>
              Bowen's approach to Treaty matters is evolving. We are working to
              expand coverage of Treaty settlement legislation, incorporate Waitangi Tribunal
              findings, and improve detection of Treaty-related queries.
            </p>
            <p>
              This is sensitive and important work. We welcome feedback from users, particularly
              those with expertise in Treaty jurisprudence.
            </p>
            <p>info@bowenpublic.com</p>
          </section>

          {/* Section 3: Essay */}
          <section id="essay" className="mb-12 border-t border-slate-200 pt-12">
            <h2 className="font-bold">From Possession to Ownership: Land Law and the Treaty in Colonial New Zealand</h2>
            <p className="text-sm text-slate-500 mb-4">
              Essay by Joe Davies, Founder 
            </p>

            <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 my-6">
              "Land is much more than the sods of earth that comprise it... socially land gives us
              somewhere to live, somewhere to build a family, somewhere to be an active citizen,
              it provides the blank canvas against which we shape our lives and our businesses."
              <footer className="text-sm mt-2">— Chris Bevan</footer>
            </blockquote>

            <p>
              In light of this quote it is important to consider how this blank canvas, providing
              peace and opportunity for our lives, is ultimately regulated through its title legal
              system, in checks and balances, documentation and processes providing legitimacy to
              the symbolic wax and seal.
            </p>

            <h3>Two Systems of Title</h3>
            <p>
              Kevin Gray and Susan Francis Gray write that the idea of title relativity, rooted in
              possession of property or land, is a fundamental aspect of land and property law.
              This principle states that ownership persists as long as possession is maintained,
              valid against all but superior claims.
            </p>
            <p>
              Stuart Banner states that by distinguishing between "land" as the physical substance
              and "property" as the conceptual framework governing rights to use land, we can
              observe in colonial New Zealand the imposition of two divergent property systems by
              the British and the Māori on the same land.
            </p>

            <h3>Māori Land Rights Before 1840</h3>
            <p>
              John White writes that prior to European influence on New Zealand, Māori traditionally
              distributed property rights based on function rather than geography, assigning them
              to individuals and families. For example, one family might utilise the same tree for
              fowling, while another would gather berries from it.
            </p>
            <p>
              The Māori did not have a written language and their land was inherited not from
              individual to individual but rather the hapū or the greater iwi, and distributed
              amongst its resources by rangatira.
            </p>

            <h3>The Treaty and Pre-emption</h3>
            <p>
              New Zealand as a British colony began in 1840, when the Treaty of Waitangi was signed by 500 Chiefs and
              a representative of Her Majesty Queen Victoria. Article Two gave the Crown the
              exclusive right of pre-emption—the sole right to purchase lands from Māori.
            </p>
            <p>
              This was tested in 1847 when Governor George Grey brought <em>R v Symonds</em> to the
              Supreme Court. Chief Justice William Martin ruled that "the sole and absolute right
              of pre-emption from the aboriginal inhabitants vest in and can only be exercised by
              her Majesty, her Heirs and Successors."
            </p>

            <h3>The Native Land Court</h3>
            <p>
              The overhaul came in 1865 when The Native Land Court was established by the colonial
              government. The court began to assign individual titles to Māori land. James Belich
              states that in 1800, the Māori owned over 60 million acres of land; by 1911, they
              owned only 7 million, much of which was not productive land.
            </p>

            <h3>Wi Parata and "A Simple Nullity"</h3>
            <p>
              In 1877, Wi Parata, a prominent Māori farmer and political figure, challenged
              Bishop Octavius Hadfield over the Anglican Church's failure to fulfil an agreement
              with Ngāti Toa. The court dismissed the case, with Chief Justice James Prendergast
              deeming the Treaty irrelevant to domestic law:
            </p>
            <blockquote className="border-l-4 border-slate-300 pl-4 italic text-slate-600 my-6">
              "So far indeed as that instrument purported to cede sovereignty... it must be
              regarded as a simple nullity. No body politic existed capable of making cession
              of sovereignty, nor could the thing itself exist."
            </blockquote>
            <p>
              This position dominated NZ law for over a century before being overturned by
              modern Treaty jurisprudence, beginning with the Lands Case in 1987.
            </p>

            <h3>Modern Interpretations</h3>
            <p>
              The rehabilitation of Te Tiriti began with the Treaty of Waitangi Act 1975, which
              established the Waitangi Tribunal to hear claims of Crown breaches against Treaty
              principles. Initially limited to prospective claims, the Tribunal's jurisdiction was
              extended in 1985 to cover historical grievances dating back to 1840.
            </p>
            <p>
              The watershed moment came in 1987 with <em>NZ Maori Council v Attorney-General</em>,
              commonly known as the Lands Case. The Court of Appeal rejected the Wi Parata doctrine,
              holding that the Treaty created obligations enforceable in law. President Cooke
              articulated foundational principles: the Treaty signified a partnership between Māori
              and the Crown, requiring both parties to act reasonably and in good faith.
            </p>
            <p>
              Subsequent jurisprudence has elaborated these principles. The Crown bears a duty of
              active protection—not merely passive recognition—of Māori interests. Where the Crown
              has breached its obligations, it must provide appropriate redress. The settlement
              process, now spanning several decades, has seen the Crown negotiate agreements with
              iwi across the country, combining formal apologies with cultural, financial, and
              land-based redress.
            </p>
            <p>
              Te Tiriti today occupies a unique constitutional position: not supreme law in the
              traditional sense, yet increasingly woven into statute and recognised by courts as
              fundamental to New Zealand's legal architecture. Its interpretation remains contested,
              with ongoing debate about the relationship between kāwanatanga and tino rangatiratanga,
              and how Treaty principles should inform contemporary governance. What is no longer
              contested is that Te Tiriti is far from "a simple nullity"—it stands as a living
              document at the heart of New Zealand's constitutional arrangements.
            </p>

            <h3>Conclusion</h3>
            <p>
              By the close of the nineteenth century, Māori found themselves stripped of the
              majority of their ancestral lands, along with their traditional land system of
              possession in use. An alternative framework for delineating land rights—that of
              title and ownership—had supplanted the old order.
            </p>
            <p>
              Recognising this history, it becomes evident that the legal framework governing
              land ownership plays a crucial role in shaping our societies. By exploring the
              historical evolution of land registration and the transition from possession-based
              to ownership-based titles, we gain valuable context for understanding New Zealand's
              legal jurisdiction—and why Te Tiriti remains central to it.
            </p>

            <h3>References</h3>
            <ul className="text-sm space-y-2">
              <li><em>Asher v Whitlock</em> (1865–66) LR 1 QB 1</li>
              <li>Banner, S. (1999). Two Properties, One Land: Law and Space in Nineteenth-Century New Zealand. <em>Law & Social Inquiry</em>, 24(4), 807-852.</li>
              <li>Belich, J. (1988). <em>The New Zealand Wars and the Victorian Interpretation of Racial Conflict</em>. Auckland: Penguin.</li>
              <li>Gray, K., & Gray, S. F. (1998). The idea of property in land. In S. Bright & J. Dewar (Eds.), <em>Land Law: Themes and Perspectives</em> (pp. 15–51). Oxford University Press.</li>
              <li>Gray, K., & Gray, S. F. (2011). <em>Land Law</em> (7th ed.). Oxford University Press.</li>
              <li>Keenan, S. (2015). <em>Subversive Property: Law and the Production of Spaces of Belonging</em>. Abingdon: Routledge.</li>
              <li>New Zealand History. (n.d.). Treaty of Waitangi. Retrieved from <a href="https://nzhistory.govt.nz/politics/treaty-of-waitangi" className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">nzhistory.govt.nz</a></li>
              <li>Oxford University Press. (2020). <em>Equity, Trusts & Land Law</em> (compiled for The Open University) (4th ed.).</li>
              <li><em>Pye v Graham</em> [2002] UKHL 30</li>
              <li><em>R v Symonds</em> SC Auckland (1847) NZHC 1; (1847) NZPCC 387</li>

              <li>Wards, I. (1968). <em>The Shadow of the Land: A Study of British Policy and Racial Conflict in New Zealand 1832-1852</em>. Wellington: Department of Internal Affairs.</li>
              <li>White, J. (1888). <em>The Ancient History of the Maori</em>. Wellington: George D.</li>
            </ul>
          </section>

          <section className="border-t border-slate-200 pt-8">
            <p className="text-sm text-slate-500">
              Bowen is a free public legal information tool. It provides information, not legal advice.
              For legal decisions involving Treaty matters, consult a qualified lawyer with expertise
              in this area.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
