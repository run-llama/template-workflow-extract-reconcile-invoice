import React from "react";
import { APP_TITLE } from "./config";

export interface BreadcrumbItem {
  label: string;
  href?: string;
  isCurrentPage?: boolean;
}

export const ToolbarCtx = React.createContext<{
  buttons: React.ReactNode[];
  setButtons: (fn: (prev: React.ReactNode[]) => React.ReactNode[]) => void;
  breadcrumbs: BreadcrumbItem[];
  setBreadcrumbs: (items: BreadcrumbItem[]) => void;
}>({
  buttons: [],
  setButtons: () => {},
  breadcrumbs: [],
  setBreadcrumbs: () => {},
});

export const ToolbarProvider = ({
  children,
}: {
  children: React.ReactNode;
}) => {
  const [buttons, setButtons] = React.useState<React.ReactNode[]>([]);
  const [breadcrumbs, setBreadcrumbs] = React.useState<BreadcrumbItem[]>([
    { label: APP_TITLE, href: "/" },
  ]);

  return (
    <ToolbarCtx.Provider
      value={{ buttons, setButtons, breadcrumbs, setBreadcrumbs }}
    >
      {children}
    </ToolbarCtx.Provider>
  );
};

export const useToolbar = () => React.useContext(ToolbarCtx);
