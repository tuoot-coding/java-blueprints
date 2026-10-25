import { uiText } from "@/shared/i18n/ru";

export function TestResultsPanel() {
  return (
    <section className="flex h-full min-h-0 flex-col bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
        {uiText.testingTitle}
      </div>
      <div className="flex-1 overflow-auto p-3 text-xs leading-relaxed text-zinc-500">
        {uiText.testingUnavailable}
      </div>
    </section>
  );
}
