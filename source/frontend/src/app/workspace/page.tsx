import { ErrorBoundary } from "@/components/layout/ErrorBoundary";
import { WorkspaceShell } from "@/components/layout/WorkspaceShell";

/** IDE / Dashboard: разбор Java, схема, диагностика, сравнение поведения. */
export default function WorkspacePage() {
  return (
    <ErrorBoundary>
      <WorkspaceShell />
    </ErrorBoundary>
  );
}
