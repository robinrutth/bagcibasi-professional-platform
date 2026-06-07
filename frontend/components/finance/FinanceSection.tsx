import { Carbon, Finance } from "@/types";

const money = (value: number) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);

const number = (value: number) =>
  new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value);

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function FinanceSection({ finance, carbon }: { finance: Finance; carbon: Carbon }) {
  return (
    <section className="gridTwo" id="finance">
      <div className="panel">
        <div className="sectionHead">
          <h2>Finans Yönetimi</h2>
          <span>15 gün tahmin</span>
        </div>
        <Metric label="Güncel kasa" value={money(finance.current_cash)} />
        <Metric label="Bekleyen tahsilat" value={money(finance.pending_collections)} />
        <Metric label="Beklenen çıkış" value={money(finance.projected_outflow)} />
        <Metric label="15 gün tahmini" value={money(finance.projected_cash_15_days)} />
        <p className="panelNote">{finance.ai_warning}</p>
      </div>

      <div className="panel" id="carbon">
        <div className="sectionHead">
          <h2>Carbon & ESG</h2>
          <span>Aylık özet</span>
        </div>
        <Metric label="Toplam CO2" value={`${number(carbon.total_co2_kg)} kg`} />
        <Metric label="En yüksek hat" value={carbon.highest_emission_route ?? "-"} />
        <p className="panelNote">{carbon.optimization_note}</p>
      </div>
    </section>
  );
}

