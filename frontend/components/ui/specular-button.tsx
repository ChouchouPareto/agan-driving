import type { ButtonHTMLAttributes, ReactNode } from "react";

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  children: ReactNode;
  tone?: "blue" | "ink" | "paper";
};

// CSS-first adaptation of the React Bits SpecularButton interaction.
// It keeps the moving highlight without mounting a WebGL canvas per control.
export function SpecularButton({ children, className = "", tone = "paper", ...props }: Props) {
  return <button className={`specularButton specularButton--${tone} ${className}`} {...props}><span>{children}</span></button>;
}
