import { MAX_LOCAL_JAVA_FILE_BYTES } from "@/shared/config/env";
import { uiText } from "@/shared/i18n/ru";

export function isJavaFileName(fileName: string): boolean {
  return fileName.toLowerCase().endsWith(".java");
}

export async function readLocalJavaFile(file: File): Promise<{ fileName: string; text: string }> {
  if (!isJavaFileName(file.name)) {
    throw new Error(uiText.fileWrongExtension);
  }
  if (file.size > MAX_LOCAL_JAVA_FILE_BYTES) {
    throw new Error(uiText.fileTooLarge);
  }

  try {
    const text = await file.text();
    return { fileName: file.name, text };
  } catch {
    throw new Error(uiText.fileReadError);
  }
}

export function downloadLocalJavaFile(fileName: string, sourceText: string): void {
  const safeName = fileName.toLowerCase().endsWith(".java") ? fileName : `${fileName || "Main"}.java`;
  const blob = new Blob([sourceText], { type: "text/x-java-source;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = safeName;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}
