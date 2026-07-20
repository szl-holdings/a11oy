// VENDORED FROM szl-holdings/platform@ed400a4f378330becd53346420b4d89ae8281dc5 — artifacts/sentra/src/pages/document-engine.tsx
// DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync.
import {
  BatchPdfPanel,
  DocumentEnginePanel,
  SigningDashboard,
} from '@szl-holdings/shared-ui/document-engine';
import { cn } from '@szl-holdings/shared-ui/utils';
import { motion } from 'framer-motion';
import { BookOpen, FileText, Layers, Pen } from 'lucide-react';
import { useState } from 'react';

const TABS = [
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'signing', label: 'Signing', icon: Pen },
  { id: 'pdf-batch', label: 'PDF Batches', icon: Layers },
] as const;

type TabId = (typeof TABS)[number]['id'];

export default function AegisDocumentEngine() {
  const [activeTab, setActiveTab] = useState<TabId>('documents');

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex-shrink-0"
      >
        <div className="flex items-center gap-3 px-6 pt-6 pb-0">
          <div className="w-8 h-8 rounded-xl bg-[#f5f5f5]/20 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-[#f5f5f5]" />
          </div>
          <div>
            <h1 className="text-xl font-display font-bold text-white">Document Engine</h1>
            <p className="text-xs text-white/40">
              Incident reports, compliance evidence, and audit documentation
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 px-6 pt-4 border-b border-white/10">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-t-lg border-b-2 transition-colors',
                  isActive
                    ? 'border-[#f5f5f5] text-[#f5f5f5] bg-[#f5f5f5]/5'
                    : 'border-transparent text-white/50 hover:text-white',
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </motion.div>

      <div className="flex-1 overflow-hidden">
        {activeTab === 'documents' && (
          <DocumentEnginePanel appSource="aegis" accentColor="#f5f5f5" className="h-full" />
        )}
        {activeTab === 'signing' && (
          <SigningDashboard appSource="aegis" accentColor="#f5f5f5" className="h-full" />
        )}
        {activeTab === 'pdf-batch' && (
          <BatchPdfPanel appSource="aegis" accentColor="#f5f5f5" className="h-full" />
        )}
      </div>
    </div>
  );
}
