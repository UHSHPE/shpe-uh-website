import { api } from "./client";

// Public because the leaderboard appears on the unauthenticated membership page.
export function getLeaderboard() {
  return api.get("/leaderboard");
}
