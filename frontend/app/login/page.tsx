"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/hooks/useAuth";

export default function LoginPage() {
  const router = useRouter();
  const auth = useAuth();
  const [message, setMessage] = useState("Kullanıcı bilgilerinizle giriş yapın.");

  useEffect(() => {
    if (auth.ready && auth.isAuthenticated) {
      router.replace("/");
    }
  }, [auth.ready, auth.isAuthenticated, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await auth.login(String(form.get("username")), String(form.get("password")));
      router.replace("/");
    } catch {
      setMessage("Giriş başarısız. Bilgileri kontrol et.");
    }
  }

  if (!auth.ready) return null;

  return (
    <main className="loginPage">
      <section className="loginCard">
        <h1>Bağcıbaşı Logistics</h1>
        <p className="panelNote">Production authentication aktif.</p>
        <form className="loginForm vertical" onSubmit={onSubmit}>
          <input name="username" placeholder="Kullanıcı adı" />
          <input name="password" type="password" placeholder="Şifre" />
          <button type="submit">Giriş Yap</button>
        </form>
        <p className="panelNote">{message}</p>
      </section>
    </main>
  );
}
