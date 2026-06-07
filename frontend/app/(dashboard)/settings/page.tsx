"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { useAuth } from "@/hooks/useAuth";
import { usePermissions } from "@/hooks/usePermissions";
import { useToast } from "@/hooks/useToast";
import { updateCurrentUser } from "@/lib/api/auth";
import { apiRequest } from "@/lib/api/client";

const PLATFORM_SETTINGS_KEY = "bagcibasi_platform_settings";

type PlatformSettings = {
  platformName: string;
  currency: string;
  basePrice: number;
  profitMargin: number;
};

const defaultPlatformSettings: PlatformSettings = {
  platformName: "Bagcibasi Logistics AI Platform",
  currency: "TRY",
  basePrice: 250,
  profitMargin: 28,
};

function loadPlatformSettings() {
  if (typeof window === "undefined") return defaultPlatformSettings;
  const stored = window.localStorage.getItem(PLATFORM_SETTINGS_KEY);
  if (!stored) return defaultPlatformSettings;
  try {
    return { ...defaultPlatformSettings, ...(JSON.parse(stored) as Partial<PlatformSettings>) };
  } catch {
    return defaultPlatformSettings;
  }
}

export default function SettingsPage() {
  const router = useRouter();
  const auth = useAuth();
  const permissions = usePermissions();
  const toast = useToast();
  const [platformSettings, setPlatformSettings] = useState<PlatformSettings>(defaultPlatformSettings);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSubmitting, setProfileSubmitting] = useState(false);
  const [platformMessage, setPlatformMessage] = useState<string | null>(null);
  const [passwordMessage, setPasswordMessage] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const isAdmin = permissions.role === "admin";

  useEffect(() => {
    setPlatformSettings(loadPlatformSettings());
  }, []);

  function readableError(error: unknown, fallback: string) {
    if (!(error instanceof Error)) return fallback;
    try {
      const parsed = JSON.parse(error.message) as { detail?: string | Array<{ msg?: string }> };
      if (typeof parsed.detail === "string") return parsed.detail;
      if (Array.isArray(parsed.detail)) return parsed.detail.map((item) => item.msg).filter(Boolean).join(", ") || fallback;
    } catch {
      return error.message || fallback;
    }
    return fallback;
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const fullName = String(form.get("full_name") ?? "").trim();

    setProfileMessage(null);
    setProfileError(null);
    setProfileSubmitting(true);
    try {
      const updatedUser = await updateCurrentUser({ full_name: fullName, password: null });
      auth.updateUser(updatedUser);
      setProfileMessage("Bilgileriniz guncellendi");
      toast.success("Bilgileriniz guncellendi");
    } catch (requestError) {
      const message = `Guncelleme basarisiz: ${readableError(requestError, "Profil guncellenemedi.")}`;
      setProfileError(message);
      toast.error(message);
    } finally {
      setProfileSubmitting(false);
    }
  }

  function savePlatformSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    window.localStorage.setItem(PLATFORM_SETTINGS_KEY, JSON.stringify(platformSettings));
    setPlatformMessage("Platform ayarlari kaydedildi.");
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const currentPassword = String(form.get("current_password") ?? "");
    const newPassword = String(form.get("new_password") ?? "");
    const repeatPassword = String(form.get("repeat_password") ?? "");

    setPasswordMessage(null);
    setPasswordError(null);

    if (newPassword !== repeatPassword) {
      setPasswordError("Yeni sifreler eslesmiyor.");
      return;
    }
    if (newPassword.length < 6) {
      setPasswordError("Yeni sifre en az 6 karakter olmali.");
      return;
    }

    setPasswordSubmitting(true);
    try {
      await apiRequest("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      formElement.reset();
      const message = "Sifreniz basariyla guncellendi. Lutfen tekrar giris yapin.";
      setPasswordMessage(message);
      toast.success(message);
      await auth.logout();
      router.replace("/login");
    } catch (requestError) {
      const message = `Guncelleme basarisiz: ${readableError(requestError, "Sifre degistirilemedi.")}`;
      setPasswordError(message);
      toast.error(message);
    } finally {
      setPasswordSubmitting(false);
    }
  }

  return (
    <ProtectedRoute requiredPermission="settings.read">
      <main className="dashboardPage">
        <header className="dashboardHeader">
          <div>
            <p className="eyebrow">Yonetim</p>
            <h1>Ayarlar</h1>
          </div>
        </header>

        <section className="gridTwo">
          <form className="panel settingsForm" onSubmit={saveProfile}>
            <div className="sectionHead">
              <h2>Kullanici Profili</h2>
              <span>{auth.user?.role ?? "rol"}</span>
            </div>
            <label>
              <span>Ad</span>
              <input name="full_name" defaultValue={auth.user?.full_name ?? ""} placeholder="Ad soyad" />
            </label>
            <label>
              <span>Email</span>
              <input name="email" type="email" defaultValue={auth.user?.username ?? ""} placeholder="email@firma.com" disabled />
            </label>
            <button className="wideButton" type="submit" disabled={profileSubmitting}>
              {profileSubmitting ? "Kaydediliyor" : "Profili Kaydet"}
            </button>
            {profileMessage && <p className="panelNote">{profileMessage}</p>}
            {profileError && <div className="errorBanner">{profileError}</div>}
          </form>

          <form className="panel settingsForm" onSubmit={changePassword}>
            <div className="sectionHead">
              <h2>Sifre Degistir</h2>
              <span>Guvenlik</span>
            </div>
            <label>
              <span>Mevcut sifre</span>
              <input name="current_password" type="password" autoComplete="current-password" required />
            </label>
            <label>
              <span>Yeni sifre</span>
              <input name="new_password" type="password" autoComplete="new-password" minLength={6} required />
            </label>
            <label>
              <span>Yeni sifre tekrar</span>
              <input name="repeat_password" type="password" autoComplete="new-password" minLength={6} required />
            </label>
            <button className="wideButton" type="submit" disabled={passwordSubmitting}>
              {passwordSubmitting ? "Guncelleniyor" : "Sifreyi Guncelle"}
            </button>
            {passwordMessage && <p className="settingsSuccess">{passwordMessage}</p>}
            {passwordError && <div className="errorBanner">{passwordError}</div>}
          </form>
        </section>

        {isAdmin ? (
          <form className="panel settingsForm" onSubmit={savePlatformSettings}>
            <div className="sectionHead">
              <h2>Platform Ayarlari</h2>
              <span>Sadece admin</span>
            </div>
            <div className="settingsGrid">
              <label>
                <span>Platform adi</span>
                <input
                  value={platformSettings.platformName}
                  onChange={(event) => setPlatformSettings((current) => ({ ...current, platformName: event.target.value }))}
                />
              </label>
              <label>
                <span>Para birimi</span>
                <input
                  value={platformSettings.currency}
                  onChange={(event) => setPlatformSettings((current) => ({ ...current, currency: event.target.value || "TRY" }))}
                />
              </label>
              <label>
                <span>Taban fiyat</span>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={platformSettings.basePrice}
                  onChange={(event) => setPlatformSettings((current) => ({ ...current, basePrice: Number(event.target.value) || 0 }))}
                />
              </label>
              <label>
                <span>Kar marji (%)</span>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={platformSettings.profitMargin}
                  onChange={(event) => setPlatformSettings((current) => ({ ...current, profitMargin: Number(event.target.value) || 0 }))}
                />
              </label>
            </div>
            <button className="wideButton" type="submit">
              Platform Ayarlarini Kaydet
            </button>
            {platformMessage && <p className="settingsSuccess">{platformMessage}</p>}
          </form>
        ) : (
          <section className="panel">
            <div className="sectionHead">
              <h2>Platform Ayarlari</h2>
              <span>admin</span>
            </div>
            <p className="panelNote">Bu alan yalnizca admin rolune aciktir.</p>
          </section>
        )}
      </main>
    </ProtectedRoute>
  );
}
