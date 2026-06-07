import { DashboardSummary } from "@/types";

const money = (value: number) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);

const number = (value: number) =>
  new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value);

function Kpi({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <article className="kpi">
      <span>{title}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

export function KpiGrid({ dashboard }: { dashboard: DashboardSummary }) {
  return (
    <section className="kpiGrid">
      <Kpi title="Toplam Ciro" value={money(dashboard.total_revenue)} detail="Fatura toplamı" />
      <Kpi title="Toplam Kâr" value={money(dashboard.total_profit)} detail="Operasyon kârı" />
      <Kpi title="Aktif Operasyon" value={String(dashboard.active_operations)} detail="Yolda / hazırlanıyor" />
      <Kpi title="Teslim Başarı" value={`%${number(dashboard.delivery_success_rate)}`} detail={`${number(dashboard.total_co2_kg)} kg CO2`} />
    </section>
  );
}

