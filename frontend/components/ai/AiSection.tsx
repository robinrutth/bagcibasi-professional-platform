import { AiAnalysis } from "@/types";

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

export function AiSection({
  prompt,
  setPrompt,
  result,
  run,
}: {
  prompt: string;
  setPrompt: (value: string) => void;
  result: AiAnalysis | null;
  run: () => Promise<void>;
}) {
  return (
    <section className="gridTwo" id="ai">
      <div className="panel">
        <div className="sectionHead">
          <h2>AI Operasyon Asistanı</h2>
          <span>Doğal dil</span>
        </div>
        <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
        <button className="wideButton" onClick={run}>
          Analiz Et
        </button>
      </div>
      <div className="panel">
        <div className="sectionHead">
          <h2>AI Çıktısı</h2>
          <span>Teklif önerisi</span>
        </div>
        {result ? (
          <div className="aiResult">
            <Metric label="Araç" value={result.suggested_vehicle} />
            <Metric label="Teklif" value={money(result.estimated_price)} />
            <Metric label="Kâr" value={money(result.estimated_profit)} />
            <Metric label="CO2" value={`${number(result.estimated_co2_kg)} kg`} />
            <p className="panelNote">{result.summary}</p>
          </div>
        ) : (
          <p className="panelNote">Bir sevkiyat cümlesi yazıp analiz al.</p>
        )}
      </div>
    </section>
  );
}

