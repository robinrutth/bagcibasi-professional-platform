"use client";

type QuoteResultBoxProps = {
  distanceKm: number;
  invoiceAmount: number;
  formatNumber: (value: number) => string;
  formatMoney: (value: number) => string;
};

/**
 * Renders the calculated corporate quote summary.
 * Props: distanceKm, invoiceAmount, formatNumber, and formatMoney.
 */
export function QuoteResultBox({ distanceKm, invoiceAmount, formatNumber, formatMoney }: QuoteResultBoxProps) {
  return (
    <div className="quoteBox">
      <strong>
        Tahmini Mesafe: {formatNumber(distanceKm)} km | Kurumsal Teklif: {formatMoney(invoiceAmount)}
      </strong>
    </div>
  );
}
