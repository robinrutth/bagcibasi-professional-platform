"use client";

import type { FormEvent } from "react";
import { useState } from "react";

import { vehicleLabel } from "@/components/dashboard/format";
import { downloadInvoice, emailInvoice } from "@/lib/api/documents";
import { downloadShipmentTemplate, exportShipmentsCSV, exportShipmentsExcel, importShipments, type ImportResult } from "@/lib/api/exports";
import { Shipment } from "@/types";

const money = (value: number) =>
  new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(value);

const number = (value: number) =>
  new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value);

function Badge({ value }: { value: string }) {
  const className = value === "Yüksek" ? "danger" : value === "Orta" ? "warning" : "success";
  return <span className={`badge ${className}`}>{value}</span>;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "Taslak") {
    return (
      <span className="badge" style={{ background: "#e5e7eb", color: "#4b5563" }}>
        {status}
      </span>
    );
  }
  if (status === "Hazırlanıyor") {
    return <span className="badge warning">{status}</span>;
  }
  if (status === "Tamamlandı") {
    return <span className="badge success">{status}</span>;
  }
  if (status === "İptal") {
    return <span className="badge danger">{status}</span>;
  }
  return <span className="badge">{status}</span>;
}

export function OperationsTable({
  shipments,
  canManage = false,
  onEdit,
  onDelete,
  onImported,
}: {
  shipments: Shipment[];
  canManage?: boolean;
  onEdit?: (shipment: Shipment) => void;
  onDelete?: (shipment: Shipment) => Promise<void>;
  onImported?: () => Promise<void>;
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [exporting, setExporting] = useState<"csv" | "excel" | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const filteredShipments = searchTerm.trim()
    ? shipments.filter((s) => s.customer_name?.toLowerCase().includes(searchTerm.toLowerCase()))
    : shipments;

  async function runDocumentAction(shipmentId: string, action: () => Promise<unknown>) {
    setBusyId(shipmentId);
    try {
      await action();
    } finally {
      setBusyId(null);
    }
  }

  async function runDelete(shipment: Shipment) {
    if (!onDelete) return;
    setBusyId(shipment.id);
    try {
      await onDelete(shipment);
    } finally {
      setBusyId(null);
    }
  }

  async function runExport(type: "csv" | "excel") {
    setExporting(type);
    try {
      if (type === "csv") await exportShipmentsCSV();
      if (type === "excel") await exportShipmentsExcel();
    } finally {
      setExporting(null);
    }
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!importFile) return;
    setImporting(true);
    setImportError(null);
    try {
      const result = await importShipments(importFile);
      setImportResult(result);
      await onImported?.();
    } catch (requestError) {
      setImportError(requestError instanceof Error ? requestError.message : "İçe aktarma tamamlanamadı.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <section className="panel tablePanel">
      <div className="sectionHead">
        <h2>Operasyon Listesi</h2>
        <div className="headerActions">
          <span>{filteredShipments.length} operasyon</span>
          <input
            type="text"
            placeholder="Müşteri ara..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              padding: "6px 12px",
              border: "1px solid #d1d5db",
              borderRadius: 6,
              fontSize: 14,
              outline: "none",
              width: 200,
            }}
          />
          {canManage && (
            <button className="secondaryButton" type="button" onClick={() => setIsImportOpen(true)}>
              Excel İçe Aktar
            </button>
          )}
          <div className="exportMenu">
            <button className="secondaryButton" type="button" disabled={Boolean(exporting)}>
              {exporting ? <span className="tinySpinner" aria-label="İndiriliyor" /> : "Dışa Aktar"}
            </button>
            <div className="exportMenuPanel">
              <button type="button" onClick={() => void runExport("csv")} disabled={Boolean(exporting)}>
                CSV
              </button>
              <button type="button" onClick={() => void runExport("excel")} disabled={Boolean(exporting)}>
                Excel
              </button>
            </div>
          </div>
        </div>
      </div>
      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              <th>Müşteri</th>
              <th>Güzergah</th>
              <th>Araç</th>
              <th>Fatura</th>
              <th>Kâr</th>
              <th>CO2</th>
              <th>Emisyon Sınıfı</th>
              <th>Durum</th>
              <th>Doküman</th>
              {canManage && <th>Aksiyon</th>}
            </tr>
          </thead>
          <tbody>
            {filteredShipments.map((shipment, index) => (
              <tr key={`${shipment.customer_name}-${index}`}>
                <td>{shipment.customer_name}</td>
                <td>
                  {shipment.origin} - {shipment.destination}
                </td>
                <td>{vehicleLabel(shipment.vehicle_type)}</td>
                <td>{money(shipment.invoice ?? shipment.invoice_amount)}</td>
                <td>{money(shipment.profit ?? shipment.profit_amount)}</td>
                <td>{number(shipment.co2_kg)} kg</td>
                <td>
                  <Badge value={shipment.risk_level} />
                </td>
                <td>
                  <StatusBadge status={shipment.status} />
                </td>
                <td>
                  <div className="rowActions">
                    <button
                      className="miniButton"
                      disabled={busyId === shipment.id}
                      onClick={() => void runDocumentAction(shipment.id, () => downloadInvoice(shipment.id))}
                    >
                      Fatura İndir
                    </button>
                    <button
                      className="miniButton"
                      disabled={busyId === shipment.id}
                      onClick={() => void runDocumentAction(shipment.id, () => emailInvoice(shipment.id))}
                    >
                      E-posta
                    </button>
                  </div>
                </td>
                {canManage && (
                  <td>
                    <div className="rowActions">
                      <button className="miniButton" onClick={() => onEdit?.(shipment)}>
                        Düzenle
                      </button>
                      <button className="miniButton dangerText" disabled={busyId === shipment.id} onClick={() => void runDelete(shipment)}>
                        Sil
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {isImportOpen && (
        <div className="modalBackdrop" role="presentation">
          <form className="modalPanel importModal" onSubmit={(event) => void submitImport(event)}>
            <div className="sectionHead">
              <h2>Excel İçe Aktar</h2>
              <button className="miniButton" type="button" onClick={() => setIsImportOpen(false)}>
                Kapat
              </button>
            </div>
            <input
              required
              type="file"
              accept=".xlsx,.csv"
              onChange={(event) => {
                setImportFile(event.target.files?.[0] ?? null);
                setImportResult(null);
                setImportError(null);
              }}
            />
            <div className="rowActions">
              <button className="secondaryButton" type="button" onClick={() => void downloadShipmentTemplate()}>
                Şablon İndir
              </button>
              <button className="wideButton dashboardLogout" disabled={importing || !importFile}>
                {importing ? <span className="tinySpinner" aria-label="Yükleniyor" /> : "Yükle"}
              </button>
            </div>
            {importResult && (
              <div className="quoteBox">
                <strong>
                  {importResult.success} kayıt eklendi, {importResult.errors} hata
                </strong>
              </div>
            )}
            {importError && <div className="errorBanner">{importError}</div>}
          </form>
        </div>
      )}
    </section>
  );
}
