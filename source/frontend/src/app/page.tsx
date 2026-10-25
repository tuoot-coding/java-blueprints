import { ErrorBoundary } from "@/components/layout/ErrorBoundary";
import { WorkspaceShell } from "@/components/layout/WorkspaceShell";

export default function HomePage() {
  return (
    <ErrorBoundary>
      <WorkspaceShell />
    </ErrorBoundary>
  );
}
