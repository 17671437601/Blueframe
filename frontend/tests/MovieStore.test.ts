import { MovieStore } from "../src/stores/movie";

describe("MovieStore", () => {
  it("queues script generation, voice and commentary render", async () => {
    const api = {
      getProject: vi.fn().mockResolvedValue({ id: "p", name: "Movie", project_type: "movie", status: "active", sources: [] }),
      listCommentary: vi.fn().mockResolvedValue([]),
      listEditPlans: vi.fn().mockResolvedValue([]),
      jobs: vi.fn().mockResolvedValue([]),
      generateCommentary: vi.fn().mockResolvedValue({ id: "j1", job_type: "generate_commentary", status: "queued", progress: 0 }),
      saveCommentary: vi.fn(), synthesizeCommentary: vi.fn().mockResolvedValue({ id: "j2", job_type: "synthesize_commentary", status: "queued", progress: 0 }),
      saveEditPlan: vi.fn(), renderEditPlan: vi.fn().mockResolvedValue({ id: "j3", job_type: "render_edit_plan", status: "queued", progress: 0 }),
    };
    const store = new MovieStore(api as never);
    await store.generate("p", "voice-a");
    await store.synthesize("p", "script-a");
    await store.render("p", "plan-a", "script-a");
    expect(api.generateCommentary).toHaveBeenCalledWith("p", expect.objectContaining({ consent_to_send_transcript: true }));
    expect(api.synthesizeCommentary).toHaveBeenCalled();
    expect(api.renderEditPlan).toHaveBeenCalledWith("p", "plan-a", "script-a");
  });
});
