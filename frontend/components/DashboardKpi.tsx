import { KpiGrid } from "@/components/dashboard/KpiGrid";
import type { DashboardSummary } from "@/types";

/**
 * Displays dashboard KPI cards from the provided summary data.
 * Props: dashboard.
 */
export function DashboardKpi({ dashboard }: { dashboard: DashboardSummary }) {
  return <KpiGrid dashboard={dashboard} />;
}
