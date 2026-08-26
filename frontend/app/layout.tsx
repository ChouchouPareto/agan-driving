import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "科目一智能助教",
  description: "由驾校交付的可信科目一智能答疑服务",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}

