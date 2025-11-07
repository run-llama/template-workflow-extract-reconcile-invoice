import React from "react";
import { Routes, Route } from "react-router-dom";
import { Theme } from "@radix-ui/themes";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbSeparator,
} from "@llamaindex/ui";
import { Link } from "react-router-dom";
import { Toaster } from "@llamaindex/ui";
import { useToolbar, ToolbarProvider } from "@/lib/ToolbarContext";
import { MetadataProvider } from "@/lib/MetadataProvider";

// Import pages
import HomePage from "./pages/HomePage";
import ItemPage from "./pages/ItemPage";

export default function App() {
  return (
    <Theme>
      <MetadataProvider>
        <ToolbarProvider>
          <div className="grid grid-rows-[auto_1fr] h-screen">
            <Toolbar />
            <main className="overflow-auto">
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/item/:itemId" element={<ItemPage />} />
              </Routes>
            </main>
          </div>
          <Toaster />
        </ToolbarProvider>
      </MetadataProvider>
    </Theme>
  );
}

const Toolbar = () => {
  const { buttons, breadcrumbs } = useToolbar();

  return (
    <header className="sticky top-0 z-50 flex h-16 shrink-0 items-center gap-2 border-b px-4 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <Breadcrumb>
        <BreadcrumbList>
          {breadcrumbs.map((item, index) => (
            <React.Fragment key={index}>
              {index > 0 && <BreadcrumbSeparator />}
              <BreadcrumbItem>
                {item.href && !item.isCurrentPage ? (
                  <Link to={item.href} className="font-medium text-base">
                    {item.label}
                  </Link>
                ) : (
                  <span
                    className={`font-medium ${index === 0 ? "text-base" : ""}`}
                  >
                    {item.label}
                  </span>
                )}
              </BreadcrumbItem>
            </React.Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      {buttons}
    </header>
  );
};
