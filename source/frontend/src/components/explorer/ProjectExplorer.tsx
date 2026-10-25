"use client";

import { ChevronDown, ChevronRight, FileCode2, FolderOpen } from "lucide-react";
import { useMemo, useRef, useState, type ReactNode } from "react";

import { uiText } from "@/shared/i18n/ru";
import {
  buildProjectTree,
  type ProjectFileEntry,
  type ProjectTreeNode,
} from "@/shared/lib/projectTree";

interface ProjectExplorerProps {
  fileName: string | null;
  dirty: boolean;
  projectName: string | null;
  projectFiles: ProjectFileEntry[];
  activeFilePath: string | null;
  onOpenProject: (files: FileList) => void;
  onOpenProjectFile: (path: string) => void;
  onClearProject?: () => void;
}

export function ProjectExplorer({
  fileName,
  dirty,
  projectName,
  projectFiles,
  activeFilePath,
  onOpenProject,
  onOpenProjectFile,
  onClearProject,
}: ProjectExplorerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const tree = useMemo(() => buildProjectTree(projectFiles), [projectFiles]);

  return (
    <section className="flex h-full min-h-0 flex-col border-r border-zinc-800 bg-zinc-950">
      <PanelHeading>{uiText.explorerTitle}</PanelHeading>
      <div className="flex shrink-0 flex-wrap gap-1 border-b border-zinc-800 p-2">
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded border border-zinc-700 px-2 py-1 text-[10px] text-zinc-200 hover:bg-zinc-800"
          onClick={() => inputRef.current?.click()}
        >
          <FolderOpen size={12} />
          {uiText.explorerOpenProject}
        </button>
        {projectFiles.length > 0 && onClearProject ? (
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-[10px] text-zinc-400 hover:bg-zinc-800"
            onClick={onClearProject}
          >
            {uiText.explorerClearProject}
          </button>
        ) : null}
        <input
          ref={(element) => {
            inputRef.current = element;
            if (element) {
              element.setAttribute("webkitdirectory", "");
              element.setAttribute("directory", "");
            }
          }}
          type="file"
          className="hidden"
          multiple
          onChange={(event) => {
            const list = event.target.files;
            event.target.value = "";
            if (list && list.length > 0) {
              onOpenProject(list);
            }
          }}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-2 text-xs text-zinc-400">
        {projectName ? (
          <div className="mb-2 rounded border border-zinc-800 bg-zinc-900/60 px-2 py-1.5">
            <div className="text-[10px] uppercase tracking-wide text-zinc-500">
              {uiText.explorerProjectName}
            </div>
            <div className="mt-0.5 break-all text-zinc-200">{projectName}</div>
            <div className="mt-1 text-[10px] text-zinc-500">
              {uiText.explorerFileCount}: {projectFiles.length}
            </div>
          </div>
        ) : null}

        {tree.length > 0 ? (
          <div className="space-y-0.5">
            {tree.map((node) => (
              <TreeNodeView
                key={node.id}
                node={node}
                depth={0}
                activePath={activeFilePath}
                onOpenFile={onOpenProjectFile}
              />
            ))}
          </div>
        ) : (
          <p className="leading-relaxed text-zinc-500">{uiText.explorerEmpty}</p>
        )}

        {fileName && !projectName ? (
          <div className="mt-3 rounded border border-zinc-800 bg-zinc-900/60 px-2 py-2">
            <div className="text-[10px] uppercase tracking-wide text-zinc-500">
              {uiText.explorerLocalFile}
            </div>
            <div className="mt-1 break-all text-zinc-200">
              {fileName}
              {dirty ? " *" : ""}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function TreeNodeView({
  node,
  depth,
  activePath,
  onOpenFile,
}: {
  node: ProjectTreeNode;
  depth: number;
  activePath: string | null;
  onOpenFile: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const paddingLeft = 6 + depth * 12;

  if (node.kind === "file") {
    const active = activePath === node.path;
    return (
      <button
        type="button"
        className={`flex w-full items-center gap-1 rounded px-1 py-0.5 text-left hover:bg-zinc-800 ${
          active ? "bg-sky-950/50 text-sky-100" : "text-zinc-300"
        }`}
        style={{ paddingLeft }}
        onClick={() => onOpenFile(node.path)}
        title={node.path}
      >
        <FileCode2 size={12} className="shrink-0 opacity-70" />
        <span className="truncate">{node.name}</span>
      </button>
    );
  }

  return (
    <div>
      <button
        type="button"
        className="flex w-full items-center gap-1 rounded px-1 py-0.5 text-left text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        style={{ paddingLeft }}
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span className="truncate font-medium">{node.name}</span>
      </button>
      {expanded
        ? (node.children ?? []).map((child) => (
            <TreeNodeView
              key={child.id}
              node={child}
              depth={depth + 1}
              activePath={activePath}
              onOpenFile={onOpenFile}
            />
          ))
        : null}
    </div>
  );
}

function PanelHeading({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-zinc-800 px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
      {children}
    </div>
  );
}
