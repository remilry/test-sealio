import { AppShell } from "@/screens/shell";

export default function ShellLayout({ children }: LayoutProps<"/">) {
  return <AppShell>{children}</AppShell>;
}
