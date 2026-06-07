"use client";

import { useCallback, useMemo, useState } from "react";

import type { AiAnalysis } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function readableError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function useQuote(accessToken: string) {
  const [prompt, setPrompt] = useState("İstanbul-Ankara arası 14 ton tekstil yükü");
  const [result, setResult] = useState<AiAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/ai/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) throw new Error("AI fiyat analizi alınamadı.");
      setResult(await response.json());
    } catch (requestError) {
      setError(readableError(requestError, "AI fiyat analizi alınamadı."));
    } finally {
      setLoading(false);
    }
  }, [accessToken, prompt]);

  return useMemo(
    () => ({
      prompt,
      setPrompt,
      result,
      loading,
      error,
      run,
    }),
    [error, loading, prompt, result, run],
  );
}
