import type { NextFunction, Request, Response } from "express";
import jwt from "jsonwebtoken";

const SECRET = process.env.SESSION_SIGNING_KEY!;

/** Anonymous chat sessions get a signed session token from the shop; customerId is set when logged in. */
export function sessionAuth(req: Request, res: Response, next: NextFunction) {
  try {
    const claims = jwt.verify(req.header("x-session-token") ?? "", SECRET) as { sid: string; cid?: string };
    res.locals.sessionId = claims.sid;
    res.locals.customerId = claims.cid ?? null;
    next();
  } catch {
    res.status(401).json({ error: "invalid session" });
  }
}

/** Staff SSO token with the `support-admin` role is required for transcript access and erasure. */
export function requireAdmin(req: Request, res: Response, next: NextFunction) {
  try {
    const claims = jwt.verify((req.header("authorization") ?? "").replace("Bearer ", ""), process.env.SSO_PUBLIC_KEY!, {
      algorithms: ["RS256"],
    }) as { roles?: string[] };
    if (!claims.roles?.includes("support-admin")) return res.status(403).end();
    next();
  } catch {
    res.status(401).end();
  }
}
