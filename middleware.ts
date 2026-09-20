import { NextRequest, NextResponse } from "next/server";

function adminPath() {
  return (process.env.ADMIN_PATH || "admin").replace(/^\/+|\/+$/g, "");
}

export async function middleware(req: NextRequest) {
  const configured = adminPath();
  const pathname = req.nextUrl.pathname.replace(/\/+$/, "") || "/";
  const cookieName = process.env.COOKIE_NAME || "fluent_session";
  const hasSession = Boolean(req.cookies.get(cookieName)?.value);

  // Do not call the Python API from Next.js middleware. On Vercel that
  // cross-runtime subrequest can fail before the Python function is routed,
  // causing a valid login to bounce straight back to /login.
  // The admin API itself always checks the current MongoDB ADMIN role.
  if (pathname === `/${configured}`) {
    if (!hasSession) {
      const login = req.nextUrl.clone();
      login.pathname = "/login";
      login.searchParams.set("next", `/${configured}`);
      return NextResponse.redirect(login);
    }
    const u = req.nextUrl.clone();
    u.pathname = "/admin-ui";
    return NextResponse.rewrite(u);
  }

  // Keep the internal admin route inaccessible without a session cookie.
  // The page/API performs the authoritative MongoDB role check.
  if (pathname === "/admin-ui" || pathname === "/__ADMIN__") {
    if (!hasSession) {
      const login = req.nextUrl.clone();
      login.pathname = "/login";
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
