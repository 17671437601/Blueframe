import { ProjectStore } from "../src/stores/projects";

it("creates a project, imports selected files and queues transcription", async () => {
  const api = {
    createProject: vi.fn().mockResolvedValue({ id: "project-1", name: "新项目" }),
    addProjectSources: vi.fn().mockResolvedValue([{ id: "source-1" }]),
    transcribeProject: vi.fn().mockResolvedValue({ id: "job-1" }),
    listProjects: vi.fn().mockResolvedValue([]),
  };
  const store = new ProjectStore(api as never);

  const result = await store.createFromSelection({
    name: "都市悬疑", projectType: "drama", rootId: "root-id",
    files: ["第一集.mp4", "第二集.mp4"],
    config: { target_seconds: 480, explosion_threshold: 72 },
  });

  expect(result.id).toBe("project-1");
  expect(api.createProject).toHaveBeenCalledWith(expect.objectContaining({ root_id: "root-id" }));
  expect(api.addProjectSources).toHaveBeenCalledWith("project-1", ["第一集.mp4", "第二集.mp4"]);
  expect(api.transcribeProject).toHaveBeenCalledWith("project-1");
});
