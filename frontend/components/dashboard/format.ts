export const numberFormat = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });

export function formatNumber(value: number) {
  return numberFormat.format(value);
}

export function statusClass(value: string) {
  const normalized = value.toLocaleLowerCase("tr-TR");
  if (normalized.includes("teslim")) return "success";
  if (normalized.includes("iptal") || normalized.includes("gecik")) return "danger";
  if (normalized.includes("yolda") || normalized.includes("hazir") || normalized.includes("hazır")) return "warning";
  return "success";
}

export function emissionClass(value: number) {
  if (value <= 120) return "success";
  if (value <= 300) return "warning";
  return "danger";
}

export function emissionLabel(value: number) {
  if (value <= 120) return "Yeşil";
  if (value <= 300) return "Orta";
  return "Yüksek";
}

export function vehicleLabel(value: string) {
  const labels: Record<string, string> = {
    panelvan: "Panelvan / Hafif Ticari",
    kamyonet: "Kamyonet",
    kamyon: "Kamyon (On Teker)",
    tir: "Tır (Çekici + Yarı Römork)",
    elektrikli: "Elektrikli Araç",
    truck: "Kamyon (On Teker)",
    minivan: "Kamyonet",
    electric: "Elektrikli Araç",
  };
  return labels[value] ?? value;
}
