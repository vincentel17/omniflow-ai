import { redirect } from "next/navigation";

import { getRequestSessionContext, type SessionContext } from "./dev-context";

export async function requireAuthSession(): Promise<SessionContext> {
  const session = await getRequestSessionContext();
  if (!session?.authenticated) {
    redirect("/auth");
  }
  return session;
}
