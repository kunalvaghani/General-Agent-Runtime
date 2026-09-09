import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
export const metadata: Metadata = { title: "GAR · Runtime workspace", description: "General Agent Runtime" };
export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-gar-app="runtime"><body><header className="topbar"><Link className="brand" href="/">
    <span className="brandmark">g/</span> GAR <span className="muted">/ General Agent Runtime</span></Link>
    <span className="preview">Local agent runtime</span></header>
    <div className="shell"><aside><div className="eyebrow">WORKSPACE</div>
      <nav aria-label="Main navigation"><Link href="/">◫ &nbsp; Overview</Link><Link href="/tasks/new">+ &nbsp; New task</Link>
        <Link href="/models">Models</Link><Link href="/memory">Memory</Link><Link href="/settings">Settings</Link></nav>
      <div className="aside-note"><span className="dot"/> Local by design<p>Your models.<br/>Your workspace.<br/>Your control.</p></div>
    </aside><main id="main">{children}</main></div></body></html>;
}
