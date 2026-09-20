import { NextRequest, NextResponse } from "next/server";
import { jwtVerify } from "jose";

function adminPath() {
  return (process.env.ADMIN_PATH || "admin").replace(/^\/+|\/+$/g, "");
}

async function isAdmin(req: NextRequest) {
  const token = req.cookies.get(process.env.COOKIE_NAME || "fluent_session")?.value;
  const secret = process.env.SESSION_SECRET;
  if (!token || !secret) return false;
  try {
    const key = new TextEncoder().encode(secret);
    const { payload } = await jwtVerify(token, key, { algorithms: ["HS256"] });
    return payload.role === "ADMIN";
  } catch {
    return false;
  }
}

export async function middleware(req: NextRequest) {
  const configured = adminPath();
  const pathname = req.nextUrl.pathname.replace(/\/+$/, "") || "/";

  // Only the configured admin path is publicly routable to the admin UI.
  // The internal route is protected too, so /admin-ui cannot bypass ADMIN_PATH.
  if (pathname === `/${configured}` || pathname === "/admin-ui" || pathname === "/__ADMIN__") {
    if (!(await isAdmin(req))) {
      const login = req.nextUrl.clone();
      login.pathname = "/login";
      login.searchParams.set("next", `/${configured}`);
      return NextResponse.redirect(login);
    }
    const u = req.nextUrl.clone();
    u.pathname = "/admin-ui";
    return NextResponse.rewrite(u);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/:path*"],
};
