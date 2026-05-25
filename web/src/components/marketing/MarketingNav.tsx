import { Button } from '@szl-holdings/shared-ui/ui/button';
import { Link } from 'wouter';

export function MarketingNav() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-black/50 backdrop-blur-md">
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
        <Link href="/marketing" className="text-xl font-bold text-white tracking-tight">
          SZL<span className="text-white/50">/COMMAND</span>
        </Link>

        <div className="hidden md:flex items-center space-x-8 text-sm font-medium text-white/70">
          <div className="group relative">
            <span className="cursor-pointer hover:text-white transition-colors">Ecosystem</span>
            <div className="absolute top-full left-0 pt-4 hidden group-hover:block">
              <div className="bg-[#111] border border-white/10 rounded-lg p-4 w-64 shadow-2xl">
                <Link
                  href="/marketing/apps/terra"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  DOMAINE
                </Link>
                <Link
                  href="/marketing/apps/vessels"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  SEXTANT
                </Link>
                <Link
                  href="/marketing/apps/lyte"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  KORA
                </Link>
                <Link
                  href="/sentra/"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  Sentra
                </Link>
                <Link
                  href="/marketing/apps/prism"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  Counsel
                </Link>
                <Link
                  href="/marketing/apps/szl-holdings"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  SZL Holdings
                </Link>
                <Link
                  href="/marketing/apps/carlota-jo"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  Carlota Jo
                </Link>
                <Link
                  href="/marketing/apps/stephen"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  Stephen
                </Link>
                <Link
                  href="/marketing/apps/command"
                  className="block p-2 hover:bg-white/5 rounded text-white transition-colors"
                >
                  Command
                </Link>
              </div>
            </div>
          </div>
          <Link href="/marketing/pricing" className="hover:text-white transition-colors">
            Pricing
          </Link>
          <Link href="/marketing/status" className="hover:text-white transition-colors">
            Status
          </Link>
        </div>

        <div className="flex items-center space-x-4">
          <Link
            href="/"
            className="text-sm font-medium text-white/70 hover:text-white transition-colors"
          >
            Login
          </Link>
          <Link href="/marketing/signup">
            <Button variant="default" className="bg-white text-black hover:bg-white/90">
              Get Started
            </Button>
          </Link>
        </div>
      </div>
    </nav>
  );
}
