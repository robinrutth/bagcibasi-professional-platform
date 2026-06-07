"use client";

import { OperationForm as OperationFormComponent } from "@/components/operations/OperationForm";

/**
 * Exposes the shipment creation/update form at the root component boundary.
 * Props: editingShipment, submitError, submitting, onCancelEdit, and onSubmit.
 */
export const OperationForm = OperationFormComponent;
