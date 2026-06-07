"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getCarbonSummary, getCarbonTrend } from "@/lib/api/carbon";
import type { CarbonFilters, CarbonSummary, CarbonTrend } from "@/types";

const emptySummary: CarbonSummary = {
  total_co2: 0,
  by_vehicle: [],
  trend: [],
  top_routes: [],
};

function readableError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function useCarbonSummary(filters: CarbonFilters = {}) {
  const stableFilters = useMemo(() => filters, [JSON.stringify(filters)]);
  const [summary, setSummary] = useState<CarbonSummary>(emptySummary);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await getCarbonSummary(stableFilters));
    } catch (requestError) {
      setError(readableError(requestError, "Karbon özeti yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [stableFilters]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return useMemo(() => ({ summary, loading, error, reload }), [error, loading, reload, summary]);
}

export function useCarbonTrend(period: "daily" | "weekly" | "monthly" = "weekly", filters: CarbonFilters = {}) {
  const stableFilters = useMemo(() => filters, [JSON.stringify(filters)]);
  const [trend, setTrend] = useState<CarbonTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTrend(await getCarbonTrend(period, stableFilters));
    } catch (requestError) {
      setError(readableError(requestError, "Karbon trendi yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [period, stableFilters]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return useMemo(() => ({ trend, loading, error, reload }), [error, loading, reload, trend]);
}
