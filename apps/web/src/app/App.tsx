import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Spinner } from "@/components/ui";
import { Shell } from "./Shell";

const OverviewPage = lazy(() => import("@/features/overview/OverviewPage"));
const LibraryPage = lazy(() => import("@/features/library/LibraryPage"));
const TrackPage = lazy(() => import("@/features/sonic-dna/TrackPage"));
const SonicDNAPage = lazy(() => import("@/features/sonic-dna/SonicDNAPage"));
const ComparePage = lazy(() => import("@/features/sonic-dna/ComparePage"));
const PromptStudioPage = lazy(() => import("@/features/prompt-studio/PromptStudioPage"));
const ExperimentsPage = lazy(() => import("@/features/experiments/ExperimentsPage"));
const SettingsPage = lazy(() => import("@/features/settings/SettingsPage"));
const VisualDNAPage = lazy(() => import("@/features/visual-dna/VisualDNAPage"));
const FusionStudioPage = lazy(() => import("@/features/fusion-studio/FusionStudioPage"));
const AtlasPage = lazy(() => import("@/features/resonance-atlas/AtlasPage"));

export function App() {
  return (
    <Shell>
      <Suspense fallback={<div className="p-8"><Spinner /></div>}>
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/tracks/:id" element={<TrackPage />} />
          <Route path="/sonic-dna" element={<SonicDNAPage />} />
          <Route path="/sonic-dna/compare" element={<ComparePage />} />
          <Route path="/prompt-studio" element={<PromptStudioPage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
          <Route path="/visual-dna" element={<VisualDNAPage />} />
          <Route path="/fusion-studio" element={<FusionStudioPage />} />
          <Route path="/atlas" element={<AtlasPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Shell>
  );
}
