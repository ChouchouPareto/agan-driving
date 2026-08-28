import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "阿甘学车",
  description: "由驾校交付的科目一 AI 陪练与可信答疑服务",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body><Providers>{children}</Providers></body></html>;
}
