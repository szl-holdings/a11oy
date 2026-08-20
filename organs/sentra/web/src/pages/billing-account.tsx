import { BillingAccount } from '@szl-holdings/shared-ui/billing';

const ACCENT = '#f5f5f5';

export default function SentraBillingPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">Billing & Subscription</h1>
        <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.5)' }}>
          Manage your PARAGON subscription and payment details.
        </p>
      </div>
      <BillingAccount
        accentColor={ACCENT}
        pricingUrl="/pricing"
        productName="PARAGON"
      />
    </div>
  );
}
