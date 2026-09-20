import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const configured = (process.env.ADMIN_PATH || "admin").replace(/^\/+|\/+$/g, "");
  const pathname = req.nextUrl.pathname.replace(/\/+$/, "") || "/";

  // The public/admin URL is configurable through ADMIN_PATH. The internal
  // route is never intended to be the advertised admin URL.
  if (pathname === `/${configured}`) {
    const u = req.nextUrl.clone();
    u.pathname = "/admin-ui";
    return NextResponse.rewrite(u);
  }

  // Login uses an internal redirect target so the browser does not need
  // NEXT_PUBLIC_ADMIN_PATH. The backend still enforces role=ADMIN.
  if (pathname === "/__ADMIN__") {
    const u = req.nextUrl.clone();
    u.pathname = "/admin-ui";
    return NextResponse.rewrite(u);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/:path*"],
};
