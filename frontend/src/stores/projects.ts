import { reactive } from "vue";

import type { ApiClient, ProjectSummary } from "../api/client";

interface NewProjectSelection {
  name: string;
  projectType: "drama" | "movie" | "variants" | "live";
  rootId: string;
  files: string[];
  config: Record<string, unknown>;
}

type ProjectApi = Pick<
  ApiClient,
  "listProjects" | "createProject" | "addProjectSources" | "transcribeProject"
>;

export class ProjectStore {
  projects: ProjectSummary[] = [];
  busy = false;
  error: string | null = null;

  constructor(private readonly api: ProjectApi) {}

  async refresh(): Promise<void> {
    this.projects = await this.api.listProjects();
  }

  async createFromSelection(selection: NewProjectSelection): Promise<ProjectSummary> {
    this.busy = true;
    this.error = null;
    try {
      const project = await this.api.createProject({
        name: selection.name,
        project_type: selection.projectType,
        root_id: selection.rootId,
        output_relative_path: "BlueFrame-交付",
        config: selection.config,
        idempotency_key: crypto.randomUUID(),
      });
      await this.api.addProjectSources(project.id, selection.files);
      if (selection.projectType !== "variants") await this.api.transcribeProject(project.id);
      this.projects.unshift(project);
      return project;
    } catch (error) {
      this.error = error instanceof Error ? error.message : "创建项目失败";
      throw error;
    } finally {
      this.busy = false;
    }
  }
}

let currentStore: ReturnType<typeof reactive<ProjectStore>> | undefined;

export function configureProjectStore(api: ProjectApi) {
  currentStore = reactive(new ProjectStore(api));
  return currentStore;
}

export function useProjectStore() {
  if (!currentStore) throw new Error("Project store has not been configured");
  return currentStore;
}
