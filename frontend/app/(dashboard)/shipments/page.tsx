"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { OperationForm } from "@/components/operations/OperationForm";
import { OperationsTable } from "@/components/operations/OperationsTable";
import { useAuth } from "@/hooks/useAuth";
import { usePermissions } from "@/hooks/usePermissions";
import { useShipmentOperations, useShipments } from "@/hooks/useShipments";

export default function ShipmentsPage() {
  const router = useRouter();
  const auth = useAuth();
  const permissions = usePermissions();
  const { shipments, error, reload } = useShipments({ limit: 100 });
  const shipmentOps = useShipmentOperations(shipments, reload);
  const canManage = permissions.can("shipments.*");

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) router.replace("/login");
  }, [auth.isAuthenticated, auth.ready, router]);

  if (!auth.ready || !auth.isAuthenticated) return null;

  return (
    <main className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Operasyon</p>
          <h1>Sevkiyatlar</h1>
        </div>
      </header>

      {(error || shipmentOps.shipmentError) && <div className="errorBanner">{error ?? shipmentOps.shipmentError}</div>}

      <section className="vertical" id="operations">
        {canManage && (
          <OperationForm
            editingShipment={shipmentOps.editingShipment}
            submitError={shipmentOps.shipmentError}
            submitting={shipmentOps.shipmentSubmitting}
            onCancelEdit={shipmentOps.cancelEdit}
            onSubmit={shipmentOps.submitShipment}
          />
        )}
        <OperationsTable
          shipments={shipments}
          canManage={canManage}
          onEdit={shipmentOps.selectShipmentForEdit}
          onDelete={shipmentOps.removeShipment}
          onImported={reload}
        />
      </section>
    </main>
  );
}
