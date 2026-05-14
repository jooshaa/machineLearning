import { Shell } from '@/components/shell';
import { TradeForm } from '@/components/trade-form';
import { TradeImportPanel } from '@/components/trade-import-panel';
import { TradeTable } from '@/components/trade-table';
import { getTrades } from '@/lib/api';

export default async function TradesPage() {
  const trades = await getTrades();

  return (
    <Shell>
      <div className="space-y-6">
        <TradeImportPanel />
        <TradeForm />
        <TradeTable trades={trades} />
      </div>
    </Shell>
  );
}
