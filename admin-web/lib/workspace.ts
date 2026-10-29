export const WORKSPACE_KEY = "school-workspace-id";
export const THEME_KEY = "school-theme";
export const LANGUAGE_KEY = "school-language";

export function readWorkspace(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(WORKSPACE_KEY) || "";
}

export function writeWorkspace(id: string): void {
  window.localStorage.setItem(WORKSPACE_KEY, id);
  window.dispatchEvent(new CustomEvent("school-workspace-change", { detail: id }));
}
