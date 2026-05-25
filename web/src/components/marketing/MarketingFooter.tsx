import { aboutSzlParagraph, copyrightLine } from '@szl-holdings/brand-registry';
import { Link } from 'wouter';

export function MarketingFooter() {
  return (
    <footer className="bg-black py-20 border-t border-white/10 text-white/60 text-sm">
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 md:grid-cols-4 gap-12">
        <div className="col-span-1 md:col-span-2">
          <Link
            href="/marketing"
            className="text-xl font-bold text-white tracking-tight mb-4 inline-block"
          >
            SZL<span className="text-white/50">/COMMAND</span>
          </Link>
          <p className="max-w-sm mb-6 leading-relaxed">{aboutSzlParagraph()}</p>
          <p>{copyrightLine()}</p>
        </div>

        <div>
          <h4 className="text-white font-medium mb-4">Platforms</h4>
          <ul className="space-y-3">
            <li>
              <Link href="/sentra/" className="hover:text-white transition-colors">
                Sentra
              </Link>
            </li>
            <li>
              <Link href="/marketing/apps/vessels" className="hover:text-white transition-colors">
                SEXTANT
              </Link>
            </li>
            <li>
              <Link href="/marketing/apps/terra" className="hover:text-white transition-colors">
                DOMAINE
              </Link>
            </li>
            <li>
              <Link href="/marketing/apps/lyte" className="hover:text-white transition-colors">
                KORA
              </Link>
            </li>
            <li>
              <Link href="/marketing/apps/prism" className="hover:text-white transition-colors">
                Counsel
              </Link>
            </li>
          </ul>
        </div>

        <div>
          <h4 className="text-white font-medium mb-4">Company</h4>
          <ul className="space-y-3">
            <li>
              <Link href="/marketing/pricing" className="hover:text-white transition-colors">
                Pricing
              </Link>
            </li>
            <li>
              <Link href="/marketing/status" className="hover:text-white transition-colors">
                System Status
              </Link>
            </li>
            <li>
              <a href="/trust-center" className="hover:text-white transition-colors">
                Trust Center
              </a>
            </li>
            <li>
              <a
                href="mailto:contact@szlholdings.com"
                className="hover:text-white transition-colors"
              >
                Contact Sales
              </a>
            </li>
          </ul>
        </div>
      </div>
    </footer>
  );
}
