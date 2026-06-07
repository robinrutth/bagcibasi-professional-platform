"use client";

import { AiSection } from "@/components/ai/AiSection";
import type { AiAnalysis } from "@/types";

type AiAnalysisPanelProps = {
  prompt: string;
  setPrompt: (value: string) => void;
  result: AiAnalysis | null;
  loading?: boolean;
  error?: string | null;
  run: () => Promise<void>;
};

/**
 * Provides the interactive AI logistics quote analysis panel.
 * Props: prompt, setPrompt, result, loading, error, and run.
 */
export function AiAnalysisPanel({ prompt, setPrompt, result, loading, error, run }: AiAnalysisPanelProps) {
  return (
    <>
      <AiSection prompt={prompt} setPrompt={setPrompt} result={result} run={run} />
      {loading && <div className="quoteBox">AI analizi hazırlanıyor...</div>}
      {error && <div className="errorBanner">{error}</div>}
    </>
  );
}
