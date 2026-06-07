"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createCustomer,
  deleteCustomer,
  getCustomer,
  getCustomerCarbonStats,
  getCustomers,
  getCustomerShipments,
  updateCustomer,
} from "@/lib/api/customers";
import type {
  Customer,
  CustomerCarbonStats,
  CustomerCreate,
  CustomerListParams,
  CustomerUpdate,
  CustomerWithShipments,
  PaginatedResponse,
} from "@/types";

const emptyPage: PaginatedResponse<Customer> = {
  items: [],
  total: 0,
  skip: 0,
  limit: 20,
};

function readableError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function useCustomers(params: CustomerListParams = {}) {
  const stableParams = useMemo(() => params, [JSON.stringify(params)]);
  const [data, setData] = useState<PaginatedResponse<Customer>>(emptyPage);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getCustomers(stableParams));
    } catch (requestError) {
      setError(readableError(requestError, "Müşteriler yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [stableParams]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return useMemo(
    () => ({
      customers: data.items,
      pagination: {
        total: data.total,
        skip: data.skip,
        limit: data.limit,
      },
      loading,
      error,
      reload,
    }),
    [data, error, loading, reload],
  );
}

export function useCustomer(id?: string) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [customerWithShipments, setCustomerWithShipments] = useState<CustomerWithShipments | null>(null);
  const [carbonStats, setCarbonStats] = useState<CustomerCarbonStats | null>(null);
  const [loading, setLoading] = useState(Boolean(id));
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [customerResponse, shipmentResponse, carbonResponse] = await Promise.all([
        getCustomer(id),
        getCustomerShipments(id),
        getCustomerCarbonStats(id),
      ]);
      setCustomer(customerResponse);
      setCustomerWithShipments(shipmentResponse);
      setCarbonStats(carbonResponse);
    } catch (requestError) {
      setError(readableError(requestError, "Müşteri kaydı yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return useMemo(
    () => ({
      customer,
      customerWithShipments,
      shipments: customerWithShipments?.shipments ?? [],
      carbonStats,
      loading,
      error,
      reload,
    }),
    [carbonStats, customer, customerWithShipments, error, loading, reload],
  );
}

export function useMutateCustomer() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async <T>(action: () => Promise<T>) => {
    setLoading(true);
    setError(null);
    try {
      return await action();
    } catch (requestError) {
      const message = readableError(requestError, "Müşteri işlemi tamamlanamadı.");
      setError(message);
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, []);

  return useMemo(
    () => ({
      loading,
      error,
      create: (data: CustomerCreate) => run(() => createCustomer(data)),
      update: (id: string, data: CustomerUpdate) => run(() => updateCustomer(id, data)),
      remove: (id: string) => run(() => deleteCustomer(id)),
    }),
    [error, loading, run],
  );
}
