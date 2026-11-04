"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/shared/lib/utils";
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
} from "@/shared/ui/sidebar";
import { useTenders } from "./tender.queries";
import { daysUntil } from "@/shared/utils/date";
import { formatDaysLeft } from "./deadline";

export const tenderHref = (tenderId: number) => `/tenders/${tenderId}`;

/** Sidebar group listing the open tenders with their time left. */
export function ActiveTenders() {
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Active tenders</SidebarGroupLabel>
      <SidebarMenu aria-label="Active tenders">
        <TenderLinks />
      </SidebarMenu>
    </SidebarGroup>
  );
}

function TenderLinks() {
  const { data: tenders, isPending } = useTenders();
  const pathname = usePathname();

  if (isPending) return <SidebarMenuSkeleton />;
  if (!tenders) return <p className="px-2 text-xs text-muted-foreground">Tenders unavailable</p>;
  return tenders.map((tender, index) => {
    const href = tenderHref(tender.id);
    const isActive = pathname === href || (pathname === "/" && index === 0);
    const days = daysUntil(tender.submission_deadline);
    return (
      <SidebarMenuItem key={tender.id}>
        <SidebarMenuButton isActive={isActive} className="pr-16" render={<Link href={href} />}>
          <span
            aria-hidden
            className={cn("size-1.75 shrink-0 rounded-full", isActive ? "bg-primary" : "bg-border")}
          />
          <span className="truncate">{tender.title}</span>
        </SidebarMenuButton>
        <SidebarMenuBadge className={cn(days <= 21 && "text-warning")}>
          {formatDaysLeft(days)}
        </SidebarMenuBadge>
      </SidebarMenuItem>
    );
  });
}
