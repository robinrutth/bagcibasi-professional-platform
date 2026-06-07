import { Shipment } from "@/types";

function Badge({ value }: { value: string }) {
  const className = value === "Yüksek" ? "danger" : value === "Orta" ? "warning" : "success";
  return <span className={`badge ${className}`}>{value}</span>;
}

export function RiskPanel({ shipments }: { shipments: Shipment[] }) {
  const risky = shipments.filter((shipment) => shipment.risk_level !== "Düşük" || shipment.status === "Yolda");
  return (
    <div className="panel">
      <div className="sectionHead">
        <h2>Riskli Operasyonlar</h2>
        <span>{risky.length} kayıt</span>
      </div>
      <div className="riskList">
        {risky.map((shipment, index) => (
          <article key={`${shipment.customer_name}-${index}`}>
            <strong>{shipment.customer_name}</strong>
            <span>
              {shipment.origin} - {shipment.destination}
            </span>
            <Badge value={shipment.risk_level} />
          </article>
        ))}
      </div>
    </div>
  );
}

