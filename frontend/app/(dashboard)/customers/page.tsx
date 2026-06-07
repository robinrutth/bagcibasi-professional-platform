"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";
import { useCustomers, useMutateCustomer } from "@/hooks/useCustomers";
import { usePermissions } from "@/hooks/usePermissions";
import { downloadCustomerTemplate, importCustomers, type ImportResult } from "@/lib/api/exports";
import type { Customer, CustomerCreate } from "@/types";

const pageSize = 10;

const emptyForm: CustomerCreate = {
  name: "",
  email: "",
  phone: "",
  address: "",
  city: "",
  tax_number: "",
  sector: "",
  payment_terms: "Vadeli",
  risk_level: "Dusuk",
  notes: "",
  is_active: true,
};

function normalizeForm(form: CustomerCreate): CustomerCreate {
  return Object.fromEntries(
    Object.entries(form).map(([key, value]) => [key, typeof value === "string" && value.trim() === "" ? null : value]),
  ) as CustomerCreate;
}

export default function CustomersPage() {
  const router = useRouter();
  const auth = useAuth();
  const permissions = usePermissions();
  const [search, setSearch] = useState("");
  const [city, setCity] = useState("");
  const [page, setPage] = useState(0);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerCreate>(emptyForm);
  const params = useMemo(
    () => ({ skip: page * pageSize, limit: pageSize, search, city }),
    [city, page, search],
  );
  const { customers, pagination, loading, error, reload } = useCustomers(params);
  const mutation = useMutateCustomer();
  const canManage = permissions.can("customers.*");

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) router.replace("/login");
  }, [auth.isAuthenticated, auth.ready, router]);

  function openCreate() {
    setEditingCustomer(null);
    setForm(emptyForm);
    setIsModalOpen(true);
  }

  function openEdit(customer: Customer) {
    setEditingCustomer(customer);
    setForm({
      name: customer.name,
      email: customer.email ?? "",
      phone: customer.phone ?? "",
      address: customer.address ?? "",
      city: customer.city ?? "",
      tax_number: customer.tax_number ?? "",
      sector: customer.sector ?? "",
      payment_terms: customer.payment_terms,
      risk_level: customer.risk_level,
      notes: customer.notes ?? "",
      is_active: customer.is_active,
    });
    setIsModalOpen(true);
  }

  async function submitForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = normalizeForm(form);
    if (editingCustomer) {
      await mutation.update(editingCustomer.id, payload);
    } else {
      await mutation.create(payload);
    }
    setIsModalOpen(false);
    await reload();
  }

  async function removeCustomer(customer: Customer) {
    if (!window.confirm(`${customer.name} pasife alınsın mı?`)) return;
    await mutation.remove(customer.id);
    await reload();
  }

  async function submitImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!importFile) return;
    setImporting(true);
    setImportError(null);
    try {
      const result = await importCustomers(importFile);
      setImportResult(result);
      await reload();
    } catch (requestError) {
      setImportError(requestError instanceof Error ? requestError.message : "İçe aktarma tamamlanamadı.");
    } finally {
      setImporting(false);
    }
  }

  if (!auth.ready || !auth.isAuthenticated) return null;

  return (
    <main className="dashboardPage">
      <header className="dashboardHeader">
        <div>
          <p className="eyebrow">Müşteri operasyonları</p>
          <h1>Müşteriler</h1>
        </div>
        <div className="headerActions">
          <Link className="secondaryButton" href="/dashboard">
            Dashboard
          </Link>
          {canManage && (
            <>
              <button className="secondaryButton" onClick={() => setIsImportOpen(true)}>
                Excel İçe Aktar
              </button>
              <button className="wideButton dashboardLogout" onClick={openCreate}>
                Yeni müşteri
              </button>
            </>
          )}
        </div>
      </header>

      {(error || mutation.error) && <div className="errorBanner">{error ?? mutation.error}</div>}

      <section className="panel">
        <div className="customerToolbar">
          <input
            placeholder="İsim, e-posta, telefon veya vergi no ara"
            value={search}
            onChange={(event) => {
              setPage(0);
              setSearch(event.target.value);
            }}
          />
          <input
            placeholder="Şehir filtrele"
            value={city}
            onChange={(event) => {
              setPage(0);
              setCity(event.target.value);
            }}
          />
        </div>
      </section>

      <section className="panel tablePanel">
        <div className="sectionHead">
          <h2>Müşteri Listesi</h2>
          <span>{loading ? "Yükleniyor" : `${pagination.total} kayıt`}</span>
        </div>
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Ad</th>
                <th>Şehir</th>
                <th>E-posta</th>
                <th>Telefon</th>
                <th>Emisyon Sınıfı</th>
                <th>Durum</th>
                <th>Aksiyon</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr key={customer.id}>
                  <td>{customer.name}</td>
                  <td>{customer.city ?? "-"}</td>
                  <td>{customer.email ?? "-"}</td>
                  <td>{customer.phone ?? "-"}</td>
                  <td>
                    <span className={`badge ${customer.risk_level === "Yuksek" ? "danger" : customer.risk_level === "Orta" ? "warning" : "success"}`}>
                      {customer.risk_level}
                    </span>
                  </td>
                  <td>{customer.is_active ? "Aktif" : "Pasif"}</td>
                  <td>
                    <div className="rowActions">
                      <Link className="miniButton" href={`/customers/${customer.id}`}>
                        Detay
                      </Link>
                      {canManage && (
                        <>
                          <button className="miniButton" onClick={() => openEdit(customer)}>
                            Düzenle
                          </button>
                          <button className="miniButton dangerText" onClick={() => void removeCustomer(customer)}>
                            Sil
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {customers.length === 0 && !loading && <div className="emptyState">Müşteri bulunamadı.</div>}
        <div className="paginationBar">
          <button className="secondaryButton" disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>
            Önceki
          </button>
          <span>
            Sayfa {page + 1} / {Math.max(1, Math.ceil(pagination.total / pageSize))}
          </span>
          <button
            className="secondaryButton"
            disabled={(page + 1) * pageSize >= pagination.total}
            onClick={() => setPage((value) => value + 1)}
          >
            Sonraki
          </button>
        </div>
      </section>

      {isModalOpen && (
        <div className="modalBackdrop" role="presentation">
          <form className="modalPanel customerForm" onSubmit={(event) => void submitForm(event)}>
            <div className="sectionHead">
              <h2>{editingCustomer ? "Müşteri düzenle" : "Yeni müşteri"}</h2>
              <button className="miniButton" type="button" onClick={() => setIsModalOpen(false)}>
                Kapat
              </button>
            </div>
            <input required placeholder="Müşteri adı" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            <input placeholder="E-posta" value={form.email ?? ""} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            <input placeholder="Telefon" value={form.phone ?? ""} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
            <input placeholder="Şehir" value={form.city ?? ""} onChange={(event) => setForm({ ...form, city: event.target.value })} />
            <input placeholder="Vergi no" value={form.tax_number ?? ""} onChange={(event) => setForm({ ...form, tax_number: event.target.value })} />
            <input placeholder="Sektor" value={form.sector ?? ""} onChange={(event) => setForm({ ...form, sector: event.target.value })} />
            <select value={form.risk_level} onChange={(event) => setForm({ ...form, risk_level: event.target.value })}>
              <option value="Dusuk">Düşük</option>
              <option value="Orta">Orta</option>
              <option value="Yuksek">Yüksek</option>
            </select>
            <input placeholder="Ödeme koşulu" value={form.payment_terms} onChange={(event) => setForm({ ...form, payment_terms: event.target.value })} />
            <textarea placeholder="Adres / not" value={form.address ?? ""} onChange={(event) => setForm({ ...form, address: event.target.value })} />
            <button className="wideButton" disabled={mutation.loading}>
              {mutation.loading ? "Kaydediliyor" : "Kaydet"}
            </button>
          </form>
        </div>
      )}

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
              <button className="secondaryButton" type="button" onClick={() => void downloadCustomerTemplate()}>
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
    </main>
  );
}
