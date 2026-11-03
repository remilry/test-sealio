import { setupServer } from "msw/node";

/** MSW server shared by all screen tests. Each test adds its handlers with `server.use(...)`. */
export const server = setupServer();
