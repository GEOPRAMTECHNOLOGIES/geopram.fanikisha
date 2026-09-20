import {NextRequest,NextResponse} from "next/server";
export function middleware(req:NextRequest){const p=process.env.ADMIN_PATH||"admin";if(req.nextUrl.pathname===`/${p}`||req.nextUrl.pathname===`/${p}/`){const u=req.nextUrl.clone();u.pathname="/admin-ui";return NextResponse.rewrite(u)}return NextResponse.next()}
export const config={matcher:["/:path*"]};
