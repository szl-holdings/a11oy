// VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — artifacts/sentra/src/components/CopyLinkButton.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import { toast } from '@szl-holdings/shared-ui/ui/sonner';
import { Check, Link as LinkIcon } from 'lucide-react';
import { useState } from 'react';

interface CopyLinkButtonProps {
  accent: string;
  label?: string;
}

export function CopyLinkButton({ accent, label = 'Copy link' }: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const url = typeof window !== 'undefined' ? window.location.href : '';
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else {
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
      }
      setCopied(true);
      toast.success('Link copied to clipboard');
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Failed to copy link');
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      aria-label="Copy shareable link to this view"
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors"
      style={{ background: `${accent}14`, color: accent, border: `1px solid ${accent}33` }}
    >
      {copied ? <Check className="w-3 h-3" /> : <LinkIcon className="w-3 h-3" />}
      {copied ? 'Copied' : label}
    </button>
  );
}
