import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export function BackButton({ href, label = "返回" }: { href: string; label?: string }) {
  return <Link className="backButton" href={href} aria-label={label}><ArrowLeft aria-hidden="true" size={17}/><span>{label}</span></Link>;
}
